import io
import json
import logging
import pytest
from tests.test_agent import ScriptedGateway
from resourcing_assistant.config import Settings
from resourcing_assistant.service import Service
from resourcing_assistant.models import AppError, ReadPlan, Query
from resourcing_assistant.llm import LOG
from resourcing_assistant.evaluation import invariants


def test_sql_format_and_syntax_share_one_repair_then_next_request_works(tmp_path):
    class Broken(ScriptedGateway):
        def __init__(self):
            super().__init__()
            self.plans = 0

        def call(self, name, **inputs):
            if name == "PlanReads":
                self.plans += 1
                if self.plans == 1:
                    raise AppError("invalid_model_output", "Bad format", 502)
                if self.plans == 2:
                    return ReadPlan(
                        queries=[
                            Query(
                                query_id="bad",
                                purpose="Bad query",
                                sql="SELECT invented FROM missing_table",
                            )
                        ]
                    )
            return super().call(name, **inputs)

    gateway = Broken()
    s = Service(Settings(runtime=tmp_path), gateway)
    thread = s.store.create_thread()["thread_id"]
    try:
        with pytest.raises(AppError):
            s.message(thread, "r1", "count")
        assert gateway.plans == 2
        assert s.message(thread, "r2", "count").request_status == "completed"
    finally:
        s.close()


def test_policy_violation_gets_no_repair_and_preserves_source(tmp_path):
    class Forbidden(ScriptedGateway):
        def __init__(self):
            super().__init__()
            self.plans = 0

        def call(self, name, **inputs):
            if name == "PlanReads":
                self.plans += 1
                return ReadPlan(
                    queries=[
                        Query(
                            query_id="bad",
                            purpose="Forbidden",
                            sql="DELETE FROM bookings",
                        )
                    ]
                )
            return super().call(name, **inputs)

    gateway = Forbidden()
    s = Service(Settings(runtime=tmp_path), gateway)
    thread = s.store.create_thread()["thread_id"]
    try:
        with pytest.raises(AppError):
            s.message(thread, "r1", "count")
        assert gateway.plans == 1
        assert invariants(s.settings.source, s.subject)
    finally:
        s.close()


def test_compaction_and_misleading_summary_never_change_pending_terms(tmp_path):
    class Summary(ScriptedGateway):
        def call(self, name, **inputs):
            if name == "SummarizeHistory":
                self.calls.append((name, inputs))
                return "A misleading narrative says person999 for999 hours."
            return super().call(name, **inputs)

    gateway = Summary()
    s = Service(Settings(runtime=tmp_path), gateway)
    thread = s.store.create_thread()["thread_id"]
    try:
        action = s.message(thread, "book", "book").blocks[0].action_id
        for i in range(6):
            s.message(thread, f"context{i}", "context " * 800)
        assert any(name == "SummarizeHistory" for name, _ in gateway.calls)
        assert len(s.store.history(thread)["messages"]) == 14
        result = s.decide(thread, action, "confirm")
        assert (
            result.blocks[0].fields["person_id"] == 1
            and result.blocks[0].fields["hours"] == 40
        )
        assert invariants(s.settings.source, s.subject)
    finally:
        s.close()


def test_fallback_logs_scope_no_prompt_and_retains_pending(tmp_path):
    class Shortlist(ScriptedGateway):
        def call(self, name, **inputs):
            value = super().call(name, **inputs)
            if name == "InterpretRequest" and inputs["message"] == "semantic":
                value.semantic_mode = "shortlist"
            return value

    s = Service(Settings(runtime=tmp_path), Shortlist())
    thread = s.store.create_thread()["thread_id"]
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    LOG.addHandler(handler)
    try:
        action = s.message(thread, "booking", "book").blocks[0].action_id
        result = s.message(thread, "semantic", "semantic")
        assert (
            result.request_status == "completed"
            and s.store.pending(thread)["action_id"] == action
        )
        logs = stream.getvalue()
        events = [json.loads(line) for line in logs.splitlines()]
        fallback = next(
            row for row in events if row["event"] == "semantic_fallback_started"
        )
        assert fallback["thread_id"] == thread and fallback["request_id"] == "semantic"
        assert "Staffing gap identified" not in logs
        assert s.health()["embeddings"] == "degraded"
    finally:
        LOG.removeHandler(handler)
        s.close()


def test_source_invariants_detect_illegal_working_copy_change(tmp_path):
    from resourcing_assistant.data import connect

    s = Service(Settings(runtime=tmp_path), ScriptedGateway())
    try:
        assert invariants(s.settings.source, s.subject)
        with connect(s.subject) as c:
            c.execute("UPDATE people SET display_name='Changed' WHERE person_id=1")
            c.commit()
        assert not invariants(s.settings.source, s.subject)
    finally:
        s.close()


def test_lost_commit_acknowledgement_returns_existing_receipt_on_retry(
    tmp_path, monkeypatch
):
    from contextlib import contextmanager
    import resourcing_assistant.storage as module

    real_connect = module.connect
    service = Service(Settings(runtime=tmp_path), ScriptedGateway())
    thread = service.store.create_thread()["thread_id"]
    action = service.message(thread, "r1", "book").blocks[0].action_id
    armed = [True]

    class Proxy:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, key):
            return getattr(self.connection, key)

        def commit(self):
            self.connection.commit()
            if armed[0]:
                armed[0] = False
                raise OSError("Simulated lost commit acknowledgement")

    @contextmanager
    def interrupted_connect(*args, **kwargs):
        with real_connect(*args, **kwargs) as connection:
            yield Proxy(connection)

    monkeypatch.setattr(module, "connect", interrupted_connect)
    try:
        with pytest.raises(OSError):
            service.store.decide(thread, action, "confirm")
        committed = service.store.action(thread, action)
        repeated = service.decide(thread, action, "confirm")
        assert repeated.blocks[0].booking_id == committed["booking_id"]
        assert invariants(service.settings.source, service.subject)
    finally:
        service.close()


def test_checkpoint_lag_after_commit_does_not_hide_success(tmp_path, monkeypatch):
    service = Service(Settings(runtime=tmp_path), ScriptedGateway())
    thread = service.store.create_thread()["thread_id"]
    action = service.message(thread, "r1", "book").blocks[0].action_id

    def failure(*args):
        raise OSError("Simulated checkpoint failure")

    monkeypatch.setattr(service.agent, "decision", failure)
    try:
        first = service.decide(thread, action, "confirm")
        second = service.decide(thread, action, "confirm")
        assert (
            first.blocks[0].status == "confirmed"
            and first.blocks[0].booking_id == second.blocks[0].booking_id
        )
        assert (
            first.request_status == "completed"
            and first.issues[0].code == "graph_sync_pending"
        )
        assert invariants(service.settings.source, service.subject)
    finally:
        service.close()
