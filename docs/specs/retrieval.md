# Structured and semantic retrieval

Status: selected generated-read SQL and local embedding design; implementation present; see verification coverage.
Requirements R-05/06/07/12/13/14. Calculation rules: [data](data.md). Limits: [operations](operations.md).

## Source-grounded result contract

A read result identifies query_id/purpose, typed rows or scalar metrics, stable keys,
units/currency/window, source/evidence references, executed SQL and bind parameters.
Completeness records retrieval mode, eligible/processed/matched/uncertain counts when
known, has_more and truncation reason. Distinguish shortlist, exhaustive coverage,
displayed subset and explanation sample. Never imply permission-valid SQL proves a
business-correct answer. Guessed literal SELECT answers have no source grounding.

Runtime models receive no gold answers/reference SQL or additional-case oracles.
Evaluator reads the same delivered blocks and actual database effects as the user.

The compact schema includes bounded public catalogue values (regions, skills, status
domains/codes, business units, currencies and workflow states). These are observed
source vocabulary, not question-specific expected results. Private columns stay excluded.

## Generated read plans

PlanReads receives compact schema for every allowed subject table: actual column names,
keys/relationships, grain, units, domain statuses and calculation rules. Not the full
verbatim dictionary, source rows/BLOBs, auth IDs or application/checkpoint schema.

Output contains one complete primary `answer` and up to three `additional_answers`.
Each is `{query_id, purpose, sql, parameters}`; helper lookups are not user answers.
Independent requested totals can use separate queries instead of a fragile mega-join.
Engineering default: at most four statements per plan. Oversize/malformed output uses
the same one planner-repair allowance as a later syntax/schema correction; no silent
omission. Named bound values carry names, IDs, epochs and thresholds. Identifier/schema
validation is separate because placeholders cannot bind a table/column name.

One shared repair may address format, syntax, schema or a detected output-scope/source-grain error. A permission rejection, resource
limit, valid empty result or semantically disappointing answer is not retried to obtain
a nicer result. Every actual attempt is traceable; only successful queries used in
the delivered answer are presented as SQL evidence. Earlier failed attempts remain
safe diagnostics, not proof. Never switch to a weaker connection after rejection.

Exact code renders values and conversions; DSPy explains provided evidence. Answer
all requested parts, including totals beyond top-N rows. Independent failed parts can
yield explicit partial data. Failed explanation must not erase successful rows/SQL.

Supplied engagement codes are looked up with bound exact SQL before interpretation;
matching source IDs/titles accompany the schema instead of asking the user for IDs.
This context is included in the prompt-budget estimate. Unknown codes are not guessed.

The interpreter receives the same compact source vocabulary to distinguish structured
severity/status/critical-path questions from description meaning. Non-ranking factual
lists must not silently add a top-level LIMIT; unspecified rankings show five with a
visible assumption. Explicit requested sizes take precedence. Exact count requests
need a delivered aggregate; duration and monetary totals use SUM rather than COUNT.
Requested grand totals must be visible one-row aggregates, not detail lists that ask
the user to add values. Quantity scope comes from the original request, so a model
paraphrase cannot introduce a count requirement.
Logged hours must read actual time_entries. These guards detect particular mistakes;
they do not prove arbitrary generated SQL is semantically correct.

For semantic reads, source meaning must not become a SQL LIKE/industry/provider-unit
proxy. The candidate reader exposes only exact structured columns actually mentioned
by the user. Simple broad person pools and active-project/single-unit inclusion or
exclusion pools are compiled from source catalogue values; complex filters, identity,
dates and references retain guarded generated SELECTs. No public question IDs or
expected result sets are used in this path.

## Read access policy

1. Dedicated connection opened read-only against the working subject file. App history,
   action receipts, checkpoints and vectors are not model-queryable.
2. Explicit table/column allowlist from the subject schema, excluding person_avatars,
   people.auth_user_id and technical avatar URLs. Subject tables containing other safe
   fields remain accessible; do not blacklist an entire useful table unnecessarily.
3. One statement/execution. SQLite authorizer denies writes, DDL, ATTACH/DETACH,
   unsafe PRAGMA, extension loading, unauthorized database/table/column/function access.
   Extension loading remains disabled. Limit schema introspection to supplied context.
