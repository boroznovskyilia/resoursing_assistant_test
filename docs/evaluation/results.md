# Evaluation results

One genuine inference run, runtime `ae6e196`; whole-run offline scorer `ebd3f14`.
Original report and every answer are retained unchanged. Seven wording reviews were
performed by **Codex AI-assisted source inspection**, not an independent human reviewer.
See [grading lineage, original reports and all-run history](README.md).

Run: 20261031T211131Z_822c63 · source SHA-256: 8d00b91ae6aa23bbcf0d807c2e51fa6a45f7017a6557a4f51d11cfc82bfb4259

| Case | Type | Score | Status | Review | Reason |
| --- | --- | --- | --- | --- | --- |
| gq-01 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-02 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-03 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-04 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-05 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-06 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-07 | semantic | 1.0 | passed | approved | Manual review: Inspected all ten delivered reasons, match reasons, verbatim excerpts and complete source facts. Bios, current roles and exact skill/proficiency lists match untouched source. Seven public strong matches: Olivia Walker, John Morris, Kimberly Jackson, Emily Allen, Jessica Williams, Matthew Evans, David Brown. Relevant extras: David Robinson has11 years and Data Engineering5/ETL4; Robert Green has18 total years, current Engagement Manager/Delivery Lead roles and Data Engineering3; David Adams has11 years, a Data Engineer role and PostgreSQL4. Reasons infer potential suitability; source does not establish prior migration leadership or tenure in each listed role. In particular Robert Green role/experience wording is read as overall experience plus current roles, not18 proven years in each leadership position. Shortlist metadata honestly states40/400 assessed,22 matched,0 uncertain; no exhaustive claim. |
| gq-08 | semantic | 1.0 | passed | approved | Manual review: Read every delivered reason and source excerpt. All five correct active projects:59 Pharmaceuticals+staffing/key-person;67 Healthcare+staffing;108 Pharmaceuticals+staffing;110 Pharmaceuticals+key-person;144 Healthcare+key-person. Summaries, risk descriptions, actual project/ACT status and code identities match source. No provider-unit or client-name industry inference; unrelated risks are not presented as qualifying. Coverage60/60,5 matches,0 uncertain. |
| gq-09 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-10 | out_of_scope | 1.0 | passed | approved | Manual review: Complete response explicitly states the supplied database has no weather observations/forecasts and cannot provide a weather value. It asserts no temperature, forecast, inferred weather or external fact. Source invariants passed independently. |
| own-01 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-02 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-03 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-04 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-05 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-06 | semantic | 1.0 | passed | approved | Manual review: Read all11 reasons and quoted staffing-gap evidence. Every returned project has an actual staffing-gap risk and project/ACT status; source query independently confirms IDs6,17,21,29,59,67,80,83,108,111,140. Key-person-only dependency is not counted as staffing shortage. No invented severity/history claims. Coverage60/60,11 matches,0 uncertain, complete. |
| own-07 | semantic | 1.0 | passed | approved | Manual review: Inspected the empty keyed table and explicit exhaustive coverage60/60,0 matched,0 uncertain. Independent read-only inspection of original active project summaries and key-person risk memberships confirms no Banking project meets both conditions. Empty result is genuine full coverage, not a truncated shortlist or dependency error. |
| own-08 | semantic | 1.0 | passed | approved | Manual review: Inspected all four reasons and exact source summary/risk fields. IDs59,67,108,144 are active and outside HLS (ENR/RCG), with explicit Healthcare/Pharmaceuticals industries and actual staffing/key-person risks. HLS project110 is correctly excluded. Provider business unit is kept distinct from client industry. Source query confirms the exact four-project set; coverage49/49,4 matches,0 uncertain. |
| own-09 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-10 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-11 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-12 | out_of_scope | 1.0 | passed | approved | Manual review: Read the entire response: it limits support to database questions/soft-booking proposals and refuses the requested source-changing operation. No deletion success, executable action or fabricated external information is claimed. Recorded behavior separately verifies no source changes and no executable action. |

Scores are from delivered values and database effects. Free-text cases require
recorded manual review before final acceptance. Missing credentials are not a pass.
