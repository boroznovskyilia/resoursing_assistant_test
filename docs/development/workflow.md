# Task workflow

## Current gate

Full end-to-end implementation was explicitly authorized on 2026-10-31. Read
[handoff](../plans/handoff.md), run `make progress` and inspect current task/evidence
in [progress.json](../plans/progress.json) before continuing. Update status and next
action after each meaningful boundary; never depend on chat context alone.

## After development authorization

Run `make docs`, read the next eligible work package and relevant primary contracts.
Inspect existing code/callers/checks before changing it. Use the dependency order:
agent and safe data/state first, API second, UI third. Build checks with each feature.

For nontrivial behavior define concrete observable examples, implement the smallest
complete change, run focused checks and fix failures. Record actual commands/results
and update affected contracts/scenarios if behavior legitimately changes. Do not edit
expected behavior merely because the implementation fails it. A routine technical
choice does not need another owner approval; a change to agreed scope/semantics does.

Each task reaches callers, configuration, rendering and tests affected by its behavior.
Use existing helpers/standard library before adding abstractions or dependencies.
Follow one retry policy and one fixed writer rather than parallel implementations.

## Verification and progress

Run `make check`, `git diff --check` and relevant existing application checks. Link real
test files/commands once they exist. Separate deterministic/double-backed behavior,
real SQLite/API/process/UI proof and actual Azure quality. Never call a source oracle
or scripted model result a successful real-agent evaluation.

Update package status with evidence, then continue to the next eligible task without
another routine permission request. Missing credentials do not block unrelated local
work. Preserve review_required scores and explicit external blockers. Do not mark the
whole project complete while mandatory checks are unavailable or safety failures remain.

Keep documents English, communicate with owner in Russian, and maintain concise progress
updates. Publishing, deployment and sending submission messages need applicable owner
authorization; prepare reviewable artifacts before that boundary.
