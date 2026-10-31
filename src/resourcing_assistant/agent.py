"""Controlled persistent graph; source writes only through stored-action decisions."""

import json
import os
import re
import sqlite3
from uuid import uuid4
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command, interrupt
from .config import period, capacity
from .data import RULES, ReadError, connect, has_limit
from .llm import Gateway, token_count, rendered_tokens, event
from .models import Interpretation, BookingSlots, AppError, ReadPlan, Query
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


BUTTON_REPLIES = frozenset(("yes", "confirm", "approved", "approve", "ok", "да"))


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
        pending = self.store.pending(state["thread_id"])
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
        if (
            state.get("pending_action_id")
            and state["text"].strip().lower() in BUTTON_REPLIES
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
                source_schema=self.reader.prompt_schema(question=state["text"]),
            )
        if value.intent in ("semantic", "mixed"):
            head = re.split(
                r"\b(?:with|who|whose|that|have|has|for|in|outside|having)\b",
                value.question,
                maxsplit=1,
                flags=re.I,
            )[0]
            if re.search(
                r"\b(?:people|persons?|candidates?|consultants?|engineers?|developers?|managers?)\b(?!-related)|^\s*who\b",
                head,
                re.I,
            ):
                value.semantic_kind = "person"
            elif re.search(r"\b(?:projects?|engagements?)\b", head, re.I):
                value.semantic_kind = "project"
            elif re.search(r"\brisks?\b", head, re.I):
                value.semantic_kind = "risk"
            exhaustive = bool(
                re.search(
                    r"\ball\b|\bevery\b|\bhow many\b|\bcount\b|\bnumber of\b",
                    state["text"],
                    re.I,
                )
            )
            recommendation = bool(
                re.search(
                    r"\brecommend|\bcould lead\b|\bsuitable\b|\bexperienced\b|\btop\s+\d+",
                    state["text"],
                    re.I,
                )
            )
            if exhaustive:
                value.semantic_mode = "exhaustive"
            elif recommendation or value.semantic_kind == "person":
                value.semantic_mode = "shortlist"
            elif value.semantic_kind in ("project", "risk"):
                value.semantic_mode = "exhaustive"
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
        eligibility = None
        compiled = None
        planning_question = task.question
        ranking = bool(
            re.search(r"\b(most|top|leading|highest|largest)\b", task.question, re.I)
        ) and not re.search(r"\bat\s+most\b", task.question, re.I)
        explicit_size = bool(
            re.search(
                r"\b(?:top|first|best|list|show|return)\s+(?:the\s+)?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b|\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:most|highest|leading)\b|\bonly\s+(?:one|1)\b",
                task.question,
                re.I,
            )
        )
        logged = bool(
            re.search(r"\b(logged|time entries|actual hours)\b", state["text"], re.I)
        )
        scalar_count = bool(
            re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", state["text"], re.I)
        ) and not re.search(
            r"\b(each|per|by)\b|\bbroken down\b|\bhow many\s+(?:[\w-]+\s+){0,3}(?:hours|minutes|days|weeks|months|dollars)\b",
            state["text"],
            re.I,
        )
        scalar_total = bool(
            re.search(r"\b(total|sum)\b", state["text"], re.I)
            and re.search(
                r"\b(cost|value|amount|hours|minutes|effort|revenue|price)\b",
                state["text"],
                re.I,
            )
        ) and not re.search(r"\b(each|per|by)\b|\bbroken down\b", state["text"], re.I)
        scalar_total = scalar_total or bool(
            re.search(
                r"\bhow many\s+(?:[\w-]+\s+){0,3}(?:hours|minutes|dollars)\b",
                state["text"],
                re.I,
            )
        )
        hard_capacity_list = bool(
            re.search(r"\bhard[- ]booked\b", state["text"], re.I)
            and re.search(r"%|\bpercent(?:age)?\b", state["text"], re.I)
        ) and not (scalar_count or scalar_total)
        schema = self.reader.schema
        if task.intent in ("semantic", "mixed"):
            user_text = "\n".join(
                [state["text"]]
                + [
                    t["content"]
                    for t in state["context"].get("recent_turns", [])
                    if t["role"] == "user" and isinstance(t["content"], str)
                ]
            )
            eligibility = self.reader.eligibility_columns(task.semantic_kind, user_text)
            compiled = self.reader.simple_eligibility(
                task.semantic_kind, task.question, task.slots.model_dump()
            )
            schema = [
                {
                    **s,
                    "columns": {
                        k: v
                        for k, v in s["columns"].items()
                        if k in eligibility[s["table"]]
                    },
                    "foreign_keys": [
                        fk
                        for fk in s["foreign_keys"]
                        if fk["from"] in eligibility[s["table"]]
                    ],
                    "values": {
                        k: v
                        for k, v in s.get("values", {}).items()
                        if k in eligibility[s["table"]]
                    },
                }
                for s in schema
                if s["table"] in eligibility
            ]
        elif ranking and not explicit_size:
            planning_question += "\nOutput policy: return the TOP FIVE ranked contributors/entities, ordered by the requested measure, with per-entity IDs and measures. Return any requested full total separately."
            task.assumptions.append(
                "Rankings without an explicit size show the top five for context."
            )
        elif (
            task.intent == "factual"
            and not explicit_size
            and not (scalar_count or scalar_total)
        ):
            planning_question += "\nOutput policy: return ALL matching records, without LIMIT or intermediate/helper queries. Use the supplied code-computed period/capacity values."
        if hard_capacity_list:
            planning_question += "\nOutput policy: each eligible person's row MUST include person_id, person/name, hard_booked_hours and hard_booked_pct (0-100). The user must see the derived booking measure used in the filter, including zeros. Do not return only names/IDs. Use full intersecting kind=hard minutes and code-computed period/capacity; no unrequested status exclusions."
        if logged:
            planning_question += "\nLogged hours are ACTUAL time_entries minutes via work_items, never bookings or assignments."
        if task.intent == "factual" and scalar_total:
            planning_question += "\nOutput policy: deliver each requested TOTAL as a visible one-row SUM aggregate with the complete requested filters. A detail list and an instruction for the user to sum it are NOT a total. Return optional detail separately."
        if task.intent == "factual" and scalar_count:
            planning_question += "\nOutput policy: return a visible one-row COUNT aggregate for the requested entity count. Listing entity rows without the requested count is incomplete. Separate any requested rankings/details from the full count."
        if (
            task.intent == "factual"
            and re.search(r"\b(total|sum)\b", task.question, re.I)
            and re.search(r"planned\s+cost", task.question, re.I)
            and re.search(r"\b(engagements?|projects?)\b", task.question, re.I)
        ):
            planning_question += "\nOutput policy: include total_usd AND engagement_count (COUNT DISTINCT qualifying engagements) in the aggregate row. Reporting currency is currencies.is_primary=1; use the actual currency FX from rate_cards."
        previous = ""
        results = []
        issues = []
        for attempt in range(2):
            try:
                plan = (
                    ReadPlan(
                        answer=Query(
                            query_id="eligible",
                            purpose="Exact structured candidate pool",
                            sql=compiled[0],
                            parameters=[
                                {"name": k, "value": v} for k, v in compiled[1].items()
                            ],
                        ),
                        additional_answers=[],
                    )
                    if compiled is not None
                    else self.gateway.call(
                        "PlanReads",
                        intent="semantic"
                        if task.intent in ("semantic", "mixed")
                        else "factual",
                        repair=False,
                        question=planning_question,
                        context=json.dumps(inputs),
                        allowed_schema=self.reader.prompt_schema(schema) + "\n" + RULES,
                        previous_error=previous,
                    )
                )
                if len({q.query_id for q in plan.queries}) != len(plan.queries):
                    raise ReadError("invalid_sql", "Query IDs must be unique")
                if os.getenv("RESOURCING_EVAL_ARTIFACTS") == "1":
                    directory = (
                        self.settings.runtime
                        / "read-plans"
                        / state["thread_id"]
                        / state["request_id"]
                    )
                    directory.mkdir(parents=True, exist_ok=True)
                    path = directory / f"attempt-{attempt + 1}-{uuid4().hex}.json"
                    descriptor = os.open(
                        path, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600
                    )
                    with os.fdopen(descriptor, "w") as stream:
                        stream.write(plan.model_dump_json(indent=2))
                results = []
                issues = []
                for query in plan.queries:
                    bindings = query.bindings
                    # Dates/capacity are computed in code; the model cannot replace them.
                    for key in ("window_start", "window_end", "capacity_hours"):
                        if key in bindings and key in inputs:
                            bindings[key] = inputs[key]
                    try:
                        if has_limit(
                            query.sql, outer_only=task.intent == "factual"
                        ) and (
                            task.intent in ("semantic", "mixed")
                            or not (ranking or explicit_size)
                        ):
                            raise ReadError(
                                "invalid_sql",
                                "Unrequested LIMIT can omit matching records. Return all matches; safety row limits/pagination are enforced by code.",
                            )
                        if task.intent in ("semantic", "mixed"):
                            key = {
                                "person": "person_id",
                                "project": "engagement_id",
                                "risk": "risk_id",
                            }[task.semantic_kind]
                            results.extend(
                                self.reader.read_pages(
                                    query.sql,
                                    bindings,
                                    key,
                                    query.query_id,
                                    query.purpose,
                                    eligibility=eligibility,
                                )
                            )
                        else:
                            result = self.reader.read(
                                query.sql,
                                bindings,
                                query.query_id,
                                query.purpose,
                            )
                            if (
                                hard_capacity_list
                                and query is plan.answer
                                and not {
                                    "hard_booked_hours",
                                    "hard_hours",
                                }.intersection(result["columns"])
                            ):
                                raise ReadError(
                                    "invalid_sql",
                                    "Eligible person rows must display hard_booked_hours used by the percentage filter, including zero. Returning only names/IDs omits the requested measure.",
                                )
                            if (
                                query is plan.answer
                                and logged
                                and "time_entries" not in result["source_tables"]
                            ):
                                raise ReadError(
                                    "invalid_sql",
                                    "Logged/actual hours MUST read time_entries via work_items, not bookings or assignments. Correct the primary answer source.",
                                )
                            if any(
                                k.endswith("_id") for k in result["columns"]
                            ) and len(
                                {json.dumps(r, sort_keys=True) for r in result["rows"]}
                            ) != len(result["rows"]):
                                raise ReadError(
                                    "invalid_sql",
                                    "Identical entity rows were duplicated by a join. Use EXISTS/DISTINCT or include the actual source grain identity.",
                                )
                            results.append(result)
                    except ReadError as error:
                        if error.code == "invalid_sql" and not attempt:
                            raise
                        issues.append(
                            {"code": error.code, "message": str(error), "stage": "sql"}
                        )
                if (
                    task.intent == "factual"
                    and scalar_total
                    and not issues
                    and not any(
                        len(r["rows"]) == 1
                        and re.search(r"\b(?:SUM|TOTAL)\s*\(", r["sql"], re.I)
                        for r in results
                    )
                ):
                    raise ReadError(
                        "invalid_sql",
                        "A full total was requested. Return a visible one-row SUM aggregate; listing detail rows or asking the user to add them is incomplete.",
                    )
                if (
                    task.intent == "factual"
                    and scalar_count
                    and not issues
                    and not any(
                        len(r["rows"]) == 1
                        and re.search(r"\bCOUNT\s*\(", r["sql"], re.I)
                        for r in results
                    )
                ):
                    raise ReadError(
                        "invalid_sql",
                        "An exact count was requested. Return a one-row COUNT aggregate, not only the matching entity list or grouped detail.",
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
        return {
            "read_results": results,
            "issues": issues,
            "interpretation": task.model_dump(),
        }

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
