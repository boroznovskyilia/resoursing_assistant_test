# Verification and evidence limits

Updated 2026-10-31. Application implementation is authorized and present. This document
separates executed checks from written scenarios and unavailable real-model evidence.
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

- Complete backend suite passed50 tests in14.47s in the actual clean Git clone,
  including2 real-process tests.
- The2 real HTTP process tests passed: kill/reopen before Confirm and kill mid-node,
  GET without inference, explicit Resume with one user history message.
- TypeScript/Vite build passed. Five Chromium checks against the real API passed:
  factual blocks/SQL/reload; pending read+Confirm; lost response/retry identity;
  Reject/mobile/untrusted markup; terminal-error new attempt identity. Desktop/mobile screenshots inspected.
- A clean filesystem copy without env/dependencies/runtime successfully ran `make setup`
  using cached installation packages; no source path outside checkout was needed.
  Actual Git clone ab8ba9f also passed make setup/check, Ruff, all50 backend tests and
  all5 Chromium checks. Exact final evidence is tracked in progress.json.
- Real evaluation preflight processed22 configured case definitions, writing all as
  not_run because Azure endpoint/key are absent. No agent accuracy/recall score exists.
- Original source/reference SHA-256 and8 additional read-only oracles matched during
  specification consolidation. Runtime source copy is fingerprint/version checked.

These counts are time-stamped evidence, not claims about unrun checks after future edits.
Final checks/status are recorded in progress.json. No provider quota exhaustion was observed.

## Check-to-scenario map

| Check file | Main coverage | Remaining boundary |
| --- | --- | --- |
| [Data](../../tests/test_data.py) | S-003/006/012/023–S-029/081: conversions/capacity, COUNT/CTE, permissions, time/row/byte limits, huge scalar, pages, source copy | General model join correctness requires actual eval |
| [Store](../../tests/test_storage.py) | S-037–S-043/046/047/083/087: no prewrite, exact fields, Reject, repeat/racing Confirm, supersede, request IDs, persisted state | Real interpretation quality separate |
| [Setup](../../tests/test_setup.py) | Private/exclusive env creation and preservation of credentials/source state | Genuine provider setup awaits credentials |
| [LM](../../tests/test_llm.py) | S-022/074/077: retry boundaries, no-config, actual DSPy adapter typed repair and input budget | Genuine Azure transport and reported tokens unverified |
| [Graph](../../tests/test_agent.py) | S-013/015/016/018/034/035/086: source factual/semantic transitions, ambiguity, pending reads, checkpoint reopen, partial explanation | Uses named scripted provider, not real model |
| [API](../../tests/test_api.py) | S-050–S-056/061/082/083: typed routes/errors, request/action replay, unknown fields, busy/other thread | Browser/restart checked separately |
| [Processes](../../tests/test_process.py) | S-041/055/084/085: actual kill/restart, no inference on GET, explicit Continue | Test-only model factory; no quality claim |
| [Semantics](../../tests/test_semantic.py) | S-033/034/036/079/080: memberships, reuse, fallback full scan, uncertainty, fabricated quote rejection, genuine-success recovery | Similarity recall/ranking with actual embeddings unverified |
| [Faults](../../tests/test_faults.py) | S-017/018/024/028/044/073/078/079/088: shared repair, source invariants, compaction, logs, lost commit ack/checkpoint lag | Not every possible OS/storage failure injected |
| [Scoring](../../tests/test_scoring.py) | S-068–S-070/072: tolerances, order, partial credit, absent total, review-required and run-bound manual review | Real22-case answers/manual checks unavailable |
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

Free-text review can be applied only to a matching run_id via --review-report/--reviews;
it cannot override a failed automated/source-safety check. No paid model probe occurs
in GET /health or history. Remaining evidence is listed in [NOT_DONE](../../NOT_DONE.md).
