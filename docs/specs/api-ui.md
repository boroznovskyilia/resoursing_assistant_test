# API and chat contract

Status: agreed capabilities/routes with concrete typed contract for implementation.
API/UI code exists; implemented check coverage is linked below. Requirements R-15–R-21/24/25/30.
The brief permits route/block changes; additions are explained in [DESIGN](../../DESIGN.md).

## Routes

| Method/path | Body | Success / behavior |
| --- | --- | --- |
| POST /threads | Empty typed object | 201: thread_id, created_ts; clean per-thread memory |
| GET /threads | None | 200: saved chats ordered by last activity, IDs/timestamps and short display label |
| GET /threads/{thread_id} | None | 200: ordered API transcript, request states, canonical action status, effective reference date |
| POST /threads/{thread_id}/messages | request_id, text | 200 final typed result; 202 if same request already processing |
| POST /threads/{thread_id}/confirm | action_id, decision=confirm/reject | 200 canonical action result and typed blocks; decision needs no model |
| POST /threads/{thread_id}/requests/{request_id}/resume | Empty typed object | 200 recovered final result; 202 if already processing; completed returns stored result |
| GET /health | None | 200 when live, safe configuration/component/last-observed degraded status; 503 if storage prevents service |

Ordinary HTTP JSON, no streaming or queue. A normal POST waits for its bounded graph
path, which may contain several model calls/batches; 60s is per attempt, not total turn.
Thread/action/request IDs are opaque validated references, not authentication. Default
local-only deployment, no tenants/login. Do not expose arbitrary SQL, filesystem paths,
model credentials or endpoint selection through browser requests.

## Request identity and admission

The browser creates request_id once per intentional message and retains it during
network retry. Server stores original input/fingerprint and one user history message:

| Same ID / state | Behavior |
| --- | --- |
| Original text, completed/partial | Return same saved response ID/blocks, overlay canonical card statuses; no graph rerun |
| Original text, processing | 202 with processing status; do not start another operation |
| Different text | 409 request_id_conflict |
| Interrupted | Explicit Resume required, not implicit rerun on POST/GET |
| Failed | Return saved failure; intentional new attempt uses a new request_id |

A different request while that thread is actively processing gets 409 thread_busy.
No automatic queue. Other threads can proceed. Confirm competes for the same per-thread
operation admission, so during an active read it returns thread_busy; UI offers retry.
Normal action-pending wait is idle and permits read questions. An interrupted operation
requires Resume before a new question (409 resume_required); opening another chat is
possible. Terminal recovery failure releases the thread for a new intentional message.

Resume identifies saved work and receives no new user text/booking values. It uses the
latest usable checkpoint and canonical action receipt. Unfinished nodes may rerun and
make another model call; no claim of exactly-once model inference. Completed replay
returns stored result, active replay 202, terminal failure clear error. GET never runs
the graph or a paid probe. Startup does not auto-resume interrupted requests.

During an interrupted request, a new pending-action decision also requires recovery
before changing graph state (409 resume_required); compatible terminal receipt readback
remains safe. UI disables pending decision buttons until recovery is resolved. Normal
restart of a completed preparation/human wait is unaffected and can Confirm immediately.

Confirm's idempotency key is action_id+decision, not a new booking request_id. Repeated
compatible decision returns the same receipt/history event; contradictory/stale decision
conflicts. User-entered 'yes' is not this channel. Unknown extra request fields are
rejected so new hours/IDs cannot be smuggled into Confirm.

## Typed response envelope

Pydantic v2 validates requests and responses. Discriminated block union; unknown request
fields rejected. Timestamps use documented UTC representation; subject SQL binds epochs.

Final message response fields:

- thread_id, request_id, response_message_id (stable persisted assistant message ID).
- request_status: completed or partial; processing on 202, interrupted/failed in history
  or failure/readback contracts. Never conflate request status with action status.
- blocks: ordered typed text/table/confirmation/sql blocks.
- issues: code, safe message, stage, optional affected query/entity/block and retryability.
- effective_reference_date and assumptions needed to interpret the answer.

A processing acknowledgement has the same identity, request_status=processing, nullable
response_message_id, empty blocks and current issues. This is not a completed answer.
Error responses have an error object with stable code/message/retryable and available
thread_id/request_id; no raw stack/provider payload. History messages have message_id,
sequence, role, UTC timestamp, request association and typed blocks/text. History includes
a terminal failure notice when appropriate, so a failed turn does not disappear.

| Block | Required fields / meaning |
| --- | --- |
| text | type=text, text, optional validated evidence references; safe text/formatting |
| table | type=table, block_id/title, columns with stable key/label/unit, keyed rows, evidence references and completeness |
| confirmation | type=confirmation, action_id, status, exact saved display fields, warnings/assumptions, booking_id when confirmed |
| sql | type=sql, query_id, purpose, executed statement and named bind parameters |

