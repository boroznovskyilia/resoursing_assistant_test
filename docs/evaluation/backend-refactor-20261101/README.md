# Backend refactor evaluation — 2026-11-01

Runtime `23487e3`, genuine Azure chat `gpt-4.1-mini` and embeddings
`text-embedding-3-small`, API version `2024-10-21`, reference April1 2026 UTC.

**22/22 passed from one complete genuine inference run** `20261101T190046Z_a1cdc9`:15
automatic passes plus7 explicit run-bound **Codex AI-assisted source reviews**.
No independent human review, held-out benchmark or repeated-run reliability claim.
No scorer relaxation, offline answer editing, best-case stitching or booking replay.
The original scorer logic is unchanged; inference received no expected answers/SQL.

- [Final report](results.md), [JSON](results.json), [unreviewed automatic report](automated-results.json).
- [All22 delivered answers](answers.json), [review decisions](reviews.json),
  [independent source field/quote checks](source-review-checks.json), [hash lineage](provenance.json).

## Retained failures

| Complete run | Runtime | Result | Evidence |
| --- | --- | --- | --- |
| 20261101T184828Z_97ba7b | e1e2714 | 14 automatic passes,7 review-required,1 factual failure | [Report](first-failed-results.json), [bad hard-hour SQL/answer](failed-hard-hours-answer.json) |
| 20261101T185409Z_8a6909 | 5fa44dd | 15 automatic passes,7 review-required; own-06 subsequently rejected | [Automatic](rejected-automatic-results.json), [after rejection](rejected-results.json), [review](rejected-reviews.json), [unsupported ranking claims](rejected-ranking-answer.json) |
| 20261101T190046Z_a1cdc9 | 23487e3 | 15 automatic passes then7 approved source reviews | [Final](results.json) |

The first failure used epoch interval differences instead of bookings.minutes.
The native reader now records physical-column provenance and the bounded read-policy
repair rejects that mistake. The second run introduced historical ACT-status years
through free-text ranking reasons. Ranking now determines order only; public reasons
retain original-field assessments. Both fixes have regression checks. Code changed
between these three runs; they are not repeated reliability trials of one pipeline.

All22 cases use isolated production API processes and SQLite files. Booking checks
cover no pre-confirm insert, exact terms, Reject, restart and repeat Confirm; source
invariants cover all24 original tables. Semantic review distinguishes full coverage
from a recommendation shortlist and staffing gaps from key-person dependency.

Local checks:103 backend tests,5 Chromium scenarios,9 tooling checks; locked setup/build
in a fresh local clone,10 final clone compatibility/config/trust checks. Existing
legacy schema/history/pending-checkpoint continuation and rollback after booking INSERT
are covered. All923 source documents have the same pre-refactor digests; source SELECT
counts are3/2/1 for people/projects/risks instead of801/151/1.

Reproduce with `make evaluate`. New free-text outputs intentionally exit2 until a new
run-bound review is performed; copying these reviews to another run is not validation.
Raw case databases/logs and all failed answers remain locally under
`.runtime/evaluation/<run_id>/`; exported JSON contains no credentials. Actual billed
cost, production load and unseen-question accuracy were not measured.
