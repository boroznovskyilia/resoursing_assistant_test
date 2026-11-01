"""Compatibility and transaction checks for the owner-approved persistence refactor."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import event

from resourcing_assistant.agent.state import State
from resourcing_assistant.app import create_service
from resourcing_assistant.config import Settings
from resourcing_assistant.db.session import connect
from resourcing_assistant.db.source import initialize
from resourcing_assistant.domain.calculations import period
from tests.test_agent import ScriptedGateway


@pytest.mark.parametrize(
    "kind,count,queries,digest",
    [
        (
            "person",
            400,
            3,
            "ad583feb9e348f3757cc9f03e177bd68d20bf959184792a41f1f0a6500243eac",
        ),
        (
            "project",
            150,
            2,
            "6cf4bdec5f8c5b7ad0b6bf902d5a072801ab898afec7f507069e8e4b33d4ce5c",
        ),
        (
            "risk",
            373,
            1,
            "7a71856d8ebe8e8f1b61fa71ffb3a60d99b4e949fce227694ba4d9a3580e565a",
        ),
    ],
)
def test_batched_documents_preserve_every_legacy_document(
    store, kind, count, queries, digest
):
    statements = []
    engine = store.bookings.repository.database.engine

    def observed(_, __, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", observed)
    try:
        candidates = store.agent.semantic.candidates(kind)
    finally:
        event.remove(engine, "before_cursor_execute", observed)
    # Digests were measured from the pre-refactor generator over the pinned source.
    assert len(candidates) == count and len(statements) == queries
    assert (
        hashlib.sha256(
            json.dumps([c.model_dump() for c in candidates], sort_keys=True).encode()
        ).hexdigest()
        == digest
    )
    assert store.agent.semantic.candidates(kind, set()) == []


def test_booking_insert_and_receipt_rollback_together(store):
    thread = store.conversations.create_thread()["thread_id"]
    action = store.message(thread, "prepare", "book").blocks[0].action_id
    engine = store.bookings.repository.database.engine
    with connect(store.subject, readonly=True) as c:
        before = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

    def fail_receipt(_, __, statement, *args):
        if statement.startswith("UPDATE booking_actions"):
            raise RuntimeError("Injected receipt failure after booking INSERT")

    event.listen(engine, "before_cursor_execute", fail_receipt)
    try:
        with pytest.raises(RuntimeError, match="receipt failure"):
            store.bookings.decide(thread, action, "confirm")
    finally:
        event.remove(engine, "before_cursor_execute", fail_receipt)
    with connect(store.subject, readonly=True) as c:
        assert c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == before
    assert store.bookings.action(thread, action)["status"] == "pending"
    receipt = store.bookings.decide(thread, action, "confirm")
    assert receipt["booking_id"] is not None
    assert (
        store.bookings.decide(thread, action, "confirm")["booking_id"]
        == receipt["booking_id"]
    )


def test_legacy_history_pending_action_and_checkpoint_continue(tmp_path):
    settings = Settings(runtime=tmp_path, reference_date="2026-04-01T00:00:00Z")
    subject = initialize(settings)
    fixtures = Path(__file__).parent / "fixtures"
    start, end = period("2026-04-01", "2026-04-30")
    fields = {
        "person_id": 1,
        "person": "Historical displayed person",
        "engagement_id": 1,
        "engagement": "Historical displayed project",
        "start": "2026-04-01",
        "end_inclusive": "2026-04-30",
        "end_exclusive": "2026-05-01",
        "hours": 40,
        "minutes": 2400,
        "warnings": [],
        "kind": "soft",
    }
    response = {
        "thread_id": "legacy-thread",
        "request_id": "legacy-request",
        "response_message_id": "old-answer",
        "request_status": "completed",
        "blocks": [
            {
                "type": "confirmation",
                "action_id": "legacy-action",
                "status": "pending",
                "fields": fields,
                "booking_id": None,
            }
        ],
        "issues": [],
        "effective_reference_date": settings.reference().isoformat(),
        "assumptions": [],
    }
    with connect(tmp_path / "app.sqlite") as c:
        c.executescript((fixtures / "legacy-app.sql").read_text())
        c.execute("INSERT INTO threads VALUES('legacy-thread',1,1)")
        c.execute(
            "INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-thread",
                "legacy-request",
                "book",
                "old-fingerprint",
                "completed",
                settings.reference().isoformat(),
                json.dumps(response),
                None,
                1,
                1,
            ),
        )
        c.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?,?)",
            ("old-user", "legacy-thread", "legacy-request", "user", "book", 1),
        )
        c.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?,?)",
            (
                "old-answer",
                "legacy-thread",
                "legacy-request",
                "assistant",
                json.dumps(response),
                1,
            ),
        )
        c.commit()
    with connect(subject) as c:
        c.executescript((fixtures / "legacy-bookings.sql").read_text())
        c.execute(
            "INSERT INTO booking_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-action",
                "legacy-thread",
                "legacy-request",
                1,
                1,
                start,
                end,
                2400,
                json.dumps(fields),
                "pending",
                None,
                None,
                1,
                1,
                None,
            ),
        )
        c.commit()
    # Seed the old next-node name and dictionary state, independent of current nodes.
    with sqlite3.connect(
        tmp_path / "app.sqlite", check_same_thread=False
    ) as connection:
        graph = StateGraph(State)
        graph.add_node(
            "await_action", lambda state: interrupt({"action_id": "legacy-action"})
        )
        graph.add_edge(START, "await_action")
        graph.add_edge("await_action", END)
        graph.compile(checkpointer=SqliteSaver(connection)).invoke(
            {
                "thread_id": "legacy-thread",
                "request_id": "legacy-request",
                "text": "book",
                "reference_date": settings.reference().isoformat(),
                "pending_action_id": "legacy-action",
                "active_task": {},
                "response": response,
            },
            {"configurable": {"thread_id": "legacy-thread"}},
        )
    service = create_service(settings, ScriptedGateway())
    try:
        history = service.history("legacy-thread")
        assert history["messages"][1]["message_id"] == "old-answer"
        assert history["pending_action"]["fields"] == fields
        result = service.decide("legacy-thread", "legacy-action", "confirm")
        assert result.blocks[0].booking_id is not None
        assert not result.issues
        assert not service.agent.graph.get_state(
            service.agent.config("legacy-thread")
        ).next
        assert (
            service.decide("legacy-thread", "legacy-action", "confirm")
            .blocks[0]
            .booking_id
            == result.blocks[0].booking_id
        )
    finally:
        service.close()
