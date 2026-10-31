"""Source-linked local vectors, exhaustive assessment and transparent fallback."""

import hashlib
import json
import math
import re
import time
from openai import AzureOpenAI
from .data import connect
from .llm import event, retry_call, token_count, USAGE
from .models import Candidate, AppError, Assessment


def normalize(vector):
    if not vector or not all(
        isinstance(v, (float, int)) and math.isfinite(v) for v in vector
    ):
        raise ValueError("Invalid embedding vector")
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        raise ValueError("Zero embedding vector")
    return [v / norm for v in vector]


class Semantic:
    def __init__(self, settings, store, gateway):
        self.settings, self.store, self.gateway = settings, store, gateway
        self.embedding_status = (
            "unknown" if settings.endpoint and settings.api_key else "not_configured"
        )
        with connect(store.path) as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS semantic_vectors(cache_key TEXT PRIMARY KEY, model TEXT NOT NULL, text_hash TEXT NOT NULL, dimension INTEGER NOT NULL, vector TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS semantic_memberships(source_ref TEXT PRIMARY KEY, cache_key TEXT NOT NULL REFERENCES semantic_vectors);""")

    def candidates(self, kind, eligible=None):
        result = []
        with connect(self.store.subject, readonly=True) as c:
            if kind == "person":
                for person in c.execute(
                    "SELECT person_id,display_name,bio,location_region FROM people ORDER BY person_id"
                ):
                    if eligible is not None and person["person_id"] not in eligible:
                        continue
                    roles = [
                        r[0]
                        for r in c.execute(
                            "SELECT rc.name FROM category_assignments ca JOIN rate_categories rc USING(category_id) WHERE ca.person_id=? ORDER BY ca.is_default DESC,rc.category_id",
                            (person["person_id"],),
                        )
                    ]
                    skills = [
                        dict(r)
                        for r in c.execute(
                            "SELECT s.name,ps.proficiency FROM person_skills ps JOIN skills s USING(skill_id) WHERE ps.person_id=? ORDER BY s.skill_id",
                            (person["person_id"],),
                        )
                    ]
                    text = "\n".join(
                        [
                            person["bio"] or "",
                            "Roles: " + ", ".join(roles),
                            "Skills: " + ", ".join(s["name"] for s in skills),
                        ]
                    )
                    facts = {**dict(person), "roles": roles, "skills": skills}
                    result.append(
                        Candidate(
                            source_id=f"person:{person['person_id']}",
                            kind="person",
                            entity_id=person["person_id"],
                            text=text,
                            facts=facts,
                        )
                    )
            elif kind == "project":
                for project in c.execute(
                    "SELECT engagement_id,code,title,summary FROM engagements ORDER BY engagement_id"
                ):
                    if (
                        eligible is not None
                        and project["engagement_id"] not in eligible
                    ):
                        continue
                    risks = [
                        dict(r)
                        for r in c.execute(
                            "SELECT risk_id,description,severity FROM risks WHERE engagement_id=? ORDER BY risk_id",
                            (project["engagement_id"],),
                        )
                    ]
                    text = "\n".join(
                        [project["summary"] or ""]
                        + [r["description"] or "" for r in risks]
                    )
                    result.append(
                        Candidate(
                            source_id=f"project:{project['engagement_id']}",
                            kind="project",
                            entity_id=project["engagement_id"],
                            text=text,
                            facts={**dict(project), "risks": risks},
                        )
                    )
            else:
                for risk in c.execute(
                    "SELECT r.*,e.code FROM risks r JOIN engagements e USING(engagement_id) ORDER BY risk_id"
                ):
                    if eligible is not None and risk["risk_id"] not in eligible:
                        continue
                    result.append(
                        Candidate(
                            source_id=f"risk:{risk['risk_id']}",
                            kind="risk",
                            entity_id=risk["risk_id"],
                            text=risk["description"] or "",
                            facts=dict(risk),
                        )
                    )
        return result

    def _vectors(self, documents):
        if not self.settings.endpoint or not self.settings.api_key:
            raise AppError(
                "embedding_unavailable", "Embedding deployment is not configured", 503
            )
        model = (
            self.settings.embedding_deployment
            + ":"
            + self.settings.api_version
            + ":"
            + hashlib.sha256(self.settings.endpoint.encode()).hexdigest()[:16]
        )
        records = {}
        missing = {}
        with connect(self.store.path) as c:
            for reference, text in documents:
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                key = hashlib.sha256((model + text_hash).encode()).hexdigest()
                records[reference] = key
                row = c.execute(
                    "SELECT vector,dimension FROM semantic_vectors WHERE cache_key=?",
                    (key,),
                ).fetchone()
                if row:
                    value = normalize(json.loads(row[0]))
                    if len(value) != row[1]:
                        raise ValueError("Stored vector dimension mismatch")
                else:
                    missing[key] = (text_hash, text)
        client = AzureOpenAI(
            azure_endpoint=self.settings.endpoint,
            api_key=self.settings.api_key,
            api_version=self.settings.api_version,
            max_retries=0,
            timeout=self.settings.model_timeout,
        )
        values = list(missing.items())
        try:
            for offset in range(0, len(values), 64):
                batch = values[offset : offset + 64]
                output = retry_call(
                    lambda: client.embeddings.create(
                        model=self.settings.embedding_deployment,
                        input=[v[1][1] for v in batch],
                    ),
                    stage="embedding",
                    deployment=self.settings.embedding_deployment,
                )
                usage = USAGE.get()
                used = getattr(getattr(output, "usage", None), "total_tokens", None)
                if usage is not None and isinstance(used, int):
                    usage["embedding_tokens"] = usage.get("embedding_tokens", 0) + used
                if self.embedding_status == "degraded":
                    event(
                        "embedding_recovered",
                        deployment=self.settings.embedding_deployment,
                    )
                self.embedding_status = "healthy"
                ordered = sorted(output.data, key=lambda item: item.index)
                if [v.index for v in ordered] != list(range(len(batch))):
                    raise ValueError("Embedding response omitted documents")
                with connect(self.store.path) as c:
                    for (key, (text_hash, text)), item in zip(
                        batch, ordered, strict=True
                    ):
                        vector = normalize(item.embedding)
                        c.execute(
                            "INSERT INTO semantic_vectors VALUES(?,?,?,?,?) ON CONFLICT(cache_key) DO NOTHING",
                            (key, model, text_hash, len(vector), json.dumps(vector)),
                        )
                    c.commit()
        finally:
            client.close()
        vectors = {}
        with connect(self.store.path) as c:
            for reference, key in records.items():
                vector = normalize(
                    json.loads(
                        c.execute(
                            "SELECT vector FROM semantic_vectors WHERE cache_key=?",
                            (key,),
                        ).fetchone()[0]
                    )
                )
                vectors[reference] = vector
                c.execute(
                    "INSERT INTO semantic_memberships VALUES(?,?) ON CONFLICT(source_ref) DO UPDATE SET cache_key=excluded.cache_key",
                    (reference, key),
                )
            c.commit()
        return vectors

    def shortlist(self, criteria, candidates, limit=40):
        docs = [("query:" + hashlib.sha256(criteria.encode()).hexdigest(), criteria)]
        refs = {}
        for item in candidates:
            if item.kind == "project":
                pairs = [(item.source_id + ":summary", item.facts["summary"] or "")] + [
                    (f"risk:{r['risk_id']}", r["description"] or "")
                    for r in item.facts["risks"]
                ]
            else:
                pairs = [(item.source_id, item.text)]
            refs[item.source_id] = [ref for ref, text in pairs if text]
            docs.extend((ref, text) for ref, text in pairs if text)
        vectors = self._vectors(docs)
        query = vectors[docs[0][0]]
        scores = {}
        for item in candidates:
            sims = []
            for ref in refs[item.source_id]:
                if len(query) != len(vectors[ref]):
                    raise ValueError("Query/document embedding dimensions differ")
                sims.append(
                    sum(a * b for a, b in zip(query, vectors[ref], strict=True))
                )
            scores[item.source_id] = max(sims, default=-1)
        return sorted(
            candidates, key=lambda item: (-scores[item.source_id], item.source_id)
        )[:limit]

    def assess(self, candidates, criteria, mode):
        assessments = {}
        processed = set()
        uncertain = set()
        issues = []
        batches = []
        batch = []
        for candidate in candidates:
            if batch and (
                len(batch) >= 12
                or token_count(
                    [x.model_dump() for x in batch] + [candidate.model_dump()]
                )
                > 6000
            ):
                batches.append(batch)
                batch = []
            batch.append(candidate)
        if batch:
            batches.append(batch)
        for batch in batches:
            try:
                output = self.gateway.call(
                    "AssessCandidates",
                    criteria=criteria,
                    mode=mode,
                    candidates=batch,
                )
                expected = {c.source_id: c for c in batch}
                if len(output) != len(expected) or {v.source_id for v in output} != set(
                    expected
                ):
                    raise ValueError("Assessment did not cover its full batch")
                for item in output:
                    candidate = expected[item.source_id]
                    if item.status == "match" and (
                        not item.quotes
                        or any(not q or q not in candidate.text for q in item.quotes)
                    ):
                        raise ValueError("Unsupported assessment evidence")
                for item in output:
                    processed.add(item.source_id)
                    if item.status == "uncertain":
                        uncertain.add(item.source_id)
                    assessments[item.source_id] = item
            except Exception as error:
                uncertain.update(c.source_id for c in batch)
                issues.append(
                    {
                        "code": "semantic_batch_failed",
                        "message": "A candidate batch could not be verified; the result is incomplete",
                        "stage": "semantic",
                        "retryable": True,
                    }
                )
                event(
                    "semantic_batch_failed",
                    error_class=type(error).__name__,
                    candidates=len(batch),
                )
        return assessments, processed, uncertain, issues, len(batches)

    def assess_projects(self, candidates, criteria):
        try:
            checks = self.gateway.call("PlanProjectChecks", criteria=criteria)
            if not (checks.summary or checks.risk):
                raise ValueError("Project matching needs a semantic predicate")
            documents, memberships = {}, {}
            risk_severity = bool(
                checks.risk
                and re.search(
                    r"\b(severity|critical|high|medium|low)\b", checks.risk, re.I
                )
            )
            for candidate in candidates:
                fields = {}
                if checks.summary:
                    text = candidate.facts["summary"] or ""
                    if checks.summary_scope == "industry":
                        industry = re.search(r", a (.+?) organization based in", text)
                        if industry:
                            text = industry.group(1)
                    key = "summary:" + hashlib.sha256(text.encode()).hexdigest()[:24]
                    documents[key] = Candidate(
                        source_id=key,
                        kind="project",
                        entity_id=candidate.entity_id,
                        text=text,
                        facts={"field": checks.summary_scope},
                    )
                    fields["summary"] = [key]
                if checks.risk:
                    fields["risk"] = []
                    for risk in candidate.facts["risks"]:
                        text = risk["description"] or ""
                        key = (
                            "risk:"
                            + hashlib.sha256(
                                (
                                    text
                                    + (str(risk["severity"]) if risk_severity else "")
                                ).encode()
                            ).hexdigest()[:24]
                        )
                        documents[key] = Candidate(
                            source_id=key,
                            kind="risk",
                            entity_id=risk["risk_id"],
                            text=text,
                            facts={"severity": risk["severity"]}
                            if risk_severity
                            else {},
                        )
                        fields["risk"].append(key)
                memberships[candidate.source_id] = fields
            outputs, processed_docs, issues, batch_count = {}, set(), [], 0
            for field, criterion in (
                ("summary", checks.summary),
                ("risk", checks.risk),
            ):
                if not criterion:
                    continue
                docs = [v for k, v in documents.items() if k.startswith(field + ":")]
                values, processed, _, extra, batches = self.assess(
                    docs, criterion, "exhaustive"
                )
                outputs.update(values)
                processed_docs.update(processed)
                issues.extend(extra)
                batch_count += batches
            result, processed, uncertain = {}, set(), set()
            for candidate in candidates:
                components = []
                for field, keys in memberships[candidate.source_id].items():
                    values = [outputs.get(k) for k in keys]
                    matches = [v for v in values if v and v.status == "match"]
                    unknown = any(v is None or v.status == "uncertain" for v in values)
                    status = (
                        "match" if matches else "uncertain" if unknown else "no_match"
                    )
                    components.append(
                        (status, matches, all(k in processed_docs for k in keys))
                    )
                statuses = [v[0] for v in components]
                if checks.operator == "all":
                    status = (
                        "no_match"
                        if "no_match" in statuses
                        else "match"
                        if all(v == "match" for v in statuses)
                        else "uncertain"
                    )
                else:
                    status = (
                        "match"
                        if "match" in statuses
                        else "no_match"
                        if all(v == "no_match" for v in statuses)
                        else "uncertain"
                    )
                if status != "uncertain" or all(v[2] for v in components):
                    processed.add(candidate.source_id)
                if status == "uncertain":
                    uncertain.add(candidate.source_id)
                positives = [match for _, matches, _ in components for match in matches]
                quotes = list(
                    dict.fromkeys(q for match in positives for q in match.quotes)
                )
                if status == "match" and (
                    not quotes or any(q not in candidate.text for q in quotes)
                ):
                    raise ValueError("Project evidence did not join back to source")
                result[candidate.source_id] = Assessment(
                    source_id=candidate.source_id,
                    status=status,
                    quotes=quotes,
                    reason="; ".join(dict.fromkeys(v.reason for v in positives))
                    or "Required source conditions are not all established.",
                )
            return result, processed, uncertain, issues, batch_count
        except Exception as error:
            event("project_matching_failed", error_class=type(error).__name__)
            return (
                {},
                set(),
                {c.source_id for c in candidates},
                [
                    {
                        "code": "project_matching_failed",
                        "message": "Project text conditions could not be verified",
                        "stage": "semantic",
                    }
                ],
                0,
            )

    def search(self, interpretation, eligible=None):
        start = time.monotonic()
        all_candidates = self.candidates(interpretation.semantic_kind, eligible)
        selected = all_candidates
        fallback = False
        issues = []
        if not all_candidates:
            return (
                [],
                {
                    "mode": interpretation.semantic_mode,
                    "eligible": 0,
                    "processed": 0,
                    "matched": 0,
                    "uncertain": 0,
                    "complete": True,
                    "fallback": False,
                },
                issues,
            )
        if interpretation.semantic_mode == "shortlist":
            try:
                selected = self.shortlist(
                    interpretation.criteria or interpretation.question,
                    all_candidates,
                    max(40, interpretation.requested_count * 4),
                )
            except Exception as error:
                self.embedding_status = "degraded"
                fallback = True
                event(
                    "embedding_unavailable",
                    error_class=type(error).__name__,
                    deployment=self.settings.embedding_deployment,
                    latency_ms=round((time.monotonic() - start) * 1000),
                )
                event(
                    "semantic_fallback_started",
                    candidates=len(all_candidates),
                    reason=type(error).__name__,
                )
        criteria = interpretation.criteria or interpretation.question
        if interpretation.semantic_kind == "project":
            assessments, processed, uncertain, extra, batch_count = (
                self.assess_projects(selected, criteria)
            )
        else:
            assessments, processed, uncertain, extra, batch_count = self.assess(
                selected, criteria, interpretation.semantic_mode
            )
        issues.extend(extra)
        assessed = {
            c.source_id: (c, assessments[c.source_id])
            for c in selected
            if c.source_id in assessments and assessments[c.source_id].status == "match"
        }
        matched = list(assessed.values())
        ranked = matched
        order = "source_id"
        ranking_reasons = {}
        if matched and (
            len(matched) <= 40 or interpretation.semantic_mode == "shortlist"
        ):
            try:
                if interpretation.semantic_mode == "shortlist":
                    # Carry the best requested shortlist through finite candidate groups.
                    pools = [matched[i : i + 12] for i in range(0, len(matched), 12)]
                    ranked = []
                else:
                    pools = [matched]
                    ranked = []
                for chunk in pools:
                    pool = ranked + chunk
                    count = (
                        min(interpretation.requested_count, len(pool))
                        if interpretation.semantic_mode == "shortlist"
                        else len(pool)
                    )
                    ranks = self.gateway.call(
                        "RankCandidates",
                        requested_count=count,
                        criteria=interpretation.criteria or interpretation.question,
                        candidates=json.dumps(
                            [
                                {
                                    "candidate": c.model_dump(),
                                    "assessment": a.model_dump(),
                                }
                                for c, a in pool
                            ]
                        ),
                    )
                    expected = {c.source_id: (c, a) for c, a in pool}
                    if (
                        len(ranks) != count
                        or len({r.source_id for r in ranks}) != count
                        or not {r.source_id for r in ranks} <= set(expected)
                    ):
                        raise ValueError("Ranking IDs invalid")
                    ranking_reasons.update({r.source_id: r.reason for r in ranks})
                    ranked = [expected[r.source_id] for r in ranks]
                    if interpretation.semantic_mode == "shortlist":
                        ranked = ranked[: interpretation.requested_count]
                order = "assessed_ranking"
            except Exception as error:
                issues.append(
                    {
                        "code": "ranking_unavailable",
                        "message": "Matches are shown in stable source order; suitability ranking could not be verified",
                        "stage": "semantic",
                    }
                )
                event("ranking_failed", error_class=type(error).__name__)
                ranked = sorted(matched, key=lambda pair: pair[0].source_id)
        elif len(matched) > 40:
            ranked = sorted(matched, key=lambda pair: pair[0].source_id)
        if interpretation.semantic_mode == "shortlist":
            ranked = ranked[: interpretation.requested_count]
        metadata = {
            "mode": interpretation.semantic_mode,
            "eligible": len(all_candidates),
            "processed": len(processed),
            "matched": len(matched),
            "uncertain": len(uncertain),
            "complete": len(processed) == len(all_candidates) and not uncertain,
            "fallback": fallback,
            "order": order,
        }
        if fallback:
            event(
                "semantic_fallback_completed"
                if not issues
                else "semantic_fallback_failed",
                coverage=metadata,
                batches=batch_count,
                latency_ms=round((time.monotonic() - start) * 1000),
            )
        return (
            [
                (
                    c.model_dump(),
                    {
                        **a.model_dump(),
                        "ranking_reason": ranking_reasons.get(c.source_id),
                    },
                )
                for c, a in ranked
            ],
            metadata,
            issues,
        )
