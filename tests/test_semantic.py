from types import SimpleNamespace
from resourcing_assistant.models import Interpretation, Assessment
from resourcing_assistant.semantic import Semantic
from tests.test_agent import ScriptedGateway


def test_unavailable_embeddings_full_scan_and_uncertainty(store):
    gateway = ScriptedGateway()
    semantic = Semantic(store.settings, store, gateway)
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
    matches, meta, issues = semantic.search(task, {1, 2})
    assert not meta["complete"] and meta["uncertain"] == 2 and not matches


def test_vector_cache_deduplicates_text_preserving_memberships(store, monkeypatch):
    import resourcing_assistant.semantic as module

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

    monkeypatch.setattr(module, "AzureOpenAI", Client)
    from dataclasses import replace

    settings = replace(
        store.settings, endpoint="https://test.invalid", api_key="test-placeholder"
    )
    semantic = Semantic(settings, store, ScriptedGateway())
    docs = [
        ("risk:1", "Same original description"),
        ("risk:2", "Same original description"),
    ]
    vectors = semantic._vectors(docs)
    assert len(calls) == 1 and vectors["risk:1"] == vectors["risk:2"]
    semantic._vectors(docs)
    assert len(calls) == 1
    from resourcing_assistant.data import connect

    with connect(store.path, readonly=True) as c:
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

    semantic = Semantic(store.settings, store, Bad())
    task = Interpretation(
        intent="semantic",
        question="risk",
        semantic_kind="project",
        semantic_mode="exhaustive",
    )
    matches, meta, issues = semantic.search(task, {1, 2})
    assert matches == [] and issues and not meta["complete"] and meta["processed"] == 0


def test_recovery_requires_genuine_embedding_success_not_a_cache_hit(
    store, monkeypatch
):
    import resourcing_assistant.semantic as module
    from dataclasses import replace

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

    monkeypatch.setattr(module, "AzureOpenAI", Client)
    semantic = Semantic(
        replace(
            store.settings, endpoint="https://test.invalid", api_key="test-placeholder"
        ),
        store,
        ScriptedGateway(),
    )
    docs = [("risk:1", "Original risk text")]
    semantic._vectors(docs)
    assert semantic.embedding_status == "healthy"
    semantic.embedding_status = "degraded"
    semantic._vectors(docs)
    assert len(calls) == 1 and semantic.embedding_status == "degraded"
    semantic._vectors([("risk:2", "Changed original risk text")])
    assert len(calls) == 2 and semantic.embedding_status == "healthy"
