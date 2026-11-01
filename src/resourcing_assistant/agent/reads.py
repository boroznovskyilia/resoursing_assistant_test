"""Finite read planning, canonical bindings, guarded execution and shared repair."""

import json
import os
from uuid import uuid4

from resourcing_assistant.agent.read_policy import ReadPolicy
from resourcing_assistant.agent.schemas import Interpretation, Query, ReadPlan
from resourcing_assistant.db.reader import RULES, ReadError
from resourcing_assistant.domain.calculations import capacity, period
from resourcing_assistant.errors import AppError


class ReadService:
    def __init__(self, settings, reader, gateway):
        self.settings, self.reader, self.gateway = settings, reader, gateway

    def run(self, state):
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
        policy = ReadPolicy(task, state["text"])
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
        planning_question = policy.question(task)
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
                if self.settings.evaluation_artifacts:
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
                        policy.query(task, query)
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
                            policy.result(task, query, query is plan.answer, result)
                            results.append(result)
                    except ReadError as error:
                        if error.code == "invalid_sql" and not attempt:
                            raise
                        issues.append(
                            {"code": error.code, "message": str(error), "stage": "sql"}
                        )
                policy.results(task, results, issues)
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
