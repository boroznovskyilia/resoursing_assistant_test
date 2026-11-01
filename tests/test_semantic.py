from types import SimpleNamespace

from resourcing_assistant.agent.schemas import Assessment, Interpretation
from resourcing_assistant.config import Settings
from resourcing_assistant.llm.embeddings import EmbeddingClient
from resourcing_assistant.services.retrieval import RetrievalService
from tests.test_agent import ScriptedGateway


def semantic_service(settings, store, gateway, client_factory=None):
    original = store.agent.semantic
    embeddings = (
        EmbeddingClient(settings, client_factory)
        if client_factory
        else EmbeddingClient(settings)
    )
    return RetrievalService(
        settings, original.documents, original.vectors, embeddings, gateway
    )


def test_unavailable_embeddings_full_scan_and_uncertainty(store):
    gateway = ScriptedGateway()
    semantic = semantic_service(store.settings, store, gateway)
    task = Interpretation(
        intent="semantic",
        question="staffing gaps",
        semantic_kind="project",
        semantic_mode="shortlist",
        criteria="Staffing gap",
    )
    matches, meta, issues = semantic.search(task)
    assert meta["fallback"] and meta["eligible"] == 150 and meta["processed"] == 150
    assert meta["complete"] and not issues and len(matches) <= 10
    assert semantic.embedding_status == "degraded"

    class Uncertain(ScriptedGateway):
        def call(self, name, **inputs):
            if name == "AssessCandidates":
                return [
                    Assessment(
                        source_id=c.source_id,
                        status="uncertain",
                        reason="Cannot verify",
                    )
                    for c in inputs["candidates"]
                ]
            return super().call(name, **inputs)

    semantic.gateway = Uncertain()
    task.semantic_mode = "exhaustive"
    matches, meta, issues = semantic.search(task, {1, 6})
    assert not meta["complete"] and meta["uncertain"] == 2 and not matches


def test_vector_cache_deduplicates_text_preserving_memberships(store, monkeypatch):

    calls = []

    class Client:
        def __init__(self, **kwargs):
            self.embeddings = self

        def create(self, model, input):
            calls.extend(input)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=i, embedding=[1.0, 2.0, 3.0])
                    for i in range(len(input))
                ]
            )

        def close(self):
            pass

    settings = Settings(
        **(
            store.settings.model_dump()
            | {"endpoint": "https://test.invalid", "api_key": "test-placeholder"}
        )
    )
    semantic = semantic_service(settings, store, ScriptedGateway(), Client)
    docs = [
        ("risk:1", "Same original description"),
        ("risk:2", "Same original description"),
    ]
    vectors = semantic._vectors(docs)
    assert len(calls) == 1 and vectors["risk:1"] == vectors["risk:2"]
    semantic._vectors(docs)
    assert len(calls) == 1
    from resourcing_assistant.db.session import connect

    with connect(store.conversations.path, readonly=True) as c:
        assert c.execute("SELECT COUNT(*) FROM semantic_memberships").fetchone()[0] == 2


def test_untrusted_assessment_quote_is_not_a_match(store):
    class Bad(ScriptedGateway):
        def call(self, name, **inputs):
            if name == "AssessCandidates":
                return [
                    Assessment(
                        source_id=c.source_id,
                        status="match",
                        quotes=["invented quote"],
                        reason="Fabricated",
                    )
                    for c in inputs["candidates"]
                ]
            return super().call(name, **inputs)

    semantic = semantic_service(store.settings, store, Bad())
    task = Interpretation(
        intent="semantic",
        question="risk",
        semantic_kind="project",
        semantic_mode="exhaustive",
    )
    matches, meta, issues = semantic.search(task, {1, 6})
    assert matches == [] and issues and not meta["complete"] and meta["processed"] == 0


