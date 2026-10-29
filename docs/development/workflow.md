# Task workflow

## Orientation

Run `make docs`, read the product core and the documents relevant to your task.
Find affected code, its callers, and existing checks.
Clarify expected behavior and the consequences of the change. Do not read every document.

## Implementation

For nontrivial behavior, first formulate verifiable examples:
"given these conditions, when this action occurs, expect this observable result."
Use the chosen stack's testing tools; Gherkin is optional.
A small reversible change may not need a separate plan or a new test.
For a complex task, create a temporary [plan](../plans/README.md).
Make the smallest complete change and run the relevant checks.

## Updating knowledge

Read the [documentation rules](../document_writing.md).
Compare the documents you used with the resulting behavior and commands.
Update affected knowledge in the same task. If no documentation changes are needed,
do not create a ceremonial report in the document tree. Remove completed plans
that are no longer useful. Preserve the reason behind an important choice in
[decisions](../decisions/README.md).

## Completion

Run `make check` and the actual [application checks](verification.md).
In the final response, explain what changed, how it was verified, and what remains unknown.
Documentation checks do not replace behavioral checks.

## Improving the environment

When an agent struggles, fix the specific cause: an unclear document name,
a contradictory rule, a missing scenario, or an awkward command.
For a recurring problem, repeat the original task in a fresh session and compare results.
Transfer a lesson to other projects only after checking its broader applicability;
the separate Control Center supports that process.
