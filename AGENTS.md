# Working in this project

Write repository documentation, specifications, and durable instructions in English.
Respond to the user in their language unless they request otherwise.
Keep filenames and commands unchanged.

Start each task with `make docs`. Use this document map to select only the files
relevant to the task. For a long document, inspect its headings first:
`rg -n '^#{1,6} ' path/to/document.md`.

- [Product core](docs/product/core.md): purpose, language, and constraints.
- [Architecture](docs/architecture/overview.md): boundaries and key dependencies.
- [Workflow](docs/development/workflow.md): from a task to verification.
- [Verification](docs/development/verification.md): commands and their limits.

Before editing documents, read the [documentation rules](docs/document_writing.md).
Update related requirements and checks when changing behavior.
Investigate discrepancies between code and requirements: the code may be wrong.

Before completing a task, run `make check` and the checks for the changed behavior
listed in the verification document. Report the result, updated documents, and
anything left unverified. Passing documentation checks does not prove the application works.

This is a template: the product and stack have not been defined. Do not treat
unfilled sections as requirements or choose an architecture without a task.
Do not automatically import other projects' rules. Shared conventions are adopted
when creating a project; this repository must remain understandable without Control Center.
