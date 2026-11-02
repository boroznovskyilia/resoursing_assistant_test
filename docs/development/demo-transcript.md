# Recorded demo transcript — 2 November 2026

Genuine production FastAPI/React application, Azure gpt-4.1-mini and
text-embedding-3-small. Browser interactions were automated with Playwright; no
scripted model responses or edited answers. Reference date: 1 April 2026 UTC.

The local MP4 is 2m35s, 1440×1000, with English captions and no audio. Only the
browser viewport is recorded. One long semantic-response waiting interval is shown
at8× speed and explicitly labelled; all responses and the restart/Confirm sequence
remain unchanged. The full continuous source recording is4m54s.

Local recording and verification files are under `.runtime/demo/20261102/`:
`resourcing-assistant-demo.mp4`, `resourcing-assistant-raw.webm`, `answers.json`,
`evidence.json`, `verification.json` and `rendering.json`. These files are ignored
by Git. This transcript is versioned; an accessible video/repository link must still
be supplied before external submission.

MP4 SHA-256: `b95d1514a4822cc6db16309ce6bd5706857ae40d1b8d931fa0926ef8d76f157a`.

## 1. Factual question

**User:** Who in EMEA has Python at proficiency 4 or higher and is less than 60% hard-booked between March and May 2026?

The query results list six individuals in the EMEA region who have Python proficiency of 4 or higher and are less than 60% hard-booked between March and May 2026. Their hard-booked hours range from 0 to 26 hours over the period, with corresponding hard-booked percentages from 0% up to 5%. The individuals are Anthony Thompson, Kevin Robinson, Edward Hill, Matthew Hill, Matthew White, and David Allen. The data is complete for this query and no truncation occurred. The assumptions include the date range being inclusive of March 1 to May 31, 2026, and that hard-booked hours are calculated from bookings of kind 'hard' overlapping the date range. Capacity is set at 520 hours for the period, representing standard working hours. The percentages are calculated as hard-booked hours divided by capacity hours times 100, and all listed individuals have less than 60% hard-booked allocation as requested.

**List people in EMEA with Python skill proficiency >=4 and hard-booked percentage less than 60% between March and May 2026, including person_id, name, hard_booked_hours and hard_booked_pct.**

| person id | name | hard booked hours | hard booked pct |
| --- | --- | --- | --- |
| 30 | Anthony Thompson | 10 | 1.9230769230769231 |
| 167 | Kevin Robinson | 18 | 3.4615384615384617 |
| 261 | Edward Hill | 0 | 0 |
| 280 | Matthew Hill | 0 | 0 |
| 328 | Matthew White | 0 | 0 |
| 344 | David Allen | 26 | 5 |

Coverage: `{"has_more": false, "mode": "structured", "truncated": false}`.

**Executed SQL:** List people in EMEA with Python skill proficiency >=4 and hard-booked percentage less than 60% between March and May 2026, including person_id, name, hard_booked_hours and hard_booked_pct.

```sql
WITH skill_python AS (
  SELECT ps.person_id
  FROM person_skills ps
  JOIN skills s ON ps.skill_id = s.skill_id
  WHERE s.name = 'Python' AND ps.proficiency >= 4
),
booked_hours AS (
  SELECT
    b.person_id,
    SUM(b.minutes) / 60.0 AS hard_booked_hours
  FROM bookings b
  WHERE b.kind = 'hard'
    AND b.start_ts < :window_end
    AND b.end_ts > :window_start
  GROUP BY b.person_id
),
people_emea AS (
  SELECT p.person_id, p.display_name
  FROM people p
  WHERE p.location_region = 'EMEA'
),
capacity AS (
  SELECT :capacity_hours AS capacity_hours
)
SELECT
  p.person_id,
  p.display_name AS name,
  COALESCE(bh.hard_booked_hours, 0) AS hard_booked_hours,
  CASE WHEN c.capacity_hours > 0 THEN COALESCE(bh.hard_booked_hours, 0) * 100.0 / c.capacity_hours ELSE NULL END AS hard_booked_pct
FROM people_emea p
JOIN skill_python sp ON p.person_id = sp.person_id
LEFT JOIN booked_hours bh ON p.person_id = bh.person_id
CROSS JOIN capacity c
WHERE (COALESCE(bh.hard_booked_hours, 0) * 100.0 / c.capacity_hours) < 60
ORDER BY p.person_id ASC;
```

