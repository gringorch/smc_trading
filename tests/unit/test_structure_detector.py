from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.structure import StructureConfig, analyze_structure, detect_bos, detect_swings


def _bar(ts: datetime, *, open_: str, high: str, low: str, close: str) -> OhlcvBar:
    return OhlcvBar(
        timestamp_utc=ts,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("0"),
    )


def _bars_from_ohlc(rows: list[tuple[str, str, str, str]]) -> list[OhlcvBar]:
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    out: list[OhlcvBar] = []
    for i, (open_, high, low, close) in enumerate(rows):
        out.append(
            _bar(
                t0 + timedelta(minutes=i),
                open_=open_,
                high=high,
                low=low,
                close=close,
            )
        )
    return out


def test_detect_swings_uses_configurable_left_right() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.8", "0.9"),
            ("1.0", "2.0", "1.0", "1.8"),
            ("1.8", "5.0", "1.2", "4.5"),
            ("4.4", "3.0", "1.1", "2.0"),
            ("2.0", "2.0", "0.7", "1.0"),
            ("1.0", "4.0", "1.0", "3.9"),
            ("3.9", "2.0", "1.1", "1.5"),
        ]
    )

    swings_22 = detect_swings(bars=bars, config=StructureConfig(swing_left=2, swing_right=2))
    assert [(s.kind, s.bar_index) for s in swings_22 if s.confirmed] == [("high", 2), ("low", 4)]

    swings_11 = detect_swings(bars=bars, config=StructureConfig(swing_left=1, swing_right=1))
    assert ("high", 5) in {(s.kind, s.bar_index) for s in swings_11 if s.confirmed}


def test_detect_swings_equal_highs_or_lows_do_not_mark_swing() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.8", "0.9"),
            ("1.0", "2.0", "0.9", "1.8"),
            ("1.8", "5.0", "1.0", "4.2"),
            ("4.2", "5.0", "0.7", "1.1"),
            ("1.1", "2.5", "0.9", "2.0"),
        ]
    )

    swings = detect_swings(bars=bars, config=StructureConfig(swing_left=1, swing_right=1))
    assert all(not (s.kind == "high" and s.bar_index in (2, 3)) for s in swings)


def test_detect_swings_normalizes_consecutive_same_kind() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.9", "0.95"),
            ("0.95", "3.0", "0.95", "2.8"),
            ("2.8", "2.0", "1.0", "1.2"),
            ("1.2", "4.0", "1.2", "3.9"),
            ("3.9", "3.0", "1.1", "1.5"),
            ("1.5", "2.8", "0.8", "2.2"),
            ("2.2", "2.4", "1.0", "1.2"),
            ("1.2", "2.2", "0.7", "1.8"),
            ("1.8", "2.0", "1.1", "1.5"),
        ]
    )
    swings = detect_swings(bars=bars, config=StructureConfig(swing_left=1, swing_right=1))

    kinds = [s.kind for s in swings if s.confirmed]
    assert kinds == ["high", "low"]
    assert swings[0].price == Decimal("4.0")
    assert swings[1].price == Decimal("0.7")


def test_last_unconfirmed_swing_is_optional() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.8", "0.9"),
            ("1.0", "2.0", "1.0", "1.8"),
            ("1.8", "3.0", "1.2", "2.5"),
            ("2.5", "2.0", "1.1", "1.9"),
            ("1.9", "3.5", "1.4", "3.2"),
            ("3.2", "6.0", "1.8", "5.5"),
        ]
    )

    with_unconfirmed = detect_swings(
        bars=bars,
        config=StructureConfig(swing_left=2, swing_right=2, allow_unconfirmed_last_swing=True),
    )
    without_unconfirmed = detect_swings(
        bars=bars,
        config=StructureConfig(swing_left=2, swing_right=2, allow_unconfirmed_last_swing=False),
    )

    assert any((not s.confirmed and s.bar_index == 5) for s in with_unconfirmed)
    assert all(s.bar_index != 5 for s in without_unconfirmed)


