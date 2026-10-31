# Data Dictionary — `source.sqlite`

Operational (OLTP) database for a professional-services / project-resourcing
business: clients and vendors, people and their skills, projects (engagements)
with their work breakdown, staffing and bookings, time tracking, resource
requirements, governance (approvals and risks), and vendor invoices.

## Conventions

- **Identifiers** — every table has an integer surrogate primary key (autoincrement style).
- **Timestamps** — columns ending in `_ts` (and `due_ts`, `decided_ts`, etc.) store **Unix epoch seconds (UTC)** as integers.
- **Money** — columns ending in `_cents` store amounts as **integer minor units** (e.g. cents). Divide by 100 for the decimal value.
- **Durations** — `minutes` columns store elapsed time in **minutes**; `*_hours` columns store hours as real numbers.
- **Flags** — boolean-style columns (`is_*`, `active`, `is_primary`, `is_default`, `is_milestone`, …) use integer **0/1**.
- **Foreign keys** — noted per column; `PRAGMA foreign_keys = ON` is set by the schema.

---

## Reference / lookup tables

### `currencies`
Catalog of currencies used across rate cards, engagements and invoices.

| Column | Type | Description |
|---|---|---|
| `currency_id` | INTEGER PK | Currency identifier. |
| `iso_code` | TEXT | ISO 4217 code (USD, EUR, GBP, BRL). |
| `symbol` | TEXT | Display symbol. |
| `is_primary` | INTEGER 0/1 | 1 for the organization's reporting currency. |

### `status_lookup`
Single lookup that holds the status values for every domain (projects, tasks,
bookings, requirements, teams). Rows are grouped by `domain`.

| Column | Type | Description |
|---|---|---|
| `status_id` | INTEGER PK | Status identifier (referenced by the domain tables). |
| `domain` | TEXT | Which area the status belongs to: `project`, `task`, `booking`, `requirement`, `team`. |
| `code` | TEXT | Short machine code (e.g. `ACT`, `INP`, `DNE`). |
| `label` | TEXT | Human-readable label (e.g. "In Progress"). |
| `state_group` | TEXT | Coarse bucket for reporting (e.g. `open`, `doing`, `done`, `closed`). |

### `business_units`
Top-level organizational units (industry verticals / practices).

| Column | Type | Description |
|---|---|---|
| `business_unit_id` | INTEGER PK | Business unit identifier. |
| `code` | TEXT | Short code (e.g. `FS`, `HLS`). |
| `name` | TEXT | Full name (e.g. "Financial Services"). |

### `org_units`
Delivery units nested under a business unit (capability × geography).

| Column | Type | Description |
|---|---|---|
| `org_unit_id` | INTEGER PK | Org unit identifier. |
| `code` | TEXT | Short code (e.g. `DA-NA`). |
| `name` | TEXT | Full name (e.g. "Data & Analytics — North America"). |
| `business_unit_id` | INTEGER FK → business_units | Parent business unit. |

### `parties`
Unified table of external and internal organizations. A single `party_type`
column distinguishes **clients**, **vendors**, and **internal** entities.

| Column | Type | Description |
|---|---|---|
| `party_id` | INTEGER PK | Party identifier. |
| `party_type` | TEXT | `client`, `vendor`, or `internal`. |
| `legal_name` | TEXT | Registered legal name. |
| `display_name` | TEXT | Short display name. |
| `country` | TEXT | Country. |
| `city` | TEXT | City. |

---

## People, skills and rates

### `people`
Individual resources (staff, contractors) who can be staffed on projects.

| Column | Type | Description |
|---|---|---|
| `person_id` | INTEGER PK | Person identifier. |
| `given_name` | TEXT | First name. |
| `family_name` | TEXT | Last name. |
| `display_name` | TEXT | Full display name. |
| `email` | TEXT | Contact email. |
| `bio` | TEXT | Short professional biography. |
| `auth_user_id` | TEXT | External identity/SSO user id (GUID-style). |
| `avatar_url` | TEXT | URL reference to a profile image. |
| `location_region` | TEXT | Region the person works in (EMEA, AMER, APAC, LATAM). |
| `created_ts` / `updated_ts` | INTEGER | Record create / last-update timestamps. |

