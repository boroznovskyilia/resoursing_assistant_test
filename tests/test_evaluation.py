"""Harness mechanics against real API processes with an explicit test-only model.

These tests are deliberately not real-model accuracy results.
"""

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx
import pytest

from resourcing_assistant import evaluation as ev
from resourcing_assistant.config import Settings
from resourcing_assistant.data import connect
from resourcing_assistant.scoring import score


def case(case_id, message):
    original = next(c for c in ev.cases() if c["id"] == case_id)
    return {**original, "question": message}


@pytest.fixture
def test_process(monkeypatch):
    """Replace only the subprocess factory; use the production runner/lifecycle."""
    popen = subprocess.Popen

    def start(args, **kwargs):
        args = list(args)
        args[args.index("resourcing_assistant.api:create_app")] = (
            "tests.process_app:create_app"
        )
        kwargs["env"]["TEST_RUNTIME"] = kwargs["env"]["RUNTIME_DIR"]
        return popen(args, **kwargs)

    monkeypatch.setattr(ev.subprocess, "Popen", start)


@pytest.mark.parametrize(
    "case_id,message",
    [
        ("gq-09", "book"),
        ("own-09", "ambiguous"),
        ("own-10", "book8"),
        ("own-11", "book16"),
        ("own-12", "unsupported"),
    ],
)
def test_write_cases_through_runner(test_process, tmp_path, case_id, message):
    spec = case(case_id, message)
    answer, behavior, valid = ev.run_case(Settings(), spec, tmp_path)
    result = score(spec, answer, behavior=behavior, source_invariants=valid)
    assert result["score"] == 1, result
    assert result["status"] == ("review_required" if case_id == "own-12" else "passed")
    assert valid and all(behavior.values()), behavior
    assert (tmp_path / "proposal-or-answer.json").exists()
    if case_id == "gq-09":
        for artifact in (
            "decision-1.json",
            "reject/decision.json",
            "restart/restored-history.json",
            "restart/decision-2.json",
        ):
            assert (tmp_path / artifact).exists()
        for sub in (tmp_path, tmp_path / "reject", tmp_path / "restart"):
            expected = 0 if sub.name == "reject" else 1
            assert (
                ev.count(sub / "subject.sqlite")
                == ev.count(Settings().source) + expected
            )


def test_read_case_rejects_unexpected_soft_insert(test_process, tmp_path, monkeypatch):
    original = ev.request

    def inserted(client, path, body, **kwargs):
        answer = original(client, path, body, **kwargs)
        if path.endswith("/messages"):
            with connect(tmp_path / "subject.sqlite") as c:
                row = list(
                    c.execute(
                        "SELECT * FROM bookings WHERE kind='soft' LIMIT 1"
                    ).fetchone()
                )
                row[0] = c.execute("SELECT MAX(booking_id)+1 FROM bookings").fetchone()[
                    0
                ]
                c.execute(
                    f"INSERT INTO bookings VALUES({','.join('?' for _ in row)})", row
                )
                c.commit()
        return answer

    monkeypatch.setattr(ev, "request", inserted)
    answer, behavior, valid = ev.run_case(Settings(), case("own-01", "count"), tmp_path)
    assert behavior is None and not valid
    assert (
        score(case("own-01", "count"), answer, source_invariants=valid)["status"]
        == "failed"
    )
    assert not ev.invariants(Settings().source, tmp_path / "missing.sqlite")


@pytest.mark.parametrize("fault", ["proposal_dates", "restart_minutes"])
def test_runner_catches_wrong_proposal_or_restart_row(
    test_process, tmp_path, monkeypatch, fault
):
    original = ev.request

    def corrupted(client, path, body, **kwargs):
        answer = original(client, path, body, **kwargs)
        artifact = kwargs.get("artifact", Path())
        if fault == "proposal_dates" and path.endswith("/messages"):
            ev.confirmation(answer)["fields"]["start"] = "2026-03-01"
        if (
            fault == "restart_minutes"
            and path.endswith("/confirm")
            and artifact.parent.name == "restart"
        ):
            with connect(tmp_path / "restart/subject.sqlite") as c:
                c.execute(
                    "UPDATE bookings SET minutes=1 WHERE booking_id=?",
                    (ev.confirmation(answer)["booking_id"],),
                )
                c.commit()
        return answer

    monkeypatch.setattr(ev, "request", corrupted)
    spec = case("gq-09", "book")
    answer, behavior, valid = ev.run_case(Settings(), spec, tmp_path)
    assert not behavior[
        "exact_proposal" if fault == "proposal_dates" else "restart_succeeded"
    ]
    assert (
        score(spec, answer, behavior=behavior, source_invariants=valid)["status"]
        == "failed"
    )