Parameters:

```json
{
  "window_start": 1772323200,
  "window_end": 1780272000,
  "capacity_hours": 520
}
```

Assumptions: The date range March to May 2026 is inclusive, so start_date is 2026-03-01 and end_date is 2026-05-31.; Hard-booked means bookings with kind='hard' including completed rows, counting minutes intersecting the date range.; Proficiency 4 or higher means person_skills.proficiency >= 4 for skill 'Python'.; Region EMEA means people.location_region = 'EMEA'.; Less than 60% hard-booked means total hard booking allocation percentage over the date range is under 60%.

The delivered answer passed the unchanged gq-01 scorer with score1.0.

## 2. Semantic recommendations

**User:** Find experienced data engineers who could lead a data-migration workstream.

**Source-grounded matches**

1. **Olivia Walker** (person_id=367). Olivia Walker has 12 years of experience as a Data Engineer and Delivery Lead with strong skills in Data Engineering and PostgreSQL, demonstrating both technical expertise and leadership potential suitable for leading a data-migration workstream.

   Source: Olivia Walker is a AMER-based Data Engineer with 12 years of experience delivering enterprise software and consulting engagements. | Roles: Data Engineer, Delivery Lead | Skills: Ruby on Rails, Data Engineering, PostgreSQL, Redis, AWS, Azure

   Skill levels: Ruby on Rails (3), Data Engineering (4), PostgreSQL (4), Redis (2), AWS (4), Azure (4)

2. **David Robinson** (person_id=60). David Robinson has 11 years of experience and strong data engineering skills (proficiency 5) including ETL Design, which is highly relevant for data migration. His technical competence makes him suitable to lead a data-migration workstream.

   Source: David Robinson is a LATAM-based Machine Learning Engineer with 11 years of experience delivering enterprise software and consulting engagements. | Roles: Machine Learning Engineer | Skills: Data Engineering, ETL Design, Data Viz, Prompt Engineering, Machine Learning, Scrum Mastery

   Skill levels: Data Engineering (5), ETL Design (4), Data Viz (5), Prompt Engineering (3), Machine Learning (3), Scrum Mastery (3)

3. **Edward Mitchell** (person_id=90). Edward Mitchell has 11 years of experience and explicit Data Engineering skill at high proficiency (5). Despite being a Machine Learning Engineer, his strong data engineering expertise supports suitability to lead a data-migration workstream.

   Source: Edward Mitchell is a AMER-based Machine Learning Engineer with 11 years of experience delivering enterprise software and consulting engagements. | Roles: Machine Learning Engineer | Skills: Data Engineering, Prompt Engineering, Feature Engineering

   Skill levels: Data Engineering (5), Prompt Engineering (5), Feature Engineering (3)

4. **Mark Phillips** (person_id=264). Mark Phillips has 12 years of experience and explicit Data Engineering skills with strong proficiency in PostgreSQL, making him suitable to lead a data-migration workstream.

   Source: Mark Phillips is a LATAM-based Machine Learning Engineer with 12 years of experience delivering enterprise software and consulting engagements. | Roles: Machine Learning Engineer | Skills: GraphQL, Data Engineering, Neo4j / Cypher, PostgreSQL

   Skill levels: GraphQL (2), Data Engineering (2), Neo4j / Cypher (3), PostgreSQL (4)

