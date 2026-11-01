# Accepted design baseline and remaining verification

Consolidated from owner decisions on 2026-10-31. **Saving these documents is authorized;
full application development was explicitly authorized later on 2026-10-31.** Accepted means a design choice, not a tested result.
Source obligations are in [requirements](../specs/requirements.md). No additional design
question is required before reviewing this complete package.

## Accepted owner decisions

| ID | Accepted decision | Consequence / primary contract |
| --- | --- | --- |
| DEC-01 | Exact repository name resoursing_assistant_test | Preserve spelling |
| DEC-02 | Specify and review before separately authorizing implementation | Design-first gate satisfied; full implementation explicitly authorized 2026-10-31 |
| DEC-03 | Per-thread memory only; no Store | New chat has clean memory; existing chat resumes |
| DEC-04 | Compare generated SQL and typed tools first | Comparison completed; selection superseded by DEC-05 |
| DEC-05 | Model-generated read-only SQL, fixed writer | No tool DSL or parallel alternative implementation; [retrieval](../specs/retrieval.md) |
| DEC-06 | Controlled LangGraph StateGraph | Explicit clarification/read/semantic/booking stages, bounded repair |
| DEC-07 | Compact schema for all allowed subject tables | Actual columns/FKs/units/rules; exclude private/auth/BLOB fields |
| DEC-08 | Structured multi-query read plans | query_id, purpose, sql, parameters; exact totals/rankings may use separate SELECTs |
| DEC-09 | Separate read-only connection and explicit allowlists | Policy violation is terminal; syntax/schema error gets one repair; empty result no retry |
| DEC-10 | Code renders exact values and SQL; DSPy explains evidence | Available data survives explanation failure as an explicit partial response |
| DEC-11 | Azure embeddings with local vector storage/search | text-embedding-3-small API, no external vector service or local replacement model |
| DEC-12 | Entity documents, no fixed-size chunking/overlap | Person bio+roles+skill names, full project summary, full risk description |
| DEC-13 | Deduplicate embedding texts, retain memberships and hashes | Shared risk vector never loses records/projects; invalidate changed text/model |
| DEC-14 | Both shortlist and exhaustive semantic modes | Full counts/sets require coverage of all eligible candidates |
| DEC-15 | Grounded assessment and explicit ranking | match/no_match/uncertain, validated evidence, durable displayed order |
| DEC-16 | No invented experience/leadership cutoff | Recommendations explain inference; exact count clarifies undefined threshold |
| DEC-17 | Embedding outage falls back to chat assessment of full eligible texts | Bounded attempts first; explicit local logs, health/UI degradation; no fake empty set |
| DEC-18 | One immutable pending action per thread, read questions allowed | Changes supersede old ID; second independent booking waits |
| DEC-19 | Confirm via button/explicit API only | Free-text yes cannot write; Confirm body cannot change terms |
| DEC-20 | Stable action, atomic booking+receipt, replay-safe decisions | Same Confirm returns same booking; Reject zero inserts; stale/opposite decision conflicts |
| DEC-21 | Capacity warning permits soft booking | No hidden hard overlap/capacity ban; optional links remain NULL without justification |
| DEC-22 | Two working SQLite files plus immutable original | Subject+actions transaction; separate app history/checkpoints/index; [storage](../specs/storage.md) |
| DEC-23 | Summary of old complete turns, recent turns, exact active fields | Full transcript persists; proposal/IDs/order never reconstructed from summary |
| DEC-24 | 10k input /2k output per model call | Recent ~3k, summary ~700 included; compaction trigger ~8k; [operations](../specs/operations.md) |
| DEC-25 | No arbitrary global model-call cap per message | Bound graph paths, finite batches and local retries; log actual attempts |
| DEC-26 | UTC-now default; assignment/eval explicitly 2026-04-01 | Month without year uses reference year; audit timestamps use real UTC |
| DEC-27 | Visible end day inclusive; internal UTC half-open intervals | Strict overlap, full intersecting minutes, no proration |
| DEC-28 | Mon-Fri ×8h capacity, disclosed approximation | No leave/holiday/FTE assumption; zero weekdays means no percentage |
| DEC-29 | Full-precision monetary conversion then final rounding | Reduce FX to one rate/currency; no repeated rate-card join |
| DEC-30 | Non-streaming HTTP, four typed block kinds | text/table/confirmation/sql; scalar metrics use one-row tables |
| DEC-31 | Saved-chat sidebar and clean new chat, local shared dataset | No tenants/auth, folders/search/rename or cross-thread user memory |
| DEC-32 | Stable client request_id and one active operation/thread | Completed replay, active status, conflict on changed input; no global lock/queue |
| DEC-33 | Explicit Resume for interrupted operations | GET does not invoke models; node may rerun; canonical booking receipt wins |
| DEC-34 | Interrupted thread must recover before another question | 409 resume_required; another chat remains available; terminal recovery error unlocks input |
| DEC-35 | API additions are acceptable with DESIGN explanation | GET /threads and explicit request Resume in addition to suggested routes |
| DEC-36 | Four behavioral verification layers and 22 evaluation cases | Deterministic, SQLite/API, process/UI, real Azure; doubles are not model accuracy |
| DEC-37 | Explicit score/contract/review separation, manual free-text review | Approved gold ambiguities and own all-conditions scoring; [evaluation](../specs/evaluation.md) |
| DEC-38 | Python 3.12/uv; LangGraph SQLite saver; DSPy; FastAPI/Pydantic v2 | Exact compatible package versions locked during implementation |
| DEC-39 | React/TypeScript/Vite/plain CSS; Node 26/npm; pytest/Playwright | One backend worker; independent chats progress concurrently |
| DEC-40 | Local diagnostics only | JSON stdout + rotating local logs; health/UI warnings; no external alerting |
| DEC-41 | 60s/model request, one transport retry, one format repair | Retry-After <=10s, else no immediate retry; default backoff 1s; shared SQL repair budget |
| DEC-42 | 5s/SQL execution, 1000 rows or 1 MiB result | Explicit truncation; full aggregates separate; exhaustive reads use bounded pages |
| DEC-44 | Owner explicitly authorized full end-to-end implementation on 2026-10-31 | Scope-question reply; progress.json records status/evidence; publication still separate |
| DEC-43 | Save the entire specification and development plan in English now | Russian conversation continues; no intermediate Russian repository required |

