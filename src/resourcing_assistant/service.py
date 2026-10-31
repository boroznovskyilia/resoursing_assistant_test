"""Thread-scoped admission, graph execution and authoritative action readback."""

from contextlib import contextmanager
import json
import threading
from .agent import Agent, card
from .data import initialize, Reader
from .llm import USAGE, configure_logging, event, token_count
from .models import AppError, Response
from .storage import Store


class Service:
    def __init__(self, settings, gateway=None):
        self.settings = settings
        configure_logging(settings.runtime)
        self.subject = initialize(settings)
        self.store = Store(settings, self.subject)
        self.reader = Reader(settings, self.subject)
        self.agent = Agent(settings, self.store, self.reader, gateway)
        self.locks = {}
        self.registry = threading.Lock()

    @contextmanager
    def guard(self, thread):
        self.store.require_thread(thread)
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
                self.store.overlay(json.loads(row["response"]))
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
        if token_count(text) > 9000:
            raise AppError(
                "context_budget_exceeded", "Message is too large; please narrow it", 422
            )
        self.store.require_thread(thread)
        try:
            existing = self.store.request(thread, request)
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
            row = self.store.admit(
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
                self.store.finish(row["thread_id"], row["request_id"], result)
            )
        except AppError as error:
            self.store.fail(row["thread_id"], row["request_id"], error)
            raise
        except Exception as error:
            event("operation_failed", error_class=type(error).__name__)
            failure = AppError(
                "internal_error",
                "The operation failed; saved history and actions are preserved",
                500,
            )
            self.store.fail(row["thread_id"], row["request_id"], failure)
            raise failure from error
        finally:
            event("request_finished", **usage)
            USAGE.reset(token)

    def resume(self, thread, request):
        row = self.store.request(thread, request)
        if row["status"] != "interrupted":
            return self.replay(row)
        with self.guard(thread):
            row = self.store.resume(thread, request)
            return self.execute(row, resume=True)

    def decide(self, thread, action_id, decision):
        with self.guard(thread):
            existing = self.store.action(thread, action_id)
            if existing["status"] == "pending":
                for req in self.store.history(thread)["requests"]:
                    if req["status"] in ("processing", "interrupted"):
                        raise AppError(
                            "resume_required",
                            "Continue the interrupted request before deciding this action",
                        )
            action = self.store.decide(thread, action_id, decision)
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
                result = self.store.finish(thread, "decision_" + action_id, result)
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
            if self.settings.endpoint and self.settings.api_key
            else "not_configured",
            "embeddings": self.agent.semantic.embedding_status,
            "reference_date": self.settings.reference().isoformat(),
        }

    def close(self):
        self.agent.close()
