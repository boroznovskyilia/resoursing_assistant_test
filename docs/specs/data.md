# Data model, evidence and calculation rules

Status: observed facts were checked against the supplied fingerprint; calculation
policies below are owner-agreed. Runtime copies/metadata and data checks are implemented.
The [original dictionary](../reference/source-data-dictionary.md) describes every column;
the [profile](../reference/data-profile.json) records schema, nulls, ranges and counts.

## Table grain and relationships

| Table | Rows | Grain and use |
| --- | ---: | --- |
| currencies | 4 | Currency, reporting flag |
| status_lookup | 20 | Domain-scoped status |
| business_units | 6 | Provider business/practice unit |
| org_units | 14 | Delivery organization under a business unit |
| parties | 88 | Client, vendor or internal organization |
| people | 400 | Person; person_id is identity |
| person_avatars | 400 | One image per person; exclude BLOB from retrieval |
| skills | 40 | Skill definition |
| person_skills | 2,012 | Person-skill level, not a role |
| rate_categories | 20 | Billable role/category and utilization target |
| rate_cards | 40 | Price-list/category/currency rate, not one row per currency |
| category_assignments | 551 | Person-role association and default flag |
| engagements | 150 | Client project with financials and ownership |
| work_items | 9,184 | Node in phase/workstream/task tree |
| work_item_links | 1,470 | Directed predecessor-successor link |
| resource_requirements | 488 | Project staffing need |
| requirement_requests | 729 | Request to fulfil one need; several can exist |
| team_allocations | 880 | Person's team allocation and role |
| assignments | 8,036 | Person assigned to a leaf work item |
| time_entries | 48,435 | Actual logged minutes on work item |
| bookings | 2,620 | Reserved minutes for person and project |
| approvals | 291 | Project approval event |
| risks | 373 | Project risk record; description can repeat |
| billing_documents | 1,200 | Vendor invoice; no project FK |

Total: 77,451 subject rows; database bytes: 9,535,488. Integrity check returns ok and
declared foreign-key check returns no errors. Domain consistency needs additional checks.

## Canonical joins

| Question domain | Direct path | Avoid |
| --- | --- | --- |
| Person skills | people → person_skills → skills | Treating role names as skill names |
| Person default role | people → category_assignments with is_default → rate_categories | Joining all roles and counting the person twice |
| Client of a project | engagements.client_party_id → parties.party_id | Inferring organization identity from title text |
| Project owner/manager | Corresponding engagements person FK → people | Confusing manager with an assigned worker |
| Project work | work_items.engagement_id → engagements | Summing all levels of an aggregated WBS |
| Actual project hours | time_entries → work_items → engagements; time_entries.person_id → people | Treating assignments/bookings as logged time |
| Booked person/project | bookings.person_id → people; bookings.engagement_id → engagements | Deriving booked person from team_allocations |
| Open staffing and requests | resource_requirements → requirement_requests | Replacing request rows with denormalized request_status |
| Risky projects | risks.engagement_id → engagements, normally EXISTS | Multiplying projects by repeated risk rows |
| Converted project cost | engagements → currencies; one FX row per currency from rate_cards | Joining every rate_card row |
| Invoice supplier | billing_documents.supplier_party_id → parties | Inventing a project FK |

Aggregate independent many-to-many inputs to the needed grain before joining. For
example, assignments × time_entries on work_item_id alone duplicates both measures.
Use COUNT(DISTINCT person_id) or an equivalent person-grain subquery where appropriate.

## Units, dates and statuses

- Integer cents are minor currency units. Divide by 100 with non-integer arithmetic.
  Never sum USD/EUR/GBP/BRL amounts as if they share a currency.
- Bookings/time entries are minutes; assignments/work items use hours. Preserve the
  exact value before presentation; do not ask an LLM to perform financial arithmetic.
  Convert cents and apply one FX multiplier at full precision, sum, then round only
  the final displayed monetary total to two decimal places. Do not round each row first.
