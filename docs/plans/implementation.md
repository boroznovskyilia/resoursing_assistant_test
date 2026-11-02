# Development plan and task execution flow

Status: full end-to-end implementation explicitly authorized by the owner on 2026-10-31.
Live task status/evidence is maintained only in [progress.json](progress.json).
Start/recover using [handoff](handoff.md) and `make progress`.

## Gates and completion rules

Gate definitions below are acceptance criteria. Current task status and evidence live
only in [progress.json](progress.json).

| Gate | Required evidence | Completion condition |
| --- | --- | --- |
| G0 Requirements understood | Source inventory, data facts, accepted business conventions | Source findings distinguished from business rules and agent results |
| G1 Architecture selected | Accepted choices in decision register | Selected architecture and explicit defaults reviewed |
| G2 Acceptance specified | Written scenarios, approved 22 cases, scoring, per-task criteria | Observable acceptance and required checks defined |
| G3 Development authorized | Separate explicit owner instruction | Applicable implementation authorization recorded |
| G4 Delivery verified | Real checks/results, fresh clone, demo and authorized delivery | Required checks and deliverables verified; limitations and remaining blockers explicit |

After G3, proceed through the plan without asking approval for every routine task.
Do not wait for credentials before doing independent local work. Missing Azure access
blocks live integration/evaluation only, and must remain visible. Do not mark the
objective finished because local doubles pass. Publishing/submission remains separate.

A work package is done only when its outputs exist, relevant checks pass, affected
docs/commands reflect reality and evidence is recorded. Use Not started / In progress /
Blocked / Done, with a concrete blocker and exact checks. Do not create recurring jobs,
external services or elaborate project management infrastructure for this loop.

## Dependency order

| Package | Prerequisites | Result |
| --- | --- | --- |
| WP-01 | Source review, owner choices | Complete specifications and final review package |
| WP-02 | WP-01, G3 | Locked stack/configuration and reproducible environment |
| WP-03 | WP-02 | Source copies, calculations, schema and SQL permission boundary |
| WP-04 | WP-02/03 | Threads, requests, history, checkpoints and context |
| WP-05 | WP-03/04 | Intent/entity resolution and clarification graph |
| WP-06 | WP-03/05 | Composable factual answers and SQL evidence |
| WP-07 | WP-03/05/06 | Semantic index, assessment/ranking and fallback |
| WP-08 | WP-03/04/05, WP-06/07 for mixed flows | Booking proposal, decision, recovery and pending reads |
| WP-09 | WP-04/06/07/08 | Typed FastAPI lifecycle and request recovery |
| WP-10 | WP-09 | React saved-chat UI and restoration |
| WP-11 | WP-06/07/08/09 | Full 22-case runner, scoring and review artifacts |
| WP-12 | WP-09/10/11 | Integrated fault/limit/concurrency verification and measurements |
| WP-13 | WP-10/11/12 | Fresh-clone proof, final delivery docs and demo |
| WP-14 | Existing backend/checks, owner-approved structural review | Compatible backend and persistence refactor |
| WP-15 | Existing harness, owner-approved workflow revision | Consistent change handling, HITL and session recovery |

Build the agent first, API second, UI third. Checks are written with each feature;
WP-11 is end-to-end evaluation, not the first testing task. Limits and diagnostic
instrumentation are integrated as relevant; WP-12 validates them across the system.

## WP-01 Consolidate and review the specification

Inputs: [requirements](../specs/requirements.md), [source catalogue](../reference/README.md)
and [accepted decisions](../decisions/README.md). Outputs: this complete English package,
explicit defaults, source ambiguities, task criteria and the recorded development authorization.

- T01.1 Reconcile all previously accepted choices across primary docs.
- T01.2 Review factual/semantic/booking walkthroughs and storage/API/state consistency.
- T01.3 Check scenario traceability and own-case/oracle status; run documentation checks.
- T01.4 Present package for final owner review; record G3 only on explicit instruction.

Corners: stale outside drafts, confusing design approval with permission to code,
pretending proposed defaults were owner-selected, source instructions overriding scope.
Done: docs internally coherent, no hidden business choice, and explicit authorization
recorded before application work. This package's checks concern documentation/source
inspection; subsequent application evidence belongs to the relevant implementation tasks.

## WP-02 Locked environment and configuration

