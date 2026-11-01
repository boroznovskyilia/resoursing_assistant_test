"""Semantic orchestration over injected documents, vectors and model clients."""

import hashlib
import json
import re
import time

from resourcing_assistant.agent.schemas import Assessment, Candidate
from resourcing_assistant.llm.embeddings import normalize
from resourcing_assistant.llm.tokens import token_count
from resourcing_assistant.telemetry import event


class RetrievalService:
    def __init__(self, settings, documents, vectors, embeddings, gateway):
        self.settings, self.documents, self.vectors = settings, documents, vectors
        self.embeddings, self.gateway = embeddings, gateway

    @property
    def embedding_status(self):
        return self.embeddings.status

    @embedding_status.setter
    def embedding_status(self, value):
        self.embeddings.status = value

    def candidates(self, kind, eligible=None):
        return self.documents.candidates(kind, eligible)

    def _vectors(self, documents):
        model = (
            self.settings.embedding_deployment
            + ":"
            + self.settings.api_version
            + ":"
            + hashlib.sha256(self.settings.endpoint.encode()).hexdigest()[:16]
        )
        records, texts = {}, {}
        for reference, text in documents:
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            key = hashlib.sha256((model + text_hash).encode()).hexdigest()
            records[reference] = key
            texts[key] = (text_hash, text)
        cached = self.vectors.get_many(texts)
        values = {}
        for key, (vector, dimension) in cached.items():
            value = normalize(vector)
            if len(value) != dimension:
                raise ValueError("Stored vector dimension mismatch")
            values[key] = value
        missing = [
            (key, text_hash, text)
            for key, (text_hash, text) in texts.items()
            if key not in cached
        ]
        for offset in range(0, len(missing), self.settings.embedding_batch_size):
            batch = missing[offset : offset + self.settings.embedding_batch_size]
            output = self.embeddings.embed([text for _, _, text in batch])
            additions = [
                (key, text_hash, vector)
                for (key, text_hash, _), vector in zip(batch, output, strict=True)
            ]
            self.vectors.save(model, additions)
            # Read the winner of ON CONFLICT in case another thread cached the same text.
            for key, (vector, dimension) in self.vectors.get_many(
                [key for key, _, _ in additions]
            ).items():
                value = normalize(vector)
                if len(value) != dimension:
                    raise ValueError("Stored vector dimension mismatch")
                values[key] = value
        self.vectors.memberships(records)
        return {reference: values[key] for reference, key in records.items()}

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
                len(batch) >= self.settings.assessment_batch_size
                or token_count(
                    [x.model_dump() for x in batch] + [candidate.model_dump()]
                )
                > self.settings.assessment_tokens
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
                    r"\b(severity|critical|high|medium|low)\b",
                    checks.risk,
                    re.IGNORECASE,
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
                    max(
                        self.settings.shortlist_min_candidates,
                        interpretation.requested_count
                        * self.settings.shortlist_multiplier,
                    ),
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
            len(matched) <= self.settings.max_rank_candidates
            or interpretation.semantic_mode == "shortlist"
        ):
            try:
                if interpretation.semantic_mode == "shortlist":
                    # Carry the best requested shortlist through finite candidate groups.
                    pools = [
                        matched[i : i + self.settings.rank_batch_size]
                        for i in range(0, len(matched), self.settings.rank_batch_size)
                    ]
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
        elif len(matched) > self.settings.max_rank_candidates:
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
