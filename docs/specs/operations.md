# Resource limits, failures and local diagnostics

Status: accepted policies plus labeled engineering defaults; runtime checks exist; full Azure behavior unverified.
Requirements R-04/06/11/13/14/20/24/25. Complements [retrieval](retrieval.md),
[agent](agent.md) and [API/UI](api-ui.md).

## Budgets and retry ownership

| Boundary | Agreed setting | Behavior |
| --- | --- | --- |
| One rendered model input | 10000 tokens | Count instructions, signature/format, schema, history, candidates and results |
| Model output | 2000 tokens | Configure generation and validate typed output; not model's advertised context maximum |
| Recent context / summary | Approximately 3000 /700 tokens | Included inside 10000, not additional allocations |
| Compaction trigger | Approximately 8000 rendered input tokens | Compact old complete turns before dispatch; still enforce hard input budget |
| One chat/embedding attempt | 60 seconds | Timeout at transport boundary; separate from whole multi-stage request duration |
| Transient transport retry | One retry, two attempts total | Network/timeout/429/temporary 5xx only |
| Retry delay | Retry-After <=10s; otherwise default 1s | If provider asks >10s, stop immediate retry and return failure/fallback |
| Typed output repair | One repair | Planner shares this with SQL syntax/schema repair |
| One SQL execution | 5 seconds | Deadline covers execution/fetch; SQLite busy timeout is not this deadline |
| SQL returned data | 1000 rows or 1 MiB, whichever first | Bound serialized result payload; detect and label truncation |

Authentication, authorization and invalid endpoint/deployment/config errors do not
receive pointless transport retries. Log safe error class/status. Never log raw SDK
exceptions with headers, keys or full endpoint query strings. Chat and embedding
configuration are separate, so an embedding failure need not make chat unavailable.

Own retries at one layer. Disable or account for SDK/adapter implicit retries so the
same call cannot multiply attempts invisibly. One semantic task can have an original
and a repaired generation, each with at most two transport attempts. This is not a
promise of only two physical calls for the whole user message.

The planner has one shared repair allowance for malformed output OR syntax/schema
failure, not one for each. Permission rejection, execution timeout/output limit and
valid empty results do not trigger a planner repair. A repair may not broaden access,
relax filters or silently answer a different question.

There is no arbitrary six-call/message or other global generative-call cap. Derive
work from the controlled path: one interpretation, optional compaction, a bounded
plan/repair, finite candidate batches/assessment, ranking and optional explanation.
Each batch covers a known finite input slice. Record actual calls/attempts/tokens.
Exact all-candidate requests may take longer; never claim a complete count early.

## SQL results and complete searches

A fetched detail list can be truncated without invalidating a separately executed
complete COUNT/SUM. State which is complete. Never calculate a total from only the
first 1000 rows and label it global. A single oversized scalar must also be bounded;
use SQLite length limits plus bounded fetch/serialization, not only a post-hoc byte check.

Full semantic reads use controlled keyset pages with stable source IDs and bound
cursor values. Each page obeys SQL budgets; the scan records coverage and detects a
non-advancing cursor. Source membership is established for the operation so concurrent
bookings do not silently redefine a past answer. Do not hold a long writer transaction
or write lock while calling a model.

## Partial answers and safe failure

| Failure | User-visible behavior |
| --- | --- |
| Ambiguous/missing information | Normal clarification; no execution of an invented booking |
| Empty valid query | Normal empty answer under explicit filters |
| Some independent read parts fail | Available verified blocks + issues naming missing parts; request partial |
| Explanation unavailable after reads | Deterministic tables/SQL retained; explicit explanation issue |
| Embeddings unavailable | Full eligible-text scan via chat; warning and local degraded state |
| Chat also unavailable | Available partial data or dependency error; preserve pending action/history |
| Summary cannot be produced | Safe existing context only if it fits, otherwise explicit context failure |
| SQL policy rejection | Reject safely; no lower-privilege bypass or automatic repair |
| Writer fails before commit | No confirmed booking; preserve pending action for safe retry/reject |
| Writer commits but reply fails | Receipt is truth; readback/repeat returns existing booking |
| Corrupt unrecoverable checkpoint | Explicit recovery error; never overwrite it with a new empty thread |

Never describe a write as partial. Atomic commit establishes success even if the HTTP
response was lost. Cancellation or timeout after commit cannot undo the booking.
A semantic fallback that covers all candidates with valid classifications is not
inherently a partial answer. Uncertain/unprocessed candidates prevent an unqualified
exact result. Partial request status and shortlist completeness are different concepts.

## Local observability

Structured JSON to stdout and a rotating local file; no Slack, Telegram, email, hosted
tracing or alerting service. Default rotation 5 MiB ×3 backups is an engineering default.
Record UTC time, severity, event, thread_id, request_id, stage, safe error class,
deployment/model name, attempt, latency, result/coverage counts and tokens when available.
Ordinary logs omit full prompts, full source/result texts, authorization headers,
API keys and raw private state. Stored transcript/evidence is not copied wholesale to logs.

Required events include:

- `embedding_unavailable`: class, deployment, attempts, latency.
- `semantic_fallback_started`: reason and eligible candidate count.
- `semantic_fallback_completed`: coverage, outcome, batches/calls/tokens, latency.
- `semantic_fallback_failed`: safe error and preserved action/history status.
- `embedding_recovered`: emitted after a subsequent genuine embedding request succeeds.
- Query rejection/timeout/truncation, repair, interrupted/resumed request, transaction
  outcome and recovery reconciliation, without confidential query values in ordinary logs.

An embedding outage sets last-observed component status to degraded. Health remains
alive if storage and fallback permit service; UI shows a small warning that semantic
processing may take longer. GET /health reports last-observed status/configuration,
never launches a paid probe. Initially unknown is not reported as verified healthy.
Subsequent success clears current degradation, retaining logs. Missing credentials
are configuration status, not proof that quota has run out.

## Acceptance scenarios

| ID | Scenario | Observation |
| --- | --- | --- |
| S-077 | Transient vs permanent provider errors, Retry-After boundaries | Exact attempt/delay rules, no multiplied SDK retries |
| S-078 | Planner format error followed by SQL error | One shared repair exhausted; no nested repair loop |
| S-079 | Embedding endpoint unavailable, chat works | Logged full-text fallback; coverage truthful; pending action unchanged |
| S-080 | Embeddings later work | Recovery event and health/UI degradation cleared without paid health probes |
| S-081 | SQL row/byte/time limits, including one huge cell | Bounded resource use, clear truncation/error, complete separate aggregates retained |
| S-082 | Same-thread busy and another thread progresses | Per-thread serialization, no global event-loop/provider blockage |

Implemented checks cover a subset; see the linked tests and verification limits below. Fault doubles verify transitions/logs; real integration measures
latency, token accounting and Azure compatibility when credentials are available. Limits are
initial settings, not performance guarantees or evidence of a current provider outage.

## Implemented check coverage

See [topic checks](../../tests/test_faults.py) and [current verification](../development/verification.md).
Real Azure quality and any scenario not explicitly mapped there remain unverified.
