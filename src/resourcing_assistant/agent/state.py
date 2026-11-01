"""Checkpoint-compatible graph state."""

from typing import TypedDict


class State(TypedDict, total=False):
    thread_id: str
    request_id: str
    text: str
    reference_date: str
    context: dict
    interpretation: dict
    active_task: dict
    summary: str
    summary_covered: int
    displayed_references: list
    read_results: list
    issues: list
    response: dict
    pending_action_id: str | None