- Timestamps are UTC epoch seconds and include time-of-day. Bind epoch integers,
  not ISO date text, when comparing integer timestamp fields.
- Accepted interval convention: human end day inclusive; internal start inclusive/end
  exclusive UTC. April 1-30 maps to April 1 midnight through May 1 midnight exclusive.
  Strict overlap is booking.start < period.end AND booking.end > period.start.
  A record ending exactly at period start does not intersect.
- Reference date is a configurable language anchor. It is not the real execution date
  and does not automatically filter created_ts. Data extends beyond mid-2026 into 2027.
  Unconfigured reference time defaults to current UTC; assignment startup and evaluation
  explicitly set 2026-04-01T00:00:00Z. Month without year uses the reference year,
  disclosed even for a past month; explicit next month/year wording shifts the period.
  Audit created/updated timestamps always use actual UTC time.
- Project progress is 0..1; work-item progress is 0..100. Null actual dates are unknown,
  not 1970-01-01 or evidence of a specific project state.
- Status IDs are integers with valid FK identity, but semantic codes are scoped by
  domain: ACT occurs for both project and team. Resolve by domain and code/group.

### Published status meanings

| Meaning | Predicate |
| --- | --- |
| Active project | project domain, code ACT |
| Blocked work item | task domain, code BLK |
| Open staffing need | requirement domain, state_group open: OPN and PRT |
| Submitted request | requirement_requests.state = submitted |
| Hard-booked for gq-01 | bookings.kind = hard, including completed status |
| New soft booking | kind soft; booking domain code SFT, currently status_id 13 |

Current project statuses: NEW 23, ACT 60, HLD 21, CLS 35, CAN 11. Requirements: OPN 129,
PRT 125, FLD 126, CNL 108. These counts are observations, not fixed application constants.

## Findings and consequences

### D-01 Identity ambiguity

34 display names occur twice, affecting 68 people. Amanda Mitchell is person 78 in
EMEA (Software Developer, 6 years) and person 238 in LATAM (Solutions Architect,
13 years). Ask for a discriminating field or an explicit choice before a write.
Even a full name is not a unique key. See S-013 and S-043.

### D-02 Allocation mismatch

2,095 bookings have a different person from the allocation referenced by allocation_id.
All linked project IDs agree. Booking 1 identifies person 348 but allocation 4 identifies
person 312. Follow direct booking person_id for booking facts; do not repair the source.
See S-006.

### D-03 Kind versus status

Hard bookings: HRD 640, CMP 675. Soft bookings: SFT 679, PRP 626. A filter only on HRD
does not reproduce gold. Confirming the creation of a soft booking still produces SFT,
not HRD. See S-004 and S-038.

### D-04 WBS double counting

914 roots, 2,378 internal nodes, 5,892 leaves. est_hours totals 508,554.3 across all
levels and 169,518.1 on leaves: exactly a factor of three. Current assignments and
time entries point only to leaves. Leaf-only is an effort aggregation rule, not a
universal filter for every work-item question. See S-007.

### D-05 Provider unit versus client industry

43 projects differ between HLS membership and healthcare/pharma industry classification.
Only 1 of the 11 active HLS projects also has that client industry. Industry appears
in summary; there are 15 observed industry labels. Healthcare occurs on 16 project
summaries and Pharmaceuticals on 9, before active/risk filtering. See S-008 and S-035.

### D-06 Repeated risks

373 risk records contain 10 distinct descriptions. Within projects, 36 duplicate
description groups contain 41 extra rows. Count records for risk-record questions,
distinct projects for project questions. Keep every source ID when deduplicating
embedding text. See S-010 and S-033.

### D-07 FX multiplicity

There are 9 USD, 11 EUR, 16 GBP and 4 BRL rate cards. All current rates within one
currency agree: 1, 1.08, 1.27, .19 respectively. Reduce to one rate per currency before
joining. A future set of conflicting rates requires a documented selection rule;
MAX is valid for the current constant-rate fixture, not a general FX policy.
Engineering default for conflicting rates: fail the affected conversion clearly rather
than pick an arbitrary rate. Convert full precision and round the final sum. See S-005.

