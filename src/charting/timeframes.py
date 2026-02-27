"""Timeframe parsing and UTC bucket alignment helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_SUPPORTED_TIMEFRAMES: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "2m": timedelta(minutes=2),
    "3m": timedelta(minutes=3),
    "4m": timedelta(minutes=4),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


def normalize_utc(timestamp: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def parse_timeframe(timeframe: str) -> timedelta:
    """Return timeframe duration or raise ValueError."""
    try:
        return _SUPPORTED_TIMEFRAMES[timeframe]
    except KeyError as exc:
        supported = ", ".join(_SUPPORTED_TIMEFRAMES.keys())
        raise ValueError(f"unsupported timeframe '{timeframe}'. Supported: {supported}") from exc


def bucket_start_utc(timestamp: datetime, timeframe: str) -> datetime:
    """Floor UTC timestamp to timeframe bucket start."""
    ts_utc = normalize_utc(timestamp)
    if timeframe == "1d":
        return ts_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    duration = parse_timeframe(timeframe)
    seconds = int(duration.total_seconds())
    epoch = int(ts_utc.timestamp())
    floored_epoch = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored_epoch, tz=UTC)


def supported_timeframes() -> tuple[str, ...]:
    """Supported public timeframes for charting."""
    return tuple(_SUPPORTED_TIMEFRAMES.keys())