4. Restricted safe built-in function policy includes required aggregate/date/string/math
   use. Cover COUNT(*) callbacks with empty/no column metadata and valid leading
   comments/CTEs. A naive SELECT prefix or one regex is not the security boundary.
5. 5s execution/fetch deadline; up to 1000 rows or 1 MiB result. Use progress/length
   limits and bounded fetch/serialization, including huge single strings/recursive CTEs.
6. Detect truncation explicitly, e.g. bounded extra-row fetch when safe. Do not alter
   a SUM/COUNT's underlying source to satisfy a result-row limit. Separate aggregates
   stay complete while detail lists may truncate. SQL busy timeout is not query deadline.
7. Source writes are accessible only through the separate fixed booking writer. SQLite
   has no GRANT roles; file permissions/connections/authorizer/trusted code enforce scope.

Authorizer controls permissions, not join/currency correctness. Test independent
many-to-many grains, zero rows, aliases, NULLs, direct booking.person_id and source
access behind claimed facts. Restrict resource allocations before large results are
materialized, not just after allocation. No ORM/AST parser is required by assumption;
add a dependency only if existing SQLite controls cannot meet tested requirements.

Materialized CTEs may emit table-level SQLite authorizer reads with no database or
column. Only previously observed derived names can use that exception; real tables,
views and private/system objects remain protected. Source provenance records the
underlying subject tables, never the temporary CTE name.

## Documents and local index

| Kind | Document content | Metadata |
| --- | --- | --- |
| Person | Full bio + role names + skill names | person_id, source field references; levels remain exact SQL facts |
| Project | Full summary | engagement_id/code and source summary reference |
| Risk | Full description | risk_id, engagement_id and source description reference |

Current raw fields: 400 distinct bios (max146 chars), 150 summaries (141 distinct,
max161), 373 risks (10 distinct, max83): 923 logical memberships and 551 raw unique
texts before person enrichment. One entity document, no arbitrary fixed-size splitting
or overlap. Do not embed bookings, financial rows, avatar images or chat history.

Azure text-embedding-3-small creates vectors; local SQLite stores vectors plus model/
dimension/text/config hash and memberships. Cosine search runs locally. A shared text
vector retains every risk/project membership. Changed text/model invalidates that vector;
wrong dimensions/nonfinite/corrupt vectors cannot count as no matches. Cache is derived,
rebuildable, and never more authoritative than current source rows. Person enrichment
changes the embedding hash and means old raw-text counts are not index-size promises.

Project matching first uses PlanProjectChecks to separate summary/industry and risk
conditions. Identical source fields are assessed once per request, then joined to all
parent project memberships. Industry scope uses the explicit industry phrase where
available; provider unit and client name do not establish industry. Risk requirements
need an actual matching risk record. AND/OR applies explicitly between fields; OR
inside a staffing/key-person criterion remains intact. Exact source quotations must
join back to the parent. Staff shortage is distinct from key-person dependency unless
the user's broader people-risk criterion includes both. Invalid assessments remain
uncertain, never fabricated matches. This is semantic model classification followed
by deterministic joins, not a keyword-only answer.

## Shortlist versus exhaustive mode

Raw request quantity words (all/every/count) control exhaustive coverage; a normalized
model paraphrase cannot invent an all requirement. People recommendations default to
shortlist; project/risk lists default to exhaustive. The requested answer entity is
normalized separately from the entity mentioned in its conditions.

**Shortlist:** apply exact eligibility, retrieve semantic candidates, assess evidence,
then rank. Engineering defaults: requested count or ten, initial up-to-forty vector
candidates per relevant kind. Include relevant exact structural candidates so a tiny
nearest-neighbor sample is not the sole route to skill evidence. Validate recall with
paraphrases; these numbers are initial defaults, not measured optimum or a universal
semantic threshold. Expand duplicate risk categories to all relevant memberships.

**Exhaustive:** establish all eligible source IDs and frozen criteria; read with stable
keyset pages, pack source texts under the per-call token budget, and assess every batch.
Each item returns match/no_match/uncertain plus exact source references. Validate IDs
and quoted evidence; record processed/unprocessed/uncertain sets. Aggregate at the
requested person/project/risk grain, not vector-text grain. Top-k never supplies an
unqualified full count. All candidate evidence must be considered even when display
rows truncate. Missing/uncertain coverage makes exact results provisional/partial.

