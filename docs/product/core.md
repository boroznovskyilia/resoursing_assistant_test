# Product scope

Status: owner-agreed design baseline, consolidated on 2026-10-31. Full end-to-end implementation was
explicitly authorized after specification review. See [AGENTS.md](../../AGENTS.md).

## User and outcomes

A staffing manager in a professional-services business asks questions about people,
skills, projects, staffing needs, risks and finances without writing SQL. The supplied
SQLite records are the factual source of truth. Required outcomes:

1. Correct multi-table answers, units and calculations, with executed SQL alongside.
2. Meaning-based retrieval over bios, summaries and risks, ranked with source evidence.
3. A proposed soft booking with exact terms, written only after explicit confirmation.
4. Saved chats and pending actions that survive reload and API process restart.
5. A validated API and minimal React chat exposing these behaviors.
6. Honest evaluation of all ten public and twelve additional cases.

The [requirements](../specs/requirements.md) separate source obligations from owner
choices. The [source catalogue](../reference/README.md) identifies authority and hashes.

## Domain language

| Term | Meaning |
| --- | --- |
| Person/resource | Entity identified by person_id; a display name is not unique |
| Client | A party with client type, not an application tenant |
| Engagement | Client project |
| Business unit | Provider ownership/practice; distinct from client industry |
| Role/category | Professional role, separate from a skill and its proficiency |
| Requirement/request | Staffing need and separate request to fulfil it |
| Team allocation/assignment | Project membership versus assignment to a work item |
| Booking/time entry | Reserved minutes versus actual logged minutes |
| Thread | Independent conversation, state, history and pending action |
| Proposal/action | Immutable booking terms plus durable decision receipt |
| Evidence | Executed query/results or original text linked to source IDs |

## Agreed scope

Local use, one common subject database and independent saved chats. The sidebar lists
chats; users can reopen one or create a clean chat. Bookings are shared subject facts,
so a later chat can read a confirmed booking without inheriting another chat's memory.
No multi-tenancy, login, cross-thread user memory/Store, external vector service,
external alerting, streaming, cloud hosting, avatar UI, admin CRUD or DSPy optimizer.
No chat folders, search or rename feature is planned for v1.

The UI, demo prompts and repository content are English; design discussion is Russian.
No broad multilingual-quality claim is made. Plain CSS and accessible basic controls
suffice; agent behavior and safe persistence take priority over visual polish.

## Supported behavior and limits

Support composable questions across allowed dictionary domains, changed filters and
paraphrases, not a switch over the public questions. Generated SQL provides expressive
reads under a strict access boundary. The sole source write is one soft-booking insert
per confirmed action. Updates, deletes and hard bookings are refused.

Clarify ambiguous identities or missing booking fields. Recommendations can explain
inferred suitability; exact counts requiring an undefined seniority threshold first
clarify that threshold. Do not invent leadership history, calendar/FTE/leave, exact
invoice-to-project attribution or external facts such as weather.

Return available verified data with explicit missing parts when a read/explanation
part fails. A valid empty result is normal. A write is atomic, never partially successful.
Shortlists, exhaustive coverage, display truncation and explanation samples are distinct.

## Delivery boundary

The brief mandates Python 3.11+, LangGraph, DSPy, FastAPI, React and SQLite. The selected
stack and design are recorded in [decisions](../decisions/README.md). Only model endpoints
may be external runtime services. Local logs and health/UI warnings cover degradation.

Deliver a reproducible repository, meaningful history, setup/run/evaluation README and
results table, one-page DESIGN, honest NOT_DONE and a demo with an actual API restart
before confirmation. The email asks for recording; the brief also allows a transcript.
Deadline: 2026-11-02, with time/timezone unspecified. Publishing and sending a submission
are separate actions, not authorized by a documentation or implementation instruction.
