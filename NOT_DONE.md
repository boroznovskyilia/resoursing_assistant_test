# Remaining delivery work and limits

The complete genuine Azure 22-case run and explicit AI-assisted source review are
recorded in [evaluation evidence](docs/evaluation/README.md). All delivered values,
required booking behaviors and source invariants passed from that one run, after an
offline scorer correction for a visible name alias. Original answers/reports are preserved;
no inference or writes were replayed. Earlier failed development runs are retained. This does not establish universal accuracy.

## Remaining delivery work

- Record the submission's three representative conversations and demo video, including
  an actual API restart before booking confirmation. Evaluation already exercises the
  model-backed restart/Confirm/Reject paths, but no submission video has been recorded.
- No remote repository publication, deployment, sharing or submission has occurred.
  Those require the owner's applicable scope and real repository/demo links.
- Free-text review was performed by Codex through AI-assisted inspection of actual
  source records and all delivered reasons. No independent human review, held-out
  benchmark, repeated-run reliability estimate or production-load test was performed.
- Actual Azure billed cost was not measured. Token usage, attempts, latency, public
  strong-match vector recall and representative storage growth were measured.

## Deliberate prototype limits

One local user/common dataset and one API worker; no auth/tenants/Store/streaming,
external vector/monitoring service, optimizer, admin CRUD or extra chat-management UI.
Source fingerprint is pinned to the supplied mock; arbitrary datasets/schema migration
are unsupported. Existing working state is preserved or fails clearly, never reset.

Generated SQL still needs semantic verification for joins, output units and omitted
conditions; permissions are not correctness. Scope guards cover observed failures,
not arbitrary English. The narrow semantic eligibility compiler handles known exact
filter forms; unseen compound/numeric filters and paraphrases need additional tests.
The 22 known development/acceptance questions do not prove those broader cases.

No automatic retention/checkpoint pruning. SQLite/local logs and evaluation archives
can grow. Weekday eight-hour capacity omits leave/holidays/FTE; full intersecting booking
minutes are not daily availability. Soft over-capacity is a warning. FX constants are
fixture data, not a dated FX service. Production needs real identity/authorization,
concurrency/storage, retention/calendar/FX policy and broader evaluation.

Large exhaustive sets use declared source-ID order if global ranking exceeds budget.
Recommendations use finite candidate groups. Provider outages/retry/degraded recovery
were fault-tested; no actual Azure outage/quota exhaustion was induced. Written 88
scenarios remain an inventory, not 88 independently passing tests. See [verification](docs/development/verification.md)
and [current task evidence](docs/plans/progress.json).
