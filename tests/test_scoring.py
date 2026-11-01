from resourcing_assistant.evaluation.runner import cases
from resourcing_assistant.evaluation.scoring import close, score


def answer(rows, **extra):
    return {
        "request_status": "completed",
        "blocks": [
            {"type": "table", "rows": rows},
            {"type": "sql", "sql": "SELECT from source"},
        ],
        **extra,
    }


def case(case_id):
    return next(c for c in cases() if c["id"] == case_id)


def test_gq02_partial_no_false_positive_and_duplicate():
    c = case("gq-02")
    expected = c["expected"]["rows"]
    assert score(c, answer(expected))["score"] == 1
    assert score(c, answer(expected[:30]))["score"] == 0.5
    assert score(c, answer(expected[:29]))["score"] == 0
    assert score(c, answer(expected[:30] + [{"requirement_id": 9999}]))["score"] == 0
    assert score(c, answer(expected[:31] + [expected[0]]))["score"] == 0


def test_numeric_tolerance_and_missing_delivered_total():
    assert close(1.01, 1, 0.01) and not close(1.010001, 1, 0.01)
    assert not close(float("nan"), 1) and not close(True, 1)
    c = case("gq-03")
    result = score(c, answer([{"total_usd": 5157842.1, "engagement_count": 11}]))
    assert result["status"] == "passed"
    result = score(c, answer([{"planned_cost_usd": 5157842.1}]))
    assert result["score"] == 0


def test_order_required_and_no_hidden_total():
    c = case("gq-05")
    rows = c["expected"]["top_5"][:3]
    assert score(c, answer(rows + [{"total_hours": 425}]))["score"] == 1
    assert score(c, answer(rows[::-1] + [{"total_hours": 425}]))["score"] == 0
    assert score(c, answer(rows))["score"] == 0


def test_semantic_overlap_is_not_final_pass_or_evidence():
    c = case("gq-07")
    data = [
        {
            "person": r["person"],
            "bio": "Actual source bio",
            "skills": r["skills"],
            "reason": "Needs manual review",
            "evidence": "Actual source quote",
        }
        for r in c["expected"]["strong_matches"][:4]
    ]
    result = score(c, answer(data))
    assert result["score"] == 1 and result["status"] == "review_required"
    result = score(c, answer([{"person": r["person"]} for r in data]))
    assert result["status"] == "failed"
    assert score(c, answer(data), source_invariants=False)["score"] == 0


def test_weather_and_deletion_need_review_or_observable_behavior():
    result = score(
        case("gq-10"),
        {
            "request_status": "completed",
            "blocks": [{"type": "text", "text": "No weather data"}],
        },
    )
    assert result["status"] == "review_required"
    assert (
        score(case("own-12"), answer([]), behavior={"no_changes": False})["score"] == 0
    )
    assert (
        score(case("own-12"), answer([]), behavior={"no_changes": True})["status"]
        == "review_required"
    )
    assert score(case("gq-09"), answer([]), behavior={})["status"] == "failed"


def test_duplicate_or_conflicting_aggregate_cannot_pass():
    regions = case("gq-04")["expected"]["rows"]
    assert score(case("gq-04"), answer(regions))["status"] == "passed"
    assert score(case("gq-04"), answer(regions + regions[:1]))["status"] == "failed"
    spec = case("own-01")
    assert score(spec, answer([{"people": 11}]))["status"] == "passed"
    assert score(spec, answer([{"people": 1}, {"people": 11}]))["status"] == "failed"


def test_equivalent_source_metric_aliases_keep_identical_value_checks():
    spec = case("gq-06")
    delivered = answer(
        [
            {"total_blocked_critical_items": 21},
            {"engagement_code": "ENG-2026-0111", "blocked_critical_items": 2},
        ]
    )
    assert score(spec, delivered)["status"] == "passed"
    delivered["blocks"][0]["rows"][1]["blocked_critical_items"] = 3
    assert score(spec, delivered)["status"] == "failed"
    assert (
        score(case("own-04"), answer([{"total_leaf_est_hours": 1068.1}]))["status"]
        == "passed"
    )
    assert score(case("own-01"), answer([{"people_count": 11}]))["status"] == "passed"
    assert (
        score(case("own-01"), answer([{"people_count": 99, "people": 11}]))["status"]
        == "failed"
    )


