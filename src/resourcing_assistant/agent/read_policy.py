"""Supported output-scope checks; SQLite authorizer remains the security boundary."""

import json
import re

from resourcing_assistant.db.reader import ReadError, has_limit


class ReadPolicy:
    def __init__(self, task, text):
        self.ranking = bool(
            re.search(
                r"\b(most|top|leading|highest|largest)\b", task.question, re.IGNORECASE
            )
        ) and not re.search(r"\bat\s+most\b", task.question, re.IGNORECASE)
        self.explicit_size = bool(
            re.search(
                r"\b(?:top|first|best|list|show|return)\s+(?:the\s+)?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b|\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:most|highest|leading)\b|\bonly\s+(?:one|1)\b",
                task.question,
                re.IGNORECASE,
            )
        )
        self.logged = bool(
            re.search(r"\b(logged|time entries|actual hours)\b", text, re.IGNORECASE)
        )
        self.scalar_count = bool(
            re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", text, re.IGNORECASE)
        ) and not re.search(
            r"\b(each|per|by)\b|\bbroken down\b|\bhow many\s+(?:[\w-]+\s+){0,3}(?:hours|minutes|days|weeks|months|dollars)\b",
            text,
            re.IGNORECASE,
        )
        self.scalar_total = bool(
            re.search(r"\b(total|sum)\b", text, re.IGNORECASE)
            and re.search(
                r"\b(cost|value|amount|hours|minutes|effort|revenue|price)\b",
                text,
                re.IGNORECASE,
            )
        ) and not re.search(r"\b(each|per|by)\b|\bbroken down\b", text, re.IGNORECASE)
        self.scalar_total = self.scalar_total or bool(
            re.search(
                r"\bhow many\s+(?:[\w-]+\s+){0,3}(?:hours|minutes|dollars)\b",
                text,
                re.IGNORECASE,
            )
        )
        self.hard_capacity_list = bool(
            re.search(r"\bhard[- ]booked\b", text, re.IGNORECASE)
            and re.search(r"%|\bpercent(?:age)?\b", text, re.IGNORECASE)
        ) and not (self.scalar_count or self.scalar_total)

    def question(self, task):
        planning_question = task.question
        if task.intent in ("semantic", "mixed"):
            pass
        elif self.ranking and not self.explicit_size:
            planning_question += "\nOutput policy: return the TOP FIVE ranked contributors/entities, ordered by the requested measure, with per-entity IDs and measures. Return any requested full total separately."
            task.assumptions.append(
                "Rankings without an explicit size show the top five for context."
            )
        elif (
            task.intent == "factual"
            and not self.explicit_size
            and not (self.scalar_count or self.scalar_total)
        ):
            planning_question += "\nOutput policy: return ALL matching records, without LIMIT or intermediate/helper queries. Use the supplied code-computed period/capacity values."
        if self.hard_capacity_list:
            planning_question += "\nOutput policy: each eligible person's row MUST include person_id, person/name, hard_booked_hours and hard_booked_pct (0-100). The user must see the derived booking measure used in the filter, including zeros. Do not return only names/IDs. Use full intersecting kind=hard minutes and code-computed period/capacity; no unrequested status exclusions."
        if self.logged:
            planning_question += "\nLogged hours are ACTUAL time_entries minutes via work_items, never bookings or assignments."
        if task.intent == "factual" and self.scalar_total:
            planning_question += "\nOutput policy: deliver each requested TOTAL as a visible one-row SUM aggregate with the complete requested filters. A detail list and an instruction for the user to sum it are NOT a total. Return optional detail separately."
        if task.intent == "factual" and self.scalar_count:
            planning_question += "\nOutput policy: return a visible one-row COUNT aggregate for the requested entity count. Listing entity rows without the requested count is incomplete. Separate any requested rankings/details from the full count."
        if (
            task.intent == "factual"
            and re.search(r"\b(total|sum)\b", task.question, re.IGNORECASE)
            and re.search(r"planned\s+cost", task.question, re.IGNORECASE)
            and re.search(r"\b(engagements?|projects?)\b", task.question, re.IGNORECASE)
        ):
            planning_question += "\nOutput policy: include total_usd AND engagement_count (COUNT DISTINCT qualifying engagements) in the aggregate row. Reporting currency is currencies.is_primary=1; use the actual currency FX from rate_cards."
        return planning_question

    def query(self, task, query):
        if has_limit(query.sql, outer_only=task.intent == "factual") and (
            task.intent in ("semantic", "mixed")
            or not (self.ranking or self.explicit_size)
        ):
            raise ReadError(
                "invalid_sql",
                "Unrequested LIMIT can omit matching records. Return all matches; safety row limits/pagination are enforced by code.",
            )

    def result(self, task, query, primary, result):
        if (
            self.hard_capacity_list
            and primary
            and not {
                "hard_booked_hours",
                "hard_hours",
            }.intersection(result["columns"])
        ):
            raise ReadError(
                "invalid_sql",
                "Eligible person rows must display hard_booked_hours used by the percentage filter, including zero. Returning only names/IDs omits the requested measure.",
            )
        if primary and self.logged and "time_entries" not in result["source_tables"]:
            raise ReadError(
                "invalid_sql",
                "Logged/actual hours MUST read time_entries via work_items, not bookings or assignments. Correct the primary answer source.",
            )
        if any(k.endswith("_id") for k in result["columns"]) and len(
            {json.dumps(r, sort_keys=True) for r in result["rows"]}
        ) != len(result["rows"]):
            raise ReadError(
                "invalid_sql",
                "Identical entity rows were duplicated by a join. Use EXISTS/DISTINCT or include the actual source grain identity.",
            )

    def results(self, task, results, issues):
        if (
            task.intent == "factual"
            and self.scalar_total
            and not issues
            and not any(
                len(r["rows"]) == 1
                and re.search(r"\b(?:SUM|TOTAL)\s*\(", r["sql"], re.IGNORECASE)
                for r in results
            )
        ):
            raise ReadError(
                "invalid_sql",
                "A full total was requested. Return a visible one-row SUM aggregate; listing detail rows or asking the user to add them is incomplete.",
            )
        if (
            task.intent == "factual"
            and self.scalar_count
            and not issues
            and not any(
                len(r["rows"]) == 1
                and re.search(r"\bCOUNT\s*\(", r["sql"], re.IGNORECASE)
                for r in results
            )
        ):
            raise ReadError(
                "invalid_sql",
                "An exact count was requested. Return a one-row COUNT aggregate, not only the matching entity list or grouped detail.",
            )
