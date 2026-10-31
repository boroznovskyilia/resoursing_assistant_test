# Resourcing Assistant — design summary

Implemented locally with genuine Azure chat/embedding checks. Evaluation evidence is
reported in [README](README.md); unexecuted delivery work remains explicit.
Detailed contracts: [specifications](docs/specs/README.md). [Limits](NOT_DONE.md).

**Graph and DSPy.** Controlled LangGraph StateGraph: context -> interpretation -> exact
resolution/clarification -> factual reads or semantic matching -> composition; booking
preparation persists immutable terms then interrupts. Typed DSPy signatures cover
InterpretRequest, PlanReads, PlanProjectChecks, AssessCandidates, RankCandidates, ExplainResults and
SummarizeHistory. Fixed decision execution needs no model. No free tool loop/optimizer.

**Reads and semantics.** Model-generated primary/additional-answer SELECT plans use typed named bindings and compact
allowed schema/rules; a dedicated RO SQLite connection enforces table/column/function
permissions, single statements and time/output limits. Tests/eval still must establish
join/units correctness. Exact data/SQL render in code. Local vectors from Azure index
whole bio+role+skill-name, project summary and risk documents with model/text hashes and
full source memberships. Simple semantic eligibility pools are compiled; complex exact filters retain guarded
generated reads. Project summary/industry and risk checks are assessed on deduplicated
source fields, then joined by parent identity with explicit AND/OR. Source assessment
and count-bounded ranking validate IDs/quotes; exact skills
come from SQL. All/count visits every eligible entity via bounded pages/batches, tracking
uncertainty; top-k is never a total. Large full sets can use declared source-ID order.

**State and writes.** Full transcript is separate from bounded summary/recent turns and
exact task/ordered ID references. One common dataset, independent saved chats, no Store.
Two working SQLite files: subject+booking_actions/receipts, and app history/requests/
checkpoints/index; original input is immutable. Stable request/action IDs deduplicate
retries. Confirm atomically inserts soft/SFT and saves its receipt; Reject inserts
nothing; edits supersede old IDs. Reads are allowed while waiting. Receipt-first
reconciliation handles lost responses/checkpoint lag. Explicit Resume recovers crashed
operations; GET never runs models. New questions wait for recovery or use another chat.

**API and failures.** FastAPI/Pydantic validates both directions; React/TypeScript/Vite
renders text/table/confirmation/sql. Added thread-list/Resume routes support saved chats
and recovery. One worker, per-thread admission, blocking work in a thread pool. Embedding
failure falls back to full eligible-text chat assessment; local JSON/rotating logs and
health/UI show degradation/recovery, with no paid health probes or external alerting.
Available verified reads can return partial; a committed write remains confirmed.

**Limits and assumptions.** 10k input/2k output; compaction near8k plus bounded recent
turns/700-token summary. Per-attempt60s, one transport retry, one typed repair shared
with SQL correction; no global call cap. SQL5s/1000rows/1MiB, explicit truncation and
complete separate aggregates. UTC-now default, assignment/eval pinned2026-04-01; audit
clock real UTC. Human end day inclusive/internal half-open; strict overlap preserves
gold fixture despite its >= boundary. Full intersecting hard minutes include CMP;
capacity Mon-Fri×8h, warnings permit soft bookings. Convert full precision then round
final money. Optional booking links NULL without evidence. No invented leadership.

**Evidence and production.** pytest/SQLite/API, actual kill/restart, Playwright and scorer
checks exist. Genuine22-case model results and explicit AI-assisted source review
are reported separately from test-double checks in README. No independent human
review or unseen-question accuracy claim is implied.
Production needs real identity/isolation, persistence/concurrency, calendar/FX/retention
policy and broader evals. AI assistance inspected data, developed implementation/tests
and documentation; doubles-backed results are explicitly separated from real quality.
