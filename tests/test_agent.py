import pytest
from resourcing_assistant.config import Settings
from resourcing_assistant.service import Service
from resourcing_assistant.models import (
    Interpretation,
    BookingSlots,
    ReadPlan,
    Query,
    AppError,
    Assessment,
    RankItem,
    ProjectChecks,
)


class ScriptedGateway:
    """Explicit transition-test double; never imported by production code."""

    def __init__(self):
        self.calls = []
        self.fail_explanation = False

    def call(self, name, **inputs):
        self.calls.append((name, inputs))
        if name == "InterpretRequest":
            message = inputs["message"]
            if message == "book":
                return Interpretation(
                    intent="booking",
                    question=message,
                    slots=BookingSlots(
                        person="Amanda Evans",
                        project="ENG-2026-0001",
                        hours=40,
                        start_date="2026-04-01",
                        end_date="2026-04-30",
                    ),
                )
            if message == "ambiguous":
                return Interpretation(
                    intent="booking",
                    question=message,
                    slots=BookingSlots(
                        person="Amanda Mitchell",
                        project="ENG-2026-0001",
                        hours=40,
                        start_date="2026-04-01",
                        end_date="2026-04-30",
                    ),
                )
            if message == "active semantic":
                return Interpretation(
                    intent="semantic",
                    question=message,
                    semantic_kind="project",
                    semantic_mode="exhaustive",
                    criteria="Staffing gap",
                )
            if message == "unsupported":
                return Interpretation(intent="unsupported", question=message)
            return Interpretation(intent="factual", question=message)
        if name == "PlanReads":
            if inputs["question"] == "active semantic":
                return ReadPlan(
                    answer=Query(
                        parameters=[],
                        query_id="eligible",
                        purpose="Exact active projects",
                        sql="SELECT e.engagement_id FROM engagements e JOIN status_lookup s ON s.status_id=e.status_id WHERE s.domain='project' AND s.code='ACT'",
                    ),
                    additional_answers=[],
                )
            return ReadPlan(
                answer=Query(
                    parameters=[],
                    query_id="count",
                    purpose="People count",
                    sql="SELECT COUNT(*) AS people FROM people",
                ),
                additional_answers=[],
            )
        if name == "ExplainResults":
            if self.fail_explanation:
                raise AppError("provider_unavailable", "Test failure", 503)
            return "The exact count is in the table."
        if name == "AssessCandidates":
            return [
                Assessment(
                    source_id=c.source_id,
                    status="match" if "Staffing gap" in c.text else "no_match",
                    quotes=[
                        "Staffing gap identified on this engagement; mitigation plan in progress."
                    ]
                    if "Staffing gap" in c.text
                    else [],
                    reason="Original risk description states a staffing gap.",
                )
                for c in inputs["candidates"]
            ]
        if name == "PlanProjectChecks":
            return ProjectChecks(
                summary=None, summary_scope="full", risk="Staffing gap", operator="all"
            )
        if name == "RankCandidates":
            import json

            return [
                RankItem(
                    source_id=item["candidate"]["source_id"],
                    reason="Grounded risk match",
                )
                for item in json.loads(inputs["candidates"])[
                    : inputs["requested_count"]
                ]
            ]
        if name == "SummarizeHistory":
            return "Previously discussed staffing and source data."
        raise AssertionError(name)


@pytest.fixture
def service(tmp_path):
    gateway = ScriptedGateway()
    s = Service(
        Settings(runtime=tmp_path, reference_date="2026-04-01T00:00:00Z"), gateway
    )
    yield s, gateway
    s.close()


def test_factual_dedup_partial_and_no_model_on_history(service):
    s, gateway = service
    thread = s.store.create_thread()["thread_id"]
    first = s.message(thread, "r1", "count")
    assert first.blocks[1].rows == [{"people": 400}]
    calls = len(gateway.calls)
    assert (
        s.message(thread, "r1", "count").response_message_id
        == first.response_message_id
    )
    s.store.history(thread)
    assert len(gateway.calls) == calls
    gateway.fail_explanation = True
    result = s.message(thread, "r2", "count")
    assert result.request_status == "partial"
    assert any(b.type == "sql" for b in result.blocks)
    assert any(b.type == "table" and b.rows == [{"people": 400}] for b in result.blocks)


