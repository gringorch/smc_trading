from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.ifvg import IfvgConfig, detect_ifvgs


def _bar(ts: datetime, *, o: str, h: str, l: str, c: str) -> OhlcvBar:
    return OhlcvBar(
        timestamp_utc=ts,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal("0"),
    )


def test_detect_ifvg_bullish_fvg_inversion_emits_sell_with_levels() -> None:
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.3", h="101.6", l="99.5", c="99.8"),
    ]

    signals = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            inversion_fill_pct=Decimal("1.0"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
            rr=Decimal("2"),
        ),
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.side == "sell"
    assert signal.triggered_at == bars[3].timestamp_utc
    assert signal.entry == Decimal("99.8")
    assert signal.stop == Decimal("101.0")
    assert signal.tp == Decimal("97.4")
    assert signal.reason == ["inversion_close", "displacement_ok"]


def test_detect_ifvg_bearish_fvg_inversion_emits_buy() -> None:
    t0 = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="100.5", h="101.0", l="100.0", c="100.2"),
        _bar(t0 + timedelta(minutes=1), o="100.1", h="100.4", l="99.9", c="100.0"),
        _bar(t0 + timedelta(minutes=2), o="98.9", h="99.0", l="98.5", c="98.7"),
        _bar(t0 + timedelta(minutes=3), o="98.9", h="100.5", l="98.8", c="100.3"),
    ]

    signals = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            inversion_fill_pct=Decimal("1.0"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.side == "buy"
    assert signal.entry == Decimal("100.3")
    assert signal.stop == Decimal("99.0")
    assert signal.tp == Decimal("102.9")


def test_inversion_fill_pct_changes_behavior() -> None:
    t0 = datetime(2026, 1, 3, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.1", h="101.3", l="100.1", c="100.25"),
    ]

    loose = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            inversion_fill_pct=Decimal("0.7"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    strict = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            inversion_fill_pct=Decimal("1.0"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )

    assert len(loose) == 1
    assert strict == []


def test_displacement_filter_blocks_weak_body() -> None:
    t0 = datetime(2026, 1, 4, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="100.29", h="100.9", l="100.1", c="100.25"),
    ]

    signals = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            inversion_fill_pct=Decimal("0.7"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.6"),
        ),
    )

    assert signals == []


def test_bias_required_and_dedupe_cooldown() -> None:
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.3", h="101.6", l="99.5", c="99.8"),
        _bar(t0 + timedelta(minutes=4), o="101.2", h="101.4", l="99.4", c="99.7"),
    ]

    blocked_by_bias = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            bias_required=True,
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
        htf_bias="bull",
    )
    assert blocked_by_bias == []

    deduped = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            one_signal_per_origin_fvg=True,
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    assert len(deduped) == 1

    cooldown = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            one_signal_per_origin_fvg=False,
            cooldown_bars=1,
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    assert len(cooldown) == 1


def test_min_gap_size_filters_small_origin_fvg() -> None:
    t0 = datetime(2026, 1, 6, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.3", h="101.6", l="99.5", c="99.8"),
    ]

    signals = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            min_gap_size=Decimal("1.5"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    assert signals == []


def test_max_bars_from_fvg_formation_to_inversion_is_applied() -> None:
    t0 = datetime(2026, 1, 7, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.1", h="101.3", l="100.9", c="101.0"),
        _bar(t0 + timedelta(minutes=4), o="101.3", h="101.6", l="99.5", c="99.8"),
    ]

    tight = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            min_gap_size=Decimal("0.8"),
            max_bars_from_fvg_formation_to_inversion=1,
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    wide = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            min_gap_size=Decimal("0.8"),
            max_bars_from_fvg_formation_to_inversion=2,
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )

    assert tight == []
    assert len(wide) == 1


