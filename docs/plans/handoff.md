# Resume after compact or a new session

## Current authority and entry point

Owner explicitly authorized **full end-to-end implementation** on2026-10-31, in the
scope-question reply. Do not stop at planning/status tooling or ask again to begin.
Publishing/deployment/sharing/sending remain separate. Discuss in Russian; all project
content is English. Exact Git repository name: `resoursing_assistant_test`.

1. Read [AGENTS.md](../../AGENTS.md), then [progress.json](progress.json).
2. Run `make progress` and `git status --short` in the repository. Inspect current task,
   next action, blockers/checks and actual files before resuming unfinished work.
3. Read only that task's [plan section](implementation.md) and relevant [contracts](../specs/README.md).
   [README](../../README.md) contains actual commands; [verification](../development/verification.md)
   distinguishes deterministic tests from actual Azure run and review evidence.
4. Continue independently eligible work. A newer owner instruction overrides an old
   saved gate; record it accurately. Never reset/delete uncommitted work or replay a
   completed booking because chat context is missing.

## Durable status protocol

progress.json is the single live status/evidence record; the plan owns task meanings,
dependencies and acceptance. Update current_task, next_action, updated_at, blockers,
checks and per-task status/evidence after meaningful boundaries and before compaction.
Use not_started/in_progress/blocked/done; done requires evidence and blocked a reason.
Write complete JSON via temporary file+atomic replace, then `make progress`. Do not
copy live statuses into multiple documents or mark unrun checks passed. No secrets,
raw prompts, full environment dumps or source text in status/ordinary logs.

`make check` validates IDs/status/gate/evidence against all62 plan tasks and runs tooling
tests. A fresh-process test proves saved status recovery and corrupt-state rejection.
No scheduler, daemon or external service is used. This is development progress memory,
separate from the product's LangGraph conversation state.

## Implementation orientation

- Owner approved all backend structure review items on2026-11-01 with synchronous
  SQLAlchemy. WP-14/progress.json track the current refactor; earlier22-case evidence
  remains historical until a new run is verified. Do not stop after a subset of items.
- Backend packages: api, agent, llm, services, db, domain, evaluation. app.create_service
  composes repositories/model clients/graph dependencies; app.create_app is the API
  factory. Config uses pydantic-settings/SecretStr. Native protected reader and saver
  remain; owned ORM schema matches saved files. No old Store compatibility facade.
- React/TypeScript/Vite UI and real-browser tests in frontend. Explicit fake providers
  live only in tests; production has no fake-provider switch.
- Source mock and tokenizer bundled under data; original input remains unchanged.
  .env/runtime/cache files ignored. Source/checkpoint/history/actions are durable.
- No Store, tenants/auth, streaming, hosted vector/alerting service or optimizer. Read-only
  generated SQL and fixed confirmed soft-booking writer, immutable action+receipt.
- Locked Python3.12/uv and Node26/npm. Model settings/reference date in .env.example;
  assignment/eval April1 2026, audit actual UTC, unset reference UTC-now.
- Azure access is configured in ignored0600 .env; genuine DSPy chat and1536-dimensional
  embedding smoke passed. No credential blocker remains. Actual evaluation is a sequence
  of retained failing development runs followed by complete reruns after fixes; inspect
  progress.json for the current run/task. Never stitch best case results, weaken scores,
  load expected answers/SQL into runtime or label AI-assisted review as independent human.
- Query parameters use a required typed Binding list (DSPy closes arbitrary dictionaries);
  ReadPlan has primary answer plus up to3 complete additional_answers. Source schema and
  catalogue vocabulary go to interpretation/planning. Semantic eligibility is narrow;
  simple exact pools are compiled, complex filters retain guarded generated SQL. Projects
  use PlanProjectChecks, deduplicated source-field assessment and deterministic parent joins.
- Evaluation-only read plans are in runtime/read-plans/thread/request/attempt-uuid.json;
  inspect actual failed queries rather than blindly reproducing model calls. Original
  source/gold hashes must remain unchanged. Ordinary logs omit prompts and credentials.
- Source obligations, accepted choices and88 scenario inventory are in specs/decisions.

## Current refactor completion

WP-14 is complete on runtime23487e3. All requested review items are implemented:
validated pydantic-settings, sync ORM/Core repositories, separated schemas/composition,
context/read policies, injected RAG dependencies and batched equivalent documents.
Two genuine-run defects were fixed with regressions: epoch-derived booked hours and
ranker prose replacing source explanations. Final103 backend,5 Chromium,9 tooling
checks passed; fresh-clone setup/build and existing-runtime compatibility passed.
New full Azure run20261101T190046Z_a1cdc9:15 automatic passes plus7 explicitly recorded
AI-assisted source reviews =>22/22. [Evidence](../evaluation/backend-refactor-20261101/README.md).
Both prior failed/rejected runs are preserved; no stitching or independent human review.
Actual API process/session IDs remain only in progress.json. No evaluation is active.

T13.4 demo was completed on 2 November 2026. Genuine Azure/browser capture shows factual
SQL, semantic recommendations, actual API stop/start before Confirm, receipt/history
reload and Reject. Local2m35s MP4 and continuous4m54s WebM/evidence are under
`.runtime/demo/20261102/`; the versioned [transcript](../development/demo-transcript.md)
records checks. Only semantic waiting is explicitly accelerated8x. The isolated demo
API was stopped; main saved chats/source were untouched. No upload/sharing/submission.

## Previous release evaluation evidence

The previous release QA was completed before the owner-approved WP-14 refactor. Start with [evaluation evidence](../evaluation/README.md),
not the old failing baseline: one genuine full22-case inference run, unchanged answer
artifacts, corrected whole-run offline scoring and7 explicit AI-assisted source reviews.
This is not independent human or held-out validation. The initial report and20 original
run reports remain available; final report/answer/scorer hashes were verified. All92
backend and5 browser checks passed from the actual local Git-clone rehearsal.

`progress.json` owns current validation progress, active evaluation and service IDs;
remote publication/video sharing/submission remain unfinished. Do not rerun paid
models just to restore missing chat context or replay a confirmed booking.

## Host and recovery notes

Work directory is `/Users/iliab/projects/test_ai_assist/resoursing_assistant_test`; parent
workspace has a short AGENTS entry point. Use project commands with correct workdir.
In restricted tools set UV_CACHE_DIR=/private/tmp/resourcing-uv-cache for existing
cached packages; Make otherwise uses writable .cache/uv. Chromium installed at
/private/tmp/resourcing-browsers; set PLAYWRIGHT_BROWSERS_PATH for this host.
Local HTTP ports/browser launches and downloads need tool sandbox escalation; auto-review
has allowed them. No approval-review rejection occurred. Production API/UI may be running at127.0.0.1:8000;
verify the exact PID/command/health before restarting and preserve its existing.runtime.
Current process IDs and sessions belong only in progress.json. No background goal,
automation or subagent exists. Real Azure evaluation calls are authorized; no publication,
external message or remote sharing has occurred. Credentials must never appear in reports.

The latest actual checks and local Git commits are in progress.json/Git. Do not rerun
past installation steps without cause. No tool exposed here forces Codex compaction;
do not claim it happened. Where available `/compact` is an app command:
[official documentation](https://learn.chatgpt.com/docs/developer-commands).
Continuation relies on these files, so it works even with no earlier chat history.