Scalar metrics use a one-row table with stable keys, not a fifth block kind. Row values
are typed scalars/null; source IDs/evidence metadata enable scoring. Completeness names
shortlist/exhaustive mode, eligible/processed/matched/uncertain counts where known,
truncation/has_more and explanation sampling. Never make one boolean stand for all of
these. Action statuses: pending/confirmed/rejected/superseded. No proposed terms are
accepted from a confirmation request; use the stored snapshot.

## Status and errors

| HTTP | Stable examples | Notes |
| --- | --- | --- |
| 200 | completed/partial, clarification, refusal, empty result, pending card | Pending card preparation is completed request, not perpetual spinner |
| 202 | processing | Only acknowledgement of already active work, no duplicate execution |
| 404 | thread_not_found, action_not_found, request_not_found | Wrong-thread action uses not-found without revealing other thread data |
| 409 | thread_busy, resume_required, request_id_conflict, action_conflict, action_superseded, no_pending_action | No source mutation |
| 422 | invalid_request, context_budget_exceeded, invalid_proposal | Pydantic/value/input-budget failure; safe explanatory body |
| 503 | provider_unavailable, source_unavailable, storage_unavailable | No usable answer and required dependency unavailable |
| 500 | recovery_failed, internal_error | Sanitized unexpected/corrupt state; no fabricated empty history |

A generated SQL policy failure becomes explicit failed/partial processing with a safe
issue, not a fake empty result or permission relaxation. Read results available despite
an independent failure return 200 partial. API body validation failure does not insert
a user turn/action. A committed write is confirmed even if later serialization/graph
sync fails; recovery reads the receipt before claiming any outcome.

## UI behavior

Saved-chat sidebar + New chat, one open thread, server history, message input/send,
loading/errors, typed blocks and accessible Confirm/Reject. No folders/search/rename.
Browser stores only navigation/request identity needed for retry; API stores history.
Reopening/reloading restores exact context/card and active/interrupted request state.

While processing, show progress without duplicate sends. While action pending, allow
read questions. While request interrupted, show Continue; disable new questions until
recovery completes/fails terminally. New chat remains usable. Unknown thread/storage
failure shows an error, not fabricated empty history.

Historical cards resolve canonical action status. Terminal/superseded buttons are
inactive. Lost decision response triggers authoritative readback before claiming failure;
if readback also fails, show unknown status and safe retry instructions. Do not say
'nothing was created'. Multiple clicks are blocked in UI for usability; server safety
still enforces idempotency.

Render safe text, not model-supplied executable HTML. Tables preserve null versus zero,
units and dates, with headers/overflow. SQL is collapsible with exact binds. Keyboard
access/focus, visible errors and narrow/wide layouts are required. Plain CSS, no external
fonts/assets needed at runtime. Show reference date and unobtrusive embedding-fallback
warning. Missing credentials allow health/history but genuine processing gives an honest
configuration failure/fallback as appropriate; never production scripted answers.

## Planned scenarios

| ID | Given / when | Observable assertions |
| --- | --- | --- |
| S-050 | Unknown thread or malformed request | Agreed meaningful HTTP status/body; no hidden thread creation |
| S-051 | Blank/oversized input or invalid decision enum | Typed validation failure; no state/source mutation |
| S-052 | Confirm without matching pending action | Conflict/not-found policy, zero inserts |
| S-053 | Concurrent messages in one thread | Agreed serialization/conflict, deterministic order; other threads not globally blocked |
| S-054 | Another thread references an action ID | Rejected before source write |
| S-055 | Network retry/lost response on message/decision | Request policy explicit; same action cannot duplicate booking |
| S-056 | Terminal action viewed in old history | Updated terminal card; no active duplicate-create button |
| S-057 | Storage/checkpoint unavailable | Honest error/readback state, no invented empty history or false success |
| S-058 | Server emits invalid/unknown response block | Response validation or explicit fallback; no silently omitted evidence |
| S-059 | Open/create thread and send message | Server-ordered transcript, usable input, correct association |
| S-060 | Text/table/SQL results including nulls, zeros and wide columns | Safe faithful rendering, readable evidence and SQL parameters |
| S-061 | Confirm/Reject from card | Calls agreed endpoint with saved action ID and explicit decision |
| S-062 | Slow/failed request, missing model configuration | Visible loading/error, usable retry/readback, no fake answer |
| S-063 | Reload with pending or completed action | Loads API transcript/action status; URL alone is not transcript |
| S-064 | Keyboard/mobile/wide result/untrusted markup | Accessible decisions/focus/overflow; markup does not execute |
| S-065 | Fresh clone following final documented setup | Starts locally with only model runtime service; no undocumented prior artifacts |

Implemented checks cover a subset; see the linked tests and verification limits below. Future contract tests use API clients, UI tests use browser
interactions, and a subprocess restart test verifies actual persisted files.

## Implemented check coverage

See [topic checks](../../tests/test_api.py) and [current verification](../development/verification.md).
Real Azure quality and any scenario not explicitly mapped there remain unverified.
