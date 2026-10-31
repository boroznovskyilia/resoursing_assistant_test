from resourcing_assistant.evaluation import cases
from resourcing_assistant.scoring import score, close


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


def test_empty_set_needs_an_actual_keyed_result():
    spec = case("own-02")
    missing = answer([])
    assert score(spec, missing)["status"] == "failed"
    missing["blocks"][0]["columns"] = [{"key": "person_id", "label": "Person ID"}]
    assert score(spec, missing)["status"] == "passed"
    missing["blocks"][0]["rows"] = [{"unrelated_field": 1}]
    assert score(spec, missing)["status"] == "failed"


def test_manual_review_is_bound_to_run_and_does_not_override_failed_facts():
    from resourcing_assistant.evaluation import ManualReview, apply_review
    import pytest

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
