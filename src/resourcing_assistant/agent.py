"""Controlled persistent graph; source writes only through stored-action decisions."""

import json
import re
import sqlite3
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command, interrupt
from .config import period, capacity
from .data import RULES, ReadError, connect
from .llm import Gateway, token_count, rendered_tokens, event
from .models import Interpretation, BookingSlots, AppError
from .semantic import Semantic


class State(TypedDict, total=False):
    thread_id: str
    request_id: str
    text: str
    reference_date: str
    context: dict
    interpretation: dict
    active_task: dict
    summary: str
    summary_covered: int
    displayed_references: list
    read_results: list
    issues: list
    response: dict
    pending_action_id: str | None


def card(action):
    return {
        "type": "confirmation",
        "action_id": action["action_id"],
        "status": action["status"],
        "fields": action["fields"],
        "booking_id": action["booking_id"],
    }


def text_block(text):
    return {"type": "text", "text": text}


def table_block(result):
    return {
        "type": "table",
        "block_id": result["query_id"],
        "title": result["purpose"],
        "columns": [
            {"key": key, "label": key.replace("_", " ")} for key in result["columns"]
        ],
        "rows": result["rows"],
        "completeness": {
            "mode": "structured",
            "truncated": result["truncated"],
            "has_more": result["truncated"],
        },
        "evidence": [
            {"query_id": result["query_id"], "source_tables": result["source_tables"]}
        ],
    }


