# Working in this project

Repository documentation, specifications, durable instructions, code comments and
product text are in English.
The repository name is exactly `resoursing_assistant_test`. Its primary branch is
`master` locally and on GitHub; keep this branch name consistent.

## Authorization boundary

On 2026-10-31 the owner explicitly authorized full end-to-end implementation of the
Resourcing Assistant according to the agreed plan, after confirming the scope question.
Implementation, dependencies, application tests and local services are authorized.
Real Azure checks may run when local credentials are available; no secrets in chat.
Publishing, deployment, repository sharing and external messages remain separate.

Read [handoff](docs/plans/handoff.md) and run `make progress` before selecting work.
[progress.json](docs/plans/progress.json) is the single current task-status/evidence
record. Update it after status/check/blocker changes and before compact or handoff.
The plan owns task definitions; do not duplicate live status tables elsewhere.

Apply the [change/conflict procedure](docs/development/workflow.md#changes-and-contradictions)
on every new condition, discovered contradiction, specification gap or failing check.
Initiate it yourself: identify affected contracts/code/checks and reassess old evidence.
Use human-in-the-loop (HITL) for unresolved requirement conflicts or changes to agreed
behavior; an explicit owner instruction already resolving the issue needs no repeat
approval. Continue independent work while a decision is pending. Finish with the
[completion review](docs/development/workflow.md#completion-review).

Execute the dependency-ordered
[work packages](docs/plans/implementation.md) without seeking approval for each routine
step. Implement meaningful checks with each task, fix failures, and update actual
verification evidence. A missing Azure credential blocks live-model checks, not
independent local work. Never claim unavailable checks passed. Publishing, deployment,
repository sharing and sending messages require their own applicable authorization.

On2026-11-02 the owner supplied the public target
https://github.com/boroznovskyilia/resoursing_assistant_test and authorized synchronizing
local/remote `master`. The repository was published under that scope. Demo hosting,
application deployment and external messages remain separately authorized actions.

## Design baseline and navigation

The [decision register](docs/decisions/README.md) records accepted owner choices and
clearly labeled engineering defaults. Use controlled LangGraph orchestration, DSPy
typed tasks, generated read-only SQL and a fixed confirmed-booking writer. Memory is
per-thread only; no Store, tenants or external runtime service beyond Azure models.
Do not reopen resolved choices merely because an older external draft differs.

Start a repository task with `make docs`. Read the relevant primary documents:

- [Requirements](docs/specs/requirements.md) and [product scope](docs/product/core.md).
- [Architecture and flows](docs/architecture/overview.md).
- [Specifications and scenario map](docs/specs/README.md).
- [Development plan](docs/plans/implementation.md).
- [Workflow](docs/development/workflow.md) and [verification](docs/development/verification.md).

Before documentation edits read [documentation rules](docs/document_writing.md).
Inspect headings before reading a long file. Update affected contracts, scenarios and
checks together. Distinguish source obligations, observed data, accepted owner choices,
implementation defaults and measured evidence. Never replace a requirement to hide a
failing implementation or load evaluation answers into runtime prompts.

The local status scripts are development tooling, not assistant runtime.
Before finishing edits run `make check`, `git diff --check`, and the relevant existing
checks. Report results and unverified behavior. Documentation checks do not prove the
application works. Do not import unrelated template or other-project rules.