5. **Patricia Campbell** (person_id=374). Patricia Campbell has 12 years of experience as a Data Engineer with relevant technical skills including SQL Modeling and Azure, suitable to lead a data-migration workstream.

   Source: Patricia Campbell is a APAC-based Data Engineer with 12 years of experience delivering enterprise software and consulting engagements. | Roles: Data Engineer | Skills: Ruby on Rails, SQL Modeling, Kubernetes, Azure, Security Review, Performance Tuning, Docker

   Skill levels: Ruby on Rails (3), SQL Modeling (2), Kubernetes (5), Azure (5), Security Review (5), Performance Tuning (3), Docker (4)

6. **Matthew Evans** (person_id=87). Matthew Evans has 8 years of experience as a Data Engineer with relevant skills in Data Engineering and PostgreSQL at proficient levels, indicating strong technical competence suitable for leading a data-migration workstream.

   Source: Matthew Evans is a EMEA-based Data Engineer with 8 years of experience delivering enterprise software and consulting engagements. | Roles: Data Engineer, Senior Developer | Skills: Data Engineering, PostgreSQL, Docker, Machine Learning

   Skill levels: Data Engineering (2), PostgreSQL (5), Docker (2), Machine Learning (3)

7. **Donald Lee** (person_id=169). Donald Lee has 8 years of experience including the role of Data Engineer and strong technical skills relevant to data engineering, making him suitable to lead a data-migration workstream.

   Source: Donald Lee is a LATAM-based Consultant with 8 years of experience delivering enterprise software and consulting engagements. | Roles: Consultant, Data Engineer | Skills: API Design, Event Sourcing, GraphQL, Go, Project Management, Business Analysis

   Skill levels: API Design (5), Event Sourcing (5), GraphQL (5), Go (3), Project Management (5), Business Analysis (5)

8. **Emily Allen** (person_id=342). Emily Allen has 8 years of experience as a Data Engineer with strong skills in ETL Design and SQL Modeling, which are critical for data migration, making her suitable to lead a data-migration workstream.

   Source: Emily Allen is a LATAM-based Data Engineer with 8 years of experience delivering enterprise software and consulting engagements. | Roles: Data Engineer | Skills: ETL Design, SQL Modeling, Azure, Observability, Security Review, Docker

   Skill levels: ETL Design (3), SQL Modeling (5), Azure (3), Observability (3), Security Review (5), Docker (3)

9. **Robert Williams** (person_id=207). Robert Williams has 9 years of experience with explicit Data Engineering skills and relevant technical skills, suitable to lead a data-migration workstream.

   Source: Robert Williams is a APAC-based Machine Learning Engineer with 9 years of experience delivering enterprise software and consulting engagements. | Roles: Machine Learning Engineer, Consultant | Skills: Data Engineering, ETL Design, PostgreSQL, Redis, Kafka, Prompt Engineering, Feature Engineering

   Skill levels: Data Engineering (2), ETL Design (4), PostgreSQL (2), Redis (2), Kafka (3), Prompt Engineering (3), Feature Engineering (2)

10. **John Morris** (person_id=91). John Morris has 8 years of experience as a Data Engineer with strong skills in ETL Design and SQL Modeling, essential for data migration, making him suitable to lead a data-migration workstream.

   Source: John Morris is a AMER-based Data Engineer with 8 years of experience delivering enterprise software and consulting engagements. | Roles: Data Engineer, Scrum Master | Skills: Python, Data Engineering, ETL Design, SQL Modeling, Kafka, Kubernetes

   Skill levels: Python (3), Data Engineering (2), ETL Design (5), SQL Modeling (3), Kafka (4), Kubernetes (2)

Coverage: `{"complete": false, "eligible": 400, "fallback": false, "matched": 23, "mode": "shortlist", "order": "assessed_ranking", "processed": 40, "uncertain": 0}`.

**Coverage and matching count**

| eligible | processed | matched | uncertain |
| --- | --- | --- | --- |
| 400 | 40 | 23 | 0 |

