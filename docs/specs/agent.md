# Graph, DSPy tasks and conversation memory

Status: owner-selected contract and implemented graph. Known-case real-model results
and explicit AI-assisted review: [evaluation evidence](../evaluation/README.md).
Requirements R-03/04/07/09/11/12/28, O-02/03. Exact library interfaces are verified during
implementation; policies are defined here and in [operations](operations.md).

## Admission, routing and clarification

Each message has thread_id and a stable client request_id. Admit it once, persist its
user message and request status, then load only this thread's context. A thread has
one active operation. Message retries, interrupted work and normal waiting for a
confirmation are distinct; [API/UI](api-ui.md) defines the states.

InterpretRequest returns factual, semantic, booking, mixed or unsupported intent,
normalized task, supplied slots, semantic mode, unresolved references, assumptions
and missing information. Validate all typed output. Interpretation never authorizes
SQL privileges or a write. Names and model-selected IDs are checked against source.

| Situation | Required behavior |
| --- | --- |
| Missing booking person/project/hours/period | Ask for missing fields, keep validated supplied fields |
| Two people share a full name | Show distinguishing ID/region/role; ask, never first-row select |
| 'The second one' | Use exact persisted displayed IDs/order; clarify if multiple lists plausible |
| Conflicting name and selected ID | Clarify conflict, do not silently prefer either |
| Month without year | Use reference year and show assumption, even if month is in the past |
| Experienced people recommendation | Explain role/years/skill criteria; no universal invented cutoff |
| Exact count with undefined experience threshold | Clarify threshold, then freeze criterion for every batch |
| Empty valid result | Return empty under stated conditions, no retry to manufacture matches |
| New topic during clarification | Route independently; do not leak old booking slots into unrelated tasks |
| Hard booking/delete/update or external facts | Explain unsupported operation/missing data; no source mutation |

Composite find-and-book requests retain supplied booking slots. Retrieve/offer candidates,
clarify the intended person if necessary, then prepare the immutable action. Being
first in an internal ranking is not permission to silently book that person.

## Controlled stages and transitions

| Stage | Operation | Next / bounded failure |
| --- | --- | --- |
| load_context | Reconcile durable request/action, load references and bounded context | compact if needed, then interpret; explicit recovery error if irrecoverable |
| compact | DSPy SummarizeHistory over older complete turns | preserve exact state and full transcript; safe-window/error on failure |
| interpret | DSPy InterpretRequest | validate, then resolve or clarify/refuse |
| resolve | Exact source lookup and displayed-reference validation | missing/ambiguous -> saved clarification; enough -> route |
| plan_reads | DSPy PlanReads with compact complete allowed schema | permission/resource checks; one shared format/SQL repair |
| execute_reads | Read-only source connection, typed results/provenance | empty normal; independent failures can yield partial results |
| retrieve_candidates | Exact eligible IDs/text; local vector shortlist or all candidates | embedding failure -> full eligible-text scan |
| assess_candidates | DSPy AssessCandidates for each finite token-bounded batch | validate IDs/evidence; retain uncertain/unprocessed status |
| rank_candidates | DSPy RankCandidates over assessed evidence | validate ordering/IDs; source-ID tie fallback; no invented facts |
| prepare_action | Normalize/revalidate, persist stable immutable action | save card and graph link; no source booking |
| await_action | Replay-safe LangGraph interrupt for a typed external event | read message, terms change, or explicit decision event |
| apply_decision | Fixed writer using stored action; no model | atomic receipt; then reconcile exact status |
| compose | Deterministic table/metric/SQL/card blocks + optional DSPy explanation | partial data if explanation fails; never rewrite committed receipt |
| persist_response | Save response, result references and request terminal status | return ordinary HTTP JSON |

There is no free agent/tool loop. One shared planner repair covers format or syntax/
schema errors. Permission violations are terminal. No arbitrary global six-call cap
exists; finite batches and local retry budgets determine actual work.

## Interrupts, read questions and new messages

Keep the interrupted node small and replay-safe: load the exact action, call interrupt,
then validate the typed resume event. Do not generate new terms, insert a booking or
append duplicate history before interrupt. Node resume may run from its beginning.

While a proposal is pending, a message endpoint resumes the waiting graph with a typed
message event containing the already admitted request_id. It routes through the normal
read/interpretation path while retaining pending_action_id. A read answer completes its
request and returns to await_action. It does not replace the pending proposal with the
latest factual task. Proposal changes create a new action and supersede the old one.
A second independent booking asks the user to finish the first action.

Confirm/Reject is a typed API decision, not model classification of 'yes'. Execute the
fixed transactional decision from the saved action, then resume/reconcile graph using
the durable receipt. If graph synchronization fails after commit, preserve success and
repair the graph from that receipt before further execution; do not call the writer
again blindly. GET performs deterministic readback only, never graph/model execution.

Normal saved interrupt means request completed + action pending. A crashed in-flight
request means request interrupted and requires explicit Resume. Before another question
in that thread, finish recovery or terminate it with an honest recovery error. Opening
another chat is always possible. See [storage](storage.md) for the recovery matrix.

## Explicit DSPy signatures

These contracts are implemented by typed DSPy signatures and Pydantic models. Every generative call,
including repair/summary, must use DSPy with typed fields. Start with Predict where
sufficient; an optimizer or separate judge is not part of the baseline.