Requirements R-01/02/24/25/30. Outputs: Python3.12/uv lock, Node26/npm lock when frontend
is introduced, minimal package layout, configuration schema and secret-free env example.

- T02.1 Resolve compatible LangGraph/checkpointer/DSPy/FastAPI/Pydantic/test versions;
  lock exact versions and verify import/runtime compatibility in an isolated env.
- T02.2 Define Azure endpoint/key configuration, supplied deployment/API-version values,
  paths, reference clock and agreed resource limits. Assignment startup explicitly sets
  2026-04-01; an unset reference clock uses UTC-now. Audit clock stays separate.
- T02.3 Ignore secrets/runtime/logs; document local source initialization and repeat setup.
- T02.4 Establish provider adapter with one retry owner, explicit timeouts/cache semantics,
  and missing-config behavior. When credentials exist, run minimal genuine DSPy chat and
  embedding smoke checks; otherwise record live checks blocked and continue locally.

Corners: endpoint/version mismatch, unavailable interpreter/deployment, hidden adapter
retries, accidental shared LM cache in evaluation, relative paths, first-run downloads,
existing runtime overwrite. No extra hosted service or generic provider abstraction.
Tests: configuration/clock/retry boundaries and imports; S-065/073/074/077. Done when
locked environment reproduces and missing credentials fail honestly. Live integration
remains explicitly incomplete until actually checked, never substituted with doubles.

## WP-03 Data, calculations and read access

Requirements R-05/06/08/13/14/28. Primary contracts: [data](../specs/data.md),
[retrieval](../specs/retrieval.md), [storage](../specs/storage.md).

- T03.1 Package the mock source for reproducible local setup, verify fingerprint, create
  only absent working copies, and enforce immutable-original handling/schema versioning.
- T03.2 Implement deterministic UTC/date/minute/cent/FX/capacity helpers. Use strict
  half-open overlap, full intersecting hard minutes, correct grains and final rounding.
- T03.3 Produce compact allowed schema/rules for all eligible subject tables/columns.
- T03.4 Implement dedicated RO reader, authorizer/function controls, named bindings,
  single-statement handling, 5s/1000row/1MiB limits and executed query provenance.
- T03.5 Return complete aggregates and explicitly truncated detail; support stable source
  pages for exhaustive text scanning without model-authored pagination interpolation.

Corners: D-01–D-14, direct booking FK, WBS rollups, FX fanout/conflicts, zero bookings,
zero weekdays, strict60%, NULL dates, repeated risks, COUNT(*)/CTE/comments, attached
DB/private columns, recursive/huge scalar queries and unsafe source constants.
Tests: arithmetic/boundary micro-fixtures, real SQLite joins and adversarial access;
S-001–S-012/023–S-030/081. Done when source hashes unchanged, calculations match source
oracles, valid reads work and denied/resource-heavy queries stop safely. Permissions
alone are not evidence that the model selects semantically correct SQL.

## WP-04 Durable chats, requests and bounded context

Requirements R-04/11/21, O-03. [Storage](../specs/storage.md), [agent](../specs/agent.md).

- T04.1 Create own app records and supported LangGraph SQLite saver integration. Keep
  subject action receipts separate; never model-query app/checkpointer tables.
- T04.2 Persist ordered full transcript and stable request/message identities; input
  fingerprint conflicts, terminal replay and startup interrupted-state detection.
- T04.3 Persist exact task slots/IDs/displayed ordering and pending link. Fresh chat has
  clean memory, no Store. Reconcile receipt/history lag without paid calls.
- T04.4 Count full rendered prompts and implement old-complete-turn compaction with
  10k/2k budgets, ~8k trigger, ~3k recent/~700 summary. Preserve source full history.
- T04.5 Implement safe summary failure/context overflow; no silent critical truncation
  and no automatic history/checkpoint TTL. Retain resumable stage inputs.

Corners: summary distortion, oversized first input, incomplete turn pairs, multiple
ranked lists, history duplicated on retry, missing/corrupt checkpoint reset, growing
old checkpoints, current clock versus stored request clock. Tests S-015–S-021/083–S-085,
with real files/restarts. Done when history/context/identity survive restarts and every
memory boundary holds without relying on browser storage or narrative summary.

## WP-05 Interpretation, resolution and clarification

Requirements R-03/09/12/28. [Agent contracts](../specs/agent.md).

