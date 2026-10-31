"""Configuration, clocks and deterministic domain conversions."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    source: Path = ROOT / "data/source.sqlite"
    runtime: Path = ROOT / ".runtime"
    reference_date: str | None = None
    endpoint: str = ""
    api_key: str = ""
    api_version: str = "2024-10-21"
    chat_deployment: str = "gpt-4.1-mini"
    embedding_deployment: str = "text-embedding-3-small"
    model_timeout: float = 60
    sql_timeout: float = 5
    row_limit: int = 1000
    byte_limit: int = 1048576

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        return cls(
            runtime=Path(os.getenv("RUNTIME_DIR", ROOT / ".runtime")).resolve(),
            reference_date=os.getenv("REFERENCE_DATE") or None,
            endpoint=os.getenv("AZURE_ENDPOINT")
            or os.getenv("AZURE_API_BASE")
            or os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_API_VERSION", "2024-10-21"),
            chat_deployment=os.getenv("CHAT_DEPLOYMENT", "gpt-4.1-mini"),
            embedding_deployment=os.getenv(
                "EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
            ),
        )

    def reference(self):
        value = (
            datetime.fromisoformat(self.reference_date.replace("Z", "+00:00"))
            if self.reference_date
            else datetime.now(timezone.utc)
        )
        if value.tzinfo is None:
            raise ValueError("Reference date must include timezone")
        return value.astimezone(timezone.utc)


def utc_now():
    return int(datetime.now(timezone.utc).timestamp())


def day_epoch(value: str):
    return int(
        datetime.combine(
            date.fromisoformat(value), datetime.min.time(), timezone.utc
        ).timestamp()
    )


def period(start: str, inclusive_end: str):
    a = day_epoch(start)
    b = day_epoch((date.fromisoformat(inclusive_end) + timedelta(days=1)).isoformat())
    if b <= a:
        raise ValueError("End day must not precede start day")
    return a, b


def to_minutes(hours):
    try:
        amount = Decimal(str(hours)) * 60
        if (
            not amount.is_finite()
            or amount <= 0
            or amount != amount.to_integral_value()
            or amount > 2**63 - 1
        ):
            raise ValueError(
                "Hours must be positive and representable as whole minutes"
            )
        return int(amount)
    except InvalidOperation as error:
        raise ValueError("Invalid hours") from error


def capacity(start_ts: int, end_ts: int):
    a = datetime.fromtimestamp(start_ts, timezone.utc).date()
    b = datetime.fromtimestamp(end_ts, timezone.utc).date()
    return (
        sum((a + timedelta(days=i)).weekday() < 5 for i in range(max(0, (b - a).days)))
        * 8
    )