def test_detect_bos_uses_close_and_only_confirmed_swings() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.8", "0.9"),
            ("1.0", "2.0", "1.0", "1.8"),
            ("1.8", "5.0", "1.2", "4.5"),
            ("4.4", "3.0", "1.1", "2.0"),
            ("2.0", "2.0", "0.7", "1.0"),
            ("1.0", "4.0", "1.0", "3.9"),
            ("3.9", "5.3", "3.8", "5.05"),
            ("5.1", "5.4", "4.8", "5.2"),
        ]
    )
    cfg = StructureConfig(swing_left=2, swing_right=2, bos_buffer=Decimal("0.1"))
    swings = detect_swings(bars=bars, config=cfg)
    events = detect_bos(bars=bars, swings=swings, config=cfg)

    assert len(events) == 1
    assert events[0].side == "bull"
    assert events[0].bar_index == 7
    assert events[0].close == Decimal("5.2")


def test_detect_bos_ignores_unconfirmed_swing_breaks() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.8", "0.9"),
            ("1.0", "2.0", "1.0", "1.8"),
            ("1.8", "3.0", "1.2", "2.5"),
            ("2.5", "2.0", "1.1", "1.9"),
            ("1.9", "3.5", "1.4", "3.2"),
            ("3.2", "6.0", "1.8", "6.0"),
        ]
    )
    cfg = StructureConfig(swing_left=2, swing_right=2, allow_unconfirmed_last_swing=True)
    swings = detect_swings(bars=bars, config=cfg)
    events = detect_bos(bars=bars, swings=swings, config=cfg)
    assert any(not s.confirmed for s in swings)
    assert events == []


def test_derive_structure_state_builds_dealing_range_from_last_bos() -> None:
    bars = _bars_from_ohlc(
        [
            ("1.5", "2.0", "1.0", "1.4"),
            ("1.4", "1.8", "0.6", "1.0"),
            ("1.0", "2.2", "0.9", "2.0"),
            ("2.0", "3.0", "1.2", "2.8"),
            ("2.8", "2.4", "1.1", "2.0"),
            ("2.0", "3.4", "2.0", "3.2"),
            ("3.2", "3.3", "2.5", "2.9"),
        ]
    )
    cfg = StructureConfig(swing_left=1, swing_right=1, bos_buffer=Decimal("0"))
    result = analyze_structure(bars=bars, config=cfg)

    assert result.state.current_bias == "bull"
    assert result.state.current_bias_since == bars[5].timestamp_utc
    assert result.state.current_dealing_range is not None
    dr = result.state.current_dealing_range
    assert dr.low == Decimal("1.1")
    assert dr.high == Decimal("3.4")
    assert dr.mid == Decimal("2.25")
    assert dr.discount_zone == (Decimal("1.1"), Decimal("2.25"))
    assert dr.premium_zone == (Decimal("2.25"), Decimal("3.4"))
    assert dr.low_source == "last_confirmed_swing_low"
    assert dr.high_source == "last_confirmed_swing_high"


def test_state_is_consistent_when_preconditions_missing() -> None:
    few_bars = _bars_from_ohlc(
        [
            ("1.0", "1.0", "0.8", "0.9"),
            ("1.0", "1.1", "0.9", "1.0"),
            ("1.0", "1.2", "0.95", "1.1"),
        ]
    )
    neutral = analyze_structure(bars=few_bars, config=StructureConfig(swing_left=2, swing_right=2))
    assert neutral.state.current_bias == "neutral"
    assert neutral.state.current_dealing_range is None


@pytest.mark.parametrize(
    ("config", "match"),
    [
        (StructureConfig(swing_left=0), "swing_left"),
        (StructureConfig(swing_right=0), "swing_right"),
        (StructureConfig(bos_buffer=Decimal("-0.01")), "bos_buffer"),
    ],
)
def test_structure_config_validation(config: StructureConfig, match: str) -> None:
    bars = _bars_from_ohlc([("1.0", "1.1", "0.9", "1.0"), ("1.0", "1.2", "0.95", "1.1")])
    with pytest.raises(ValueError, match=match):
        detect_swings(bars=bars, config=config)
