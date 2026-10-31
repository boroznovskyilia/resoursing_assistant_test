# Soft-booking protocol and recovery

Status: implemented writer/persistence with process tests and genuine model-backed
booking checks. Evidence: [evaluation](../evaluation/README.md).
Requirements R-08–R-11/13/14. Physical schema: [storage](storage.md).

## Invariants

1. Interpretation, clarification and proposal display create no source booking.
2. Only explicit API/button Confirm of an exact saved action can insert a booking.
3. Reject changes own action state only, creating zero source rows.
4. One action inserts at most one booking, including concurrent calls/replay/lost response.
5. Created booking is kind soft, booking-domain SFT (currently status_id 13), never hard.
6. Source rows are never repaired, updated or deleted. No side-effect team/requirement row.
7. Committed receipt remains truth if graph, explanation or HTTP delivery later fails.

## Identity, fields and dates

Required: person, engagement, hours and period. Resolve exact source IDs; duplicate full
names require clarification. Selected displayed positions use the persisted displayed
order. A conflicting ID/name needs clarification. Composite find-and-book can retrieve,
ask which candidate, retain other slots, then propose. No implicit choice of 'best'.

| Field | Validation |
| --- | --- |
| person_id/engagement_id | Exist, unambiguous and checked again before commit |
| Visible period | Human start/end days inclusive; month without year uses reference year, shown explicitly |
| Internal interval | UTC epochs, start inclusive/end exclusive, nonempty ordered interval |
| Hours/minutes | Finite positive amount exactly representable as integer minutes within SQLite integer range; no silent sub-minute rounding |
| Kind/status | Server-fixed soft + lookup domain booking/code SFT; not model-selected hard/status |
| Audit fields | Real UTC now, independent of configured reference date |
| Optional links | NULL unless a justified source relationship is explicitly established |

Amanda/April/40h means person 1, engagement 1, 2400 minutes, visible April 1-30 2026,
internal `[2026-04-01T00:00Z,2026-05-01T00:00Z)`. Gold allows April30/May1 ends but has
conflicting 'inside April' wording; the half-open representation is the accepted
assumption. It is shown in DESIGN and tests, not silently hidden.

Existing maximum 960 minutes is not a validation cap: gold requires 2400. No hidden
ban on past dates, overlapping soft bookings or identical business tuples. Warn if
requested hours exceed estimated weekday capacity or known commitments suggest a
conflict, disclose approximation, but allow the soft proposal/confirmation. Missing
FTE/leave/day allocation cannot justify claiming definitive feasibility.

## Immutable preparation and pending conversation

Create stable action_id once and persist canonical fields/display snapshot keyed to
thread_id and origin_request_id before exposing a card. Replay finds that same action.
Graph checkpoints hold the link, never summary-reconstructed booking terms.

Only one pending action/thread. Read questions are allowed, preserve pending terms,
and return to the waiting stage. Free-text 'yes' prompts the user to use Confirm;
it does not write. A second independent booking asks to finish the first. A requested
change creates a new action and atomically supersedes the old one; old cards conflict.
Read/provider failures do not delete a pending proposal. No automatic expiry is selected.

## Action transitions

| Current | Event | Result |
| --- | --- | --- |
| No complete action | Missing/invalid business field | Clarify, zero inserts |
| Pending | Confirm for same thread/action | Revalidate; atomically insert one booking and receipt |
| Pending | Reject | rejected, zero source inserts |
| Pending | Change terms | Old superseded + new immutable pending action, one subject transaction |
| Pending | Read question | Preserve action, answer and wait again |
| Pending | Second independent booking | Ask to finish current action; no silent replacement |
| Confirmed | Repeat Confirm | Same booking_id/receipt, no new row |
| Rejected | Repeat Reject | Stable rejected result, no new row |
| Confirmed/Rejected | Opposite decision | Conflict; no source reversal |
| Superseded | Confirm/Reject from old card | Stale-action conflict |
| Any | Wrong thread / unknown ID | Meaningful not-found/conflict, zero source writes |

A genuinely new action with identical values after a prior terminal action is allowed.
Idempotency belongs to action identity, not a person/project/date/hours tuple.

## Fixed decision transaction

Confirm accepts action_id and decision only, never new person/date/hour values:

