"""Validated application settings; dotenv is read only at the composition boundary."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import AliasChoices, AwareDatetime, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        frozen=True,
        populate_by_name=True,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )
    source: Path = Field(
        default=ROOT / "data/source.sqlite", validation_alias="SOURCE_DATABASE"
    )
    runtime: Path = Field(default=ROOT / ".runtime", validation_alias="RUNTIME_DIR")
    reference_date: AwareDatetime | None = None
    endpoint: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AZURE_ENDPOINT", "AZURE_API_BASE", "AZURE_OPENAI_ENDPOINT"
        ),
    )
    api_key: SecretStr = Field(
        default="",
        validation_alias=AliasChoices("AZURE_API_KEY", "AZURE_OPENAI_API_KEY"),
    )
    api_version: str = Field(default="2024-10-21", validation_alias="AZURE_API_VERSION")
    chat_deployment: str = "gpt-4.1-mini"
    embedding_deployment: str = "text-embedding-3-small"
    model_timeout: float = Field(default=60, gt=0, allow_inf_nan=False)
    sql_timeout: float = Field(default=5, gt=0, allow_inf_nan=False)
    row_limit: int = Field(default=1000, gt=0)
    byte_limit: int = Field(default=1048576, gt=0)
    message_token_limit: int = Field(default=9000, gt=0)
    model_input_tokens: int = Field(default=10000, gt=0)
    model_output_tokens: int = Field(default=2000, gt=0)
    context_compact_tokens: int = Field(default=8000, gt=0)
    history_tokens: int = Field(default=3000, gt=0)
    summary_tokens: int = Field(default=700, gt=0)
    assessment_tokens: int = Field(default=6000, gt=0)
    assessment_batch_size: int = Field(default=12, gt=0)
    embedding_batch_size: int = Field(default=64, gt=0)
    shortlist_min_candidates: int = Field(default=40, gt=0)
    shortlist_multiplier: int = Field(default=4, gt=0)
    rank_batch_size: int = Field(default=12, gt=0)
    max_rank_candidates: int = Field(default=40, gt=0)
    graph_recursion_limit: int = Field(default=30, gt=0)
    evaluation_artifacts: bool = Field(
        default=False, validation_alias="RESOURCING_EVAL_ARTIFACTS"
    )

    @model_validator(mode="after")
    def valid_budgets(self):
        if self.context_compact_tokens >= self.model_input_tokens:
            raise ValueError(
                "Context compaction must start before the model input limit"
            )
        if self.history_tokens + self.summary_tokens >= self.context_compact_tokens:
            raise ValueError(
                "History and summary must fit below the compaction threshold"
            )
        return self

    @classmethod
    def from_env(cls):
        return cls(_env_file=ROOT / ".env", _env_file_encoding="utf-8")

    @property
    def azure_configured(self):
        return bool(self.endpoint and self.api_key.get_secret_value())

    def reference(self):
        return (self.reference_date or datetime.now(UTC)).astimezone(UTC)
