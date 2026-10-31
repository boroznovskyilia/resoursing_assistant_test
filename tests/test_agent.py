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
            if message == "semantic":
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
            if inputs["question"] == "semantic":
                return ReadPlan(
                    queries=[
                        Query(
                            query_id="eligible",
                            purpose="Exact active projects",
                            sql="SELECT e.engagement_id FROM engagements e JOIN status_lookup s ON s.status_id=e.status_id WHERE s.domain='project' AND s.code='ACT'",
                        )
                    ]
                )
            return ReadPlan(
                queries=[
                    Query(
                        query_id="count",
                        purpose="People count",
                        sql="SELECT COUNT(*) AS people FROM people",
                    )
                ]
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
        if name == "RankCandidates":
            import json

            return [
                RankItem(
                    source_id=item["candidate"]["source_id"],
                    reason="Grounded risk match",
                )
                for item in json.loads(inputs["candidates"])
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
    result = s.message(thread, "r1", "semantic")
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
    s.message(thread, "semantic", "semantic")
    before = s.agent.graph.get_state(s.agent.config(thread)).values[
        "displayed_references"
    ]
    s.message(thread, "count", "count")
    after = s.agent.graph.get_state(s.agent.config(thread)).values[
        "displayed_references"
    ]
    assert before == after and before[0]["ids"]
