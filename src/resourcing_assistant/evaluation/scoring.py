"""Score only delivered values; free-text truth remains an explicit review item."""

import re
from decimal import Decimal, InvalidOperation

ALIASES = {
    "display_name": "person",
    "person_name": "person",
    "location_region": "region",
    "code": "engagement",
    "engagement_code": "engagement",
    "blocked_critical_items": "blocked_items",
    "blocked_critical_items_count": "blocked_items",
    "total_leaf_est_hours": "leaf_est_hours",
    "total_estimated_leaf_task_hours": "leaf_est_hours",
    "total_estimated_leaf_hours": "leaf_est_hours",
    "hard_hours": "hard_booked_hours",
    "total_cost_usd": "total_usd",
    "total_usd_value": "total_usd",
    "total_planned_cost": "total_usd",
    "total_planned_cost_usd": "total_usd",
    "count_people": "people",
    "people_count": "people",
    "person_count": "people",
    "total_people": "people",
}


def rows(answer):
    result = []
    queries = {
        b.get("query_id"): b for b in answer.get("blocks", []) if b["type"] == "sql"
    }
    for block in answer.get("blocks", []):
        if block["type"] == "table":
            scopes = {}
            for reference in block.get("evidence", []):
                query = queries.get(reference.get("query_id"), {})
                for key, value in query.get("parameters", {}).items():
                    if key.endswith("_id") and re.search(
                        r":" + re.escape(key) + r"\b", query.get("sql", "")
                    ):
                        scopes.setdefault(key, []).append(value)
            # Only visible, linked query identity; never fill a missing measure/oracle value.
            identity = {k: v[0] for k, v in scopes.items() if all(x == v[0] for x in v)}
            for row in block["rows"]:
                normalized, conflicts = {}, set()
                for key, value in row.items():
                    key = (
                        "person"
                        if key == "name" and "person_id" in {**identity, **row}
                        else ALIASES.get(key, key)
                    )
                    # The visible result grain distinguishes a grand count from per-entity counts.
                    if (
                        key == "blocked_items"
                        and len(block["rows"]) == 1
                        and not any(
                            k.endswith("_id")
                            or k
                            in (
                                "code",
                                "engagement",
                                "engagement_code",
                                "person",
                                "display_name",
                                "region",
                            )
                            for k in {**identity, **row}
                        )
                    ):
                        key = "total_blocked_critical_items"
                    if key in normalized and normalized[key] != value:
                        conflicts.add(key)
                    normalized[key] = value
                result.append(
                    {**identity, **normalized, **{k: None for k in conflicts}}
                )
    return result


def close(actual, expected, tolerance=0):
    if isinstance(actual, bool) or actual is None:
        return False
    try:
        a = Decimal(str(actual).replace(",", ""))
        b = Decimal(str(expected))
        t = Decimal(str(tolerance))
        return a.is_finite() and b.is_finite() and abs(a - b) <= t
    except (InvalidOperation, ValueError, TypeError):
        return False


def metric(data, key):
    found = [r[key] for r in data if key in r]
    return found[0] if len(found) == 1 else None