## Stack contract

| Layer | Selected baseline | Verification still required |
| --- | --- | --- |
| Python | 3.12, uv, isolated environment and lockfile | Interpreter installation and dependency compatibility |
| Agent/checkpoints | LangGraph StateGraph, langgraph-checkpoint-sqlite | Exact saver integration, interrupt replay and restart behavior |
| Generative steps | DSPy explicit typed signatures | Azure transport, retry/cache behavior and token accounting |
| API | FastAPI, Pydantic v2 | Runtime contract/response validation |
| SQL | stdlib sqlite3, explicit transactions/read controls | Authorizer/function policy and deadlines on real queries |
| Vectors | Local SQLite cache + in-process cosine search | Numeric representation chosen minimally; no vector server |
| Frontend | React, TypeScript, Vite, plain CSS; Node 26/npm | Build and browser integration |
| Tests | pytest and Playwright | Deterministic and real-process scenarios; real Azure eval separately |

Exact package versions are now locked and local setup/build/checks exist.
See [verification](../development/verification.md) and [genuine evaluation](../evaluation/README.md)
for known-case results and explicit AI-assisted review; unseen quality remains unverified.

## Engineering defaults included in this specification

These complete the implementation plan without pretending every detail was explicitly
selected by the owner. Change them only with a reason and corresponding tests/docs;
changes to agreed business behavior still require owner review.

- At most four statements in one planner output. Reject oversize plans and use the same
  single planner-repair budget; never silently drop a requested part.
- Default recommendation count ten when the user supplies no count. Initial vector
  candidate pool up to forty per relevant document kind, after exact eligibility,
  with source-grounded assessment; measure recall. Exhaustive mode has no top-k cutoff.
- Semantic batches are packed deterministically under the full 10k input budget, not
  a claimed universal fixed number of documents. Oversized single documents fail
  explicitly until a source-span splitting policy is implemented.
- Deterministic tie fallback uses source ID. Initial local file logging rotates at
  5 MiB with three backups. No automatic transcript/action TTL or checkpoint pruning.
- Conflicting FX rates fail the affected conversion clearly rather than selecting an
  arbitrary MAX. Current fixture has one constant per currency.
- Summary failure keeps original history; use the previous summary and a safe complete
  recent window only if mandatory current fields/input still fit. Otherwise fail before
  execution. No fabricated summary or silent critical-input truncation.

## Remaining work, not another questionnaire

1. Full implementation authorized on 2026-10-31; record actual task evidence in progress.json.
2. Implementation-time verification of versions, Azure endpoint/credentials, prompt
   sizes, latency, token usage, query limits and semantic recall. Credentials come later.
3. Submission logistics: exact deadline time/timezone, repository publication/access,
   recipient address and recording. No external communication has been authorized.

No unanswered business-rule choice is being hidden behind these items. If implementation
reveals a contradiction that changes behavior, report the concrete conflict and impact;
do not restart a long questionnaire for ordinary implementation choices.

## Backend structure revision — owner accepted 2026-11-01

Apply every structural review item, from required config validation through batched
document loading. Use pydantic-settings and **synchronous** SQLAlchemy, not async ORM.
Separate API/agent/ORM schemas, dependency assembly, context/read orchestration and
model/cache/source responsibilities. Preserve public API, saved data/checkpoints,
read-only SQL protections and atomic idempotent Confirm. No generic base managers or
CRUD framework. Details: [module map](../architecture/overview.md#backend-module-boundaries),
[WP-14](../plans/implementation.md#wp-14-owner-approved-backend-structure-and-persistence-refactor).