For counts with an undefined material condition, clarify that condition before scanning
(e.g. how many years means experienced). For ordinary recommendations, explain role,
bio years and relevant exact skills rather than imposing a hidden universal cutoff.
Do not invent successful leadership or infer proficiency from cosine distance.

RankCandidates returns ordered IDs and source-grounded suitability reasons. Code
validates references/duplicates and fills exact facts from SQL. Persist the displayed
order for follow-up. Ties can use stable source-ID order as an engineering default.

## Failure and fallback

On embedding failure, apply the bounded transport policy, mark/log local degradation,
then assess the full eligible original-text set through chat DSPy batches and rank.
No external fallback service, local embedding model, keyword-only success or canned
answer is introduced. The fallback may be slower/costlier but can be complete if every
candidate is covered. Chat failure gives verified partial data or an honest error,
preserving history and pending action. No matches and retrieval unavailable are distinct.
Health/UI/log events and recovery behavior are in [operations](operations.md).

## Planned scenarios

| ID | Given / when | Expected observation |
| --- | --- | --- |
| S-001 | A changed skill/region factual request | Relevant real source rows, not a hard-coded gold answer |
| S-002 | A factual answer uses multiple queries | Every presented metric traces to the executed successful queries/values |
| S-003 | March-May 2026 and a threshold | Correct window, disclosed 520h capacity convention; exactly 60% excluded |
| S-004 | Person has zero, completed hard, or soft bookings | Zero included; hard/CMP included; soft excluded from hard metric |
| S-005 | Mixed currency projects and repeated rate cards | One FX per currency; expected converted total without multiplication |
| S-006 | Booking allocation belongs to another person | Booked person comes from direct booking FK |
| S-007 | WBS has parents with rolled-up effort | One-grain effort total, no triple count |
| S-008 | HLS and healthcare-client sets differ | Uses the explicitly requested concept |
| S-009 | Multi-part time/risk question | Complete total and requested ranking, not just one of them |
| S-010 | Repeated risks/requests exist | Correct entity-grain count and existence semantics |
| S-011 | Null actual date or dangling soft reference | No crash, false 1970 date or unintended loss of unrelated rows |
| S-012 | Configured reference date differs from machine date | Language uses configured date; source rows are not silently time-travel filtered |
| S-023 | Name contains quotes or SQL syntax | Bound literal; cannot widen selection or change query structure |
| S-024 | Query tries write/DDL/ATTACH/unsafe PRAGMA/function | Rejected without source mutation or weaker-connection fallback |
| S-025 | Valid query starts with comments/CTE or uses COUNT(*) | Executes under the agreed read policy; not rejected by a naive prefix guard |
| S-026 | Read targets checkpoint/app table/BLOB/auth field | Denied before private data leaves storage |
| S-027 | Query is expensive or recursive/returns huge scalar | Deadline/output limit stops it with a meaningful failure |
| S-028 | Invalid read plan then bounded repair | At most agreed retries; all attempts traceable; no loops |
| S-029 | Result exceeds display/explanation budget | Exact aggregates preserved, truncation/sample labels truthful |
| S-030 | Model proposes a guessed constant as a source-derived fact | No false provenance; semantic correctness review detects unsupported answer |
| S-031 | 'Data migration' has no identical skill entry | Related skills and bio experience yield grounded candidates |
| S-032 | Same semantic request is paraphrased | Meaning and exact constraints preserved |
| S-033 | Many records share ten risk descriptions | All relevant categories/source IDs considered; cache reuse loses no records |
| S-034 | Exhaustive semantic count after top-k retrieval | Does not certify a partial candidate list as the full set |
| S-035 | Client industry is only in summary | Correct active project set with industry and risk evidence |
| S-036 | Text lacks claimed experience/skill or contains instructions | No fabricated fact, no treating source text as authority to execute actions |

Implemented checks cover a subset; see the linked tests and verification limits below. Unit tests will validate calculations and permissions; source-backed
integration tests validate joins; real-model evaluation validates interpretation/recall.

## Implemented check coverage

See [topic checks](../../tests/test_data.py) and [current verification](../development/verification.md).
Real Azure quality and any scenario not explicitly mapped there remain unverified.
