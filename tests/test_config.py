from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from resourcing_assistant import config
from resourcing_assistant.config import Settings


def test_invalid_reference_and_resource_limits_fail_before_startup():
    for value in ("2026-04-01", "2026-04-01T12:00:00", "invalid"):
        with pytest.raises(ValidationError):
            Settings(reference_date=value)
    for field in (
        "row_limit",
        "byte_limit",
        "sql_timeout",
        "model_timeout",
        "assessment_batch_size",
    ):
        with pytest.raises(ValidationError):
            Settings(**{field: 0})
    with pytest.raises(ValidationError):
        Settings(context_compact_tokens=10000)
    assert Settings(reference_date="2026-04-01T03:00:00+03:00").reference() == datetime(
        2026, 4, 1, tzinfo=UTC
    )
    assert Settings().reference().tzinfo == UTC


def test_dotenv_does_not_mutate_environment_and_aliases_preserve_precedence(
    monkeypatch, tmp_path
):
    for name in (
        "AZURE_ENDPOINT",
        "AZURE_API_BASE",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "AZURE_ENDPOINT=https://first.invalid\nAZURE_API_KEY=test-placeholder\n"
    )
    first = Settings.from_env()
    dotenv.write_text(
        "AZURE_ENDPOINT=https://second.invalid\nAZURE_API_KEY=test-placeholder\n"
    )
    assert Settings.from_env().endpoint == "https://second.invalid"
    assert "test-placeholder" not in repr(first)
    monkeypatch.setenv("AZURE_ENDPOINT", "")
    monkeypatch.setenv("AZURE_API_BASE", "https://environment.invalid")
    assert Settings.from_env().endpoint == "https://environment.invalid"
    assert (
        Settings(endpoint="https://explicit.invalid").endpoint
        == "https://explicit.invalid"
    )
    assert not Settings(endpoint="", api_key="").azure_configured


def test_settings_validation_error_hides_secret_inputs():
    with pytest.raises(ValidationError) as error:
        Settings(api_key="test-private-placeholder", context_compact_tokens=10000)
    assert "test-private-placeholder" not in str(error.value)
