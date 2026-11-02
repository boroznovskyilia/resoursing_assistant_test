# resoursing_assistant_test

Local conversational Resourcing Assistant: persistent LangGraph agent, typed DSPy
steps, FastAPI and React chat over the supplied professional-services SQLite database.

The default branch is `master`.

**Implementation is present and locally tested. Real Azure evaluation is recorded
below.** Scripted providers are confined to tests.

## Setup and run

Prerequisites: Python 3.12, uv, Node 26/npm and Make. Installation downloads packages;
runtime uses only local files plus the supplied Azure model endpoint. The mock source
and model-matching tokenizer are bundled, with fingerprint validation.

Clone the repository and run the following commands from its root directory.

```sh
make setup
```

This installs locked dependencies, creates `.env` only if absent, prepares the working
source without overwriting existing state, and builds the React UI. Add the supplied
Azure-compatible resource endpoint and key to the local `.env`:

```dotenv
AZURE_ENDPOINT=<provided-resource-endpoint>
AZURE_API_KEY=<provided-key>
AZURE_API_VERSION=2024-10-21
CHAT_DEPLOYMENT=gpt-4.1-mini
EMBEDDING_DEPLOYMENT=text-embedding-3-small
REFERENCE_DATE=2026-04-01T00:00:00Z
RUNTIME_DIR=.runtime
```

The supplied endpoint/API version passed genuine chat and embedding smoke checks.
`AZURE_API_BASE` is also accepted as an endpoint alias. Do not commit
secrets. Start one local worker and open http://127.0.0.1:8000:

```sh
make run
```

Existing chats, checkpoints, pending actions and confirmed bookings survive restart.
An unset reference date uses current UTC; assignment setup/eval explicitly pin April1
2026. Audit timestamps always use real UTC. An unconfigured model gives a clear error;
health/history/UI still work. No automatic background model calls or health probes.

For UI development, run the API above and `npm --prefix frontend run dev`; Vite proxies
API requests to port8000. The production build is served by FastAPI at the same origin.

## Backend organization