def test_cli_reports_isolation_failure_and_manual_review(
    test_process, tmp_path, monkeypatch
):
    specs = [case("own-11", "book16"), case("gq-10", "unsupported")]
    monkeypatch.setattr(ev, "cases", lambda: specs)
    monkeypatch.setattr(
        ev.Settings,
        "from_env",
        lambda: Settings(endpoint="test-only", api_key="test-only"),
    )
    monkeypatch.setattr(sys, "argv", ["evaluation", "--output", str(tmp_path)])
    assert ev.main() == 2  # Provisional free-text result cannot produce a green run.
    report_path = next(tmp_path.glob("*/results.json"))
    report = json.loads(report_path.read_text())
    assert [r["status"] for r in report["results"]] == ["passed", "review_required"]
    assert (report_path.parent / "results.md").exists()
    assert (report_path.parent / "own-11-answer.json").exists()
    assert ev.count(report_path.parent / "gq-10/subject.sqlite") == ev.count(
        Settings().source
    )
    review = report_path.parent / "reviews.json"
    review.write_text(
        json.dumps(
            {
                "run_id": report["run_id"],
                "reviewer": "Test-only fixture review",
                "cases": {
                    "gq-10": {
                        "accepted": True,
                        "notes": "Explicit fixture refuses unsupported requests",
                    }
                },
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluation", "--review-report", str(report_path), "--reviews", str(review)],
    )
    assert ev.main() == 0
    assert json.loads(report_path.read_text())["results"][1]["reviews"]


def test_cli_missing_configuration_and_unknown_case(tmp_path, monkeypatch):
    monkeypatch.setattr(ev.Settings, "from_env", lambda: Settings())
    monkeypatch.setattr(sys, "argv", ["evaluation", "--output", str(tmp_path)])
    assert ev.main() == 2
    report = json.loads(next(tmp_path.glob("*/results.json")).read_text())
    assert len(report["results"]) == 22
    assert all(
        r["status"] == "not_run" and r["score"] is None for r in report["results"]
    )
    monkeypatch.setattr(sys, "argv", ["evaluation", "--case", "missing"])
    with pytest.raises(SystemExit) as error:
        ev.main()
    assert error.value.code == 2


def test_startup_failure_closes_process_log_and_client(tmp_path, monkeypatch):
    client = httpx.Client()
    monkeypatch.setattr(client, "get", lambda *a, **kw: httpx.Response(503))
    monkeypatch.setattr(ev.httpx, "Client", lambda **kw: client)
    logs = []

    def failed(*args, **kwargs):
        logs.append(kwargs["stdout"])
        return SimpleNamespace(poll=lambda: 1)

    monkeypatch.setattr(ev.subprocess, "Popen", failed)
    with pytest.raises(RuntimeError, match="process failed"):
        with ev.server(Settings(), tmp_path):
            pytest.fail("A failed process cannot become ready")
    assert client.is_closed and logs[0].closed


def test_case_failure_is_reported_and_does_not_stop_next_case(
    test_process, tmp_path, monkeypatch
):
    specs = [case("own-01", "fail"), case("own-11", "book16")]
    monkeypatch.setattr(ev, "cases", lambda: specs)
    monkeypatch.setattr(
        ev.Settings,
        "from_env",
        lambda: Settings(endpoint="test-only", api_key="test-only"),
    )
    monkeypatch.setattr(sys, "argv", ["evaluation", "--output", str(tmp_path)])
    assert ev.main() == 2
    report_path = next(tmp_path.glob("*/results.json"))
    report = json.loads(report_path.read_text())
    assert [r["status"] for r in report["results"]] == ["failed", "passed"]
    assert report["results"][0]["reason"] == "provider_unavailable"
    assert (report_path.parent / "own-01/proposal-or-answer.json").exists()
