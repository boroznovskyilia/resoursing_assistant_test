# Documentation rules

## What to preserve

Write documentation, specifications, and durable instructions in English.
Preserve current rules, reasons behind decisions, and repeatable verification procedures.
Do not turn conversations, raw logs, or every intermediate agent action into instructions.
Update an existing document when it is sufficient instead of creating another one.

## Discoverability

Name each file after its topic. Give each topic one primary document.
Use descriptive headings; start with a short explanation, then provide details.
Connect related topics with ordinary relative Markdown links.
Do not require reading the entire tree at the start of every task.

## Document ownership

| Information | Primary location |
| --- | --- |
| Original assignment and source facts | [Source catalogue](reference/README.md) and preserved inputs |
| Product obligations and behavior | [Requirements](specs/requirements.md), [scope](product/core.md) and the relevant [topic contract](specs/README.md) |
| Accepted choices, reasons and explicitly superseded decisions | [Decision register](decisions/README.md) |
| Task definitions, dependencies and acceptance | [Implementation plan](plans/implementation.md) |
| Live task status, pending questions, next action and evidence references | [progress.json](plans/progress.json) |
| Executed results and their limits | Linked test output/reports and [verification](development/verification.md); exported runs in [evaluation](evaluation/README.md) |
| Session recovery steps and host precautions | [handoff](plans/handoff.md) |

Link to the primary location instead of copying current statuses or result summaries.
Date and label historical evidence; mark replaced decisions as superseded and link
their replacement. Neither a newer file nor passing code overrides an agreed rule.
Resolve uncertain meaning through the workflow's human-decision boundary.

## Connecting documents to implementation

For a behavioral rule, reference specific executable scenarios and how to run them.
For an operation, provide its command, prerequisites, and observable result.
When a check has not been implemented, explicitly state "no check exists yet."
Do not call text an executable specification unless it can actually be executed.

## When to update

Initiate the [change/conflict procedure](development/workflow.md#changes-and-contradictions)
when behavior, interfaces, commands or constraints change, or when you discover a gap
or contradiction. It defines impact review, HITL, evidence reassessment and completion.
Clarify an unambiguous accepted rule independently; changes to its meaning need an
applicable owner decision. Explicitly label unverified assumptions. Preserve source
artifacts and historical reports rather than rewriting them to match new behavior.

## Plans and decisions

Keep the current steps of a complex task in [plans](plans/README.md).
After completion, delete plans that are no longer useful; Git preserves their history.
Retain this implementation plan while progress.json validates task IDs against it;
retire corresponding status references together before removing any definitions.
Move the lasting reasons behind choices to [decisions](decisions/README.md).
Do not use the plan for a past change as the description of the current product.

## Link checks

`make check` verifies that ordinary inline Markdown links point to existing local targets.
Use relative paths without spaces. The checker does not validate external URLs,
heading-only links, reference-style links, or fragment identifiers. It does not
verify meaning or run the application. Execute commands shown in examples separately,
only when appropriate and safe in the current environment.
