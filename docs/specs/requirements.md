# Requirements and traceability

Status: consolidated requirements baseline. Source obligations below are distinguished
from owner-selected implementation safeguards and engineering defaults. Implemented checks and remaining evidence are mapped in verification.md.

Source IDs refer to [the catalogue](../reference/README.md). Written scenario IDs refer
to [the scenario map](README.md); they are not executable tests. Acceptance is assessed
against the entire user-facing behavior, not only a narrow scoring field.

## Owner instructions

| ID | Requirement | Status | Acceptance |
| --- | --- | --- | --- |
| O-01 | Repository name is exactly resoursing_assistant_test | Agreed | README/repository identity preserves spelling |
| O-02 | Complete and review requirements, decomposition, architecture and test specifications before any implementation | Agreed | Design-first gate satisfied; full implementation authorized 2026-10-31 |
| O-03 | Persist only per-thread conversational memory; no cross-thread Store in first version | Agreed 2026-10-31 | New thread does not inherit another thread's working memory; S-016 |
| O-04 | Compare model-generated SQL and structured tools before selection | Completed; generated read SQL selected | DEC-04/05, architecture comparison |
| O-05 | Independent saved chats, common dataset; no multi-tenancy/auth/Store | Agreed | DEC-03/31; S-016, S-054 |
| O-06 | Save the complete specification and dependency-ordered development plan in English | Authorized | DEC-43; all repository documents |
| O-07 | No application implementation without a separate explicit start instruction | Explicit start instruction received 2026-10-31 | progress.json authorization evidence |

## Required application behavior

| ID | Obligation | Source | Acceptance scenarios |
| --- | --- | --- | --- |
| R-01 | Provide an agent, API and React chat; implement in that order | SRC-B §3 | S-001, S-065; delivery review |
| R-02 | Use Python 3.11+, LangGraph, DSPy, FastAPI, React, SQLite | SRC-B Stack | Stack review and later clean-install check |
| R-03 | Every language-model step is a DSPy module with an explicit signature | SRC-B §3.1 | S-022; static call-path review including summary/repair/evaluation judges |
| R-04 | Save conversation state with a LangGraph checkpointer and resume after restart | SRC-B §3.1 | S-015, S-041 |
| R-05 | Answer factual multi-table questions with correct conversions | SRC-B §3.1 | S-001–S-012, all factual gold |
| R-06 | Return the query or queries that produced each factual answer | SRC-B §3.1 | S-002, S-025, S-030 |
| R-07 | Match free-text meaning and return ranked grounded shortlists | SRC-B §3.1 | S-031–S-036, gq-07/08 |
| R-08 | Support only one source-table write: insertion of a soft booking | SRC-B §2/6 | S-024, S-042, S-048 |
| R-09 | Show person, engagement, dates and hours; write only after confirmation | SRC-B §3.1 | S-037, S-038 |
| R-10 | Permit rejection without creating a booking | SRC-B §3.2; SRC-G gq-09 | S-039 |
| R-11 | Confirmation still works after API process restart | SRC-B §3.1/5 | S-041, S-045 |
| R-12 | Refuse or clarify questions beyond available data rather than guess | SRC-B §3.1 | S-013, S-014, S-036, gq-10 |
| R-13 | Do not modify/delete source rows; no other source-table inserts | SRC-B §2/6 | S-024, S-049 |
| R-14 | Parameterize or validate all executed SQL; never concatenate raw model output into a query | SRC-B §6 | S-023–S-030 |
| R-15 | API supports conversation history, message sending and pending-action confirmation/rejection | SRC-B §3.2 | S-050–S-057 |
| R-16 | Validate API request and response bodies using Pydantic | SRC-B §3.2 | S-050, S-051, S-058 |
| R-17 | Meaningful HTTP errors for unknown threads and missing pending actions | SRC-B §3.2 | S-050, S-052 |
| R-18 | Chat shows one thread's history and accepts new messages | SRC-B §3.3 | S-059 |
| R-19 | UI renders every supported block; tables, confirmation/rejection, collapsible SQL in suggested contract | SRC-B §3.3 | S-060, S-061 |
| R-20 | UI has visible loading and error states | SRC-B §3.3 | S-062 |
| R-21 | Browser reload restores current thread from API rather than browser-held transcript | SRC-B §3.3 | S-063 |
| R-22 | Evaluate ten gold and at least ten new questions across all three main request types | SRC-B §4 | S-066, S-067 |
| R-23 | Runner scores each answer, prints a results table, and includes that table in README | SRC-B §4/5 | S-068–S-072 |
| R-24 | Run locally with documented commands and no service beyond model endpoint | SRC-B §6 | S-065, S-074 |
| R-25 | Use supplied model endpoint/settings and never commit secrets | SRC-B §6; SRC-E | S-073, S-074 |
| R-26 | Provide README, one-page DESIGN and NOT_DONE with required contents | SRC-B §5 | S-075; document review |
| R-27 | Keep meaningful Git history, accessible repository, demo with restart confirmation | SRC-B §5/7 | S-076; actual process-restart demo |
| R-28 | Make 'now' explicit and configurable | SRC-B §2; SRC-G notes | S-003, S-012 |
| R-29 | Disclose assumptions, known limitations, AI-assistant use and production changes in DESIGN | SRC-B §5/6 | S-075 |
| R-30 | Fresh-clone README commands work | SRC-B §7 | S-065 |

