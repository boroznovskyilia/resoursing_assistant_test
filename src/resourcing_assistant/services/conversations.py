"""Thread-scoped admission, graph execution and authoritative action readback."""

import json
import threading
from contextlib import contextmanager

from resourcing_assistant.api.responses import card
from resourcing_assistant.api.schemas import Response
from resourcing_assistant.errors import AppError
from resourcing_assistant.llm.tokens import token_count
from resourcing_assistant.telemetry import USAGE, event


class ConversationService:
    def __init__(self, settings, conversations, bookings, agent, subject):
        self.settings, self.conversations, self.bookings = (
            settings,
            conversations,
            bookings,
        )
        self.agent, self.subject = agent, subject
        self.locks = {}
        self.registry = threading.Lock()

    def history(self, thread):
        return read_history(self.conversations, self.bookings, self.settings, thread)

    @contextmanager
    def guard(self, thread):
        self.conversations.require_thread(thread)
        with self.registry:
            lock = self.locks.setdefault(thread, threading.Lock())
        if not lock.acquire(blocking=False):
            raise AppError(
                "thread_busy",
                "A request is already running in this conversation",
                409,
                True,
            )
        try:
            yield
        finally:
            lock.release()

    def replay(self, row):
        if row["response"]:
            return Response.model_validate(
                self.bookings.overlay(json.loads(row["response"]))
            )
        if row["status"] == "processing":
            return Response(
                thread_id=row["thread_id"],
                request_id=row["request_id"],
                request_status="processing",
                effective_reference_date=row["reference_date"],
            )
        if row["status"] == "interrupted":
            raise AppError(
                "resume_required", "Use Continue to resume this interrupted request"
            )
        if row["status"] == "failed":
            error = json.loads(row["error"] or "{}")
            raise AppError(
                error.get("code", "request_failed"),
                error.get(
                    "message",
                    "This request failed; use a new request ID for a new attempt",
                ),
                error.get("status", 500),
            )
        raise AppError(
            "recovery_failed", "Saved request has no recoverable response", 500
        )

    def message(self, thread, request, text):
        if not text.strip():
            raise AppError("invalid_request", "Message cannot be blank", 422)
        if token_count(text) > self.settings.message_token_limit:
            raise AppError(
                "context_budget_exceeded", "Message is too large; please narrow it", 422
            )
        self.conversations.require_thread(thread)
        try:
            existing = self.conversations.request(thread, request)
        except AppError as error:
            if error.status != 404:
                raise
        else:
            if existing["text"] != text:
                raise AppError(
                    "request_id_conflict",
                    "Request ID already belongs to a different message",
                )
            return self.replay(existing)
        with self.guard(thread):
            row = self.conversations.admit(
                thread, request, text, self.settings.reference().isoformat()
            )
            return self.execute(row)

    def execute(self, row, *, resume=False):
        usage = {"thread_id": row["thread_id"], "request_id": row["request_id"]}
        token = USAGE.set(usage)
        try:
            result = self.agent.run(
                row["thread_id"],
                row["request_id"],
                row["text"],
                row["reference_date"],
                resume=resume,
            )
            result = Response.model_validate(result).model_dump(mode="json")
            return Response.model_validate(
                self.conversations.finish(row["thread_id"], row["request_id"], result)
            )
        except AppError as error:
            self.conversations.fail(row["thread_id"], row["request_id"], error)
            raise
        except Exception as error:
            event("operation_failed", error_class=type(error).__name__)
            failure = AppError(
                "internal_error",
                "The operation failed; saved history and actions are preserved",
                500,
            )
            self.conversations.fail(row["thread_id"], row["request_id"], failure)
            raise failure from error
        finally:
            event("request_finished", **usage)
            USAGE.reset(token)

    def resume(self, thread, request):
        row = self.conversations.request(thread, request)
        if row["status"] != "interrupted":
            return self.replay(row)
        with self.guard(thread):
            row = self.conversations.resume(thread, request)
            return self.execute(row, resume=True)

    def decide(self, thread, action_id, decision):
        with self.guard(thread):
            existing = self.bookings.action(thread, action_id)
            if existing["status"] == "pending":
                for req in self.history(thread)["requests"]:
                    if req["status"] in ("processing", "interrupted"):
                        raise AppError(
                            "resume_required",
                            "Continue the interrupted request before deciding this action",
                        )
            action = self.bookings.decide(thread, action_id, decision)
            issues = []
            try:
                self.agent.decision(thread, action)
            except Exception as error:
                event(
                    "action_graph_lag",
                    action_id=action_id,
                    error_class=type(error).__name__,
                )
                issues.append(
                    {
                        "code": "graph_sync_pending",
                        "message": "Decision is committed; graph synchronization needs recovery",
                        "stage": "recovery",
                        "retryable": True,
                    }
                )
            result = {
                "thread_id": thread,
                "request_id": "decision_" + action_id,
                "request_status": "completed",
                "blocks": [card(action)],
                "issues": issues,
                "effective_reference_date": self.settings.reference().isoformat(),
            }
            # The receipt is already committed. A failing app-history write cannot undo it.
            try:
                result = self.conversations.finish(
                    thread, "decision_" + action_id, result
                )
            except Exception as error:
                event(
                    "action_history_lag",
                    action_id=action_id,
                    error_class=type(error).__name__,
                )
            return Response.model_validate(result)

    def health(self):
        return {
            "status": "alive",
            "chat": "configured_unverified"
            if self.settings.azure_configured
            else "not_configured",
            "embeddings": self.agent.semantic.embedding_status,
            "reference_date": self.settings.reference().isoformat(),
        }

    def close(self):
        self.agent.close()
        self.conversations.database.close()
        self.bookings.repository.database.close()


def read_history(conversations, bookings, settings, thread):
    result = conversations.history(thread)
    for row in result["messages"]:
        if row["role"] == "assistant":
            row["content"] = bookings.overlay(row["content"])
    result["pending_action"] = bookings.pending(thread)
    result["effective_reference_date"] = settings.reference().isoformat()
    return result
