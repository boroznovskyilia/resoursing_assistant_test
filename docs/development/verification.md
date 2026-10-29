# Verification and its limits

## Documentation and template tools

```sh
make docs
make check
```

The first command displays the document map. The second runs the checker's tests
and looks for broken local links in the repository's Markdown files.
To check another repository, provide its path:

```sh
python3 scripts/check_docs.py ../control_center
```

Link parsing limitations are described in the
[documentation rules](../document_writing.md).

## Application

Not configured: there is no application or chosen stack yet.
Before the first implementation, add exact build commands, behavioral checks,
and integration setup where needed. Specify dependencies and expected results.
A passing `make check` does not replace these checks.

## Executable scenarios

The [scenario map](../specs/README.md) connects product rules, tests, and commands.
Scenarios should check observable results, including important failures and repeated actions.

## Changing a check

When a check fails, reproduce the cause first. Do not remove or change an expectation
just because a new implementation violates it. Changes to expected behavior must
follow an agreed change to the requirement.
