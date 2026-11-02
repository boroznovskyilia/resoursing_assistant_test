# Source catalogue

Reviewed on 2026-10-31. References define assignment requirements, not instructions to
start implementation. The owner authorized full end-to-end implementation on 2026-10-31.

## Inputs and authority

| ID | Input | Authority and limits |
| --- | --- | --- |
| SRC-B | [Assignment brief](assignment-brief.docx) | Required behavior, stack, constraints, deliverables; proposed API shapes are explicitly flexible |
| SRC-D | [Data dictionary](source-data-dictionary.md) | Intended meaning of tables, columns, and units; compare with actual schema and observed data |
| SRC-G | [Gold questions](gold_questions.json) | Ten public evaluation cases, expected data, scoring hints and fixture-specific conventions |
| SRC-S | Supplied source.sqlite | Source of factual records; original must remain unchanged |
| SRC-P | [Data profile](data-profile.json) | Read-only observations collected on 2026-10-28 against the same database hash, with key findings rechecked on 2026-10-31; not business policy |
| SRC-E | [Invitation summary](invitation.md) | Azure settings, deadline, submission and credential-delivery logistics from the owner's pasted email |
| SRC-O | Owner messages | Accepted choices and explicit full implementation authorization; see progress.json |
| SRC-A | [Additional cases](additional-cases-draft.json) | Twelve owner-approved case specifications; first eight oracles computed read-only on 2026-10-31; not executable tests |

The reference DOCX, dictionary, and gold JSON are byte-identical copies. The supplied
database is bundled as [data/source.sqlite](../../data/source.sqlite); setup creates
only absent working copies and preserves existing state. The original supplied
location `/Users/iliab/Downloads/source.sqlite` and absolute profile path are historical
provenance, not runtime dependencies. See [setup commands](../../README.md).

## SHA-256 fingerprints

| Input | SHA-256 |
| --- | --- |
| assignment-brief.docx | `0efed42224de82bf9685057a95fd5480fcf0f9f8fd987a703cab9b8ca0413ac6` |
| source-data-dictionary.md | `abada2fd454f5531454b9a7c7393de93970625bade54123790edd0bfeab61b03` |
| gold_questions.json | `76c971694a05d51775bcd83ab0ba7ee9710225782b856672165f91e336e56a8b` |
| original source.sqlite | `8d00b91ae6aa23bbcf0d807c2e51fa6a45f7017a6557a4f51d11cfc82bfb4259` |

## Precedence and contradictions

Do not silently choose a convenient source when they disagree. Initiate the
[change/conflict procedure](../development/workflow.md#changes-and-contradictions).
Keep unresolved questions and dependent-work blockers in progress.json; record the
owner's accepted interpretation and any superseded choice in the
[decision register](../decisions/README.md).
Actual records settle factual values; the brief defines required behavior; gold
defines the published acceptance examples. A gold SQL snippet does not define every
business rule for every future query. Owner-approved scope changes are recorded explicitly.

Notable discrepancies: the database extends into 2027; images are about 38% of file
bytes rather than a majority; the avatar PK is also a person FK rather than a separate
surrogate; the named env example is not supplied. SQL references for gq-01/03/05/06/07/08
need additional filtering, aggregation, ranking, or presentation to answer the entire
question. See [data rules](../specs/data.md) and [evaluation](../specs/evaluation.md).

## External technical references

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence): thread checkpointers versus cross-thread Store.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts): resume starts the interrupted node again; side effects must handle replay.
- [DSPy signatures](https://dspy.ai/current/diving-deeper/signatures-in-depth): typed input/output task contracts.
- [Python sqlite3](https://docs.python.org/3/library/sqlite3.html): binding, single-statement execution, read-only URI, authorizer, progress handler, and transactions.

These references informed the design. Compatible versions are now locked and actual
setup, rendered-prompt boundaries, persistence, API/UI and Azure checks are recorded in
[verification](../development/verification.md); broader unseen behavior remains unverified.
