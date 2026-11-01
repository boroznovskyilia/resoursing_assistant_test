"""UTC calendar, duration and booking capacity rules."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation


def utc_now():
    return int(datetime.now(UTC).timestamp())


def day_epoch(value: str):
    return int(
        datetime.combine(
            date.fromisoformat(value), datetime.min.time(), UTC
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
    a = datetime.fromtimestamp(start_ts, UTC).date()
    b = datetime.fromtimestamp(end_ts, UTC).date()
    return (
        sum((a + timedelta(days=i)).weekday() < 5 for i in range(max(0, (b - a).days)))
        * 8
    )
