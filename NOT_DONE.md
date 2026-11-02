# Remaining delivery work and limits

The latest full genuine Azure run20261101T190046Z_a1cdc9 on runtime23487e3 passed
22/22 after7 explicit AI-assisted source reviews.15 cases passed automatically.
[Current answers/reviews and both retained failures](docs/evaluation/backend-refactor-20261101/README.md).
The first post-refactor run exposed a duration-unit error; the second had an explanation
rejected for invented historical status years. Both were fixed and tested before the
new complete run. No answer stitching, scorer relaxation or independent human review.
Previous release evidence is preserved separately. This does not establish universal accuracy.

## Remaining delivery work

- The three representative UI conversations were recorded on 2 November 2026 using
  genuine Azure models, including an actual API restart before Confirm and a separate
  Reject. A local 2m35s captioned MP4 and full4m54s source recording are prepared;
  the video still needs an accessible delivery link. The versioned
  [transcript](docs/development/demo-transcript.md) includes verified write/source checks.
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