### `person_avatars`
Binary profile picture per person, kept out of the `people` row because the
image is heavy. One row per person.

| Column | Type | Description |
|---|---|---|
| `person_id` | INTEGER PK, FK → people | The person this portrait belongs to. |
| `mime` | TEXT | Image MIME type (`image/jpeg`, `image/png`). |
| `width` / `height` | INTEGER | Pixel dimensions. |
| `source` | TEXT | How the image was produced. |
| `source_url` | TEXT | Origin URL when applicable (else NULL). |
| `byte_size` | INTEGER | Size of the binary in bytes. |
| `bytes` | BLOB | Raw image bytes. |
| `created_ts` | INTEGER | When the avatar was stored. |

### `skills`
Catalog of skills that people can hold.

| Column | Type | Description |
|---|---|---|
| `skill_id` | INTEGER PK | Skill identifier. |
| `name` | TEXT | Skill name (e.g. "Ruby on Rails"). |
| `description` | TEXT | Short description. |
| `family` | TEXT | Grouping (e.g. `backend`, `data`, `frontend`, `platform`, `ai`, `delivery`). |

### `person_skills`
Junction table linking people to skills (many-to-many), with proficiency.

| Column | Type | Description |
|---|---|---|
| `person_skill_id` | INTEGER PK | Row identifier. |
| `person_id` | INTEGER FK → people | The person. |
| `skill_id` | INTEGER FK → skills | The skill held. |
| `proficiency` | INTEGER | Proficiency level (1–5). |
| `acquired_ts` | INTEGER | When the skill was acquired. |

### `rate_categories`
Billing roles / rate categories (e.g. "Senior Developer", "Project Manager")
with a utilization target.

| Column | Type | Description |
|---|---|---|
| `category_id` | INTEGER PK | Rate category identifier. |
| `ref_number` | TEXT | External reference code (e.g. `RC-003`). |
| `name` | TEXT | Category / role name. |
| `description` | TEXT | Short description. |
| `target_util_pct` | INTEGER | Target billable utilization, 0–100. |

### `rate_cards`
Priced rate cards per category, per price list and currency.

| Column | Type | Description |
|---|---|---|
| `rate_card_id` | INTEGER PK | Rate card identifier. |
| `category_id` | INTEGER FK → rate_categories | The role being priced. |
| `pricelist_id` | INTEGER | Price list this card belongs to (1 = Standard, 2 = Premium). |
| `currency_id` | INTEGER FK → currencies | Currency of `unit_price_cents`. |
| `fx_rate` | REAL | Exchange rate of the currency to the reporting currency. |
| `unit_price_cents` | INTEGER | Hourly bill rate, in minor units of `currency_id`. |
| `tier` | TEXT | Pricing tier label (`standard`, `premium`). |

### `category_assignments`
Which rate categories (roles) each person is assigned to; one is the default.

| Column | Type | Description |
|---|---|---|
| `cat_assignment_id` | INTEGER PK | Row identifier. |
| `person_id` | INTEGER FK → people | The person. |
| `category_id` | INTEGER FK → rate_categories | The role assigned. |
| `label` | TEXT | Display label. |
| `is_default` | INTEGER 0/1 | 1 for the person's primary role. |

---

## Projects and work

