"""Validate durable task status against the plan; show a compact resume snapshot."""

import json
from datetime import datetime
from pathlib import Path
import re
import sys

STATUSES = {"not_started", "in_progress", "blocked", "done"}


def validate(state, plan):
    expected = re.findall(r"^- (T\d{2}\.\d+) ", plan, re.MULTILINE)
    tasks = state["tasks"]
    if state["schema_version"] != 1 or [t["id"] for t in tasks] != expected:
        raise ValueError("Task inventory must match implementation.md exactly")
    if datetime.fromisoformat(state["updated_at"]).utcoffset() is None:
        raise ValueError("updated_at must include a timezone")
    authorization = state["authorization"]
    if authorization["application_development"] not in {"authorized", "not_authorized"}:
        raise ValueError("Invalid application authorization status")
    if not authorization["evidence"].strip() or not state["next_action"].strip():
        raise ValueError(
            "Authorization evidence and a concrete next action are required"
        )
    active = []
    for task in tasks:
        if task["status"] not in STATUSES:
            raise ValueError(f"{task['id']}: invalid status")
        if not isinstance(task["evidence"], list) or any(
            not isinstance(item, str) or not item.strip() for item in task["evidence"]
        ):
            raise ValueError(f"{task['id']}: evidence must be nonblank strings")
        if task["status"] == "done" and not task["evidence"]:
            raise ValueError(f"{task['id']}: done requires evidence")
        if task["status"] == "blocked" and not (task["blocker"] or "").strip():
            raise ValueError(f"{task['id']}: blocked requires a reason")
        if task["status"] == "in_progress":
            active.append(task["id"])
        if task["status"] in {"in_progress", "done"} and not task["id"].startswith(
            "T01."
        ):
            if authorization["application_development"] != "authorized":
                raise ValueError(
                    "Application task started without recorded authorization"
                )
    if active != ([state["current_task"]] if state["current_task"] else []):
        raise ValueError(
            "current_task must identify the single in_progress task, or be null"
        )
    for check in state["last_checks"]:
        if check["result"] not in {"passed", "failed", "not_run"}:
            raise ValueError("Invalid check result")
        if not check["command"].strip() or not check["scope"].strip():
            raise ValueError("Each check needs command and scope")
    return tasks


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    try:
        state = json.loads((root / "docs/plans/progress.json").read_text())
        tasks = validate(state, (root / "docs/plans/implementation.md").read_text())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Invalid progress state: {error}", file=sys.stderr)
        return 1
    print(
        f"Application development: {state['authorization']['application_development']}"
    )
    print(f"Current task: {state['current_task'] or 'none'}")
    print(f"Next: {state['next_action']}")
    print(
        "Tasks: "
        + ", ".join(
            f"{status}={sum(t['status'] == status for t in tasks)}"
            for status in sorted(STATUSES)
        )
    )
    for task in tasks:
        if task["status"] in {"in_progress", "blocked"}:
            print(
                f"{task['id']}: {task['status']}"
                + (f" — {task['blocker']}" if task["blocker"] else "")
            )
    for blocker in state["blockers"]:
        print(f"Blocker ({blocker['scope']}): {blocker['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