def test_pending_read_confirmation_and_real_checkpoint_reopen(service):
    s, gateway = service
    thread = s.store.create_thread()["thread_id"]
    response = s.message(thread, "r1", "book")
    action = response.blocks[0].action_id
    assert response.request_status == "completed"
    assert s.agent.graph.get_state(s.agent.config(thread)).next == ("await_action",)
    s.message(thread, "r2", "count")
    assert s.store.pending(thread)["action_id"] == action
    before = len(gateway.calls)
    s.message(thread, "r3", "yes")
    assert len(gateway.calls) == before
    s.close()
    restarted = Service(s.settings, gateway)
    try:
        result = restarted.decide(thread, action, "confirm")
        assert result.blocks[0].status == "confirmed"
        assert (
            restarted.decide(thread, action, "confirm").blocks[0].booking_id
            == result.blocks[0].booking_id
        )
        assert len(gateway.calls) == before
        assert (
            restarted.store.history(thread)["messages"][1]["content"]["blocks"][0][
                "status"
            ]
            == "confirmed"
        )
        restarted.message(thread, "r4", "count")
    finally:
        restarted.close()
    # Closing an already-closed sqlite connection is supported.


def test_ambiguity_and_clean_new_thread(service):
    s, gateway = service
    thread = s.store.create_thread()["thread_id"]
    response = s.message(thread, "r1", "ambiguous")
    assert s.store.pending(thread) is None
    assert any(
        b.type == "table" and {r["person_id"] for r in b.rows} == {78, 238}
        for b in response.blocks
    )
    other = s.store.create_thread()["thread_id"]
    s.message(other, "r1", "count")
    context = next(
        inputs["context"]
        for name, inputs in reversed(gateway.calls)
        if name == "InterpretRequest"
    )
    assert "Amanda Mitchell" not in context


def test_exhaustive_semantic_source_set(service):
    s, _ = service
    thread = s.store.create_thread()["thread_id"]
    result = s.message(thread, "r1", "active semantic")
    matches = next(
        b
        for b in result.blocks
        if b.type == "table" and b.block_id == "semantic_matches"
    )
    assert len(matches.rows) == 11
    assert matches.completeness["complete"] is True
    assert matches.completeness["eligible"] == 60
    assert matches.completeness["processed"] == 60


def test_scalar_followup_keeps_last_entity_order(service):
    s, _ = service
    thread = s.store.create_thread()["thread_id"]
    s.message(thread, "semantic", "active semantic")
    before = s.agent.graph.get_state(s.agent.config(thread)).values[
        "displayed_references"
    ]
    s.message(thread, "count", "count")
    after = s.agent.graph.get_state(s.agent.config(thread)).values[
        "displayed_references"
    ]
    assert before == after and before[0]["ids"]


def test_factual_window_bindings_cannot_override_code_clock(tmp_path):
    class WrongClock(ScriptedGateway):
        def call(self, name, **inputs):
            if name == "InterpretRequest":
                return Interpretation(
                    intent="factual",
                    question="Period",
                    slots=BookingSlots(start_date="2026-03-01", end_date="2026-05-31"),
                )
            if name == "PlanReads":
                return ReadPlan(
                    answer=Query(
                        query_id="period",
                        purpose="Period",
                        sql="SELECT :window_start AS start, :window_end AS end, :capacity_hours AS capacity FROM people WHERE person_id=1",
                        parameters=[
                            {"name": "window_start", "value": 0},
                            {"name": "window_end", "value": 1},
                            {"name": "capacity_hours", "value": 1},
                        ],
                    ),
                    additional_answers=[],
                )
            return super().call(name, **inputs)

    from resourcing_assistant.config import period

    s = Service(Settings(runtime=tmp_path), WrongClock())
    try:
        thread = s.store.create_thread()["thread_id"]
        result = s.message(thread, "period", "Period")
        block = next(b for b in result.blocks if b.type == "table")
        start, end = period("2026-03-01", "2026-05-31")
        assert block.rows == [{"start": start, "end": end, "capacity": 520}]
        sql = next(b for b in result.blocks if b.type == "sql")
        assert sql.parameters["window_start"] == start
    finally:
        s.close()


@pytest.mark.parametrize(
    "message,normalized,kind,mode",
    [
        (
            "Suggest people experienced in migrations",
            "List all people experienced in migrations",
            "person",
            "shortlist",
        ),
        (
            "Which projects have people-related risks?",
            "Which projects have people-related risks?",
            "project",
            "exhaustive",
        ),
        (
            "Find project managers for projects",
            "Find project managers for projects",
            "person",
            "shortlist",
        ),
        (
            "List all people with cloud experience",
            "List people with cloud experience",
            "person",
            "exhaustive",
        ),
    ],
)
def test_semantic_output_scope_uses_request(message, normalized, kind, mode, service):
    s, gateway = service
    original = gateway.call

    def call(name, **inputs):
        if name == "InterpretRequest":
            return Interpretation(
                intent="semantic",
                question=normalized,
                semantic_kind="risk",
                semantic_mode="exhaustive",
            )
        return original(name, **inputs)

    gateway.call = call
    result = s.agent.interpret({"text": message, "context": {}})
    assert result["interpretation"]["semantic_kind"] == kind
    assert result["interpretation"]["semantic_mode"] == mode
