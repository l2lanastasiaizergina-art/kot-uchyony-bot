from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def period_key(value: datetime | None = None) -> str:
    return (value or utc_now()).strftime("%Y-%m")

