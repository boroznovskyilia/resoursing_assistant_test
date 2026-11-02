# Resume after compact or a new session

## Recovery order

1. Read [AGENTS.md](../../AGENTS.md) for project rules and applicable authorization.
   Run `make docs`, `make progress` and `git status --short` in the repository.
2. Inspect [progress.json](progress.json): current_task, next_action, pending blockers,
   per-task evidence and last_checks. Compare them with the actual diff/files before
   choosing work; an interruption may have left changes not reflected in saved status.
3. Read only the relevant [plan section](implementation.md), [contracts](../specs/README.md)
   and existing code/checks. Use [README](../../README.md) for commands and
   [verification](../development/verification.md) for evidence layers and limits.
4. If conditions changed or records disagree, initiate the
   [change/conflict procedure](../development/workflow.md#changes-and-contradictions).
   Preserve uncommitted work. Recover the intended next step without deleting files,
   rerunning paid inference just to restore context or replaying a completed booking.
5. Continue independently eligible work. A pending owner decision blocks only dependent
   changes. An explicit owner instruction resolving the issue needs no repeat approval;
   unresolved requirement meaning follows the workflow's HITL boundary.

## Durable state

The [document ownership map](../document_writing.md#document-ownership) identifies
primary sources. The plan defines work; progress.json owns live status, pending
questions, evidence references and the next action. The
[workflow](../development/workflow.md#evidence-and-continuity) defines atomic saves,
status transitions and evidence reassessment. Update it after meaningful boundaries
and before handoff; `make progress` must accept the saved state.

Keep current process/session IDs and service state only in progress.json; verify the
actual process/health before acting on them. Historical model runs, reviews and failures
are linked from [evaluation](../evaluation/README.md); delivery artifacts and checks
are in [submission](../development/submission.md). Neither a saved pass nor an old
completion proves acceptance for a changed contract. Do not copy old run reviews.

## Implementation and host precautions

- Workdir: `/Users/iliab/projects/resoursing_assistant_test`. Preserve local/remote
  `master`; use AGENTS.md for authorization and progress.json for outstanding work.
- Use the [architecture](../architecture/overview.md#backend-module-boundaries) for
  module boundaries. Explicit test providers live only in tests; production has no
  fake-provider switch. Existing SQLite chats, checkpoints and booking receipts must
  survive restart; never reset them to simplify recovery.
- Source fixtures and tokenizer are bundled under data. Preserve original source/gold
  artifacts; model prompts must not receive evaluation expectations or reference SQL.
  Credentials and runtime files are ignored; never expose them in reports.
- For a failed evaluation, inspect its saved responses and evaluation-only read plans
  under the case runtime's `read-plans/` before repeating model calls.
- In this restricted host, cached packages can use
  `UV_CACHE_DIR=/private/tmp/resourcing-uv-cache`; Chromium is installed at
  `/private/tmp/resourcing-browsers` via PLAYWRIGHT_BROWSERS_PATH. Inspect availability
  before reinstalling. Ports/browser launches/downloads may need sandbox escalation.
- Before restarting a local service, verify its command, PID and runtime directory.
  Preserve the existing runtime. Health/history reads must not invoke paid models.

These files support resumption when an agent is started; they do not start a new
session or background job. Fresh-process tooling tests prove saved JSON loading and
corruption rejection, not reliable agent recovery after actual context loss. Reconcile
observed state and save a concrete next action rather than assuming a compact succeeded.
