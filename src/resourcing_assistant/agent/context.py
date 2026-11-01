"""Bounded model context over complete turns and durable exact references."""

import json

from resourcing_assistant.db.reader import RULES
from resourcing_assistant.errors import AppError
from resourcing_assistant.llm.tokens import rendered_tokens, token_count
from resourcing_assistant.services.conversations import read_history
from resourcing_assistant.telemetry import event

BUTTON_REPLIES = frozenset(("yes", "confirm", "approved", "approve", "ok", "да"))


class ContextBuilder:
    def __init__(self, settings, conversations, bookings, reader, gateway):
        self.settings, self.conversations, self.bookings = (
            settings,
            conversations,
            bookings,
        )
        self.reader, self.gateway = reader, gateway

    def build(self, state):
        pending = self.bookings.pending(state["thread_id"])
        if pending and state["text"].strip().lower() in BUTTON_REPLIES:
            return {
                "context": {
                    "reference_date": state["reference_date"],
                    "pending_action": pending,
                },
                "pending_action_id": pending["action_id"],
                "issues": [],
                "read_results": [],
                "response": {},
            }
        history = read_history(
            self.conversations, self.bookings, self.settings, state["thread_id"]
        )["messages"]
        roles = {}
        for row in history:
            roles.setdefault(row["request_id"], set()).add(row["role"])
        complete = []
        for row in history:
            if roles[row["request_id"]] != {"user", "assistant"}:
                continue
            if row["request_id"] == state["request_id"]:
                continue
            content = row["content"]
            if isinstance(content, dict):
                content = {
                    **content,
                    "blocks": [
                        {**b, "rows": b.get("rows", [])[:10]}
                        if b["type"] == "table"
                        else b
                        for b in content["blocks"]
                        if b["type"] != "sql"
                    ],
                }
            complete.append(
                {"role": row["role"], "content": content, "sequence": row["sequence"]}
            )
        recent = complete[:]
        older = []

        def prompt_estimate():
            context = {
                "summary": state.get("summary", ""),
                "recent_turns": recent,
                "active_task": state.get("active_task", {}),
                "displayed_references": state.get("displayed_references", []),
                "pending_action": pending,
            }
            planner = rendered_tokens(
                "PlanReads",
                intent="factual",
                question=state["text"],
                context=json.dumps(context),
                allowed_schema=self.reader.prompt_schema() + "\n" + RULES,
                previous_error="",
            )
            interpreter = rendered_tokens(
                "InterpretRequest",
                message=state["text"],
                context=json.dumps(context),
                source_schema=self.reader.prompt_schema(question=state["text"]),
            )
            return max(planner, interpreter)

        while len(recent) > 2 and (
            token_count(recent) > self.settings.history_tokens
            or prompt_estimate() > self.settings.context_compact_tokens
        ):
            older.extend(recent[:2])
            recent = recent[2:]
        summary = state.get("summary", "")
        covered = state.get("summary_covered", 0)
        to_summarize = [row for row in older if row["sequence"] > covered]
        if to_summarize:
            try:
                new = self.gateway.call(
                    "SummarizeHistory",
                    previous_summary=summary,
                    turns=json.dumps(to_summarize),
                )
                if token_count(new) > self.settings.summary_tokens:
                    raise ValueError("Summary exceeds700 tokens")
                summary = new
                covered = max(r["sequence"] for r in to_summarize)
            except Exception as error:
                event("summary_failed", error_class=type(error).__name__)
                # Exact active IDs/proposal stay outside summary; full UI history is untouched.
                if token_count(recent) > self.settings.history_tokens:
                    raise AppError(
                        "context_budget_exceeded",
                        "Cannot safely compact current context",
                        422,
                    )
        pending = self.bookings.pending(state["thread_id"])
        context = {
            "reference_date": state["reference_date"],
            "summary": summary,
            "recent_turns": recent,
            "active_task": state.get("active_task", {}),
            "displayed_references": state.get("displayed_references", []),
            "pending_action": pending,
        }
        return {
            "context": context,
            "summary": summary,
            "summary_covered": covered,
            "pending_action_id": pending["action_id"] if pending else None,
            "issues": [],
            "read_results": [],
            "response": {},
        }