1. Validate request/thread/action ownership and per-thread operation admission.
2. Begin a short subject write transaction with database-level serialization.
3. Reread action. Return a compatible terminal receipt, or reject conflicting status.
4. For pending Confirm, validate exact saved fields, source entities and soft status.
5. Execute a fixed parameterized INSERT into bookings, leaving unjustified optional
   columns NULL and setting real created/updated timestamps.
6. Update the same action to confirmed with resulting booking_id and audit timestamp.
7. Commit both changes together. Then synchronize app history/checkpoint/card.

Reject uses the same serialized association/status check but updates only own action.
A transaction failure before commit leaves no confirmed source row; pending can be
retried or rejected. A failed revalidation inserts nothing, preserves the action with
clear issue, and still allows Reject. No LLM call is necessary for either decision.

No in-memory lock or graph checkpoint alone guarantees this atomicity. Receipt and
booking must share the same database transaction; app-file commits can lag and require
reconciliation. Concurrent Confirm/Confirm returns one booking; Confirm/Reject has one
terminal winner and a meaningful conflict for the other.

## Pause and failure boundaries

LangGraph resumes an interrupted node from its beginning. Keep the pause node replay-safe:
no non-idempotent insert or regenerated proposal before interrupt. Typed read/change/
decision events and canonical durable action drive subsequent routing.

| Failure point | Durable truth and recovery |
| --- | --- |
| Before proposal saved | No complete card/action; no source write |
| Proposal saved before pause/card checkpoint | Lookup by origin request, recover exact same action or explicit error |
| Waiting checkpoint saved, HTTP lost | History/readback restores same pending card |
| Normal API restart | Confirm/Reject same exact action without model regeneration |
| Writer fails before commit | Rollback; no booking without receipt |
| Commit succeeds, reply/checkpoint fails | Receipt returns existing booking_id; no second INSERT |
| Reject commits, response lost | Canonical rejected status, no insertion |
| Unrecoverable checkpoint/linkage | Explicit recovery error; never invent terms or replace old thread with empty state |

GET never creates a booking. App readback overlays canonical status onto old cards.
The normal restart and all commit-boundary claims require actual subprocess and fault
checks during implementation; no such evidence exists yet.

## Planned scenarios

| ID | Given / when | Observable assertions |
| --- | --- | --- |
| S-037 | Complete booking request produces proposal | Exact displayed fields, durable action; source bookings count/hash unchanged |
| S-038 | Confirm Amanda/ENG-2026-0001/April/40h | Exactly one row: person 1, engagement 1, soft/SFT, 2400 minutes, agreed timestamps |
| S-039 | Reject proposed booking | Zero new source rows; user sees rejected/no booking |
| S-040 | Same Confirm repeats, then opposite decision | Stable booking_id on repeats; opposite decision conflicts |
| S-041 | Kill and recreate the API process before decision | Same thread, exact proposal and successful Confirm/Reject |
| S-042 | Zero/negative/NaN/infinite/sub-minute hours, invalid dates or reversed interval | Clear validation/clarification; no source change; 40h remains permitted |
| S-043 | Ambiguous person, unknown project or conflicting selected ID | Disambiguate/reject safely; never first-row selection |
| S-044 | Commit succeeds but response/checkpoint update fails | Retried decision/history return one existing booking, not duplicate |
| S-045 | Crash between proposal persistence and pause checkpoint | Recover same immutable proposal or explicit fail-closed recovery; no source insert or changed terms |
| S-046 | Concurrent Confirm/Confirm and Confirm/Reject | One terminal state; at most one booking; meaningful conflict |
| S-047 | Source/action terms change or a stale card is used | Revalidation and action/thread checks prevent stale or cross-thread write |
| S-048 | Ask for hard booking, deletion, update, or retrieved text says to confirm | Unsupported action/injected authority cannot mutate source |
| S-049 | Compare full source state before/after each case | Only allowed confirmed booking inserts differ; other tables and original supplied file unchanged |

Implemented checks cover a subset; see the linked tests and verification limits below. Future tests include unit validation, SQLite integration/concurrency,
fault injection and actual subprocess/API restart; model quality is a separate layer.

## Implemented check coverage

See [topic checks](../../tests/test_storage.py) and [current verification](../development/verification.md).
Known-case Azure results and explicit AI-assisted review are recorded in [evaluation evidence](../evaluation/README.md).
Unseen quality and unmapped scenarios remain unverified.
