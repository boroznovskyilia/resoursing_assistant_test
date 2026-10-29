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

## Connecting documents to implementation

For a behavioral rule, reference specific executable scenarios and how to run them.
For an operation, provide its command, prerequisites, and observable result.
When a check has not been implemented, explicitly state "no check exists yet."
Do not call text an executable specification unless it can actually be executed.

## When to update

When behavior, interfaces, commands, or constraints change, review affected documents
as part of the same task. Explicitly label unverified assumptions.
If code contradicts a requirement, do not rewrite the requirement just to make them match.
Agree on changes to goals, product constraints, or the meaning of a rule with the owner.
After a failure, add the smallest useful safeguard: clearer navigation, a scenario,
or a command. Add a more elaborate process only when the problem recurs.

## Plans and decisions

Keep the current steps of a complex task in [plans](plans/README.md).
After completion, delete plans that are no longer useful; Git preserves their history.
Move the lasting reasons behind choices to [decisions](decisions/README.md).
Do not use the plan for a past change as the description of the current product.

## Link checks

`make check` verifies that ordinary inline Markdown links point to existing local targets.
Use relative paths without spaces. The checker does not validate external URLs,
heading-only links, reference-style links, or fragment identifiers. It does not
verify meaning or run the application. Execute commands shown in examples separately,
only when appropriate and safe in the current environment.