class Agent:
    def __init__(self, settings, store, reader, gateway=None):
        self.settings, self.store, self.reader = settings, store, reader
        self.gateway = gateway or Gateway(settings)
        self.semantic = Semantic(settings, store, self.gateway)
        self.connection = sqlite3.connect(
            store.path, check_same_thread=False, timeout=5
        )
        builder = StateGraph(State)
        for name in (
            "load_context",
            "interpret",
            "resolve",
            "read",
            "match",
            "compose",
            "prepare",
            "await_action",
        ):
            builder.add_node(name, getattr(self, name))
        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "interpret")
        builder.add_edge("interpret", "resolve")
        builder.add_conditional_edges("resolve", self.route)
        builder.add_conditional_edges(
            "read",
            lambda s: (
                "match"
                if Interpretation.model_validate(s["interpretation"]).intent
                in ("semantic", "mixed")
                else "compose"
            ),
        )
        builder.add_edge("match", "compose")
        builder.add_conditional_edges(
            "compose", lambda s: "await_action" if s.get("pending_action_id") else END
        )
        builder.add_edge("prepare", "await_action")
        self.graph = builder.compile(checkpointer=SqliteSaver(self.connection))

    def config(self, thread):
        return {"configurable": {"thread_id": thread}, "recursion_limit": 30}

    def load_context(self, state):
        history = self.store.history(state["thread_id"])["messages"]
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
            }
            return rendered_tokens(
                "PlanReads",
                question=state["text"],
                context=json.dumps(context),
                allowed_schema=json.dumps(self.reader.schema) + "\n" + RULES,
                previous_error="",
            )

        while len(recent) > 2 and (
            token_count(recent) > 3000 or prompt_estimate() > 8000
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
                if token_count(new) > 700:
                    raise ValueError("Summary exceeds700 tokens")
                summary = new
                covered = max(r["sequence"] for r in to_summarize)
            except Exception as error:
                event("summary_failed", error_class=type(error).__name__)
                # Exact active IDs/proposal stay outside summary; full UI history is untouched.
                if token_count(recent) > 3000:
                    raise AppError(
                        "context_budget_exceeded",
                        "Cannot safely compact current context",
                        422,
                    )
        pending = self.store.pending(state["thread_id"])
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

    def interpret(self, state):
        if state.get("pending_action_id") and state["text"].strip().lower() in (
            "yes",
            "confirm",
            "approved",
            "approve",
            "ok",
            "да",
        ):
            value = Interpretation(
                intent="clarification",
                question=state["text"],
                clarification="Use the Confirm or Reject button on the saved proposal. A text reply does not create a booking.",
            )
        else:
            value = self.gateway.call(
                "InterpretRequest",
                message=state["text"],
                context=json.dumps(state["context"]),
            )
        return {"interpretation": value.model_dump()}

    def response(self, state, blocks, issues=None, assumptions=None):
        issues = issues if issues is not None else state.get("issues", [])
        return {
            "thread_id": state["thread_id"],
            "request_id": state["request_id"],
            "request_status": "partial" if issues else "completed",
            "blocks": blocks,
            "issues": issues,
            "effective_reference_date": state["reference_date"],
            "assumptions": assumptions or [],
        }

    def resolve(self, state):
        task = Interpretation.model_validate(state["interpretation"])
        if task.intent == "unsupported":
            message = (
                "The supplied database contains no weather observations or forecasts, so I cannot provide a weather value."
                if re.search(
                    r"\b(weather|forecast|temperature|rain)\b", task.question, re.I
                )
                else "I can answer questions grounded in this professional-services database and propose soft bookings. The requested external information or source-changing operation is not supported."
            )
            return {
                "response": self.response(state, [text_block(message)]),
                "active_task": {},
            }
        if task.intent == "clarification" or task.clarification:
            return {
                "response": self.response(
                    state,
                    [text_block(task.clarification or "Please clarify the request.")],
                ),
                "active_task": task.model_dump(),
            }
        if task.intent != "booking":
            return {"active_task": {}}
        previous = state["context"].get("active_task", {})
        slots = task.slots.model_dump(exclude_none=True)
        pending = self.store.pending(state["thread_id"])
        base = {}
        if task.modify_pending and pending:
            f = pending["fields"]
            base = {
                "person_id": f["person_id"],
                "engagement_id": f["engagement_id"],
                "start_date": f["start"],
                "end_date": f["end_inclusive"],
                "hours": f["hours"],
            }
        elif not pending and previous.get("intent") == "booking":
            base = previous.get("slots", {})
        values = BookingSlots.model_validate(
            {**{k: v for k, v in base.items() if v is not None}, **slots}
        )
        if task.selected_position:
            groups = state["context"].get("displayed_references", [])
            if (
                len(groups) == 1
                and 1 <= task.selected_position <= len(groups[0]["ids"])
                and groups[0]["kind"] == "person"
            ):
                values.person_id = groups[0]["ids"][task.selected_position - 1]
            else:
                task.clarification = "Which displayed list and person do you mean? Please select a person ID."
        options = []
        with connect(self.store.subject, readonly=True) as c:
            if values.person_id is not None:
                found = c.execute(
                    "SELECT person_id,display_name,location_region FROM people WHERE person_id=?",
                    (values.person_id,),
                ).fetchall()
                if len(found) != 1 or (
                    values.person
                    and values.person.casefold() != found[0]["display_name"].casefold()
                ):
                    task.clarification = "The person name and ID do not resolve consistently. Please choose the intended person."
            elif values.person:
                found = c.execute(
                    "SELECT person_id,display_name,location_region FROM people WHERE lower(display_name)=lower(?)",
                    (values.person,),
                ).fetchall()
                if len(found) == 1:
                    values.person_id = found[0]["person_id"]
                else:
                    task.clarification = "Please choose an unambiguous person ID."
                    options = [dict(r) for r in found]
            if values.engagement_id is not None:
                found = c.execute(
                    "SELECT engagement_id,code,title FROM engagements WHERE engagement_id=?",
                    (values.engagement_id,),
                ).fetchall()
                if len(found) != 1 or (
                    values.project
                    and values.project.casefold()
                    not in (found[0]["code"].casefold(), found[0]["title"].casefold())
                ):
                    task.clarification = (
                        "The project name and ID do not resolve consistently."
                    )
            elif values.project:
                found = c.execute(
                    "SELECT engagement_id,code,title FROM engagements WHERE lower(code)=lower(?) OR lower(title)=lower(?)",
                    (values.project, values.project),
                ).fetchall()
                if len(found) == 1:
                    values.engagement_id = found[0]["engagement_id"]
                else:
                    task.clarification = (
                        "Please provide an unambiguous project code or ID."
                    )
        missing = [
            key
            for key in ("person_id", "engagement_id", "hours", "start_date", "end_date")
            if getattr(values, key) is None
        ]
        task.slots = values
        if task.clarification or missing:
            blocks = [
                text_block(
                    task.clarification or "Please provide: " + ", ".join(missing)
                )
            ]
            if options:
                blocks.append(
                    {
                        "type": "table",
                        "block_id": "person_options",
                        "title": "People with this name",
                        "columns": [{"key": k, "label": k} for k in options[0]],
                        "rows": options,
                    }
                )
            return {
                "interpretation": task.model_dump(),
                "active_task": task.model_dump(),
                "response": self.response(state, blocks, assumptions=task.assumptions),
            }
        if pending and not task.modify_pending:
            return {
                "response": self.response(
                    state,
                    [
                        text_block(
                            "Finish the current booking with Confirm/Reject before creating a second independent proposal."
                        ),
                        card(pending),
                    ],
                ),
                "active_task": {},
            }
        return {"interpretation": task.model_dump(), "active_task": task.model_dump()}

    def route(self, state):
        if state.get("response"):
            return "await_action" if state.get("pending_action_id") else END
        intent = state["interpretation"]["intent"]
        return "prepare" if intent == "booking" else "read"

    def read(self, state):
        task = Interpretation.model_validate(state["interpretation"])
        inputs = {
            "reference_date": state["reference_date"],
            "slots": task.slots.model_dump(),
            "semantic_kind": task.semantic_kind,
            "semantic_mode": task.semantic_mode,
            "context": state["context"],
        }
        if task.slots.start_date and task.slots.end_date:
            a, b = period(task.slots.start_date, task.slots.end_date)
            inputs.update(window_start=a, window_end=b, capacity_hours=capacity(a, b))
        previous = ""
        results = []
        issues = []
        for attempt in range(2):
            try:
                plan = self.gateway.call(
                    "PlanReads",
                    repair=False,
                    question=task.question,
                    context=json.dumps(inputs),
                    allowed_schema=json.dumps(self.reader.schema) + "\n" + RULES,
                    previous_error=previous,
                )
                if len({q.query_id for q in plan.queries}) != len(plan.queries):
                    raise ReadError("invalid_sql", "Query IDs must be unique")
                results = []
                issues = []
                for query in plan.queries:
                    try:
                        if task.intent in ("semantic", "mixed"):
                            key = {
                                "person": "person_id",
                                "project": "engagement_id",
                                "risk": "risk_id",
                            }[task.semantic_kind]
                            results.extend(
                                self.reader.read_pages(
                                    query.sql,
                                    query.parameters,
                                    key,
                                    query.query_id,
                                    query.purpose,
                                )
                            )
                        else:
                            results.append(
                                self.reader.read(
                                    query.sql,
                                    query.parameters,
                                    query.query_id,
                                    query.purpose,
                                )
                            )
                    except ReadError as error:
                        if error.code == "invalid_sql" and not attempt:
                            raise
                        issues.append(
                            {"code": error.code, "message": str(error), "stage": "sql"}
                        )
                break
            except (ReadError, AppError) as error:
                code = error.code
                if attempt or code not in ("invalid_sql", "invalid_model_output"):
                    raise AppError(
                        code, "Read plan could not be executed safely", 502
                    ) from error
                previous = str(error)
        if not results:
            raise AppError("read_failed", "No requested query could be completed", 502)
        return {"read_results": results, "issues": issues}

    def match(self, state):
        task = Interpretation.model_validate(state["interpretation"])
        key = {"person": "person_id", "project": "engagement_id", "risk": "risk_id"}[
            task.semantic_kind
        ]
        rows = [r for result in state["read_results"] for r in result["rows"]]
        if rows and not all(key in row for row in rows):
            raise AppError(
                "invalid_model_output",
                f"Semantic filter must return {key} for each eligible entity",
                502,
            )
        eligible = {int(row[key]) for row in rows}
        matches, metadata, issues = self.semantic.search(task, eligible)
        rendered = []
        references = []
        for candidate, assessment in matches:
            f = candidate["facts"]
            row = {
                key: candidate["entity_id"],
                "reason": assessment.get("ranking_reason") or assessment["reason"],
                "match_reason": assessment["reason"],
                "evidence": " | ".join(assessment["quotes"]),
            }
            if task.semantic_kind == "person":
                row.update(
                    person=f["display_name"],
                    bio=f["bio"],
                    roles=", ".join(f["roles"]),
                    skills=", ".join(
                        f"{s['name']} ({s['proficiency']})" for s in f["skills"]
                    ),
                )
            elif task.semantic_kind == "project":
                row.update(
                    engagement=f["code"],
                    summary=f["summary"],
                    risks=" | ".join(
                        dict.fromkeys(
                            r["description"] for r in f["risks"] if r["description"]
                        )
                    ),
                )
            else:
                row.update(
                    engagement=f["code"], risk=f["description"], severity=f["severity"]
                )
            rendered.append(row)
            references.append(candidate["entity_id"])
        cols = [
            {"key": k, "label": k.replace("_", " ")}
            for k in (rendered[0] if rendered else [key, "reason", "evidence"])
        ]
        block = {
            "type": "table",
            "block_id": "semantic_matches",
            "title": "Source-grounded matches",
            "columns": cols,
            "rows": rendered,
            "completeness": metadata,
            "evidence": [
                {"source_id": c["source_id"], "quotes": a["quotes"]} for c, a in matches
            ],
        }
        counts = {
            "type": "table",
            "block_id": "semantic_counts",
            "title": "Coverage and matching count",
            "columns": [
                {"key": k, "label": k}
                for k in ("eligible", "processed", "matched", "uncertain")
            ],
            "rows": [
                {
                    k: metadata[k]
                    for k in ("eligible", "processed", "matched", "uncertain")
                }
            ],
            "completeness": metadata,
        }
        blocks = [block, counts]
        if metadata["uncertain"] or (
            metadata["mode"] == "exhaustive" and not metadata["complete"]
        ):
            blocks.insert(
                0,
                text_block(
                    f"At least {metadata['matched']} verified matches; an exact total is unavailable because some candidates are uncertain or unprocessed."
                ),
            )
            issues.append(
                {
                    "code": "incomplete_semantic_coverage",
                    "message": "Exact semantic total is not established",
                    "stage": "semantic",
                }
            )
        if metadata["fallback"]:
            blocks.insert(
                0,
                text_block(
                    "Embeddings unavailable: assessed original candidate texts with the chat model; this may take longer."
                ),
            )
        if task.intent == "mixed":
            blocks.append(
                text_block(
                    "Choose the person ID you want to book. The supplied booking details will be retained."
                )
            )
        return {
            "response": self.response(
                state, blocks, state["issues"] + issues, task.assumptions
            ),
            "displayed_references": [{"kind": task.semantic_kind, "ids": references}],
            "active_task": {**task.model_dump(), "intent": "booking"}
            if task.intent == "mixed"
            else {},
        }

    def compose(self, state):
        task = Interpretation.model_validate(state["interpretation"])
        results = state["read_results"]
        issues = state["issues"][:]
        if state.get("response"):
            response = state["response"]
            blocks = response["blocks"]
            issues = response["issues"]
        else:
            blocks = [table_block(result) for result in results]
            try:
                sample = [
                    {
                        **r,
                        "rows": r["rows"][:20],
                        "explanation_sample": len(r["rows"]) > 20,
                    }
                    for r in results
                ]
                explanation = self.gateway.call(
                    "ExplainResults",
                    question=task.question,
                    evidence=json.dumps(
                        {
                            "results": sample,
                            "assumptions": task.assumptions,
                            "rules": RULES,
                        }
                    ),
                )
                blocks.insert(0, text_block(explanation))
            except Exception as error:
                event("explanation_failed", error_class=type(error).__name__)
                issues.append(
                    {
                        "code": "explanation_unavailable",
                        "message": "Verified tables and SQL are available; the explanation could not be generated",
                        "stage": "explanation",
                    }
                )
        blocks.extend(
            {
                "type": "sql",
                **{k: r[k] for k in ("query_id", "purpose", "sql", "parameters")},
            }
            for r in results
        )
        references = state.get("displayed_references", [])
        if task.intent == "factual":
            newer = []
            for result in results:
                for kind, key in [
                    ("person", "person_id"),
                    ("project", "engagement_id"),
                ]:
                    if key in result["columns"]:
                        newer.append(
                            {"kind": kind, "ids": [r[key] for r in result["rows"]]}
                        )
            if newer:
                references = newer
        return {
            "response": self.response(state, blocks, issues, task.assumptions),
            "displayed_references": references,
        }

    def prepare(self, state):
        task = Interpretation.model_validate(state["interpretation"])
        try:
            action = self.store.prepare(
                state["thread_id"],
                state["request_id"],
                task.slots,
                replace_pending=task.modify_pending,
            )
        except ValueError as error:
            return {
                "response": self.response(state, [text_block(str(error))]),
                "active_task": task.model_dump(),
            }
        return {
            "pending_action_id": action["action_id"],
            "active_task": {},
            "response": self.response(
                state, [card(action)], assumptions=task.assumptions
            ),
        }

    def await_action(self, state):
        action_id = state.get("pending_action_id")
        if not action_id:
            return Command(goto=END)
        action = self.store.action(state["thread_id"], action_id)
        event_input = interrupt({"action_id": action_id, "status": action["status"]})
        if event_input["kind"] == "message":
            return Command(
                update={
                    k: event_input[k] for k in ("request_id", "text", "reference_date")
                },
                goto="load_context",
            )
        if event_input["kind"] == "decision":
            action = self.store.action(state["thread_id"], action_id)
            if action["status"] == "pending":
                raise AppError("action_conflict", "Action decision has not committed")
            return Command(
                update={"pending_action_id": None, "active_task": {}}, goto=END
            )
        raise AppError("invalid_request", "Unknown resume event", 422)

    def run(self, thread, request, text, reference, *, resume=False):
        config = self.config(thread)
        snapshot = self.graph.get_state(config)
        if resume:
            if snapshot.values.get("request_id") != request:
                return self.run(thread, request, text, reference, resume=False)
            if not snapshot.next and snapshot.values.get("response"):
                return snapshot.values["response"]
            if not snapshot.next:
                raise AppError(
                    "recovery_failed",
                    "No usable unfinished graph checkpoint exists",
                    500,
                )
            value = self.graph.invoke(None, config)
        elif snapshot.next:
            # Only a deliberate human-action interrupt accepts a new message.
            if not any(t.interrupts for t in snapshot.tasks):
                previous = self.store.request(thread, snapshot.values["request_id"])
                if previous["status"] != "failed":
                    raise AppError(
                        "resume_required", "Continue the interrupted operation first"
                    )
                value = self.graph.invoke(
                    {
                        "thread_id": thread,
                        "request_id": request,
                        "text": text,
                        "reference_date": reference,
                    },
                    config,
                )
            else:
                value = self.graph.invoke(
                    Command(
                        resume={
                            "kind": "message",
                            "request_id": request,
                            "text": text,
                            "reference_date": reference,
                        }
                    ),
                    config,
                )
        else:
            value = self.graph.invoke(
                {
                    "thread_id": thread,
                    "request_id": request,
                    "text": text,
                    "reference_date": reference,
                },
                config,
            )
        if not value.get("response"):
            raise AppError("recovery_failed", "Graph produced no durable response", 500)
        return value["response"]

    def decision(self, thread, action):
        snapshot = self.graph.get_state(self.config(thread))
        if (
            snapshot.next
            and snapshot.values.get("pending_action_id") == action["action_id"]
        ):
            self.graph.invoke(Command(resume={"kind": "decision"}), self.config(thread))

    def close(self):
        self.connection.close()
