# Verification layers, evaluation and scoring specification

Status: owner-agreed scoring baseline with implemented runner and local scorer checks.
Actual Azure answers remain unavailable. Source oracles were computed read-only; that is not agent performance.
Requirements: R-05–R-14/22/23/26–R-30.

## Four behavioral verification layers

| Layer | What it proves | What it cannot prove |
| --- | --- | --- |
| Deterministic unit/component tests | Validation, math, identities, permissions and transition rules | Real model interpretation or semantic recall |
| SQLite/API integration | Persistence, SQL results, transactions, endpoint contracts and readback | Overall LLM quality with a scripted provider |
| Process restart and UI | Actual process recovery, browser reload, blocks and decision flow | Semantic correctness on unseen questions |
| Real-model evaluation | End-to-end interpretation, query/tool selection, retrieval and answer quality | Universal correctness beyond the observed cases |

Documentation checks are a separate executable maintenance check, not one of these
behavioral layers. Use scripted providers only as explicit test doubles. No scripted
production answers, fake 'Azure passed' table or mixing double-backed results into model accuracy.

## Published gold cases

Original inputs: [gold JSON](../reference/gold_questions.json). Ten cases: six factual,
two semantic, one write and one out-of-scope. Reference date is 2026-04-01T00:00:00Z.
Use an untouched isolated working copy for independently scored cases.

| Case | Published expectation | Required scoring detail |
| --- | --- | --- |
| gq-01 | Six named EMEA Python people; hard hours 0,0,0,10,18,26 | Set by person; per-person hours tolerance .5; SQL required |
| gq-02 | 32 requirement IDs | Exact set; accepted .5 credit for 30/31 correct IDs and no extras; SQL required |
| gq-03 | 5,157,842.10 USD, 11 active HLS engagements | total_usd tolerance 1.0 USD; SQL required |
| gq-04 | AMER 1, EMEA 1, LATAM 3 | Exact region counts; APAC 0 or omission accepted |
| gq-05 | Mark Stewart 131.5, Andrew King 90.5, Patricia Anderson 62 first; total 425 | First three ordered; hours and total tolerance .5; SQL required |
| gq-06 | 21 blocked critical items; five tied top projects with 2 | Primary count tolerance 0; SQL required; answer also names valid leader(s) |
| gq-07 | At least four people from ten strong matches | Overlap plus (title OR experience from bio) AND actual skill with proficiency |
| gq-08 | Five projects, at least four matches | Accepted overlap minimum four; explanation needs client industry and people-risk category |
| gq-09 | Amanda 1, project 1, April 2026, 40h, soft/SFT, 2400 minutes | All behaviors: no insert before decision, Confirm, Reject, restart; exactly one row |
| gq-10 | No weather answer; optional known start date/city separated | Any asserted weather value fails |

The three zero-hour people in gq-01 must remain in the result. Applying only HRD or
proportional overlap changes expected hours. Its reference SQL does not test <60%;
the application still must. gq-03 needs total beyond detail rows; gq-05 needs total
beyond top five; gq-06 needs a total beyond grouped rows. gq-07 SQL is alphabetical,
not a suitability ranking. gq-08 yields six project/risk rows but five projects.

Keep public metric and broader contract checks distinct: an implementation can match
21 and still omit requested leading projects. Do not silently rewrite source scoring
or hide incomplete answers behind a narrow passing number.

## Accepted scoring mechanics

- Factual: compare delivered structured values/keys with oracle values; numeric unit
  normalization and tolerances are explicit. Duplicates do not earn extra credit.
- Lists: match the source key; preserve requested ordering for gq-05. Internally use
  entity IDs to resolve name collisions without changing published visible expectations.
- Scalars: use a visible one-row metric table. Do not replace an absent
  delivered total with a hidden oracle calculation and call the answer correct.
- Provenance: all relevant successful queries/values are exposed; no constant guessed
  answer, failed-query draft or source-incompatible join counts as proper grounding.
