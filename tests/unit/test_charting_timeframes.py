from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from charting.timeframes import bucket_start_utc, normalize_utc, parse_timeframe, supported_timeframes


def test_supported_timeframes_contains_extended_minutes() -> None:
    assert {"1m", "2m", "3m", "4m", "5m", "15m", "1h", "4h", "1d"}.issubset(
        set(supported_timeframes())
    )


def test_parse_timeframe_raises_for_invalid_value() -> None:
    with pytest.raises(ValueError, match="unsupported timeframe"):
        parse_timeframe("7m")


def test_normalize_utc_keeps_aware_and_upgrades_naive() -> None:
    naive = datetime(2026, 1, 1, 10, 0)
    aware = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)

    assert normalize_utc(naive).tzinfo == UTC
    assert normalize_utc(aware) == aware


def test_bucket_start_utc_for_intraday_and_daily() -> None:
    ts = datetime(2026, 1, 1, 10, 7, 40, tzinfo=UTC)

    assert bucket_start_utc(ts, "5m") == datetime(2026, 1, 1, 10, 5, tzinfo=UTC)
    assert bucket_start_utc(ts, "1d") == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert parse_timeframe("4h") == timedelta(hours=4)