- T05.1 Implement typed DSPy InterpretRequest and output validation in controlled graph.
- T05.2 Resolve source identities, exact filters and displayed references; keep unresolved
  slots rather than picking first matches. Verify conflicting ID/name selections.
- T05.3 Clarify only material missing definitions/booking fields; retain supplied slots
  across answers, clear unrelated completed tasks, make year/reference assumptions clear.
- T05.4 Route mixed find-and-book, unsupported writes and out-of-data requests safely.

Corners: ambiguous Amanda Mitchell, 'second one', new topic during clarification,
experienced recommendation versus exact count, no literal migration skill, injected
source instructions, no invented weather/leadership. Tests S-013/014/019/020/022/043/048,
provider-double transitions plus later real-model paraphrases. Done when typed routes,
IDs and missing-field behavior work; double-backed success is not model accuracy.

## WP-06 Factual SQL planning and responses

Requirements R-05/06/14. Selected approach is generated read-only SQL, not a second DSL.

- T06.1 Implement typed DSPy PlanReads over compact complete allowed schema/rules.
  Validate query_id/purpose/sql/parameters; default maximum four statements/plan.
- T06.2 Execute independently needed detail/total/ranking reads through WP-03. Allow one
  shared format-or-SQL repair, never permission repair or retry of a valid empty result.
- T06.3 Build exact typed table/metric/SQL blocks and persist source/order references.
- T06.4 Implement ExplainResults with source evidence, truthful completeness and partial
  fallback when a separate read/explanation fails. No LLM arithmetic or missing totals.

Corners: correct but permission-safe wrong joins; literal guessed totals; hidden LIMIT;
multiple parts; invalid then invalid again; repair changes filters; result too large
for explanation but exact data can render. Tests S-001–S-012/023–S-030/078/081 and six
factual gold/own-01–05. Done when varied source-backed questions deliver requested parts
and provenance, with deterministic checks and separately reported actual-model results.

## WP-07 Semantic retrieval, assessment and fallback

Requirements R-07/12. [Retrieval](../specs/retrieval.md), [operations](../specs/operations.md).

- T07.1 Build person bio+role+skill-name, project summary and risk-description documents.
  Cache Azure vectors locally with model/text hash/dimension; preserve all memberships.
- T07.2 Implement cosine candidate retrieval and exact eligibility, default shortlist
  pool/count, complete source batching for all/count requests and uncertainty tracking.
- T07.3 Implement typed AssessCandidates and RankCandidates, validate IDs/excerpts,
  join exact facts, render grounded ranked results and retain displayed ordering.
- T07.4 Add bounded embedding-failure fallback to full eligible-text chat assessment;
  local logs/health/UI metadata, recovery detection, no fake empty response.

Corners: repeated ten risk texts, duplicate summaries, stale/corrupt vectors, omitted
skills, industry versus HLS, undefined thresholds, classification uncertainty, failed
batches, top-k falsely called all, embedding failure with chat alive/dead. Tests
S-031–S-036/079/080, gq-07/08 and exhaustive own-06–08. Done when cache memberships,
coverage, grounding and failure transitions pass; actual recall/quality are measured
with real models and reviewed under the accepted rubric.

## WP-08 Proposals, decisions and recovery

Requirements R-08–R-11/13/14. [Booking](../specs/booking.md), [storage](../specs/storage.md).

- T08.1 Validate positive whole-minute terms/IDs/dates/status, warnings and NULL optional
  links. Persist immutable action before card; unique origin and one pending/thread.
- T08.2 Add replay-safe graph pause and typed message/decision events. Pending reads
  preserve action; edits atomically supersede it; second independent booking waits.
- T08.3 Fixed Confirm transaction rereads/revalidates and inserts soft/SFT + receipt
  atomically. Reject updates only action. Repeat same decision returns existing result.
- T08.4 Reconcile action/app/graph lag, terminal card rendering and response loss. No
  model call needed for decision. Unrecoverable ambiguous state fails closed.
- T08.5 Exercise source hashes/tables and all commit/pause crash boundaries with actual
  files, competing DB transactions and real process termination/restart.

Corners: before/after proposal save/checkpoint/commit, stale card, wrong thread, source
change, lost response, Confirm/Confirm or Confirm/Reject, huge/nonfinite/sub-minute
hours, capacity warnings, free-text yes, intentional identical new action. Tests
S-037–S-049/086–S-088; gq-09 and own-09–11. Done only with no pre-confirm/Reject writes,
one booking per action, exact terms and normal restart confirmation proved. Checkpoint
persistence or an in-memory lock alone cannot satisfy this package.