- Semantic: score overlap separately from item-specific evidence and truthfulness.
  A nonempty explanation is not proof. Validate cited IDs, excerpts, skills/levels,
  years/title and industry/risk categories against source facts. Free text still needs
  manual review under the rubric below; no hidden regex guarantee or baseline model judge.
- Write: inspect the database before/after each step, action receipt and source invariants;
  do not score based on 'created' in model prose.
- Out-of-scope: verify stated data limitation and no invented external fact. Keyword
  absence alone does not establish truthfulness; review ambiguous outputs explicitly.

### Accepted interpretation of published ambiguities

- gq-02: 1 for the exact 32 IDs; .5 for 30 or 31 correct IDs with no extras; 0 otherwise.
  This owner-approved interpretation implements the source hint, not a new employer rule.
- gq-07: at least four strong matches from the published ten. Each proposed person needs
  role/title OR experience evidence from bio, AND a relevant actual skill with level.
  Do not parse this as title OR (experience AND skill). No invented leadership record.
- gq-08: at least four of the five projects despite match=set wording. Ground each in
  client industry summary AND relevant staffing/key-person risk. Group duplicate risk
  rows without losing distinct evidence categories.
- gq-09: every specified behavior is required, with isolated Confirm/Reject/restart
  subcases. Check source row content, no pre-confirm insert and one receipt-linked row.
- gq-10: any asserted weather value fails, even alongside a refusal or known project fact.

Public metric and broader contract are separate. Extra non-gold semantic entities can
be valid; report source-grounded extras versus irrelevant/unsupported extras. A giant
unfiltered list does not satisfy a ranked relevant-shortlist contract merely by overlap.
Own cases use all required conditions =>1, otherwise0; no invented partial-credit rules.

### Manual semantic and free-text review

Code checks IDs, actual excerpts, skills/levels, years/title and industry/risk facts.
A reviewer checks relevance, logical justification, unsupported claims and faithful
refusal wording against the saved evidence. Baseline has no DSPy judge. Emit an audit
bundle per case with visible blocks, source references and automated findings.

Each report carries `score`, `contract_checks` and `review_status` separately. Free-text
checks remain review_required until actually reviewed; automated overlap is provisional,
not a final passed assertion. Record reviewer/outcome/reason and retain failed checks.
A review-required case cannot be silently converted to passed by a scripted assertion.
If review is unavailable, report the open review as a delivery limitation.

## Additional cases

[Twelve approved case specifications](../reference/additional-cases-draft.json) are specification data,
not a running harness. Five factual and three semantic oracles were computed directly
from the supplied source. Three write and one unsupported-action case have behavioral
expectations. Intervals use inclusive human end days and internal half-open UTC; scoring is
all-required as specified. The historical filename retains draft for link stability.

| Case | Intent | Coverage |
| --- | --- | --- |
| own-01 | APAC Python count | Changed region/aggregation, not a gold phrase |
| own-02 | Three simultaneous level-5 skills | Genuine empty set using valid catalogue skills |
| own-03 | BRL invoices converted to USD | Different financial domain and FX |
| own-04 | Leaf effort for ENG-2026-0001 | WBS grain and double counting |
| own-05 | Direct hard-booked time for person 348 | Allocation-person mismatch |
| own-06 | All active projects exposed to staff shortage | Risk paraphrase and project-grain completeness |
| own-07 | Banking projects dependent on a key individual | Exhaustive industry plus semantic risk, truthful empty set |
| own-08 | Healthcare/pharma risks outside HLS | Exhaustive industry versus provider unit |
| own-09 | Ambiguous Amanda Mitchell booking | No first-match write |
| own-10 | Eight-hour booking followed by Reject | No insert and visible terminal state |
| own-11 | Same action Confirm twice | Idempotent receipt and one insertion |
| own-12 | Delete Amanda's soft bookings | Unsupported write cannot mutate source |

