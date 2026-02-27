from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from charting.resampler import OhlcvBar, resample_ohlcv


def _make_1m_rows(start: datetime, count: int) -> list[OhlcvBar]:
    rows: list[OhlcvBar] = []
    for i in range(count):
        price = Decimal(100 + i)
        rows.append(
            OhlcvBar(
                timestamp_utc=start + timedelta(minutes=i),
                open=price,
                high=price + Decimal("0.7"),
                low=price - Decimal("0.4"),
                close=price + Decimal("0.2"),
                volume=Decimal("1.0"),
            )
        )
    return rows


def test_resample_1m_to_5m_groups_exact_buckets() -> None:
    rows = _make_1m_rows(datetime(2026, 1, 1, 10, 0, tzinfo=UTC), 12)

    bars = resample_ohlcv(rows, "5m")

    assert len(bars) == 3
    assert bars[0].timestamp_utc == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert bars[1].timestamp_utc == datetime(2026, 1, 1, 10, 5, tzinfo=UTC)
    assert bars[2].timestamp_utc == datetime(2026, 1, 1, 10, 10, tzinfo=UTC)
    assert bars[0].open == Decimal(100)
    assert bars[0].close == Decimal("104.2")


def test_resample_1m_to_15m_returns_partial_last_bucket() -> None:
    rows = _make_1m_rows(datetime(2026, 1, 1, 10, 0, tzinfo=UTC), 17)

    bars = resample_ohlcv(rows, "15m")

    assert len(bars) == 2
    assert bars[0].timestamp_utc == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert bars[1].timestamp_utc == datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
    assert bars[1].open == Decimal(115)
    assert bars[1].close == Decimal("116.2")


def test_resample_1m_to_1h() -> None:
    rows = _make_1m_rows(datetime(2026, 1, 1, 9, 10, tzinfo=UTC), 70)

    bars = resample_ohlcv(rows, "1h")

    assert len(bars) == 2
    assert bars[0].timestamp_utc == datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    assert bars[1].timestamp_utc == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def test_resample_1m_to_1d() -> None:
    day1 = _make_1m_rows(datetime(2026, 1, 1, 23, 58, tzinfo=UTC), 2)
    day2 = _make_1m_rows(datetime(2026, 1, 2, 0, 0, tzinfo=UTC), 3)

    bars = resample_ohlcv(day1 + day2, "1d")

    assert len(bars) == 2
    assert bars[0].timestamp_utc == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert bars[1].timestamp_utc == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
