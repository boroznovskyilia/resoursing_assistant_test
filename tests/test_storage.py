from concurrent.futures import ThreadPoolExecutor

import pytest

from resourcing_assistant.agent.schemas import BookingSlots
from resourcing_assistant.app import create_service
from resourcing_assistant.db.session import connect
from resourcing_assistant.errors import AppError
from tests.test_agent import ScriptedGateway


def slots(hours=40):
    return BookingSlots(
        person_id=1,
        engagement_id=1,
        hours=hours,
        start_date="2026-04-01",
        end_date="2026-04-30",
    )


def count(store):
    with connect(store.subject, readonly=True) as c:
        return c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]


def test_prepare_confirm_repeat_and_wrong_thread(store):
    thread = store.conversations.create_thread()["thread_id"]
    before = count(store)
    action = store.bookings.prepare(thread, "request", slots())
    assert count(store) == before
    assert (
        store.bookings.prepare(thread, "request", slots())["action_id"]
        == action["action_id"]
    )
    other = store.conversations.create_thread()["thread_id"]
    with pytest.raises(AppError):
        store.bookings.decide(other, action["action_id"], "confirm")
    result = store.bookings.decide(thread, action["action_id"], "confirm")
    assert result["status"] == "confirmed" and count(store) == before + 1
    assert (
        store.bookings.decide(thread, action["action_id"], "confirm")["booking_id"]
        == result["booking_id"]
    )
    with pytest.raises(AppError):
        store.bookings.decide(thread, action["action_id"], "reject")
    with connect(store.subject, readonly=True) as c:
        booking = dict(
            c.execute(
                "SELECT * FROM bookings WHERE booking_id=?", (result["booking_id"],)
            ).fetchone()
        )
    assert (
        booking["minutes"] == 2400
        and booking["kind"] == "soft"
        and booking["status_id"] == 13
    )
    assert booking["allocation_id"] is None and booking["requirement_id"] is None
    assert result["fields"]["end_exclusive"] == "2026-05-01"


def test_reject_supersede_and_one_pending(store):
    thread = store.conversations.create_thread()["thread_id"]
    before = count(store)
    old = store.bookings.prepare(thread, "r1", slots())
    with pytest.raises(AppError):
        store.bookings.prepare(thread, "r2", slots(8))
    new = store.bookings.prepare(thread, "r2", slots(8), replace_pending=True)
    assert store.bookings.action(thread, old["action_id"])["status"] == "superseded"
    with pytest.raises(AppError):
        store.bookings.decide(thread, old["action_id"], "confirm")
    assert (
        store.bookings.decide(thread, new["action_id"], "reject")["status"]
        == "rejected"
    )
    store.bookings.decide(thread, new["action_id"], "reject")
    assert count(store) == before


def test_restart_and_concurrent_confirm(store):
    thread = store.conversations.create_thread()["thread_id"]
    action = store.bookings.prepare(thread, "r1", slots())
    before = count(store)
    restarted = create_service(store.settings, ScriptedGateway())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: restarted.bookings.decide(
                    thread, action["action_id"], "confirm"
                ),
                range(8),
            )
        )
    assert len({r["booking_id"] for r in results}) == 1 and count(store) == before + 1
    assert restarted.bookings.pending(thread) is None


def test_request_dedup_restart_and_resume(store):
    thread = store.conversations.create_thread()["thread_id"]
    store.conversations.admit(thread, "r1", "First", "2026-04-01T00:00:00Z")
    assert (
        store.conversations.admit(thread, "r1", "First", "2026-04-01T00:00:00Z")[
            "status"
        ]
        == "processing"
    )
    with pytest.raises(AppError):
        store.conversations.admit(thread, "r1", "Changed", "2026-04-01T00:00:00Z")
    restarted = create_service(store.settings, ScriptedGateway())
    assert restarted.conversations.request(thread, "r1")["status"] == "interrupted"
    with pytest.raises(AppError):
        restarted.conversations.admit(thread, "r2", "New", "2026-04-01T00:00:00Z")
    restarted.conversations.resume(thread, "r1")
    result = {
        "thread_id": thread,
        "request_id": "r1",
        "request_status": "completed",
        "blocks": [],
        "effective_reference_date": "2026-04-01T00:00:00Z",
    }
    first = restarted.conversations.finish(thread, "r1", result)
    second = restarted.conversations.finish(thread, "r1", result)
    assert first["response_message_id"] == second["response_message_id"]
    assert len(restarted.history(thread)["messages"]) == 2


def test_terms_tampering_rejected_and_new_identical_action_allowed(store):
    thread = store.conversations.create_thread()["thread_id"]
    before = count(store)
    action = store.bookings.prepare(thread, "r1", slots())
    with connect(store.subject) as c:
        c.execute(
            "UPDATE booking_actions SET minutes=480 WHERE action_id=?",
            (action["action_id"],),
        )
        c.commit()
    with pytest.raises(AppError):
        store.bookings.decide(thread, action["action_id"], "confirm")
    assert count(store) == before
    store.bookings.decide(thread, action["action_id"], "reject")
    one = store.bookings.prepare(thread, "r2", slots())
    store.bookings.decide(thread, one["action_id"], "confirm")
    two = store.bookings.prepare(thread, "r3", slots())
    store.bookings.decide(thread, two["action_id"], "confirm")
    assert count(store) == before + 2