def test_body_atr_displacement_uses_atr_warmup() -> None:
    t0 = datetime(2026, 1, 8, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.3", h="101.6", l="99.5", c="99.8"),
    ]

    warmup_blocks = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            displacement_rule="body_atr",
            atr_period=10,
            displacement_body_atr_mult=Decimal("0.1"),
        ),
    )
    period_ready = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            displacement_rule="body_atr",
            atr_period=1,
            displacement_body_atr_mult=Decimal("0.1"),
        ),
    )

    assert warmup_blocks == []
    assert len(period_ready) == 1


def test_sweep_required_and_stop_model_beyond_sweep_extreme() -> None:
    t0 = datetime(2026, 1, 9, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.5", h="101.8", l="101.2", c="101.4"),
        _bar(t0 + timedelta(minutes=4), o="101.3", h="101.4", l="99.5", c="99.8"),
    ]

    signals = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            min_gap_size=Decimal("0.81"),
            sweep_required=True,
            sweep_lookback_bars=2,
            max_bars_between_sweep_and_inversion=2,
            stop_model="beyond_sweep_extreme",
            sl_buffer=Decimal("0.1"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )

    assert len(signals) == 1
    signal = signals[0]
    assert "sweep_ok" in signal.reason
    assert signal.stop == Decimal("101.9")


def test_poi_required_populates_poi_and_reason() -> None:
    t0 = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
    bars = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.3", h="101.6", l="99.5", c="99.8"),
    ]

    signals = detect_ifvgs(
        bars=bars,
        config=IfvgConfig(
            poi_required=True,
            poi_low=Decimal("100.1"),
            poi_high=Decimal("100.9"),
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )

    assert len(signals) == 1
    assert signals[0].poi is not None
    assert "poi_ok" in signals[0].reason


def test_limit_retest_entry_model_variants() -> None:
    t0 = datetime(2026, 1, 11, 0, 0, tzinfo=UTC)
    bars_sell = [
        _bar(t0, o="99.2", h="100.0", l="99.0", c="99.8"),
        _bar(t0 + timedelta(minutes=1), o="99.9", h="100.4", l="99.7", c="100.2"),
        _bar(t0 + timedelta(minutes=2), o="101.2", h="101.5", l="101.0", c="101.3"),
        _bar(t0 + timedelta(minutes=3), o="101.3", h="101.6", l="99.5", c="99.8"),
    ]
    sell = detect_ifvgs(
        bars=bars_sell,
        config=IfvgConfig(
            entry_model="limit_retest",
            limit_retest_level="gap_near_edge",
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    assert len(sell) == 1
    assert sell[0].entry == Decimal("101.0")

    bars_buy = [
        _bar(t0, o="100.5", h="101.0", l="100.0", c="100.2"),
        _bar(t0 + timedelta(minutes=1), o="100.1", h="100.4", l="99.9", c="100.0"),
        _bar(t0 + timedelta(minutes=2), o="98.9", h="99.0", l="98.5", c="98.7"),
        _bar(t0 + timedelta(minutes=3), o="98.9", h="100.5", l="98.8", c="100.3"),
    ]
    buy = detect_ifvgs(
        bars=bars_buy,
        config=IfvgConfig(
            entry_model="limit_retest",
            limit_retest_level="gap_far_edge",
            displacement_rule="body_pct_range",
            displacement_min_body_pct=Decimal("0.5"),
        ),
    )
    assert len(buy) == 1
    assert buy[0].entry == Decimal("100.0")


@pytest.mark.parametrize(
    ("config", "match"),
    [
        (IfvgConfig(min_gap_size=Decimal("-0.1")), "min_gap_size"),
        (IfvgConfig(max_bars_from_fvg_formation_to_inversion=0), "max_bars_from_fvg_formation_to_inversion"),
        (IfvgConfig(displacement_min_body_pct=Decimal("1.1")), "displacement_min_body_pct"),
        (IfvgConfig(poi_required=True), "poi_required"),
        (IfvgConfig(rr=Decimal("0")), "rr must be > 0"),
    ],
)
def test_detect_ifvg_validates_config(config: IfvgConfig, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        detect_ifvgs(bars=[], config=config)