Synchronous FastAPI/LangGraph with pydantic-settings and SQLAlchemy repositories.
API schemas, model-task schemas and ORM records are separate. The application factory
is `resourcing_assistant.app:create_app`; `make run` uses this entry point.
Read-only model SQL retains the native SQLite authorizer/limits; the ORM does not
replace that security boundary. Existing runtime files and checkpoints are preserved.
See the [module map and transaction boundaries](docs/architecture/overview.md#backend-module-boundaries).

Settings validate timezone-aware reference dates and positive limits before startup.
Explicit settings override environment, environment overrides dotenv, then defaults.
Empty environment values are ignored so endpoint aliases can work. An absent reference
date means UTC now; setup/evaluation explicitly select the assignment date. Secrets
use SecretStr and are not printed. Limits retain the agreed defaults and can be set
through their uppercase field names; see [Settings](src/resourcing_assistant/config.py).

## Verification

```sh
make check
make test
npm --prefix frontend run build
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run test:e2e
```

`make check` runs nine repository-tooling tests, local-link checks and durable progress
validation. Backend tests cover calculations, SQL permissions/limits, receipts/retries,
compaction, graph/API transitions, semantics, scoring and actual process kill/restart.
Playwright exercises the real local API and UI using a clearly labeled test-only
provider. Browser tests require a build and a free localhost port8017. On a restricted
agent host, local ports/browser launch may need sandbox escalation. The current machine
uses `PLAYWRIGHT_BROWSERS_PATH=/private/tmp/resourcing-browsers` for its browser installation;
normal setup can use Playwright's default browser path.

See [verification evidence and limits](docs/development/verification.md) for exact
results/test-file mapping. Passing doubles-backed tests is not real model accuracy.

## Real-model evaluation

```sh
make evaluate
# Optional selected case:
uv run python -m resourcing_assistant.evaluation --case gq-01
```

The runner executes all10 public +12 own cases against actual API subprocesses, each
with isolated durable files. gq-09 includes separate Confirm/Reject and genuine restart
subcases. Source oracles are scorer inputs only, never agent prompts. Reports and
answer/review evidence are under `.runtime/evaluation/<run_id>/`. JSON includes score,
contract_checks, review_status, timings, model settings and available call/token usage.
Step responses, decision receipts and restored history are retained inside each case
directory, including HTTP error responses. Read-only cases must leave every source
row unchanged; write cases check visible dates, exact persisted terms and receipts.
Exit0 means every case fully passed; exit2 means failed, partial-credit, not-run or
review-required cases remain. It never fills a missing answer from an oracle.

If the scorer is corrected, `uv run python -m resourcing_assistant.evaluation --rescore-report PATH/results.json`
grades every saved answer from that run offline into `rescored-results.json`, preserving
the original and recorded source/write observations. It makes no model calls, never
fills missing metrics and clears prior free-text approvals. Review the new report.

Semantic/refusal wording needs manual review. After inspecting saved answers/source
records, a reviewer can apply a run-bound review JSON without calling models again:

```sh
uv run python -m resourcing_assistant.evaluation --review-report PATH/results.json --reviews PATH/reviews.json
```

Review file shape: `{"run_id":"actual-run-id","reviewer":"reviewer-name","cases":{"gq-07":{"accepted":true,"notes":"source-grounded review findings"}}}`.
Reviews cannot override failed automated/source-safety checks. [Evaluation contract](docs/specs/evaluation.md).
This includes own-12: unchanged data alone cannot prove that the deletion refusal is truthful.

Latest backend runtime `23487e3`: genuine full run `20261101T190046Z_a1cdc9`
passed **22/22 after7 explicit AI-assisted source reviews** (15 automatic passes
before review). The earlier post-refactor factual failure and rejected ranking
explanation are retained; no answers were edited/combined and scoring was not relaxed.
[Current answers, reviews, failures and hash lineage](docs/evaluation/backend-refactor-20261101/README.md).
Final local checks:103 backend tests,5 Chromium scenarios,9 tooling checks; fresh-clone
locked setup/build and saved-runtime compatibility passed.

The table below reports the latest run `20261101T190046Z_a1cdc9`, including its seven
explicit AI-assisted source reviews. This is the known development/acceptance set,
not an independent human review, held-out benchmark or repeated-run reliability claim.
Previous-release answers, measurements and run history remain available separately in
[historical evaluation evidence](docs/evaluation/README.md).

| Case | Type | Score | Status | Review |
| --- | --- | --- | --- | --- |
| gq-01 | factual | 1.0 | passed | not_required |
| gq-02 | factual | 1.0 | passed | not_required |
| gq-03 | factual | 1.0 | passed | not_required |
| gq-04 | factual | 1.0 | passed | not_required |
| gq-05 | factual | 1.0 | passed | not_required |
| gq-06 | factual | 1.0 | passed | not_required |
| gq-07 | semantic | 1.0 | passed | approved |
| gq-08 | semantic | 1.0 | passed | approved |
| gq-09 | write | 1.0 | passed | not_required |
| gq-10 | out_of_scope | 1.0 | passed | approved |
| own-01 | factual | 1.0 | passed | not_required |
| own-02 | factual | 1.0 | passed | not_required |
| own-03 | factual | 1.0 | passed | not_required |
| own-04 | factual | 1.0 | passed | not_required |
| own-05 | factual | 1.0 | passed | not_required |
| own-06 | semantic | 1.0 | passed | approved |
| own-07 | semantic | 1.0 | passed | approved |
| own-08 | semantic | 1.0 | passed | approved |
| own-09 | write | 1.0 | passed | not_required |
| own-10 | write | 1.0 | passed | not_required |
| own-11 | write | 1.0 | passed | not_required |
| own-12 | out_of_scope | 1.0 | passed | approved |

## Demo

The [recorded demo transcript](docs/development/demo-transcript.md) covers factual
SQL, semantic recommendations, and a pending booking confirmed after an actual API
process restart, followed by Reject. Genuine Azure models were used throughout.
A local 2m35s MP4 with English captions is prepared; its long semantic waiting period
is explicitly accelerated8x, with the full continuous source recording retained.
Video upload, repository sharing and external submission remain outstanding.

## Design and continued development

- [DESIGN](DESIGN.md): concise architecture, state, retrieval, failures and assumptions.
- [NOT_DONE](NOT_DONE.md): external blockers and unverified delivery work.
- [Full specifications](docs/specs/README.md), [architecture/flows](docs/architecture/overview.md),
  [accepted decisions](docs/decisions/README.md) and [source catalogue](docs/reference/README.md).
- [Development tasks](docs/plans/implementation.md), [current status](docs/plans/progress.json)
  and [compact/new-session handoff](docs/plans/handoff.md). Run `make progress` to resume.

Only confirmed soft-booking inserts are allowed in the working subject copy. Immutable
action IDs and atomic receipts prevent duplicate writes on retry. Original data stays
unchanged. No login/tenants, Store, external vector/logging service, streaming or optimizer.
Publishing/deployment/submission are separate from local implementation authorization.
