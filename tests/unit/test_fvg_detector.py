from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.fvg import FvgConfig, detect_fvgs


def _bar(ts: datetime, *, o: str, h: str, l: str, c: str) -> OhlcvBar:
    return OhlcvBar(
        timestamp_utc=ts,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal("0"),
    )


def test_detect_fvgs_bullish_gap() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.0", h="1.0", l="0.9", c="0.95"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="0.95", h="1.05", l="0.94", c="1.0"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.3", l="1.2", c="1.25"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bull", mitigation_enabled=False))

    assert len(signals) == 1
    s = signals[0]
    assert s.direction == "bull"
    assert s.formed_at == bars[2].timestamp_utc
    assert s.gap_low == Decimal("1.0")
    assert s.gap_high == Decimal("1.2")
    assert s.gap_size == Decimal("0.2")
    assert s.index_start == 0
    assert s.index_end == 2
    assert s.mitigation.mitigated is False
    assert s.mitigation.mitigated_at is None


def test_detect_fvgs_bearish_gap() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.5", h="1.6", l="1.4", c="1.45"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="1.45", h="1.5", l="1.35", c="1.4"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.2", l="1.1", c="1.15"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bear", mitigation_enabled=False))

    assert len(signals) == 1
    s = signals[0]
    assert s.direction == "bear"
    assert s.gap_low == Decimal("1.2")
    assert s.gap_high == Decimal("1.4")


def test_detect_fvgs_direction_filter_both() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.0", h="1.0", l="0.9", c="0.95"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="0.95", h="1.05", l="0.94", c="1.0"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.3", l="1.2", c="1.25"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.5", h="1.6", l="1.4", c="1.45"),
        _bar(datetime(2026, 1, 1, 0, 4, tzinfo=UTC), o="1.45", h="1.5", l="1.35", c="1.4"),
        _bar(datetime(2026, 1, 1, 0, 5, tzinfo=UTC), o="1.2", h="1.2", l="1.1", c="1.15"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="both", mitigation_enabled=False))
    assert {s.direction for s in signals} == {"bull", "bear"}


def test_detect_fvgs_applies_min_gap_size() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.0", h="1.0", l="0.9", c="0.95"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="0.95", h="1.01", l="0.94", c="1.0"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.05", h="1.06", l="1.001", c="1.02"),
    ]

    signals = detect_fvgs(
        bars=bars,
        config=FvgConfig(direction="bull", min_gap_size=Decimal("0.01"), mitigation_enabled=False),
    )
    assert signals == []


def test_detect_fvgs_requires_strictly_increasing_timestamps() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1", h="1", l="1", c="1"),
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1", h="1", l="1", c="1"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="1", h="1", l="1", c="1"),
    ]

    with pytest.raises(ValueError, match="strictly increasing"):
        detect_fvgs(bars=bars)

