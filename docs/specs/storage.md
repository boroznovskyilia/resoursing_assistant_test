# Persistence schema and recovery contract

Status: design schema, implemented storage contract; exact checks linked below. Requirements R-04/08/11/13/21.
[Booking](booking.md) owns source-write semantics; [API/UI](api-ui.md) owns public state.

## Files, connections and initialization

| File | Contents | Access |
| --- | --- | --- |
| Original source.sqlite | Supplied immutable dataset | Read-only input; never overwrite or use as writer target |
| Working subject SQLite | Source copy, confirmed soft bookings, own booking_actions | Model RO connection; separate trusted action/writer connections |
| App SQLite | threads, requests, messages, LangGraph saver tables, local semantic cache | Application/checkpointer/index only; never model SQL |

Only absent working files are initialized. Restart opens existing files and preserves
progress. Validate schema version/source fingerprint; fail visibly on corrupt or
incompatible state rather than reset. Original source tables gain no UPDATE/DELETE
and no INSERT except allowed bookings in the working copy. Own auxiliary tables may
be inserted/updated; that permission does not extend to source rows.

Use explicit short transactions and foreign_keys=ON on writers. Connections must obey
the chosen thread/async ownership rules. Never keep a writer transaction or event-loop
block around an LLM call. One backend worker with per-thread operation admission is
the supported topology; database constraints/transactions still protect action races.
SQLite offers no per-table database user/GRANT isolation. File access, read-only URI,
authorizer and limited trusted writer methods are the practical boundary.

During authorized setup package the supplied mock database as a local reproducible
input and document its fingerprint/copy command; no hard-coded Downloads path may be
needed by fresh-clone runtime. Runtime copies, app state, logs and credentials are
ignored by Git. No database file is copied or migration run during this design task.

## Subject-side booking_actions

One own table stores exact proposal and receipt together. Required logical columns:

| Field | Meaning / constraint |
| --- | --- |
| action_id | Opaque primary key, established once |
| thread_id, origin_request_id | Owner thread and stable preparation request; pair unique |
| person_id, engagement_id | Valid subject FKs |
| start_ts, end_ts, minutes | Exact UTC half-open interval, positive whole minutes, start < end |
| display_snapshot | Validated JSON of names/code, visible dates, hours, assumptions and warnings actually shown |
| status | pending / confirmed / rejected / superseded |
| booking_id | Nullable FK; unique when set; required iff confirmed |
| superseded_by | Nullable action reference for changed terms |
| created_ts, updated_ts, decided_ts | Real UTC audit timestamps; decided_ts nullable before terminal state |

Enforce at most one pending row/thread with a partial unique index. Application checks
thread existence in app DB; no cross-file FK is claimed. Enforce status/receipt checks
on own table, stable origin uniqueness and booking_id uniqueness. Exact terms/snapshot
are immutable after creation; only decision/status/receipt fields change.

Replacement transaction marks the old pending action superseded and inserts the new
pending action with a new ID; link superseded_by within the same subject transaction.
A crashed preparation replay looks up (thread_id, origin_request_id) and returns that
action, not a fresh one. An intentionally new request may create identical business
terms only after the prior action is terminal; business-tuple dedup is not required.

Confirmed source booking and status/booking_id receipt commit in one subject transaction.
The app DB cannot atomically commit with this file; reconciliation is explicit below.

## App-side logical records

| Record | Required logical data and invariants |
| --- | --- |
| threads | thread_id, created/updated UTC times, checkpoint configuration/version; never inferred from browser history |
| requests | (thread_id,request_id) primary identity, kind, original-input fingerprint/reference, effective reference time, status, phase/checkpoint reference, response_message_id, safe error, timestamps |
| messages | Stable message_id, thread_id, monotonic per-thread sequence, role, typed blocks/text, request reference, UTC time; unique request/role output identities prevent replay duplicates |
| Checkpointer tables | Owned by langgraph-checkpoint-sqlite; do not hand-design or expose their private schema |
| Semantic vectors | Model/config identity, text hash, dimension, finite vector data, source-text reference, built timestamp; unique matching cache key |
| Semantic memberships | Source kind/PK, parent project/person, field reference, current document hash/vector key; preserve all memberships for shared text |

The request stores enough normalized input to resume without asking the browser to
resend edited text. Stable request IDs are per thread; same ID/different original text
conflicts. A summary coverage boundary prevents summarizing the same turns repeatedly.
History keeps full structured result blocks and ordered source references; checkpoints
may reference those rather than duplicate every large result in every superstep.

