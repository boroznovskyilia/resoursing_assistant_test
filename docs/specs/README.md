# Executable scenario map

Status: no business scenarios exist yet. This file is an index, not an executable specification.

When the first rule is defined, add a row with relative links:

| Product rule | Executable scenario file | Command | Verification boundaries |
| --- | --- | --- | --- |

Keep executable scenarios with the chosen stack's tests; do not duplicate them here.
Given / When / Then can help express each example: initial conditions, an action,
and an observable result. A dedicated parser and Event Sourcing are optional.

Scenarios check stated expectations, not the completeness of all requirements.
Product rules live in the [product core and its linked documents](../product/core.md).
Execution instructions belong in [verification](../development/verification.md).