## WP-09 FastAPI contracts and lifecycle

Requirements R-15–R-17/24/25. [API/UI](../specs/api-ui.md).

- T09.1 Implement typed seven-route contract, discriminated blocks/errors and strict
  unknown-input-field rejection; no arbitrary query/write endpoint.
- T09.2 Per-thread admission/dedup/status, no queue; independent chats progress off the
  event loop even during blocking DB/model work. Repeated requests never duplicate turns.
- T09.3 Explicit Resume using saved input/checkpoint; startup marks interrupted, GET does
  not run models, completed replay returns stable response, new question needs recovery.
- T09.4 Canonical action readback/history, safe health/configuration/degraded status and
  receipt-first recovery. Preserve existing data on service recreation.

Corners: unknown/malformed/wrong-thread IDs, 202 replay versus409 busy, pending wait
versus interrupted request, dependency failure/partial data, invalid outgoing block,
commit before HTTP disconnect, no fake empty history. Tests S-050–S-058/077/082–S-088.
Done when response/error/status contracts and actual lifecycle/restart tests pass.

## WP-10 React chat and accessibility

Requirements R-18–R-21. React/TypeScript/Vite, Node26/npm, plain CSS.

- T10.1 Create minimal frontend and lock dependencies; integrate saved-chat sidebar,
  new/open chat, current navigation and ordered API history.
- T10.2 Render safe text, typed metric/data tables, collapsible SQL and immutable action
  cards with canonical status. Confirm/Reject submits ID+decision only.
- T10.3 Preserve request_id on retries; loading/error/processing/Continue states and
  receipt readback after lost response; pending read questions remain usable.
- T10.4 Show effective reference date and local semantic-fallback warning. Implement
  keyboard/focus/header/overflow behavior, narrow/wide layouts and safe markup handling.

Corners: reload mid-request, reopened pending/terminal/superseded card, double click,
null versus0, wide table, invalid thread, storage failure, unknown booking outcome,
input stuck disabled. Playwright S-059–S-065 plus pending/recovery UI integration.
Done when three main flows and reload/restart work against the real local API, with
no browser-only transcript, secret bundle, external assets or optimistic write claims.

## WP-11 Evaluation runner and review artifacts

Requirements R-22/23. [Evaluation](../specs/evaluation.md) and approved case JSON.

- T11.1 Execute ten public and twelve own cases against the actual agent, isolated
  working source/app directories per case; write substeps share only their own fixture.
- T11.2 Score delivered blocks/effects with published keys/tolerances/order and accepted
  ambiguities. No runtime oracle leakage, hidden missing totals or model prose as write proof.
- T11.3 Output score, contract_checks and review_status, source-grounded review bundles,
  settings/source hash, calls/tokens/latency and per-case reasons. Preserve all run results.
- T11.4 Run actual Azure end-to-end evaluation when access exists; manually review
  free-text justifications/refusals. Keep review_required until review truly occurs.

Corners: gq-02 partial edge, gq-07 precedence/extra candidates, gq-08 overlap/grouping,
weather value alongside refusal, contamination, stochastic best-run cherry-picking,
manual review unavailable. Tests scorer boundaries S-066–S-072 and all22 real cases.
Done when reproducible runner/report exist and actual results are recorded; missing
Azure/review remains an explicit blocker to final quality acceptance, not a fake pass.

## WP-12 Integrated limits, faults and measurements

Requirements R-04/11/13/14/20/24/25. Instrumentation is added with each earlier feature.

- T12.1 Verify 10k/2k context, per-attempt retries, shared repair, SQL limits and finite
  batch coverage across integrated flows; log actual rather than assumed attempt counts.
- T12.2 Inject timeout/429/5xx/auth/index/corrupt-state/summary/explanation failures and
  inspect bounded behavior, fallback/recovery logs, safe errors and preserved state.
- T12.3 Verify independent-chat progress, no long DB writer lock during calls, source
  invariants and all core safety cases under cancellation/response-loss/restart.
- T12.4 Measure latency, token usage, recall and storage growth; tune engineering defaults
  only on evidence and rerun affected checks. Report deployment/settings/source context.

