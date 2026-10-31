# Verification and evidence limits

Updated 2026-10-31. Application implementation is authorized and present. This document
separates executed deterministic checks, genuine model runs, explicit source review
and remaining evidence limits.
Current task statuses: [progress.json](../plans/progress.json).

## Executable commands

```sh
make setup
make check
make test
npm --prefix frontend run build
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run test:e2e
make evaluate
```

Setup installs locked dependencies, preserves existing .env/runtime and builds the UI.
`make check` runs9 repository-tooling tests, Markdown links and progress inventory.
`make test` runs pytest, including actual HTTP subprocess kill/restart tests. Browser
checks require the built UI, Chromium and localhost8017. In the restricted Codex host,
ports/browser launch and dependency downloads require allowed sandbox escalation;
normal local terminals do not have that sandbox restriction. Its installed browser
path is `/private/tmp/resourcing-browsers` via PLAYWRIGHT_BROWSERS_PATH.

## Current evidence

- Runtime checkpoint `ae6e196` was checked in a genuine local Git clone at
  `/private/tmp/resourcing-final-rehearsal.AuHpxg`, initially without .env/dependencies/runtime.
  Locked setup, idempotent setup and TypeScript/Vite build passed; no model calls in setup.
- The complete backend suite passed 92 tests, including real API subprocess restart,
  all five evaluation write branches, source invariants, receipt replay, bounded repairs,
  context/compaction, DSPy structured-output bindings, semantic field joins and review gates.
- All five actual Chromium API/UI scenarios passed: facts/SQL/reload, pending reads/Confirm,
  lost-response identity, Reject/mobile/untrusted markup and terminal-error retry.
  Browser/backend doubles are explicit test-only providers, not actual-model accuracy.
- Nine repository-tooling tests, links/progress validation, Ruff checks/format and
  whitespace checks passed. Desktop/mobile screenshots were inspected previously.
- Genuine Azure DSPy chat and 1536-dimensional embedding smoke passed. Complete real
  run `20261031T211131Z_822c63` passed all 22 cases after seven explicit **AI-assisted** source
  reviews; before review 15 passed and seven required review. See [full answers,
  reports, measurements and all-run history](../evaluation/README.md). This is one
  known development/acceptance set, not independent human or held-out validation.
  Inference used runtime `ae6e196`; scorer `ebd3f14` regraded every saved answer after
  a name-alias correction, retaining recorded source/write observations and original report.
- Genuine booking evaluation checks pre-confirm no-write, exact visible/persisted terms,
  Confirm, Reject, actual process restart and repeat Confirm. All 24 original source
  tables are compared; read/ambiguity/Reject permit no appended bookings.
- All four supplied-file hashes match the originals in Downloads. Configured Azure key
  was absent from Git history blobs and all documentation; .env is ignored, mode 0600.
  Final state checks are recorded in progress.json. No live quota exhaustion was observed.

These are checkpoint-specific observations, not proof about future edits or arbitrary
questions. Timing/token/recall/storage methodology and actual counts are exported in
[measurements](../evaluation/measurements.json); Azure billed cost is unknown.

## Check-to-scenario map

| Check file | Main coverage | Remaining boundary |
| --- | --- | --- |
| [Data](../../tests/test_data.py) | S-003/006/012/023–S-029/081: conversions/capacity, COUNT/CTE, permissions, time/row/byte limits, huge scalar, pages, source copy | General model join correctness requires actual eval |
| [Store](../../tests/test_storage.py) | S-037–S-043/046/047/083/087: no prewrite, exact fields, Reject, repeat/racing Confirm, supersede, request IDs, persisted state | Real interpretation quality separate |
| [Setup](../../tests/test_setup.py) | Private/exclusive env creation and preservation of credentials/source state | Genuine smoke and evaluation checked separately |
| [LM](../../tests/test_llm.py) | S-022/074/077: retry boundaries, no-config, actual DSPy adapter typed repair and input budget | Actual deployment checked separately; outages are injected |
| [Graph](../../tests/test_agent.py) | S-013/015/016/018/034/035/086: source factual/semantic transitions, ambiguity, pending reads, checkpoint reopen, partial explanation | Uses named scripted provider, not real model |
| [API](../../tests/test_api.py) | S-050–S-056/061/082/083: typed routes/errors, request/action replay, unknown fields, busy/other thread | Browser/restart checked separately |
| [Processes](../../tests/test_process.py) | S-041/055/084/085: actual kill/restart, no inference on GET, explicit Continue | Test-only model factory; no quality claim |
| [Semantics](../../tests/test_semantic.py) | S-033/034/036/079/080: memberships, reuse, fallback full scan, uncertainty, fabricated quote rejection, genuine-success recovery | One public strong-match recall measurement; unseen recall unverified |
| [Faults](../../tests/test_faults.py) | S-017/018/024/028/044/073/078/079/088: shared repair, source invariants, compaction, logs, lost commit ack/checkpoint lag | Not every possible OS/storage failure injected |
| [Scoring](../../tests/test_scoring.py) | S-068–S-070/072: tolerances, order, partial credit, absent total, review-required and run-bound manual review | Seven wording/source reviews are AI-assisted, not independent human |
| [Evaluation runner](../../tests/test_evaluation.py) | S-070–S-074: five write-case branches through actual API subprocesses, restart receipts/exact terms, read-only source changes, startup cleanup, reports/review exit codes and failure continuation | Explicit test-only model; no Azure accuracy claim |
| [Browser](../../frontend/e2e/chat.spec.ts) | S-059–S-064: rendering/history, pending/decision flow, network retry, mobile/markup | One Chromium engine; not universal accessibility certification |
| [Continuity tooling](../../scripts/test_check_progress.py) | Fresh-process status restore, invalid state rejection, inventory/gate/evidence checks | Does not trigger Codex compact or prove app behavior |

The88 scenario IDs remain a written acceptance inventory. A mapped scenario can have
uncovered variants; this table is not proof that every scenario/variant passed. No
hidden test-double results appear in real-model score tables.

## Live evaluation and review

The runner in [evaluation.py](../../src/resourcing_assistant/evaluation.py) starts actual
API subprocesses with isolated source/app files; gq-09 has separate Confirm/Reject and
restart subcases. It checks delivered blocks and database invariants. Reports include
settings, hashes, timing, attempts/tokens where available and review status. Score0.5
is partial_credit, not a full pass. Exit2 also covers not_run/review-required results.
Each case retains step responses, decisions and restart history, including failed HTTP
responses. Read-only/ambiguity/Reject cases allow no source inserts; confirmed and
restarted bookings must match exact terms. Scorers reject contradictory aggregate
rows and missing keyed results that would otherwise look like valid empty sets.

Free-text review can be applied only to a matching run_id via --review-report/--reviews;
it cannot override a failed automated/source-safety check. No paid model probe occurs
in GET /health or history. Remaining evidence is listed in [NOT_DONE](../../NOT_DONE.md).
