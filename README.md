# template_proj

A minimal project template with a document tree and local link checks.
This is our implementation of progressive disclosure, not a copy of Rinat's setup.

## Getting started

1. Read [AGENTS.md](AGENTS.md) and run `make docs`.
2. In a new project, complete the [product core](docs/product/core.md).
3. Describe the first task and verifiable examples of expected behavior.
4. Choose a stack suited to the task and add actual verification commands to
   [verification.md](docs/development/verification.md).
5. Run `make check` and the application checks.

The template tools require Python 3 and Make. No packages need to be installed.
When `tree` is unavailable, `make docs` uses `find`.

## Layout

```text
AGENTS.md                 short agent entry point
docs/product/             product goals, language, and rules
docs/architecture/        system structure and constraints
docs/development/         workflow and verification
docs/specs/               executable scenario map
docs/decisions/           reasons behind important decisions
docs/plans/               active plans for complex tasks only
scripts/                  link checker and its tests
```

Add local `AGENTS.md` files when a part of the code needs its own rules.
A skill can package a repeatable procedure; keep current product rules in documents
and reference them from the skill.

## Creating a project from the template

From the `projects` directory, replace `my_project` with an unused project name:

```sh
git clone --no-hardlinks ./template_proj ./my_project
git -C ./my_project remote remove origin
```

The new repository starts with the template's history but no longer has a remote
pointing to it. Update the README title, complete the product core, configure
verification, and make your own commit. The neighboring Control Center contains
the registration procedure; the copied project does not depend on that document.

## How documentation is updated

The agent updates affected knowledge as part of a task, following the
[workflow](docs/development/workflow.md). There is no continuous background process.
Keep documentation and specifications in English. `make check` verifies local link
targets and the checker itself; requirements and application behavior need separate checks.