| Signature | Inputs | Typed outputs | Code validates |
| --- | --- | --- | --- |
| InterpretRequest | Message, compact actual source schema, reference time, summary/recent context, exact active task, displayed result references, pending action metadata | intent, normalized_task, slots, semantic_mode, criteria, missing_fields, clarification, assumptions | Enums/shapes, supported intent, supplied field consistency |
| PlanReads | Explicit factual/semantic intent, normalized task, all allowed compact schema/rules, resolved parameters, optional prior repair error | answer plus up to three additional_answers: query_id/purpose/sql/parameters | Unique query IDs/binding names, statement count, params, read policy, execution limits |
| PlanProjectChecks | Frozen project criteria | Summary predicate/scope, risk predicate, AND/OR operator | At least one predicate; source-field assessment and parent joins preserve both conditions |
| AssessCandidates | Frozen criteria, source-linked texts, exact relevant facts | Per candidate: source_id, match/no_match/uncertain, evidence references, reasoning | IDs belong to batch; quotations/spans exist; exact facts are source-backed |
| RankCandidates | Criteria, assessed candidates, verified facts/evidence, requested count | Ordered source IDs and per-item suitability reasons | IDs/uniqueness/order length, no new facts or source-free qualification |
| ExplainResults | Question, exact metrics/rows, source excerpts, completeness and issues | explanation and source-linked item justifications | Required evidence exists; no replacement math or fabricated fields |
| SummarizeHistory | Prior summary and older complete turns | Bounded summary of goals/choices/unresolved issues | Budget and preservation of exact active data outside summary |

Small assessment/ranking steps may be merged when their combined typed contract stays
inspectable. Embedding API calls are retrieval, not a generative signature. Fault
providers are test-only, never production answer substitutes.

PlanReads carries bindings as a required list of typed `{name,value}` records. The
DSPy Structured Outputs adapter closes object properties and otherwise erases arbitrary
nested dictionary keys; an adapter-level regression guards this boundary. Code converts
the records to SQLite named bindings. Executed SQL API blocks still use a parameter
dictionary. Public catalogue values accompany schema; source IDs/answers are never guessed.

## Working state contract

| Field group | Contents / lifetime |
| --- | --- |
| Identity | thread_id, current_request_id, request kind, phase; server-controlled |
| Current input | Original message reference, normalized task and effective_reference_ts |
| Context | summary, summary coverage boundary, references to recent complete turns |
| Exact task | Typed filters/slots, validated IDs, missing fields, assumptions, frozen semantic criteria |
| Displayed results | message/block IDs, entity kind, ordered IDs, stable source/evidence references |
| Execution | Read-plan/result references, processed semantic batches, coverage/uncertain IDs, local repair counters |
| Pending link | pending_action_id only as reference; exact canonical action lives in subject DB |
| Response | Current block/evidence references, issues and completion metadata |

Never persist API keys, SDK clients, open connections or locks in graph state. Runtime
configuration supplies those. Keep large rows/candidate vectors in their durable result
or index storage; pass bounded relevant slices to a model. Exact interrupted-node
inputs remain reconstructible. Clear obsolete transient arrays/counters between tasks.

Full transcript is durable ordered UI history. A checkpoint is working execution state.
Neither implies every saved message is sent to the model. A new thread gets no other
thread's context. Shared subject bookings are facts, not cross-thread personal memory.
Completed booking slots do not silently become defaults for a new unrelated booking.

## Context and compaction

Per call: 10000 rendered input tokens, 2000 output; recent turns ~3000 and summary ~700
inside the input budget. Trigger compaction near 8000. Count actual DSPy signature,
format instructions, examples, schema, results and candidates; do not count only chat.

Summarize only older complete turns, retain recent complete pairs and exact active
fields/order. Never truncate critical user instructions, IDs or proposal terms. Reduce
optional explanatory evidence first; deterministic large tables need not pass through
ExplainResults. If mandatory input still cannot fit, ask to narrow or return context
budget error before executing. Single oversized input is not silently shortened.

On failed summary retain original transcript and last successful state. Use the prior
summary and safe recent complete window only when mandatory current data still fits;
otherwise fail clearly. No post-commit summary is required to report booking success.
No automatic TTL is selected. Compaction does not imply deletion of transcript or old
checkpoint records; disclose storage growth.

## Planned scenarios

| ID | Given / when | Required observation |
| --- | --- | --- |
| S-013 | Two people share the entered name | Agent asks for disambiguation; uses IDs and does not write |
| S-014 | Requested external fact or unsupported invoice attribution | Explains exact missing data; may return clearly separated known facts |
| S-015 | Process restarts after completed factual turn | Existing thread history and working context resume |
| S-016 | New thread is created after another has selected a person | No inherited selection or pending action |
| S-017 | Conversation exceeds history budget | Compaction is bounded; full transcript remains available |
| S-018 | Summary omits or distorts a booking detail | Exact persisted typed fields govern proposal/confirmation |
| S-019 | User says 'the second one' after a ranked table | Resolves displayed ID, not new alphabetical order |
| S-020 | User changes hours/period during clarification | Affected fields/calculations update; unrelated old fields do not leak |
| S-021 | Provider or compaction fails/time budget expires | Explicit failure; original history retained; no source mutation |
| S-022 | Static review of every model call path | DSPy signatures include interpretation, semantic selection, explanation, repair and summary |

Implemented checks cover a subset; see the linked tests and verification limits below. These are written specifications for later unit/integration/model
tests, not a claim of execution or correctness.

## Implemented check coverage

See [topic checks](../../tests/test_agent.py) and [current verification](../development/verification.md).
Known-case Azure results and explicit AI-assisted review are recorded in [evaluation evidence](../evaluation/README.md).
Unseen quality and unmapped scenarios remain unverified.
