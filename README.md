# resoursing_assistant_test

Local conversational Resourcing Assistant: persistent LangGraph agent, typed DSPy
steps, FastAPI and React chat over the supplied professional-services SQLite database.

**Implementation is present and locally tested. Actual Azure model quality is not yet
verified: the endpoint/key have not been supplied.** No scripted provider exists in
production; deterministic providers are confined to tests.

## Setup and run

Prerequisites: Python 3.12, uv, Node 26/npm and Make. Installation downloads packages;
runtime uses only local files plus the supplied Azure model endpoint. The mock source
and model-matching tokenizer are bundled, with fingerprint validation.

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

Endpoint/key compatibility will be validated when access is available. Do not commit
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

Semantic/refusal wording needs manual review. After inspecting saved answers/source
records, a reviewer can apply a run-bound review JSON without calling models again:

```sh
uv run python -m resourcing_assistant.evaluation --review-report PATH/results.json --reviews PATH/reviews.json
```

Review file shape: `{"run_id":"actual-run-id","reviewer":"reviewer-name","cases":{"gq-07":{"accepted":true,"notes":"source-grounded review findings"}}}`.
Reviews cannot override failed automated/source-safety checks. [Evaluation contract](docs/specs/evaluation.md).
This includes own-12: unchanged data alone cannot prove that the deletion refusal is truthful.

Latest preflight run `20261031T192453Z_9f3790`: all22 cases **not_run** because endpoint/key
are absent. No accuracy or pass-rate claim is available:

| Case | Type | Score | Status |
| --- | --- | --- | --- |
| gq-01 | factual | — | not_run |
| gq-02 | factual | — | not_run |
| gq-03 | factual | — | not_run |
| gq-04 | factual | — | not_run |
| gq-05 | factual | — | not_run |
| gq-06 | factual | — | not_run |
| gq-07 | semantic | — | not_run |
| gq-08 | semantic | — | not_run |
| gq-09 | write | — | not_run |
| gq-10 | out_of_scope | — | not_run |
| own-01 | factual | — | not_run |
| own-02 | factual | — | not_run |
| own-03 | factual | — | not_run |
| own-04 | factual | — | not_run |
| own-05 | factual | — | not_run |
| own-06 | semantic | — | not_run |
| own-07 | semantic | — | not_run |
| own-08 | semantic | — | not_run |
| own-09 | write | — | not_run |
| own-10 | write | — | not_run |
| own-11 | write | — | not_run |
| own-12 | out_of_scope | — | not_run |

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