## Permissions and optional items

- SRC-B §2 permits auxiliary tables, columns, views and indexes. This does not permit
  backfilling or repairing source rows to make queries easier.
- SRC-B §3.2 permits changing endpoints/block shapes with an explanation in DESIGN.
  Functionality R-15–R-21 remains mandatory.
- Streaming, Vite, a UI framework, Docker Compose, vector indexing and DSPy optimization
  are not individually mandatory. A semantic retrieval capability is mandatory.
- Open-source libraries and AI coding assistants are allowed. Hidden hosted agent/RAG
  orchestration is not allowed. A framework's existence does not justify another service.
- The brief permits recording or transcript; the email asks for recording. Recommend
  a short video satisfying both, but record the distinction.

## Fixture conventions and ambiguities

| ID | Published convention | What it does not settle |
| --- | --- | --- |
| C-01 | reference_date = 2026-04-01T00:00:00Z | Does not define a historical database snapshot or retention policy |
| C-02 | UTC epoch seconds; intervals include start and exclude end | gq-01 overlap SQL uses >= at the left boundary; gq-09 wording conflicts about May 1 |
| C-03 | Reporting USD; FX multiplier USD 1, EUR 1.08, GBP 1.27, BRL .19 | No effective-date FX history exists; future conflicting rates need an explicit policy |
| C-04 | gq-01 capacity 520 hours; reasonable alternatives accepted for candidate membership | Exact overlapping-booking hour tolerances still matter |
| C-05 | gq-02 open requirements include OPN and PRT; submitted state is in requirement_requests | Not all domain statuses with open group mean active projects |
| C-06 | gq-01 hard time comes from kind=hard and full minutes of intersecting bookings | No daily allocation, leave or FTE data; no evidence for exact daily availability |
| C-07 | gq-07 uses role/experience from bio and related data skills; gq-08 industry from summary | Does not prove past leadership ability or define universal seniority thresholds |

Do not treat all reference SQL as a complete answer implementation. gq-01 omits the
percentage filter; gq-03/05/06 need totals; gq-07 needs ranking; gq-08 needs grouping
and industry evidence. See [evaluation](evaluation.md) for exact accepted scoring rules.

## Accepted safeguards, not separately mandated source features

| ID | Accepted safeguard | Why | Decision / scenarios |
| --- | --- | --- | --- |
| P-01 | Immutable action ID and idempotent confirmation | Prevent duplicate bookings during retries/crashes | DEC-18/20; S-040, S-044–S-047 |
| P-02 | Read allowlist, resource budgets and separate fixed writer | Enforce R-13/14 in code rather than prompts | DEC-05/09/42; S-023–S-030 |
| P-03 | Bounded working memory and compaction | Control context growth without deleting history | DEC-23/24; S-017–S-021 |
| P-04 | Reuse embeddings for identical text and keep all source IDs | Reduce duplicate work without losing recall | DEC-11/13; S-033 |
| P-05 | Separate deterministic invariants from model-quality evaluation | Avoid claiming scripted-test success as model accuracy | DEC-36/37; S-066–S-074 |
| P-06 | Explicit completeness metadata and truthful partial-result wording | Avoid reporting top-k or truncated lists as exhaustive | DEC-10/14/30; S-009, S-029, S-034 |

The [decision register](../decisions/README.md) records the consolidated choices.
Additional recovery/limits scenarios S-077–S-088 extend the original scenario map.
Accepted design is still not authorization to implement or evidence of passing checks.
