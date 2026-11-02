# Task workflow

## Start and resume

Read [AGENTS.md](../../AGENTS.md) for applicable authorization and
[handoff](../plans/handoff.md) for recovery. Run `make docs`, `make progress` and
`git status --short`. Reconcile saved status with actual files and checks before
selecting work; an interrupted session may have changed files without saving status.
Read the next eligible [work package](../plans/implementation.md) and relevant primary
contracts, then inspect existing code, callers and checks. Add a task definition and
matching progress entry for new work rather than reusing an unrelated completed task.
Keep at most one task in_progress; continue eligible work without routine approval requests.

## Changes and contradictions

Start this procedure yourself whenever an owner changes a condition, a requirement or
document conflicts with another source or code, a specification gap is found, or a
check fails. Use the existing task; create a follow-up if the issue is outside it.

1. Establish the expected behavior and its authority. Compare source requirements,
   accepted owner decisions, explicit engineering defaults and observed facts using
   the [document ownership map](../document_writing.md#document-ownership) and
   [source catalogue](../reference/README.md). A newer explicit owner instruction can
   replace an earlier choice within its stated scope; file recency or current code
   alone cannot settle a requirement conflict. Preserve original source artifacts.
2. Before dependent edits, record a short impact entry in the task's progress evidence:
   the trigger and requirement/decision IDs or document sections; affected contracts
   and scenarios; code/callers, configuration, stored data, API/UI and checks; and
   checks needing rerun. Search existing IDs, links and callers. Mark categories that
   do not apply and expand the entry when another dependency is discovered. This is
   a concise task record, not a second specification or a new status document.
3. Apply the human-decision boundary below. If a new owner decision is needed, prepare
   the conflict, concrete user-visible consequences, viable options and a recommendation
   before asking. Save the pending question/options/impact in the task blocker and mark
   only dependent work blocked. Set current_task to null or another eligible in_progress
   task and update next_action. Elapsed time is not approval. Continue independent work
   while awaiting the answer. Otherwise proceed without an approval request.
4. Reassess affected task acceptance and evidence before claiming the new behavior.
   Reopen a task whose acceptance no longer holds or add a follow-up for a changed contract;
   keep the old task as historical if its original completion remains valid. Record
   which prior results no longer establish current acceptance and which checks must
   run. Preserve original reports, failures and review decisions unchanged.
5. Once the meaning is settled, update affected contracts, scenarios, checks and
   implementation in the same task. If an accepted decision is replaced, record which
   one the new choice supersedes and update references to the active rule. A bug against
   an unchanged requirement needs a reproducing check and a code fix; never weaken the requirement
   or oracle to hide failure. For documentation-only corrections, preserve existing
   behavior and explain the source of the correction. Reuse existing helpers and
   dependencies; complete affected callers, configuration and rendering together.
6. Run focused checks, fix failures and perform the completion review below. Save
   actual results and the next action in progress.json before handing off or compacting.
   After a failure, add the smallest useful safeguard: a scenario, clearer instruction
   or command. Add more process only when a recurring failure justifies it.

## Human decisions

Use human-in-the-loop (HITL) according to meaning, not the size of the diff.

| Situation | Agent action |
| --- | --- |
| Code violates an unambiguous active requirement | Fix code and relevant checks independently |
| Documentation contradicts an already accepted decision, or lacks an explanation of an unambiguous rule | Correct or clarify it independently, preserving the agreed meaning |
| A technical choice stays within agreed behavior and constraints | Choose the smallest complete solution and verify it |
| Requirements conflict or allow materially different user-visible results | Ask the owner to resolve the ambiguity before dependent changes |
| A proposal changes agreed scope, behavior, constraints or acceptance | Obtain the owner's decision before dependent changes |
| An explicit owner instruction already resolves the exact change | Record and apply it without asking for the same approval again |

Record the owner's answer, scope and rationale in the decision register when it changes
the durable baseline; clear the task blocker and resume through the same impact review.
An autonomous agent may discover and propose a business change, but cannot authorize
its own proposal. Publishing, deployment and external messages still require applicable
owner authorization; prepare reviewable artifacts before that boundary.

## Completion review

Before marking done, review the final diff against the impact entry and establish:

- Which requirement/decision or documentation correction the result implements.
- Whether affected contracts, scenarios, code/callers, config/data and user instructions
  agree, including references to any replaced rule.
- Which actual commands/results establish acceptance for this change and what remains
  unverified. Historical passes alone do not establish changed acceptance.
- Whether any contradictions, assumptions or pending owner decisions remain. Record
  concrete limits/blockers; do not mark acceptance done with required checks or decisions missing.

Run `make check`, `git diff --check` and relevant existing application checks. A
documentation-only change needs documentation/tooling checks and a manual consistency
review; application/model reruns need a behavioral reason. Link checks/test files and
record observed results. Report what changed, why, verification and material limits.

## Evidence and continuity

[progress.json](../plans/progress.json) is the single live task-status/evidence record.
Update status, current_task, next_action, updated_at, blockers and checks after meaningful
boundaries and before handoff. Save complete JSON via temporary file and atomic replace,
then run `make progress`. Keep secrets, raw prompts and environment dumps out of it.

Keep evidence scoped to its contract, runtime/checkpoint and verification layer. Separate
deterministic doubles, real SQLite/API/process/UI behavior and genuine Azure quality.
A previous passed result proves only its recorded scope; document reuse with a reason
or rerun affected checks. Do not overwrite historical results or copy old free-text
reviews to a new run. Preserve review_required and actual failures.

Tooling validates saved structure, IDs, statuses and local link targets; it does not
verify evidence truth, task dependencies, scenario coverage or semantic consistency.
The completion review is the agent's responsibility. No check exists yet that proves
future agent compliance with this procedure or reliable recovery after actual context loss.

After completing a task, continue the next independently eligible task. Missing Azure
credentials block live-model checks only. An owner decision blocks only dependent work.
If nothing eligible remains, save the pending question and next action and report the
blocker. This file-based workflow does not start an agent or background job by itself.
