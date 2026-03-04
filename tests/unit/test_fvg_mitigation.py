from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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


def test_fvg_mitigation_wick_bull_scans_after_formation() -> None:
    # Bull gap: high[0]=1.0 < low[2]=1.2 => gap (1.0, 1.2)
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.0", h="1.0", l="0.9", c="0.95"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="0.95", h="1.25", l="0.94", c="1.0"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.3", l="1.2", c="1.25"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.25", h="1.26", l="1.19", c="1.23"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bull", mitigation_rule="wick"))
    assert len(signals) == 1
    assert signals[0].mitigation.mitigated is True
    assert signals[0].mitigation.mitigated_at == bars[3].timestamp_utc


def test_fvg_mitigation_close_bull() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.0", h="1.0", l="0.9", c="0.95"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="0.95", h="1.25", l="0.94", c="1.0"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.3", l="1.2", c="1.25"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.25", h="1.26", l="1.21", c="1.19"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bull", mitigation_rule="close"))
    assert signals[0].mitigation.mitigated is True
    assert signals[0].mitigation.mitigated_at == bars[3].timestamp_utc


def test_fvg_mitigation_wick_bear() -> None:
    # Bear gap: low[0]=1.4 > high[2]=1.2 => gap (1.2, 1.4)
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.5", h="1.6", l="1.4", c="1.45"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="1.45", h="1.5", l="1.35", c="1.4"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.2", l="1.1", c="1.15"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.15", h="1.21", l="1.1", c="1.12"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bear", mitigation_rule="wick"))
    assert signals[0].mitigation.mitigated is True
    assert signals[0].mitigation.mitigated_at == bars[3].timestamp_utc


def test_fvg_mitigation_close_bear() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.5", h="1.6", l="1.4", c="1.45"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="1.45", h="1.5", l="1.35", c="1.4"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.2", l="1.1", c="1.15"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.15", h="1.19", l="1.1", c="1.21"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bear", mitigation_rule="close"))
    assert signals[0].mitigation.mitigated is True
    assert signals[0].mitigation.mitigated_at == bars[3].timestamp_utc


def test_fvg_mitigation_disabled() -> None:
    bars = [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.0", h="1.0", l="0.9", c="0.95"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="0.95", h="1.25", l="0.94", c="1.0"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.2", h="1.3", l="1.2", c="1.25"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.25", h="1.26", l="1.19", c="1.23"),
    ]

    signals = detect_fvgs(bars=bars, config=FvgConfig(direction="bull", mitigation_enabled=False))
    assert signals[0].mitigation.mitigated is False
    assert signals[0].mitigation.mitigated_at is None