### D-08 Insufficient daily schedule

Bookings hold total minutes and an interval, not hours per day. Gold sums full minutes
of intersecting records. Proportional clipping would change expected hours. Reference
SQL additionally treats end==window_start as intersecting; accepted application
policy uses strict overlap instead. A read-only comparison found identical six people
and hours on this fixture because no contributing hard record ends at that boundary.
Keep a synthetic boundary test so the distinction is real. Full intersecting minutes
are not additive over successive periods: the same booking may contribute to each
period it crosses. Do not claim precise daily availability or prorate without data.

### D-09 Missing capacity inputs

No holidays, leave, individual work schedules or FTE are supplied. Gold's window has
65 Monday-Friday days × 8 hours = 520 hours. A shared workweek assumption must be
disclosed. Zero-weekday windows have no defined percentage; show hours and the
capacity limitation rather than divide by zero. Over-capacity proposals warn but remain
allowed soft bookings. A strict 'less than 60%' excludes exactly 60%. No bookings means zero known
hard-booked time, not proven absence of all real-world commitments. See S-003/004.

### D-10 Nulls and partially specified measures

23 projects have null actual_start_ts, 104 null actual_end_ts, and 92 approvals null
decided_ts. Soft requirement references are not FK-enforced; none currently dangle,
but absence must not crash reads. Some requirement effort/duration units are not
specified. Do not invent conversions from similarly named columns. See S-011/012.

### D-11 Invoice attribution is incomplete

37 of 39 work-item cost-center codes occur on multiple projects. CC-120 spans 8 projects.
31 invoices have no work-item cost-center match. An exact project-invoice allocation
cannot be proved from the database; explain that boundary instead of arbitrary joins.
Vendor/currency/due-date invoice questions remain answerable. See S-014.

### D-12 Observed ranges are not validation policy

Existing bookings range from 120 to 960 minutes, but gold requires inserting 2,400.
Do not validate against current maxima. Validate meaning, finiteness, duration, dates
and existence of entities instead. See S-042.

### D-13 Schema constraints are incomplete

Enums and ranges are mostly not protected by CHECK; names are not UNIQUE. Enable FK
checking on every writer connection. The statement that every table has a separate
surrogate ID has an exception: person_avatars.person_id is both PK and FK. No avatar
entity or SSO subsystem is required for this assignment.

### D-14 Source and model boundaries

Only bio, summary and risk description are designated unstructured retrieval fields.
Skills, roles, dates, currencies and levels are exact evidence, not vector-distance
facts. The templated bio supports title/years, not a claim of demonstrated leadership.
Images total 3,664,966 bytes (~38% of file size); omit them, auth IDs and technical
avatar URLs from prompts. Do not fetch external URLs while answering. See S-031/036.

## Planned data verification

Read-only checks must compare source fingerprint, table counts, declared FKs and the
specific domain joins above. Synthetic isolated test databases cover missing references,
duplicate names, conflicting FX, boundary timestamps and nulls. Creating those test
fixtures later does not authorize changing the supplied database in the application.

The golden SQL has been checked against the supplied file, but this is not evidence
of future agent quality. Data checks exist in tests/test_data.py; known-case model results are in
[evaluation evidence](../evaluation/README.md). Calculations, edge fixtures
and write invariants are assigned to [work packages](../plans/implementation.md).

## Hard-hour source provenance

The native authorizer records physical source columns as well as tables. A recognized
hard-booked percentage list must read bookings.minutes; aliasing an interval/epoch
calculation as minutes/hours cannot satisfy this check. The same bounded planner
repair owns this violation. Planner instructions explicitly state SUM(minutes)/60,
full intersecting hard rows including completed bookings, and timestamps for overlap
only. This minimum provenance guard is not a general proof of arbitrary SQL arithmetic.
[Reader checks](../../tests/test_data.py) and [repair checks](../../tests/test_faults.py).
