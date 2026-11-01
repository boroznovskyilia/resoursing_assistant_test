"""Real-agent evaluation. Oracles are used only by this separate runner/scorer."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from resourcing_assistant.config import ROOT, Settings
from resourcing_assistant.db.reader import SUBJECT_TABLES
from resourcing_assistant.db.session import connect
from resourcing_assistant.domain.calculations import period
from resourcing_assistant.evaluation.scoring import score


def cases():
    reference = ROOT / "docs/reference"
    return (
        json.loads((reference / "gold_questions.json").read_text())["questions"]
        + json.loads((reference / "additional-cases-draft.json").read_text())[
            "questions"
        ]
    )


def invariants(source, working):
    if not working.exists():
        return False
    with (
        connect(source, readonly=True) as original,
        connect(working, readonly=True) as actual,
    ):
        for table in SUBJECT_TABLES | {"person_avatars"}:
            old = [
                tuple(r)
                for r in original.execute(f'SELECT * FROM "{table}" ORDER BY 1')
            ]
            new = [
                tuple(r) for r in actual.execute(f'SELECT * FROM "{table}" ORDER BY 1')
            ]
            if table == "bookings":
                if new[: len(old)] != old:
                    return False
                if any(row[6] != "soft" for row in new[len(old) :]):
                    return False
            elif new != old:
                return False
    return True


@contextmanager
def server(settings, runtime):
    runtime.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {
        **os.environ,
        "RUNTIME_DIR": str(runtime),
        "REFERENCE_DATE": "2026-04-01T00:00:00Z",
        "AZURE_ENDPOINT": settings.endpoint,
        "AZURE_API_KEY": settings.api_key.get_secret_value(),
        "AZURE_API_VERSION": settings.api_version,
        "CHAT_DEPLOYMENT": settings.chat_deployment,
        "EMBEDDING_DEPLOYMENT": settings.embedding_deployment,
        "RESOURCING_EVAL_ARTIFACTS": "1",
    }
    with (runtime / "process.log").open("a") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "resourcing_assistant.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=900
            ) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    try:
                        if client.get("/health", timeout=0.5).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Evaluation API process failed; see local process log"
                        )
                    time.sleep(0.05)
                else:
                    raise RuntimeError("Evaluation API did not start")
                yield client, process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def request(client, path, body, *, artifact=None):
    response = client.post(path, json=body)
    payload = response.json()
    if artifact:
        artifact.write_text(json.dumps(payload, indent=2))
    if response.status_code >= 400:
        raise RuntimeError(payload.get("error", {}).get("code", "http_error"))
    return payload


def count(path):
    with connect(path, readonly=True) as c:
        return c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]


def confirmation(answer):
    cards = [b for b in answer["blocks"] if b["type"] == "confirmation"]
    return cards[0] if len(cards) == 1 else {}


def exact_booking(path, booking_id, hours, start, end):
    with connect(path, readonly=True) as c:
        row = c.execute(
            "SELECT person_id,engagement_id,kind,status_id,minutes,start_ts,end_ts FROM bookings WHERE booking_id=?",
            (booking_id,),
        ).fetchone()
    return row is not None and tuple(row) == (1, 1, "soft", 13, hours * 60, start, end)


def run_case(settings, case, runtime):
    path = runtime / "subject.sqlite"
    inserted = 0
    with server(settings, runtime) as (client, process):
        thread = request(client, "/threads", {})["thread_id"]
        before = count(path)
        answer = request(
            client,
            f"/threads/{thread}/messages",
            {"request_id": uuid4().hex, "text": case["question"]},
            artifact=runtime / "proposal-or-answer.json",
        )
        cards = [b for b in answer["blocks"] if b["type"] == "confirmation"]
        behavior = None
        if case["type"] == "write":
            behavior = {
                "no_insert_before_confirmation": count(path) == before
                and invariants(settings.source, path)
            }
            if case["id"] == "own-09":
                behavior["ambiguous_person_clarified"] = not cards and {
                    r.get("person_id")
                    for b in answer["blocks"]
                    if b["type"] == "table"
                    for r in b["rows"]
                } == {78, 238}
            else:
                behavior["proposal_present"] = len(cards) == 1
                if len(cards) != 1:
                    return answer, behavior, invariants(settings.source, path)
                card = cards[0]
                fields = card["fields"]
                action = card["action_id"]
                expected_hours = (
                    40
                    if case["id"] == "gq-09"
                    else (8 if case["id"] == "own-10" else 16)
                )
                expected_start, expected_end = (
                    period("2026-04-01", "2026-04-30")
                    if case["id"] == "gq-09"
                    else period("2026-04-02", "2026-04-02")
                    if case["id"] == "own-10"
                    else period("2026-05-04", "2026-05-05")
                )
                behavior["exact_proposal"] = (
                    card["status"] == "pending"
                    and fields.get("person_id") == 1
                    and fields.get("person") == "Amanda Evans"
                    and fields.get("engagement_id") == 1
                    and fields.get("engagement") == "ENG-2026-0001"
                    and fields.get("hours") == expected_hours
                    and fields.get("minutes") == expected_hours * 60
                    and fields.get("kind") == "soft"
                    and fields.get("start")
                    == datetime.fromtimestamp(expected_start, UTC).date().isoformat()
                    and fields.get("end_exclusive")
                    == datetime.fromtimestamp(expected_end, UTC).date().isoformat()
                    and fields.get("end_inclusive")
                    == datetime.fromtimestamp(expected_end - 86400, UTC)
                    .date()
                    .isoformat()
                )
                decisions = case.get(
                    "decision_sequence", [case.get("decision", "confirm")]
                )
                results = [
                    request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": d},
                        artifact=runtime / f"decision-{i + 1}.json",
                    )
                    for i, d in enumerate(decisions)
                ]
                behavior["decision_receipts"] = all(
                    r.get("request_status") == "completed"
                    and confirmation(r).get("action_id") == action
                    and confirmation(r).get("status")
                    == ("confirmed" if d == "confirm" else "rejected")
                    for r, d in zip(results, decisions)
                )
                if decisions[0] == "reject":
                    behavior["reject_zero_insert"] = count(path) == before
                else:
                    inserted = 1
                    booking = confirmation(results[0]).get("booking_id")
                    behavior["exact_confirmed_row"] = (
                        exact_booking(
                            path, booking, expected_hours, expected_start, expected_end
                        )
                        and count(path) == before + 1
                    )
                    behavior["repeat_receipt"] = all(
                        booking is not None
                        and confirmation(r).get("booking_id") == booking
                        for r in results
                    )
        if case["id"] == "own-12":
            behavior = {
                "no_source_changes": count(path) == before,
                "no_executable_action": not cards,
                "refusal_visible": any(b["type"] == "text" for b in answer["blocks"]),
            }
    valid = invariants(settings.source, path) and count(path) == before + inserted
    if case["id"] == "gq-09":
        # Separate isolated Reject and genuine process-restart subcases.
        for mode in ("reject", "restart"):
            sub = runtime / mode
            subpath = sub / "subject.sqlite"
            with server(settings, sub) as (client, process):
                thread = request(client, "/threads", {})["thread_id"]
                before = count(subpath)
                proposed = request(
                    client,
                    f"/threads/{thread}/messages",
                    {"request_id": uuid4().hex, "text": case["question"]},
                    artifact=sub / "proposal.json",
                )
                cards = [b for b in proposed["blocks"] if b["type"] == "confirmation"]
                if len(cards) != 1:
                    behavior[mode + "_succeeded"] = False
                    continue
                action = cards[0]["action_id"]
                behavior[mode + "_no_prewrite"] = count(
                    subpath
                ) == before and invariants(settings.source, subpath)
                if mode == "reject":
                    result = request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": "reject"},
                        artifact=sub / "decision.json",
                    )
                    behavior["reject_succeeded"] = (
                        confirmation(result).get("status") == "rejected"
                        and confirmation(result).get("action_id") == action
                        and count(subpath) == before
                    )
                else:
                    process.kill()
                    process.wait()
            if mode == "restart":
                with server(settings, sub) as (client, _):
                    restored = client.get(f"/threads/{thread}").json()
                    (sub / "restored-history.json").write_text(
                        json.dumps(restored, indent=2)
                    )
                    result = request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": "confirm"},
                        artifact=sub / "decision-1.json",
                    )
                    repeated = request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": "confirm"},
                        artifact=sub / "decision-2.json",
                    )
                    first, second = confirmation(result), confirmation(repeated)
                    behavior["restart_succeeded"] = (
                        restored["pending_action"]["action_id"] == action
                        and first.get("status") == second.get("status") == "confirmed"
                        and first.get("action_id") == second.get("action_id") == action
                        and first.get("booking_id") == second.get("booking_id")
                        and exact_booking(
                            subpath,
                            first.get("booking_id"),
                            40,
                            *period("2026-04-01", "2026-04-30"),
                        )
                        and count(subpath) == before + 1
                    )
            valid = (
                valid
                and invariants(settings.source, subpath)
                and count(subpath) == before + (mode == "restart")
            )
    return answer, behavior, valid


def markdown(report):
    lines = [
        "# Evaluation results",
        "",
        f"Run: {report['run_id']} · source SHA-256: {report['source_sha256']}",
        "",
        "| Case | Type | Score | Status | Review | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["results"]:
        lines.append(
            f"| {row['id']} | {row['type']} | {row.get('score') if row.get('score') is not None else '—'} | {row['status']} | {row.get('review_status', 'not_run')} | {row['reason'].replace('|', '/')} |"
        )
    lines += [
        "",
        "Scores are from delivered values and database effects. Free-text cases require",
        "recorded manual review before final acceptance. Missing credentials are not a pass.",
        "",
    ]
    return "\n".join(lines)


class ManualDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    accepted: bool
    notes: str = Field(min_length=1)


class ManualReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str
    reviewer: str = Field(min_length=1)
    cases: dict[str, ManualDecision]


def apply_review(report, review):
    if report["run_id"] != review.run_id:
        raise ValueError("Review belongs to another run")
    available = {r["id"]: r for r in report["results"]}
    if set(review.cases) - set(available):
        raise ValueError("Review names an unknown case")
    for key, decision in review.cases.items():
        row = available[key]
        if row.get("review_status") not in ("review_required", "approved", "rejected"):
            raise ValueError("Case is not eligible for free-text review")
        row.setdefault("reviews", []).append(
            {
                "reviewer": review.reviewer,
                "accepted": decision.accepted,
                "notes": decision.notes,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        row["review_status"] = "approved" if decision.accepted else "rejected"
        checks = row["contract_checks"]
        if "manual_weather_refusal_review" in checks:
            checks["manual_weather_refusal_review"] = decision.accepted
        row["status"] = (
            "passed"
            if decision.accepted
            and row["score"] == 1
            and all(v is True for v in checks.values())
            else "failed"
        )
        row["reason"] = "Manual review: " + decision.notes
    return report


def rescore_saved(report, directory):
    """Recompute every available answer; retain recorded external write/source observations."""
    specs = {c["id"]: c for c in cases()}
    for row in report["results"]:
        path = directory / f"{row['id']}-answer.json"
        if not path.exists():
            continue  # A missing/failed inference cannot become a fabricated answer.
        spec = specs[row["id"]]
        checks = row.get("contract_checks", {})
        behavior = None
        if spec["type"] == "write" or row["id"] == "own-12":
            behavior = {
                k: v
                for k, v in checks.items()
                if k not in {"source_invariants", "response_complete", "executed_sql"}
            }
        fresh = score(
            spec,
            json.loads(path.read_text()),
            behavior=behavior,
            source_invariants=checks.get("source_invariants") is True,
        )
        row.pop("reviews", None)
        row.update(fresh)
    return report


def usage_stats(path):
    total = {
        "chat_attempts": 0,
        "embedding_attempts": 0,
        "chat_tokens": None,
        "embedding_tokens": None,
    }
    for log in path.rglob("assistant.log"):
        for line in log.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") != "request_finished":
                continue
            for key in total:
                if key in event:
                    total[key] = (total[key] or 0) + event[key]
    return total


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--review-report", type=Path)
    modes.add_argument("--rescore-report", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--case", action="append", dest="selected")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/evaluation")
    args = parser.parse_args()
    if args.rescore_report:
        if args.reviews:
            parser.error("--reviews requires --review-report")
        original = args.rescore_report.read_bytes()
        report = rescore_saved(json.loads(original), args.rescore_report.parent)
        report["rescoring"] = {
            "original_report_sha256": hashlib.sha256(original).hexdigest(),
            "scorer_sha256": hashlib.sha256(
                (ROOT / "src/resourcing_assistant/evaluation/scoring.py").read_bytes()
            ).hexdigest(),
            "at": datetime.now(UTC).isoformat(),
            "method": "All saved answers from this run, unchanged. Recorded source/write observations retained; no inference or write replay. Free-text reviews reset to required.",
            "answer_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(args.rescore_report.parent.glob("*-answer.json"))
            },
        }
        output = args.rescore_report.with_name("rescored-" + args.rescore_report.name)
        output.write_text(json.dumps(report, indent=2))
        output.with_suffix(".md").write_text(markdown(report))
        print("Rescored report:", output)
        return 0 if all(r["status"] == "passed" for r in report["results"]) else 2
    if args.review_report:
        if not args.reviews:
            parser.error("--review-report requires --reviews")
        report = json.loads(args.review_report.read_text())
        review = ManualReview.model_validate_json(args.reviews.read_text())
        apply_review(report, review)
        args.review_report.write_text(json.dumps(report, indent=2))
        args.review_report.with_suffix(".md").write_text(markdown(report))
        return 0 if all(r["status"] == "passed" for r in report["results"]) else 2
    if args.reviews:
        parser.error("--reviews requires --review-report")
    settings = Settings.from_env()
    all_cases = cases()
    selected = [q for q in all_cases if not args.selected or q["id"] in args.selected]
    if args.selected and set(args.selected) - {q["id"] for q in selected}:
        parser.error("Unknown case ID")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:6]
    output = args.output / run_id
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "source_sha256": hashlib.sha256(settings.source.read_bytes()).hexdigest(),
        "reference_date": "2026-04-01T00:00:00Z",
        "api_version": settings.api_version,
        "chat_deployment": settings.chat_deployment,
        "embedding_deployment": settings.embedding_deployment,
        "results": [],
    }
    for case in selected:
        start = time.monotonic()
        if not settings.azure_configured:
            result = {
                "score": None,
                "status": "not_run",
                "review_status": "not_run",
                "contract_checks": {},
                "reason": "Azure endpoint/key not configured",
            }
        else:
            try:
                answer, behavior, valid = run_case(settings, case, output / case["id"])
                (output / f"{case['id']}-answer.json").write_text(
                    json.dumps(answer, indent=2)
                )
                result = score(case, answer, behavior=behavior, source_invariants=valid)
            except Exception as error:
                result = {
                    "score": 0,
                    "status": "failed",
                    "review_status": "not_run",
                    "contract_checks": {},
                    "reason": str(error)
                    if isinstance(error, RuntimeError)
                    else type(error).__name__,
                }
        report["results"].append(
            {
                "id": case["id"],
                "type": case["type"],
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "usage": usage_stats(output / case["id"])
                if (output / case["id"]).exists()
                else None,
                **result,
            }
        )
        print(case["id"], result["status"], result["reason"])
    (output / "results.json").write_text(json.dumps(report, indent=2))
    (output / "results.md").write_text(markdown(report))
    print("Report:", output / "results.md")
    return 0 if all(r["status"] == "passed" for r in report["results"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