Deduplicate decision-history entries using action_id/decision/event identity. Repeated
Confirm/Reject may return current status but does not append another fake user action
or assistant booking-created turn. Response IDs remain stable on idempotent readback.
No automatic TTL/deletion or historical checkpoint pruning is selected for v1; disclose
local disk growth. No Store or customer profile table is needed.

## Request and action states are independent

Request: processing -> completed / partial / failed. On startup, in-flight persisted
processing requests become interrupted. Explicit Resume returns interrupted -> processing,
then a terminal outcome, or a terminal recovery error. A normal human-action wait is
request completed with action pending, not request processing/interrupted.

Action: pending -> confirmed / rejected / superseded. Repeat same terminal decision
returns the saved result; opposite or stale decision conflicts. A source transaction
failure leaves pending. A new unrelated read cannot clear/replace pending_action_id.

A completed response is idempotently returned without rerunning the graph. Canonical
action status is overlaid on historical confirmation cards, so old cards cannot create
again. No history or GET/health read implicitly runs paid model work or inserts bookings.

## Reconciliation matrix

| Durable state | Recovery |
| --- | --- |
| User message/request saved, no completed graph stage | Mark interrupted after restart; Resume from known input/checkpoint, no duplicate message |
| Action saved, card/checkpoint missing | Find by origin request; use exact stored terms to materialize/recover card and waiting state; no booking insert |
| Completed read response exists, request status lagging | Restore terminal request from durable response identity; no second model answer |
| Pending action + saved human wait | Reload current card/status; Confirm/Reject works after normal restart |
| Confirmed receipt, app history/checkpoint lagging | Receipt/booking_id settle success; repair display/history and graph link deterministically |
| Rejected/superseded receipt, old pending card | Render canonical terminal status; reject stale Confirm |
| Interrupted request + usable checkpoint | User Resume runs latest saved stage; unfinished node may rerun, with local budgets and idempotency |
| Checkpoint/action linkage unambiguous but behind | Reconcile known action receipt before further graph execution |
| Missing/corrupt state beyond unambiguous recovery | Fail closed with explicit recovery error; do not guess terms or erase history |

Before a new graph operation, consult canonical action/request state; app links are
references, not proof that a booking did or did not commit. GET may perform deterministic
readback/reconciliation of persisted records but cannot run the graph or model. If
safe reconciliation is impossible, show a recovery error rather than invented emptiness.

While interrupted, reject a different new message with 409 resume_required until Resume
finishes or fails terminally. Other chats remain usable. Do not introduce job queues,
background auto-resume or a cancel/discard feature. A normal pending card still permits
read questions because its preparation request is completed, not interrupted.

A terminal recovery error ends the interrupted request, not the conversation history.
It releases request admission. A later intentional message can start a new execution
from intact persisted transcript/result references and canonical action data, explicitly
acknowledging unfinished work was not recovered. Do not pretend the damaged node resumed,
reconstruct booking terms from summary, or reset the conversation silently. If those
underlying durable records are also corrupt/unavailable, report storage/recovery failure;
only a separate new chat can safely proceed. Retain damaged state for diagnosis.

## Acceptance scenarios

| ID | Scenario | Observation |
| --- | --- | --- |
| S-083 | Same request replay and same ID with changed text | Stable response/no duplicate history; changed input conflicts |
| S-084 | Kill API mid-node, reopen history, explicitly Resume | GET does not call model; one user message, safe node replay |
| S-085 | New question while interrupted | 409 resume_required; another chat works; terminal recovery failure unlocks input |
| S-086 | Normal pending action plus factual follow-up | Request completes, exact pending card survives, graph returns to wait |
| S-087 | Edit proposal then click old card | Atomic replacement; old superseded action cannot insert |
| S-088 | Subject receipt ahead of app checkpoint/history | One booking, canonical status and stable readback after reconciliation |

Implemented checks cover a subset; see the linked tests and verification limits below. Implement real SQLite constraint/concurrency tests and actual
process restart/fault injection; in-memory object recreation is insufficient evidence.

## Implemented check coverage

See [topic checks](../../tests/test_process.py) and [current verification](../development/verification.md).
Known-case Azure results and explicit AI-assisted review are recorded in [evaluation evidence](../evaluation/README.md).
Unseen quality and unmapped scenarios remain unverified.