Coverage: `{"complete": false, "eligible": 400, "fallback": false, "matched": 23, "mode": "shortlist", "order": "assessed_ranking", "processed": 40, "uncertain": 0}`.

**Executed SQL:** Exact structured candidate pool

```sql
SELECT person_id FROM people ORDER BY person_id
```

Parameters:

```json
{}
```

Assumptions: Experienced means demonstrated proficiency or seniority in data engineering skills.; Leading a data-migration workstream implies suitability for leadership roles, which requires semantic assessment of bio or skills.; Data-migration is a concept that requires semantic understanding, not just a literal skill name.

The public gq-07 automated checks scored1.0. Codex separately inspected the
delivered reasons/source fields; this is AI-assisted review, not independent human
validation. Suitability for leading a workstream is an inference from experience,
roles and skills, not proof of prior migration leadership. This recording is not a
new full22-case evaluation run.

## 3. Booking and actual API restart

**User:** Soft-book Amanda Evans on ENG-2026-0001 for 40 hours in April 2026.

**Booking card — pending**

```json
{
  "action_id": "b5b07d32a3f44d9fb3c34a7b2b1e0d35",
  "status": "pending",
  "fields": {
    "person_id": 1,
    "person": "Amanda Evans",
    "engagement_id": 1,
    "engagement": "ENG-2026-0001",
    "start": "2026-04-01",
    "end_inclusive": "2026-04-30",
    "end_exclusive": "2026-05-01",
    "hours": 40,
    "minutes": 2400,
    "warnings": [],
    "kind": "soft"
  },
  "booking_id": null
}
```

Assumptions: April 2026 interpreted as 2026-04-01 to 2026-04-30 inclusive

Before proposal: 2620 bookings. While pending: 2620.

Stopped actual API process 9231; health became unreachable. Started new process 10085 with the same demo SQLite files. Reloaded the same UI conversation. The proposal and Confirm/Reject buttons were restored; no booking had been inserted.

**User action:** Confirm soft booking after restart.

**Booking card — confirmed**

```json
{
  "action_id": "b5b07d32a3f44d9fb3c34a7b2b1e0d35",
  "status": "confirmed",
  "fields": {
    "person_id": 1,
    "person": "Amanda Evans",
    "engagement_id": 1,
    "engagement": "ENG-2026-0001",
    "start": "2026-04-01",
    "end_inclusive": "2026-04-30",
    "end_exclusive": "2026-05-01",
    "hours": 40,
    "minutes": 2400,
    "warnings": [],
    "kind": "soft"
  },
  "booking_id": 2621
}
```

After Confirm: 2621 bookings; saved booking #2621 is soft/SFT, Amanda Evans, ENG-2026-0001, 2400minutes, 1–30 April2026 inclusive. Repeating Confirm returned HTTP200 and the count stayed unchanged.

## 4. Reject safety check

**User:** Soft-book Amanda Evans on ENG-2026-0001 for 8 hours on May 4, 2026.

**Booking card — pending**

```json
{
  "action_id": "27b8e4243c3e4bff8973a4fa87e4c5d1",
  "status": "pending",
  "fields": {
    "person_id": 1,
    "person": "Amanda Evans",
    "engagement_id": 1,
    "engagement": "ENG-2026-0001",
    "start": "2026-05-04",
    "end_inclusive": "2026-05-04",
    "end_exclusive": "2026-05-05",
    "hours": 8,
    "minutes": 480,
    "warnings": [],
    "kind": "soft"
  },
  "booking_id": null
}
```

Assumptions: May 4, 2026 interpreted as a single day booking

**User action:** Reject. The UI displayed rejected status; the second proposal
created no booking. The final database has exactly one additional confirmed soft
booking. All24 original-table invariants passed; only the permitted booking insert
was added. The original input file and existing main workspace were not modified.

## Verification boundaries

Media metadata and representative frames were checked. This demo supplements the
existing22-case evaluation; it does not establish unseen-question accuracy or
production-load reliability. No video upload, repository publication or email was sent.
