# Not done and remaining verification

Updated 2026-10-31. Local implementation, locked environment, source/tokenizer assets,
API/UI, repository progress recovery and an isolated22-case evaluation runner exist.
Actual task evidence is in [progress.json](docs/plans/progress.json).

## External blockers

- Azure resource endpoint/key are not configured. Actual chat/embedding compatibility,
  real semantic recall, factual interpretation, end-to-end scores and provider latency/
  token-cost measurements remain unverified. All22 evaluation entries are not_run,
  never passed. The owner will add access locally later; no secrets are requested in chat.
- Manual free-text semantic/refusal review follows the genuine run. Automated overlap
  alone cannot make those cases pass. The runner supports run-bound review records.
- Final three model-backed demo conversations/recording, including actual API restart
  before confirmation, remain pending genuine access. Process/UI tests prove mechanics
  using explicit test doubles; they are not the submission's model-quality demo.
- No remote repository URL/publication or submission has been performed. Publishing,
  sharing, recipient/time clarification and sending anything need applicable owner scope.

## Deliberate limits

Local single-user/common dataset, one API worker; no auth/tenants/Store/streaming,
external vector/monitoring service, optimizer, admin CRUD or extra chat-management UI.
Source fingerprint is pinned to the supplied mock; arbitrary datasets/schema migration
are not supported. Working state is preserved or fails clearly, never silently reset.

No automatic retention or checkpoint pruning. SQLite/local logs can grow. Weekday8h
capacity lacks leave/holidays/FTE; intersecting full booking minutes are not daily
availability. Over-capacity is a warning for soft bookings. Rates are fixture constants,
not a dated FX service. Production needs identity/authorization, concurrency/storage,
retention/calendar/FX policy, monitoring and broader held-out evaluation.

Large exhaustive result sets use deterministic source-ID order when a single global
suitability ranking would exceed the model budget; this is identified in metadata.
Recommendation rankings use finite candidate groups, still requiring real recall/ranking
validation. Input tokens are estimated with the bundled model-matching tokenizer plus
format overhead; provider-reported usage should be checked against estimates with access.

## Acceptance honesty

Written88 scenarios are an inventory, not a claim of88 passing tests. Current exact
checks and unmapped/unverified scope are in [verification](docs/development/verification.md).
No safety failure may be averaged away. Update this file after actual validation rather
than retaining obsolete no-application claims or inventing a complete delivery.