### `engagements`
Client projects. Holds ownership, schedule (planned vs. actual), status,
effort and financial figures (planned vs. actual cost and revenue, in the
engagement's currency).

| Column | Type | Description |
|---|---|---|
| `engagement_id` | INTEGER PK | Project identifier. |
| `code` | TEXT | Human project number (e.g. `ENG-2025-0042`). |
| `title` | TEXT | Project title. |
| `summary` | TEXT | Short description. |
| `client_party_id` | INTEGER FK → parties | Client organization. |
| `delivery_unit_id` | INTEGER FK → org_units | Delivery unit responsible. |
| `manager_person_id` | INTEGER FK → people | Project manager. |
| `owner_person_id` | INTEGER FK → people | Project owner. |
| `business_unit_id` | INTEGER FK → business_units | Owning business unit. |
| `planned_start_ts` / `planned_end_ts` | INTEGER | Baseline schedule. |
| `actual_start_ts` / `actual_end_ts` | INTEGER | Actual dates (nullable until they occur). |
| `scheduling_mode` | TEXT | `auto`, `manual` or `fixed`. |
| `status_id` | INTEGER FK → status_lookup | Project status (`project` domain). |
| `pct_complete` | REAL | Progress, 0–1. |
| `budget_effort_hours` | REAL | Planned effort in hours. |
| `effort_done_hours` / `effort_left_hours` | REAL | Completed / remaining effort. |
| `planned_cost_cents` / `actual_cost_cents` | INTEGER | Planned / actual cost. |
| `planned_revenue_cents` / `actual_revenue_cents` | INTEGER | Planned / actual revenue. |
| `currency_id` | INTEGER FK → currencies | Currency of the money columns. |
| `source_tag` | TEXT | Origin/source system tag. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `work_items`
Work Breakdown Structure of a project: a 3-level tree (phases → workstreams →
tasks) via a self-referencing `parent_item_id`. Summary rows aggregate their
children; leaf rows carry the actual effort.

| Column | Type | Description |
|---|---|---|
| `work_item_id` | INTEGER PK | Work item identifier. |
| `engagement_id` | INTEGER FK → engagements | Owning project. |
| `wbs_code` | TEXT | Hierarchical WBS code (e.g. `1.2.3`). |
| `item_number` | INTEGER | Sequential number within the project. |
| `label` | TEXT | Task / phase name. |
| `parent_item_id` | INTEGER FK → work_items | Parent item (NULL for top-level phases). |
| `sort_order` | INTEGER | Display order. |
| `est_hours` | REAL | Planned effort in hours. |
| `done_hours` / `left_hours` | REAL | Completed / remaining effort. |
| `pct` | REAL | Progress percentage (0–100). |
| `is_milestone` | INTEGER 0/1 | 1 for zero-effort milestone markers. |
| `is_critical` | INTEGER 0/1 | 1 if on the critical path. |
| `is_manual` | INTEGER 0/1 | 1 if manually scheduled. |
| `planned_start_ts` / `planned_end_ts` | INTEGER | Planned dates. |
| `sched_start_ts` / `sched_end_ts` | INTEGER | Scheduled dates. |
| `planned_cost_cents` / `actual_cost_cents` | INTEGER | Planned / actual cost. |
| `planned_revenue_cents` / `actual_revenue_cents` | INTEGER | Planned / actual revenue. |
| `status_id` | INTEGER FK → status_lookup | Task status (`task` domain). |
| `cost_center_code` | TEXT | Cost center the work is charged to. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `work_item_links`
Scheduling dependencies between two work items (predecessor → successor).

| Column | Type | Description |
|---|---|---|
| `link_id` | INTEGER PK | Dependency identifier. |
| `engagement_id` | INTEGER FK → engagements | Project the dependency belongs to. |
| `predecessor_item_id` | INTEGER FK → work_items | The item that must come first. |
| `successor_item_id` | INTEGER FK → work_items | The dependent item. |
| `link_kind` | TEXT | Dependency type: `FS`, `SS`, `FF`, `SF`. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

---

## Staffing, time and bookings

### `resource_requirements`
Open staffing needs on a project ("we need a role, here, for this window").

| Column | Type | Description |
|---|---|---|
| `requirement_id` | INTEGER PK | Requirement identifier. |
| `name` | TEXT | Requirement label (e.g. "Open role: Data Engineer"). |
| `engagement_id` | INTEGER FK → engagements | Project needing the resource. |
| `role_category_id` | INTEGER FK → rate_categories | Requested role. |
| `status_id` | INTEGER FK → status_lookup | Requirement status (`requirement` domain). |
| `is_primary` | INTEGER 0/1 | 1 if a primary requirement. |
| `alloc_method` | TEXT | Allocation method (`full`, `percentage`, `by-hours`). |
| `work_location` | TEXT | `onsite`, `remote`, `hybrid`. |
| `from_ts` / `to_ts` | INTEGER | Needed-from / needed-to window. |
| `effort` | REAL | Requested effort. |
| `duration` / `remaining_duration` / `fulfilled_duration` | REAL | Total / remaining / fulfilled duration. |
| `fulfilled_hours` | REAL | Hours already fulfilled. |
| `pct` | REAL | Fulfillment percentage. |
| `cost_price_cents` | INTEGER | Cost rate for the role. |
| `quantity` | INTEGER | Number of resources needed. |
| `city` / `state_or_province` / `country` | TEXT | Location of the requirement. |
| `latitude` / `longitude` | REAL | Geocoordinates of the location. |
| `request_status` | TEXT | Free-text request state. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `requirement_requests`
Requests raised to fulfil a resource requirement (a requirement can have several).

| Column | Type | Description |
|---|---|---|
| `request_id` | INTEGER PK | Request identifier. |
| `requirement_id` | INTEGER FK → resource_requirements | The requirement being fulfilled. |
| `state` | TEXT | Request state (`submitted`, `approved`, `declined`, `fulfilled`). |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `team_allocations`
Project team membership: a person allocated to a project in a given role, with
planned/booked hours. One row per person per team allocation.

| Column | Type | Description |
|---|---|---|
| `allocation_id` | INTEGER PK | Allocation identifier. |
| `name` | TEXT | Team name (e.g. "Acme Delivery Team"). |
| `engagement_id` | INTEGER FK → engagements | Project. |
| `category_id` | INTEGER FK → rate_categories | Role on the team. |
| `person_id` | INTEGER FK → people | Team member. |
| `requirement_id` | INTEGER | Related resource requirement (soft reference). |
| `org_unit_id` | INTEGER FK → org_units | Delivery unit supplying the person. |
| `billing_kind` | TEXT | `T&M`, `fixed-fee`, `non-billable`, `capitalized`. |
| `alloc_method` | TEXT | Allocation method. |
| `worker_kind` | TEXT | `employee`, `contractor`, `subcontractor`, `partner`. |
| `start_ts` / `end_ts` | INTEGER | Allocation window. |
| `hours` / `required_hours` | REAL | Allocated / required hours. |
| `hard_hours` / `soft_hours` | REAL | Hard-booked / soft-booked hours. |
| `pct` | REAL | Allocation percentage. |
| `active` | INTEGER 0/1 | 1 if the allocation is active. |
| `status_id` | INTEGER FK → status_lookup | Team status (`team` domain). |
| `owner_person_id` | INTEGER FK → people | Allocation owner. |
| `business_unit_id` | INTEGER FK → business_units | Owning business unit. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `assignments`
A person assigned to a specific work item (task-level assignment) with hours.

| Column | Type | Description |
|---|---|---|
| `assignment_id` | INTEGER PK | Assignment identifier. |
| `person_id` | INTEGER FK → people | Assigned person. |
| `work_item_id` | INTEGER FK → work_items | The task assigned to (leaf tasks). |
| `start_ts` / `end_ts` | INTEGER | Assignment window. |
| `hours` | REAL | Hours assigned. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `time_entries`
Time logged by a person against a work item (timesheet lines).

| Column | Type | Description |
|---|---|---|
| `entry_id` | INTEGER PK | Time entry identifier. |
| `person_id` | INTEGER FK → people | Who logged the time. |
| `work_item_id` | INTEGER FK → work_items | The task the time was logged on. |
| `entry_ts` | INTEGER | When the work was done. |
| `minutes` | INTEGER | Minutes recorded. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `bookings`
Scheduled reservations of a person's time for a project (schedule-board rows).

| Column | Type | Description |
|---|---|---|
| `booking_id` | INTEGER PK | Booking identifier. |
| `header_id` | INTEGER | Grouping id for bookings created together. |
| `person_id` | INTEGER FK → people | Booked person. |
| `engagement_id` | INTEGER FK → engagements | Project the booking is for. |
| `allocation_id` | INTEGER FK → team_allocations | Related team allocation. |
| `status_id` | INTEGER FK → status_lookup | Booking status (`booking` domain). |
| `kind` | TEXT | `hard` or `soft` booking. |
| `category_id` | INTEGER FK → rate_categories | Role booked under. |
| `requirement_id` | INTEGER | Related resource requirement (soft reference). |
| `start_ts` / `end_ts` | INTEGER | Booking window. |
| `minutes` | INTEGER | Booked duration in minutes. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

---

## Governance and billing

### `approvals`
Approval events raised on a project (e.g. budget or gate approvals).

| Column | Type | Description |
|---|---|---|
| `approval_id` | INTEGER PK | Approval identifier. |
| `engagement_id` | INTEGER FK → engagements | Project the approval belongs to. |
| `state` | TEXT | `pending`, `approved`, `rejected`, `escalated`. |
| `decided_ts` | INTEGER | When it was decided (NULL while pending). |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `risks`
Risk-register entries for a project.

| Column | Type | Description |
|---|---|---|
| `risk_id` | INTEGER PK | Risk identifier. |
| `engagement_id` | INTEGER FK → engagements | Project the risk belongs to. |
| `description` | TEXT | Risk description. |
| `severity` | TEXT | `low`, `medium`, `high`, `critical`. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

### `billing_documents`
Vendor invoices. A standalone table (not linked by foreign key to projects);
any project association is by `cost_center_code` value.

| Column | Type | Description |
|---|---|---|
| `doc_id` | INTEGER PK | Invoice identifier. |
| `doc_number` | TEXT | Invoice number (e.g. `INV-2025-00042`). |
| `supplier_party_id` | INTEGER FK → parties | Vendor that issued the invoice. |
| `amount_cents` | INTEGER | Invoice amount. |
| `currency_id` | INTEGER FK → currencies | Invoice currency. |
| `due_ts` | INTEGER | Payment due date. |
| `cost_center_code` | TEXT | Cost center charged. |
| `approval_state` | TEXT | `pending`, `approved`, `paid`, `disputed`. |
| `created_ts` / `updated_ts` | INTEGER | Record timestamps. |

---

## Table summary

| Table | Purpose |
|---|---|
| `currencies` | Currency catalog. |
| `status_lookup` | Status values for all domains. |
| `business_units` | Top-level organizational units. |
| `org_units` | Delivery units under business units. |
| `parties` | Clients, vendors and internal organizations. |
| `people` | Individual resources. |
| `person_avatars` | Profile images (BLOB) per person. |
| `skills` | Skill catalog. |
| `person_skills` | People ↔ skills, with proficiency. |
| `rate_categories` | Billing roles / rate categories. |
| `rate_cards` | Priced rate cards per category/pricelist/currency. |
| `category_assignments` | People ↔ roles. |
| `engagements` | Client projects. |
| `work_items` | Project work breakdown structure. |
| `work_item_links` | Task dependencies. |
| `resource_requirements` | Open staffing needs. |
| `requirement_requests` | Requests to fulfil requirements. |
| `team_allocations` | Project team membership. |
| `assignments` | Person ↔ task assignments. |
| `time_entries` | Logged time (timesheets). |
| `bookings` | Scheduled time reservations. |
| `approvals` | Project approval events. |
| `risks` | Project risk register. |
| `billing_documents` | Vendor invoices. |
