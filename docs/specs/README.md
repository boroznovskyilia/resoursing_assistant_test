# Specification and scenario map

Status: behavioral acceptance inventory with an implemented local application and
linked checks. Written scenarios are not automatically executable/passed; consult
[current coverage and limits](../development/verification.md) and
[task evidence](../plans/progress.json). Actual Azure run/review evidence is linked from [README](../../README.md).

## Primary specifications

| Topic | Primary document | Main requirements | Written scenarios |
| --- | --- | --- | --- |
| Source obligations and owner boundaries | [Requirements](requirements.md) | O-01–O-07, R-01–R-30 | Traceability inventory |
| Data grains, joins and observed anomalies | [Data](data.md) | R-05/07/13/28 | S-001–S-014 plus domain cases |
| Intent, clarification, graph and memory | [Agent](agent.md) | R-03/04/11/12, O-03 | S-013–S-022 |
| Read permissions and structured/text retrieval | [Retrieval](retrieval.md) | R-05/06/07/13/14 | S-001–S-012, S-023–S-036 |
| Proposal, decisions and atomic recovery | [Booking](booking.md) | R-08–R-11/13/14 | S-037–S-049 |
| API contracts and browser interaction | [API and UI](api-ui.md) | R-15–R-21/24/30 | S-050–S-065 |
| Persistence and reconciliation | [Storage](storage.md) | R-04/08/11/13/21 | S-083–S-088 plus booking/API cases |
| Limits, retries and local diagnostics | [Operations](operations.md) | R-04/06/11/13/14/20/24/25 | S-077–S-082 |
| Oracles, scoring, isolation and submission | [Evaluation](evaluation.md) | R-22–R-30 | S-066–S-076 |

There are 88 numbered written scenarios across the behavioral documents. A scenario
can contain related variants (e.g. concurrent Confirm/Confirm and Confirm/Reject), so
this is not a claim of 88 implemented or independently executed tests.

## Implemented verification layers

Deterministic pytest checks, real SQLite/API integration, actual process/restart and
Chromium UI tests are linked in [verification](../development/verification.md).
The actual-model22-case runner uses isolated production API subprocesses; results
and explicit review status are linked from [README](../../README.md).
Each future behavior change updates relevant existing checks and this scenario map;
do not claim an unrun scenario passed or change expected behavior to hide a failure.

## Core safety and continuity checks

Before release demonstrate: no pre-confirm write; repeated Confirm one booking; Reject
zero; stale/superseded card blocked; wrong-thread action blocked; normal restart works;
post-commit lost-response readback; message request deduplication; explicit Resume and
GET without model calls; per-thread busy with another thread progressing; compaction
preserves exact fields/order; source invariants hold. These checks are mandatory and
cannot be averaged away by an evaluation score. See the explicit executed check coverage; unverified variants remain open.
