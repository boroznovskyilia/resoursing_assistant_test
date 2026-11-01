# Current backend evaluation

The synchronous SQLAlchemy/pydantic-settings refactor is validated on runtime23487e3:
**22/22 from one complete genuine Azure run20261101T190046Z_a1cdc9**, after7 explicit
AI-assisted source reviews (15 automatic passes). Both preceding post-refactor failures
are retained. [Current evidence, delivered answers and hash lineage](backend-refactor-20261101/README.md).

The previous release evidence below remains historical and unchanged.

# Previous release — genuine Azure evaluation evidence

Run `20261031T211131Z_822c63`, runtime checkpoint `ae6e196`, API version `2024-10-21`,
chat `gpt-4.1-mini`, embeddings `text-embedding-3-small`.
Reference date `2026-04-01T00:00:00Z`. Source SHA-256 `8d00b91ae6aa23bbcf0d807c2e51fa6a45f7017a6557a4f51d11cfc82bfb4259`.
Inference runtime is unchanged from the checkpoint above. Offline scorer checkpoint
`ebd3f14` corrected a person-name column alias; no inference or writes were replayed.
The original report remains [unchanged](inference-results.json); report/answer/scorer
hashes and the grading method are recorded in results.json.

All 22 cases are passed from this **one complete genuine inference run**. The initial
scorer reported 14 passes, 7 pending reviews and 1 false negative for a `name` alias.
Whole-run offline rescoring preserves every answer and recorded source/write observation;
it never combines cases from different runs. After corrected scoring, before review: 15 automatic passes
and 7 review_required. Seven free-text cases were inspected against original source
by **Codex AI-assisted source inspection**, not an independent human reviewer or a
second DSPy judge. [Recorded decisions](reviews.json) cannot override automated failures.

- [Final report](results.md) and [machine-readable result](results.json).
- [Unreviewed automatic report](automated-results.json), [complete delivered answers](answers.json).
- [All 20 completed run reports](history.json), including failures and preflights.
- [Measured usage, latency, recall and storage](measurements.json).

The runner starts isolated production APIs with genuine Azure calls. Booking checks
include no pre-confirm write, exact terms, Confirm, Reject, restart and repeat Confirm;
source invariants are checked across all 24 original tables. No oracle is loaded into
runtime prompts. Source/gold inputs are unchanged. Earlier failed runs are retained,
not replaced with selected passing cases. These are development/acceptance questions,
not unseen held-out tests or a repeated-run reliability estimate.

Observed totals: 66 chat attempts / 7 embedding attempts;
247,401 chat tokens / 18,073 embedding tokens.
Case latency median 9.271s, p95 17.957s, total 258.442s.
Cold source-vector recall@40 on public gq-07 strong matches: 9/10;
delivered shortlist overlap 7/10 (minimum 4).
Actual Azure billed cost and production load were not measured.

Reproduce with `make evaluate`; free-text cases intentionally exit2 pending explicit
review. Apply a **new run-bound** review after inspecting its outputs via the command
in the [evaluation contract](../specs/evaluation.md). Copying old reviews is not validation.
Local raw DBs, process logs, read plans and receipts are under `.runtime/evaluation/20261031T211131Z_822c63/`;
these ignored files are not needed to read the exported evidence above.

## Original run history

Reports below retain their original scoring and review status. Code changed during
development; these are not repeated reliability trials of one fixed model pipeline.

| Run | Cases | Passed | Failed | Review required | Not run |
| --- | --- | --- | --- | --- | --- |
| 20261031T184224Z_59f5f4 | 22 | 0 | 0 | 0 | 22 |
| 20261031T192453Z_9f3790 | 22 | 0 | 0 | 0 | 22 |
| 20261031T192702Z_226c92 | 22 | 2 | 18 | 2 | 0 |
| 20261031T193204Z_b4d5b4 | 5 | 1 | 4 | 0 | 0 |
| 20261031T193403Z_3fcbcf | 5 | 3 | 2 | 0 | 0 |
| 20261031T193549Z_59fd97 | 2 | 1 | 1 | 0 | 0 |
| 20261031T193721Z_a30e07 | 22 | 8 | 11 | 3 | 0 |
| 20261031T194511Z_5bd30b | 9 | 1 | 8 | 0 | 0 |
| 20261031T195102Z_1d751d | 7 | 1 | 5 | 1 | 0 |
| 20261031T195918Z_d76f7e | 6 | 2 | 1 | 3 | 0 |
| 20261031T200441Z_36a90d | 22 | 9 | 6 | 7 | 0 |
| 20261031T201705Z_55d4b0 | 6 | 3 | 3 | 0 | 0 |
| 20261031T202538Z_94c01d | 3 | 2 | 1 | 0 | 0 |
| 20261031T203003Z_f107e4 | 22 | 13 | 4 | 5 | 0 |
| 20261031T204907Z_398bd2 | 4 | 2 | 1 | 1 | 0 |
| 20261031T205112Z_fe9cfc | 22 | 13 | 2 | 7 | 0 |
| 20261031T205637Z_c79d47 | 22 | 14 | 1 | 7 | 0 |
| 20261031T210122Z_5a22e6 | 22 | 14 | 1 | 7 | 0 |
| 20261031T210615Z_09f103 | 22 | 13 | 2 | 7 | 0 |
| 20261031T211131Z_822c63 | 22 | 14 | 1 | 7 | 0 |