Twenty-two specified questions cover the required minimum of twenty. They satisfy
the execution requirement only after the actual agent/runner have run them. Technical adversarial/restart
tests are extra coverage, not automatically counted as the ten new natural-language cases.

## Fixtures and isolation

One fresh working source copy per independent eval case. Multi-turn/restart steps
inside one case share only that case's persistent directory. Recreate fixtures rather
than cleaning up with DELETE against the original. Synthetic micro-fixtures can create
boundary, null, duplicate and FX-conflict situations without changing supplied source.

Record initial source hash and relevant row counts. For writes compare source tables,
allowing only the intended confirmed booking row; original supplied file never changes.
Read-only, ambiguity and Reject cases permit no appended bookings either. A missing
working file fails verification. Validate visible proposal dates and receipt-linked
row terms again after process restart, not only the final booking count.
Test genuine process termination/startup with stable file paths, plus injected failure
before/after transactional commit. Recreating a Python object is useful but not the
same proof as an actual subprocess/API restart.

## Measurements and repeatability

Report question ID/type, score, safety/contract checks, failure reason, elapsed time,
language-model/embedding call counts, tokens if available, model/deployment/settings,
reference date, source hash, and run identifier. Rate limits/budget come from invitation;
do not invent cost estimates without usage and current pricing. Keep secrets out of traces.

Use a bounded rerun policy for stochastic failures. Report all runs rather than only
the best result. Gold is a public acceptance/dev set, not an unseen test benchmark.
If optimization is added later, separate training/validation/held-out questions and
report before/after without training on held-out answers. Optimizer remains optional.

## Accepted completion target

No safety failure may be averaged away by high factual scores. Release target:
all mandatory deterministic invariants and booking behaviors pass; factual gold meet
their exact metrics; semantic overlap and accepted justification checks pass; out-of-data
request is refused truthfully; all twelve additional cases and UI/restart/fresh-clone scenarios pass.
Manual review status must be explicit, not inferred from an automated score. Any remaining failure is listed with evidence in NOT_DONE/README.

## Planned scenarios

| ID | Given / when | Observable assertions |
| --- | --- | --- |
| S-066 | Full evaluation run with real configured model | All ten gold executed against agent; no oracle/double runtime answers |
| S-067 | Additional case suite | At least ten approved cases covering factual, semantic, write |
| S-068 | Number/set/order metric with boundary tolerances | Correct key/order/unit, exact pass/fail at tolerance edge |
| S-069 | Incomplete or ungrounded semantic answer | Overlap does not hide missing evidence or irrelevant additions |
| S-070 | Write/no-data behavior | Database and assertions, not optimistic response prose, determine result |
| S-071 | Sequential isolated runs | Earlier write cannot contaminate later factual/write fixtures |
| S-072 | Runner output and README table | Per-case score/reason and reproducible settings; no invented passed results |
| S-073 | Logs, repo and error response inspected | No secrets/provider credentials or accidental private state |
| S-074 | Azure unavailable, throttled, or no credentials | Explicit unverified/failure status; bounded retries, no fake success |
| S-075 | Submission documents reviewed | README commands/results; one-page DESIGN includes topology/signatures/state/separation/limits/AI use; honest NOT_DONE |
| S-076 | Submission rehearsal/demo | Fresh clone and three representative conversations, real restart confirmation, accessible repo/history |

Implemented checks cover a subset; see the linked tests and verification limits below. Executable local checks and their limits are described in [verification](../development/verification.md).

## Implemented check coverage

See [topic checks](../../tests/test_scoring.py) and [current verification](../development/verification.md).
The [runner checks](../../tests/test_evaluation.py) execute isolated real API processes
with an explicit test-only model. They cover all five write-case branches, unexpected
read-side inserts, corrupted proposal/restart terms, CLI reports, review gates,
failure continuation and startup cleanup. These are harness tests, not model scores.
Real Azure quality and any scenario not explicitly mapped there remain unverified.