Corners: SDK hidden retry multiplication, global event-loop blocking, one huge scalar,
all-count quietly stopped, exceptions exposing headers, committed write reported failed,
health probe spending model budget. Tests S-017/021/027–S-029/044–S-047/073/074/077–S-088.
Done when agreed invariants pass with evidence. No unmeasured latency/SLA or invented
cost figure. No external logging/alerting service is introduced.

## WP-13 Reproduction, delivery documents and demo

Requirements R-24–R-30. Target date from invitation: 2026-11-02, exact time unspecified.

- T13.1 Run setup/build/tests/eval from a fresh checkout with no inherited runtime/cache;
  document actual commands, model/env prerequisites and mock source availability.
- T13.2 Update README with actual per-case table/commands, concise one-page DESIGN and
  honest NOT_DONE, assumptions, AI use, known limits and production changes.
- T13.3 Preserve meaningful coherent Git history and inspect tracked content/history
  for secrets. Do not fabricate commits, results or a successful demo.
- T13.4 Record factual, semantic and booking conversations; actually restart API before
  confirming saved proposal. Save recording or allowed transcript, disclose any limitation.
- T13.5 Prepare repository/demo links and submission text locally. Publish/share/send
  only under applicable explicit owner instruction; recipient/time details are logistics.

Corners: absolute Downloads runtime dependency, missing source/index setup, real versus
mock demo, review-required scores shown passed, failing safety hidden by averages,
recording not demonstrating restart. Done when fresh-clone and accepted checks are
verified and claims match evidence. Any residual failure is visible in NOT_DONE/README.

## Execution loop after G3

Follow the [task workflow](../development/workflow.md), including its change/conflict
procedure and completion review. Select work by these dependencies, keep the active
task and next action in progress.json, and continue independently eligible work while
an owner decision or external input blocks another task. Add follow-up definitions
here and matching progress entries when new work is authorized; do not reuse unrelated
completed tasks or treat an old completion as evidence for a changed contract.

Package status is recorded in progress.json. Current checks and evidence are in
[verification](../development/verification.md). This plan contains written tasks,
not an automation, active background job, completion promise or grant of model access.

## WP-14 Owner-approved backend structure and persistence refactor

Owner approved all structural review findings on 2026-11-01, using synchronous
SQLAlchemy. Preserve public API, existing runtime data, graph node names/checkpoints,
source permissions, and atomic idempotent booking decisions. No async conversion.

- T14.1 Replace dataclass configuration with validated pydantic-settings; extract domain calculations and centralize existing limits.
- T14.2 Separate API/agent schemas, dependency assembly, graph state and model responsibilities; preserve CLI entry points.
- T14.3 Introduce synchronous SQLAlchemy repositories for conversations, bookings and vectors without recreating saved data.
- T14.4 Extract read orchestration/policy and RAG dependencies; retain the native protected SQL reader and LangGraph saver.
- T14.5 Batch source document queries and verify equivalent results, query counts, restart and transaction invariants.
- T14.6 Run local regression, browser and genuine Azure evaluation; record current evidence and update architecture/setup documentation.

Done: every review item is implemented, saved-runtime compatibility is checked,
local checks pass, genuine-model results/reviews are reported honestly, and changed
imports/commands/specifications are updated. Existing evaluation artifacts remain
historical evidence rather than being relabeled as results of the new runtime.

## WP-15 Owner-approved development harness revision

Owner approved this workflow revision on 2026-11-02. Preserve application behavior,
source fixtures and historical verification artifacts; use existing documents and
progress fields without a new runtime service or semantic-validation tool.

- T15.1 Consolidate change/conflict handling, HITL, impact review and evidence freshness; remove conflicting status instructions and shorten session recovery guidance.
- T15.2 Remove the fixed owner-conversation language, align related documents, and commit/push the approved harness revision to master.

Done: one linked procedure defines triggers, authority, owner decisions, affected
contracts/code/checks, evidence reassessment and completion review. Current statuses
have one home; historical material and superseded decisions are distinguishable.
Checks: make check, git diff --check and manual walkthroughs of a contract bug, an
ambiguous requirement, an explicit owner change and interrupted-session recovery.
Walkthroughs review instruction consistency; they do not prove future agent compliance.
For T15.2, verify the language-rule removal and documentation checks, create the requested
`little harness update` commit, and verify that remote master matches the committed revision.
