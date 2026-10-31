from types import SimpleNamespace
import pytest
from resourcing_assistant.config import Settings
from resourcing_assistant.llm import retry_call, token_count, Gateway
from resourcing_assistant.models import AppError


class ProviderError(Exception):
    def __init__(self, status, delay=None):
        self.status_code = status
        self.response = SimpleNamespace(
            headers={} if delay is None else {"retry-after": str(delay)}
        )


def test_transient_retry_and_retry_after():
    calls = []
    delays = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise ProviderError(429, 2)
        return "ok"

    assert (
        retry_call(operation, stage="chat", deployment="test", sleep=delays.append)
        == "ok"
    )
    assert len(calls) == 2 and delays == [2]


@pytest.mark.parametrize(
    "status,delay", [(401, None), (403, None), (400, None), (429, 11)]
)
def test_permanent_or_long_retry_after_is_not_retried(status, delay):
    calls = []

    def operation():
        calls.append(1)
        raise ProviderError(status, delay)

    with pytest.raises(ProviderError):
        retry_call(operation, stage="chat", deployment="test", sleep=lambda _: None)
    assert len(calls) == 1


def test_retry_exhaustion_exactly_two_attempts():
    calls = []

    def operation():
        calls.append(1)
        raise ProviderError(503)

    with pytest.raises(ProviderError):
        retry_call(operation, stage="chat", deployment="test", sleep=lambda _: None)
    assert len(calls) == 2


def test_offline_tokenizer_and_missing_credentials():
    assert token_count({"message": "Hello"}) > 0
    with pytest.raises(AppError) as error:
        Gateway(Settings()).call("InterpretRequest", message="Hello", context="{}")
    assert error.value.code == "provider_unavailable"


def test_query_contract_requires_explicit_bindings():
    from pydantic import ValidationError
    from resourcing_assistant.models import Query

    assert "parameters" in Query.model_json_schema()["required"]
    with pytest.raises(ValidationError):
        Query(query_id="q", purpose="Count", sql="SELECT COUNT(*) FROM people")
    value = Query(
        query_id="q",
        purpose="Count",
        sql="SELECT COUNT(*) FROM people WHERE location_region=:region",
        parameters=[{"name": "region", "value": "APAC"}],
    )
    assert value.bindings == {"region": "APAC"}
    with pytest.raises(ValidationError):
        Query(
            query_id="q",
            purpose="Count",
            sql="SELECT :region FROM people",
            parameters=[
                {"name": "region", "value": "APAC"},
                {"name": "region", "value": "EMEA"},
            ],
        )


def test_supplied_azure_api_base_alias_with_blank_primary(monkeypatch, tmp_path):
    import resourcing_assistant.config as config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setenv("AZURE_ENDPOINT", "")
    monkeypatch.setenv("AZURE_API_BASE", "https://test.invalid")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_API_KEY", "test-only")
    assert config.Settings.from_env().endpoint == "https://test.invalid"


def test_actual_dspy_planner_adapter_preserves_named_bindings(monkeypatch):
    import json
    import dspy
    from dataclasses import replace

    def transport(self, *args, **kwargs):
        schema = kwargs["response_format"].model_json_schema()
        assert set(schema["$defs"]["Binding"]["properties"]) == {"name", "value"}
        assert schema["$defs"]["Query"]["properties"]["parameters"]["type"] == "array"
        return [
            json.dumps(
                {
                    "result": {
                        "answer": {
                            "query_id": "count",
                            "purpose": "Count",
                            "sql": "SELECT COUNT(*) AS people FROM people WHERE location_region=:region",
                            "parameters": [{"name": "region", "value": "APAC"}],
                        },
                        "additional_answers": [],
                    }
                }
            )
        ]

    monkeypatch.setattr(dspy.LM, "__call__", transport)
    plan = Gateway(
        replace(Settings(), endpoint="https://test.invalid", api_key="test-only")
    ).call(
        "PlanReads",
        intent="factual",
        question="Count people",
        context="{}",
        allowed_schema="people(location_region)",
        previous_error="",
        repair=False,
    )
    assert plan.queries[0].bindings == {"region": "APAC"}


def test_real_dspy_adapter_typed_contract_repair_and_budget(monkeypatch):
    import dspy, json
    from dataclasses import replace
    from resourcing_assistant.llm import BudgetLM

    calls = []

    def transport(self, prompt=None, *, messages=None, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return ['{"invalid_field":true}']
        return [
            json.dumps(
                {"result": {"intent": "factual", "question": "count", "slots": {}}}
            )
        ]

    monkeypatch.setattr(dspy.LM, "__call__", transport)
    settings = replace(
        Settings(), endpoint="https://test.invalid", api_key="test-placeholder"
    )
    value = Gateway(settings).call(
        "InterpretRequest",
        message="count",
        context="{}",
        source_schema="people(person_id)",
    )
    assert value.intent == "factual" and len(calls) == 2
    assert calls[0] != calls[1]
    lm = BudgetLM(
        "azure/gpt-4.1-mini",
        api_key="test-placeholder",
        num_retries=0,
        cache=False,
        engine="litellm",
    )
    with pytest.raises(AppError) as error:
        lm(messages=[{"role": "user", "content": "large " * 12000}])
    assert error.value.code == "context_budget_exceeded" and len(calls) == 2


def test_http_date_retry_after_over_ten_seconds_is_not_retried():
    from datetime import datetime, timezone, timedelta
    from email.utils import format_datetime

    calls = []

    def operation():
        calls.append(1)
        raise ProviderError(
            429,
            format_datetime(
                datetime.now(timezone.utc) + timedelta(seconds=60), usegmt=True
            ),
        )

    with pytest.raises(ProviderError):
        retry_call(operation, stage="chat", deployment="test", sleep=lambda _: None)
    assert len(calls) == 1


def test_azure_millisecond_retry_header_is_honored():
    calls = []
    delays = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            error = ProviderError(429)
            error.response.headers = {"x-ms-retry-after-ms": "1500"}
            raise error
        return "ok"

    assert (
        retry_call(operation, stage="chat", deployment="test", sleep=delays.append)
        == "ok"
    )
    assert delays == [1.5] and len(calls) == 2


def test_ambient_hosted_tracing_is_disabled_in_fresh_process():
    import os, subprocess, sys

    env = {
        **os.environ,
        "LANGCHAIN_TRACING_V2": "true",
        "LANGSMITH_TRACING": "true",
        "LITELLM_LOCAL_MODEL_COST_MAP": "False",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import resourcing_assistant,os; print(os.environ['LANGCHAIN_TRACING_V2'],os.environ['LANGSMITH_TRACING'],os.environ['LITELLM_LOCAL_MODEL_COST_MAP'])",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "false false True"