def score(case, answer, *, behavior=None, source_invariants=True):
    data = rows(answer)
    expected = case["expected"]
    rule = case.get("scoring", {})
    case_id = case["id"]
    checks = {
        "source_invariants": source_invariants,
        "response_complete": answer.get("request_status") == "completed",
    }
    if rule.get("must_include_query"):
        checks["executed_sql"] = any(
            b["type"] == "sql" and b.get("sql") for b in answer.get("blocks", [])
        )
    value = 0.0
    review = "not_required"
    reason = "Delivered values did not meet the case contract"
    if behavior is not None:
        checks.update(behavior)
        value = float(bool(behavior) and all(v is True for v in behavior.values()))
    elif case_id == "gq-01":
        delivered = [r for r in data if "person" in r and "hard_booked_hours" in r]
        mapping = {r["person"]: r for r in delivered}
        target = {r["person"]: r for r in expected["rows"]}
        value = float(
            len(mapping) == len(delivered)
            and set(mapping) == set(target)
            and all(
                close(mapping[k].get("hard_booked_hours"), r["hard_booked_hours"], 0.5)
                for k, r in target.items()
            )
        )
    elif case_id == "gq-02":
        actual = [r["requirement_id"] for r in data if "requirement_id" in r]
        target = {r["requirement_id"] for r in expected["rows"]}
        value = (
            1.0
            if set(actual) == target and len(actual) == 32
            else (
                0.5
                if len(actual) in (30, 31)
                and len(set(actual)) == len(actual)
                and set(actual) < target
                else 0.0
            )
        )
    elif case_id == "gq-03":
        value = float(close(metric(data, "total_usd"), expected["total_usd"], 1))
        checks["engagement_count"] = close(metric(data, "engagement_count"), 11)
    elif case_id == "gq-04":
        delivered = [r for r in data if "region" in r]
        actual = {r["region"]: r.get("people") for r in delivered}
        checks["unique_regions"] = len(actual) == len(delivered)
        target = {r["region"]: r["people"] for r in expected["rows"]}
        value = float(
            all(close(actual.get(k), v) for k, v in target.items())
            and not (set(actual) - set(target) - {"APAC"})
            and ("APAC" not in actual or close(actual["APAC"], 0))
        )
    elif case_id == "gq-05":
        actual = [r for r in data if "person" in r and "hours" in r]
        value = float(
            len(actual) >= 3
            and all(
                actual[i]["person"] == r["person"]
                and close(actual[i]["hours"], r["hours"], 0.5)
                for i, r in enumerate(expected["top_5"][:3])
            )
            and close(metric(data, "total_hours"), 425, 0.5)
        )
    elif case_id == "gq-06":
        value = float(close(metric(data, "total_blocked_critical_items"), 21))
        leaders = {r["engagement"] for r in expected["top_engagements"]}
        checks["requested_leaders"] = any(
            r.get("engagement") in leaders and close(r.get("blocked_items"), 2)
            for r in data
        )
    elif case_id in ("gq-07", "gq-08"):
        key = "person" if case_id == "gq-07" else "engagement"
        target = {
            r[key] for r in expected.get("strong_matches", expected.get("rows", []))
        }
        actual = [r for r in data if key in r]
        value = float(len({r[key] for r in actual} & target) >= 4)
        checks["per_item_source_evidence"] = bool(actual) and all(
            r.get("evidence") and r.get("reason") for r in actual
        )
        if case_id == "gq-07":
            checks["bio_and_skill_level"] = all(
                r.get("bio") and r.get("skills") for r in actual
            )
        else:
            checks["industry_and_risk"] = all(
                r.get("summary") and r.get("risks") for r in actual
            )
        review = "review_required"
    elif case_id == "gq-10":
        texts = [b["text"] for b in answer.get("blocks", []) if b["type"] == "text"]
        value = float(bool(texts))
        review = "review_required"
        checks["manual_weather_refusal_review"] = None
    elif case["type"] in ("factual", "semantic"):
        key = rule.get("on")
        target = expected.get("rows", [])
        if rule.get("match") == "fields":
            tolerance = rule.get("numeric_tolerance", {})
            delivered = [r for r in data if target and set(r) & set(target[0])]
            value = float(
                bool(target)
                and len(delivered) == 1
                and all(
                    all(
                        close(r.get(k), v, tolerance.get(k, 0))
                        if isinstance(v, (int, float))
                        else r.get(k) == v
                        for k, v in target[0].items()
                    )
                    for r in delivered
                )
            )
        else:
            actual = [r[key] for r in data if key in r]
            wanted = {r[key] for r in target}
            keyed_blocks = [
                b
                for b in answer.get("blocks", [])
                if b["type"] == "table"
                and (
                    any(key in r for r in b["rows"])
                    or any(
                        ALIASES.get(c["key"], c["key"]) == key
                        for c in b.get("columns", [])
                    )
                )
            ]
            checks["keyed_result_present"] = bool(keyed_blocks) and all(
                key in r for b in keyed_blocks for r in b["rows"]
            )
            value = float(set(actual) == wanted and len(actual) == len(set(actual)))
        if case["type"] == "semantic":
            review = "review_required"
            blocks = [
                b
                for b in answer.get("blocks", [])
                if b["type"] == "table" and b.get("block_id") == "semantic_matches"
            ]
            checks["exhaustive_coverage"] = bool(blocks) and all(
                b.get("completeness", {}).get("complete") for b in blocks
            )
            checks["per_item_source_evidence"] = all(
                r.get("evidence") and r.get("reason") for r in data if key in r
            )
    elif case["type"] == "out_of_scope":
        value = float(any(b["type"] == "text" for b in answer.get("blocks", [])))
        review = "review_required"
    if case_id == "own-12":
        review = "review_required"
    hard_failed = any(v is False for v in checks.values())
    if not source_invariants:
        value = 0
    if case_id.startswith("own-") and hard_failed:
        value = 0
    status = (
        "failed"
        if value == 0 or hard_failed
        else (
            "partial_credit"
            if value < 1
            else "review_required"
            if review == "review_required"
            else "passed"
        )
    )
    if status == "partial_credit":
        reason = "Published partial credit only; full case target not met"
    elif status != "failed":
        reason = (
            "Automated value checks passed; free-text review pending"
            if status == "review_required"
            else "Delivered values and automated contracts passed"
        )
    return {
        "score": value,
        "contract_checks": checks,
        "review_status": review,
        "status": status,
        "reason": reason,
    }
