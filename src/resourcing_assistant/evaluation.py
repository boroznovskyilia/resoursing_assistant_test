"""Real-agent evaluation. Oracles are used only by this separate runner/scorer."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4
import httpx
from .config import Settings, ROOT, period
from .data import SUBJECT_TABLES, connect
from .scoring import score
from pydantic import BaseModel, ConfigDict, Field


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
        return True
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
    log = (runtime / "process.log").open("a")
    env = {
        **os.environ,
        "RUNTIME_DIR": str(runtime),
        "REFERENCE_DATE": "2026-04-01T00:00:00Z",
        "AZURE_ENDPOINT": settings.endpoint,
        "AZURE_API_KEY": settings.api_key,
        "AZURE_API_VERSION": settings.api_version,
        "CHAT_DEPLOYMENT": settings.chat_deployment,
        "EMBEDDING_DEPLOYMENT": settings.embedding_deployment,
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "resourcing_assistant.api:create_app",
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
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=900)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            if client.get("/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if process.poll() is not None:
            raise RuntimeError("Evaluation API process failed; see local process log")
        time.sleep(0.05)
    else:
        process.kill()
        process.wait()
        client.close()
        log.close()
        raise RuntimeError("Evaluation API did not start")
    try:
        yield client, process
    finally:
        client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.close()


def request(client, path, body):
    response = client.post(path, json=body)
    if response.status_code >= 400:
        raise RuntimeError(response.json().get("error", {}).get("code", "http_error"))
    return response.json()


def count(path):
    with connect(path, readonly=True) as c:
        return c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]


def run_case(settings, case, runtime):
    path = runtime / "subject.sqlite"
    with server(settings, runtime) as (client, process):
        thread = request(client, "/threads", {})["thread_id"]
        before = count(path)
        answer = request(
            client,
            f"/threads/{thread}/messages",
            {"request_id": uuid4().hex, "text": case["question"]},
        )
        cards = [b for b in answer["blocks"] if b["type"] == "confirmation"]
        behavior = None
        if case["type"] == "write":
            behavior = {"no_insert_before_confirmation": count(path) == before}
            if case["id"] == "own-09":
                behavior["ambiguous_person_clarified"] = not cards and {
                    r.get("person_id")
                    for b in answer["blocks"]
                    if b["type"] == "table"
                    for r in b["rows"]
                } == {78, 238}
            else:
                behavior["proposal_present"] = len(cards) == 1
                if not cards:
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
                    fields.get("person_id") == 1
                    and fields.get("engagement_id") == 1
                    and fields.get("hours") == expected_hours
                )
                decisions = case.get(
                    "decision_sequence", [case.get("decision", "confirm")]
                )
                results = [
                    request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": d},
                    )
                    for d in decisions
                ]
                if decisions[0] == "reject":
                    behavior["reject_zero_insert"] = count(path) == before
                else:
                    booking = results[0]["blocks"][0]["booking_id"]
                    with connect(path, readonly=True) as c:
                        row = dict(
                            c.execute(
                                "SELECT * FROM bookings WHERE booking_id=?", (booking,)
                            ).fetchone()
                        )
                    behavior["exact_confirmed_row"] = (
                        row["person_id"] == 1
                        and row["engagement_id"] == 1
                        and row["kind"] == "soft"
                        and row["status_id"] == 13
                        and row["minutes"] == expected_hours * 60
                        and row["start_ts"] == expected_start
                        and row["end_ts"] == expected_end
                        and count(path) == before + 1
                    )
                    behavior["repeat_receipt"] = all(
                        r["blocks"][0]["booking_id"] == booking for r in results
                    )
        if case["id"] == "own-12":
            behavior = {
                "no_source_changes": count(path) == before,
                "no_executable_action": not cards,
                "refusal_visible": any(b["type"] == "text" for b in answer["blocks"]),
            }
    valid = invariants(settings.source, path)
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
                )
                cards = [b for b in proposed["blocks"] if b["type"] == "confirmation"]
                if len(cards) != 1:
                    behavior[mode + "_succeeded"] = False
                    continue
                action = cards[0]["action_id"]
                behavior[mode + "_no_prewrite"] = count(subpath) == before
                if mode == "reject":
                    result = request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": "reject"},
                    )
                    behavior["reject_succeeded"] = (
                        result["blocks"][0]["status"] == "rejected"
                        and count(subpath) == before
                    )
                else:
                    process.kill()
                    process.wait()
            if mode == "restart":
                with server(settings, sub) as (client, _):
                    restored = client.get(f"/threads/{thread}").json()
                    result = request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": "confirm"},
                    )
                    repeated = request(
                        client,
                        f"/threads/{thread}/confirm",
                        {"action_id": action, "decision": "confirm"},
                    )
                    behavior["restart_succeeded"] = (
                        restored["pending_action"]["action_id"] == action
                        and result["blocks"][0]["booking_id"]
                        == repeated["blocks"][0]["booking_id"]
                        and count(subpath) == before + 1
                    )
            valid = valid and invariants(settings.source, subpath)
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
                "at": datetime.now(timezone.utc).isoformat(),
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
    parser.add_argument("--review-report", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--case", action="append", dest="selected")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/evaluation")
    args = parser.parse_args()
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
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:6]
    )
    output = args.output / run_id
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": run_id,
        "source_sha256": hashlib.sha256(settings.source.read_bytes()).hexdigest(),
        "reference_date": "2026-04-01T00:00:00Z",
        "chat_deployment": settings.chat_deployment,
        "embedding_deployment": settings.embedding_deployment,
        "results": [],
    }
    for case in selected:
        start = time.monotonic()
        if not settings.endpoint or not settings.api_key:
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
