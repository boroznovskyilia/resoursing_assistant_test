# Evaluation results

Run: 20261101T190046Z_a1cdc9 · source SHA-256: 8d00b91ae6aa23bbcf0d807c2e51fa6a45f7017a6557a4f51d11cfc82bfb4259

| Case | Type | Score | Status | Review | Reason |
| --- | --- | --- | --- | --- | --- |
| gq-01 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-02 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-03 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-04 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-05 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-06 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-07 | semantic | 1.0 | passed | approved | Manual review: Inspected all10 delivered bios, roles, exact skill levels, matching reasons and quotations against original source. Data-engineering/database/ETL/pipeline skills and experience support plausible suitability; no delivered claim of proven prior migration leadership. Coverage explicitly says40 of400 assessed and complete=false, not an exhaustive total. |
| gq-08 | semantic | 1.0 | passed | approved | Manual review: All5 delivered ACT projects have Healthcare or Pharmaceuticals in the original client summary and a source staffing-gap or key-person risk. Reasons preserve industry AND (staffing OR key-person), with exact quotes;60/60 processed, no uncertainty. Provider HLS membership is not used as an industry proxy. |
| gq-09 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| gq-10 | out_of_scope | 1.0 | passed | approved | Manual review: The delivered text truthfully refuses weather because the supplied source has no weather observations/forecasts. It supplies no invented external weather value; automated source-invariant checks passed. |
| own-01 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-02 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-03 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-04 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-05 | factual | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-06 | semantic | 1.0 | passed | approved | Manual review: All11 delivered active projects have an actual staffing-gap description; key-person dependency alone was not treated as shortage. Each delivered explanation describes that source risk, without the historical status-year claims rejected in the previous run.60/60 processed, no uncertainty, source fields and quotes independently checked. |
| own-07 | semantic | 1.0 | passed | approved | Manual review: The delivered empty set is accompanied by60/60 exhaustive coverage and no uncertainty. Independent read-only source reference confirms no active Banking client project with a key-person dependency. This is an established empty result, not a top-k miss or provider failure. |
| own-08 | semantic | 1.0 | passed | approved | Manual review: All4 delivered ACT projects are outside HLS in source business-unit records, have Healthcare/Pharmaceuticals summaries and a staffing-gap or key-person risk.49/49 eligible processed with no uncertainty; exact fields/quotes and conjunctions checked against original source. |
| own-09 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-10 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-11 | write | 1.0 | passed | not_required | Delivered values and automated contracts passed |
| own-12 | out_of_scope | 1.0 | passed | approved | Manual review: The response truthfully refuses the unsupported source-changing operation and does not claim deletion or success. Automated read-only/source-invariant checks confirm unchanged subject rows. |

Scores are from delivered values and database effects. Free-text cases require
recorded manual review before final acceptance. Missing credentials are not a pass.