def test_project_facets_join_industry_and_any_matching_risk_consistently(store):
    from resourcing_assistant.agent.schemas import ProjectChecks
    from resourcing_assistant.db.reader import Reader

    class Fields(ScriptedGateway):
        def call(self, name, **inputs):
            if name == "PlanProjectChecks":
                return ProjectChecks(
                    summary="Healthcare or Pharmaceuticals",
                    summary_scope="industry",
                    risk="Staffing OR key-person",
                    operator="all",
                )
            if name == "AssessCandidates":
                result = []
                for c in inputs["candidates"]:
                    matched = (
                        c.text in ("Healthcare", "Pharmaceuticals")
                        if inputs["criteria"] == "Healthcare or Pharmaceuticals"
                        else c.text.startswith(
                            ("Staffing gap", "Key-person dependency")
                        )
                    )
                    result.append(
                        Assessment(
                            source_id=c.source_id,
                            status="match" if matched else "no_match",
                            quotes=[c.text] if matched else [],
                            reason="Original industry/risk condition",
                        )
                    )
                return result
            return super().call(name, **inputs)

    reader = Reader(store.settings, store.subject)
    sql, params = reader.simple_eligibility(
        "project", "All active healthcare projects with people risks", {}
    )
    eligible = {r["engagement_id"] for r in reader.read(sql, params)["rows"]}
    semantic = semantic_service(store.settings, store, Fields())
    task = Interpretation(
        intent="semantic",
        question="Healthcare projects with people risks",
        semantic_kind="project",
        semantic_mode="exhaustive",
    )
    matches, metadata, issues = semantic.search(task, eligible)
    assert {c["entity_id"] for c, _ in matches} == {59, 67, 108, 110, 144}
    assert metadata["complete"] and metadata["processed"] == 60 and not issues
    # The healthcare project without a risk cannot pass the industry AND risk condition.
    assert 150 not in {c["entity_id"] for c, _ in matches}


def test_recovery_requires_genuine_embedding_success_not_a_cache_hit(
    store, monkeypatch
):

    calls = []

    class Client:
        def __init__(self, **kwargs):
            self.embeddings = self

        def create(self, model, input):
            calls.append(input)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=i, embedding=[1.0, 2.0, 3.0])
                    for i in range(len(input))
                ]
            )

        def close(self):
            pass

    semantic = semantic_service(
        Settings(
            **(
                store.settings.model_dump()
                | {"endpoint": "https://test.invalid", "api_key": "test-placeholder"}
            )
        ),
        store,
        ScriptedGateway(),
        Client,
    )
    docs = [("risk:1", "Original risk text")]
    semantic._vectors(docs)
    assert semantic.embedding_status == "healthy"
    semantic.embedding_status = "degraded"
    semantic._vectors(docs)
    assert len(calls) == 1 and semantic.embedding_status == "degraded"
    semantic._vectors([("risk:2", "Changed original risk text")])
    assert len(calls) == 2 and semantic.embedding_status == "healthy"


def test_shortlist_ranking_selects_explicit_count_and_rejects_unknown_ids(store):
    import json

    from resourcing_assistant.agent.schemas import RankItem

    class Ranking(ScriptedGateway):
        bad = False
        pools = []

        def call(self, name, **inputs):
            if name == "AssessCandidates":
                return [
                    Assessment(
                        source_id=c.source_id,
                        status="match",
                        quotes=[c.text],
                        reason="Source experience",
                    )
                    for c in inputs["candidates"]
                ]
            if name == "RankCandidates":
                pool = json.loads(inputs["candidates"])
                self.pools.append((len(pool), inputs["requested_count"]))
                if self.bad:
                    return [RankItem(source_id="person:99999", reason="Unknown")]
                return [
                    RankItem(
                        source_id=p["candidate"]["source_id"],
                        reason="Source experience",
                    )
                    for p in pool[: inputs["requested_count"]]
                ]
            return super().call(name, **inputs)

    gateway = Ranking()
    semantic = semantic_service(store.settings, store, gateway)
    semantic.shortlist = lambda criteria, candidates, limit: candidates
    task = Interpretation(
        intent="semantic",
        question="Recommend experienced people",
        semantic_kind="person",
        semantic_mode="shortlist",
        requested_count=10,
    )
    matches, meta, issues = semantic.search(task, set(range(1, 26)))
    assert len(matches) == 10 and not issues and meta["order"] == "assessed_ranking"
    assert gateway.pools == [(12, 10), (22, 10), (11, 10)]
    gateway.bad = True
    _, meta, issues = semantic.search(task, {1, 2})
    assert meta["order"] == "source_id" and any(
        i["code"] == "ranking_unavailable" for i in issues
    )