def test_scoped_metric_identity_must_be_in_linked_visible_query():
    delivered = answer([{"hard_booked_hours": 30.0}])
    delivered["blocks"][0]["evidence"] = [{"query_id": "hours"}]
    delivered["blocks"][1].update(
        query_id="hours",
        sql="SELECT SUM(minutes)/60.0 AS hard_booked_hours FROM bookings WHERE person_id=:person_id",
        parameters={"person_id": 348},
    )
    assert score(case("own-05"), delivered)["status"] == "passed"
    delivered["blocks"][1]["parameters"]["person_id"] = 349
    assert score(case("own-05"), delivered)["status"] == "failed"
    delivered["blocks"][1]["parameters"]["person_id"] = 348
    delivered["blocks"][0]["evidence"] = []
    assert score(case("own-05"), delivered)["status"] == "failed"


def test_empty_set_needs_an_actual_keyed_result():
    spec = case("own-02")
    missing = answer([])
    assert score(spec, missing)["status"] == "failed"
    missing["blocks"][0]["columns"] = [{"key": "person_id", "label": "Person ID"}]
    assert score(spec, missing)["status"] == "passed"
    missing["blocks"][0]["rows"] = [{"unrelated_field": 1}]
    assert score(spec, missing)["status"] == "failed"


def test_manual_review_is_bound_to_run_and_does_not_override_failed_facts():
    import pytest

    from resourcing_assistant.evaluation.runner import ManualReview, apply_review

    report = {
        "run_id": "one",
        "results": [
            {
                "id": "gq-07",
                "score": 1.0,
                "review_status": "review_required",
                "contract_checks": {"source_invariants": True},
                "status": "review_required",
            }
        ],
    }
    wrong = ManualReview(
        run_id="two",
        reviewer="Reviewer",
        cases={"gq-07": {"accepted": True, "notes": "Reviewed source evidence"}},
    )
    with pytest.raises(ValueError):
        apply_review(report, wrong)
    right = wrong.model_copy(update={"run_id": "one"})
    apply_review(report, right)
    assert report["results"][0]["status"] == "passed"
    report["results"][0]["contract_checks"]["source_invariants"] = False
    apply_review(report, right)
    assert report["results"][0]["status"] == "failed"


def test_blocked_count_alias_follows_visible_result_grain():
    delivered = answer([{"blocked_critical_items_count": 21}])
    leaders = {
        "type": "table",
        "rows": [
            {
                "engagement_id": 31,
                "engagement_code": "ENG-2024-0031",
                "blocked_critical_items_count": 2,
            }
        ],
    }
    delivered["blocks"].insert(1, leaders)
    assert score(case("gq-06"), delivered)["status"] == "passed"
    delivered["blocks"][0]["rows"][0]["blocked_critical_items_count"] = 22
    assert score(case("gq-06"), delivered)["status"] == "failed"
    delivered["blocks"][0]["rows"][0]["blocked_critical_items_count"] = 21
    delivered["blocks"].insert(
        1, {"type": "table", "rows": [{"total_blocked_critical_items": 21}]}
    )
    assert score(case("gq-06"), delivered)["status"] == "failed"
    delivered["blocks"].pop(1)
    leaders["rows"][0]["blocked_critical_items_count"] = 21
    assert score(case("gq-06"), delivered)["status"] == "failed"


def test_person_name_alias_needs_visible_person_scope_and_cannot_hide_conflicts():
    data = [
        {
            "person_id": i + 1,
            "name": r["person"],
            "hard_booked_hours": r["hard_booked_hours"],
        }
        for i, r in enumerate(case("gq-01")["expected"]["rows"])
    ]
    assert score(case("gq-01"), answer(data))["status"] == "passed"
    data[0]["person"] = "Wrong person"
    assert score(case("gq-01"), answer(data))["status"] == "failed"
    from resourcing_assistant.evaluation.scoring import rows

    assert rows(answer([{"engagement_id": 1, "name": "Project"}])) == [
        {"engagement_id": 1, "name": "Project"}
    ]
