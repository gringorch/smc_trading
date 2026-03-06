from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.fvg import FvgMitigation, FvgSignal
from indicators.htf_poi import HtfPoiConfig, detect_htf_pois
from indicators.structure import DealingRange, StructureResult, StructureState


def _bar(ts: datetime, *, open_: str, high: str, low: str, close: str) -> OhlcvBar:
    return OhlcvBar(
        timestamp_utc=ts,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def _bars() -> list[OhlcvBar]:
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    rows: list[tuple[str, str, str, str]] = [
        ("1.40", "1.55", "1.35", "1.50"),
        ("1.50", "1.60", "1.45", "1.58"),
        ("1.58", "1.62", "1.40", "1.50"),
        ("1.50", "1.54", "1.24", "1.32"),
        ("1.32", "1.36", "1.28", "1.34"),
        ("1.34", "1.60", "1.32", "1.57"),
        ("1.57", "1.65", "1.55", "1.60"),
        ("1.60", "1.61", "1.48", "1.49"),
    ]
    return [
        _bar(t0 + timedelta(hours=i), open_=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(rows)
    ]


def _structure_result(*, bias: str) -> StructureResult:
    return StructureResult(
        swings=[],
        bos_events=[],
        state=StructureState(
            current_bias=bias,  # type: ignore[arg-type]
            current_bias_since=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            current_dealing_range=DealingRange(
                low=Decimal("1.0"),
                high=Decimal("2.0"),
                mid=Decimal("1.5"),
                discount_zone=(Decimal("1.0"), Decimal("1.5")),
                premium_zone=(Decimal("1.5"), Decimal("2.0")),
                derived_from_bos=0,
                low_source="last_confirmed_swing_low",
                high_source="last_confirmed_swing_high",
            ),
        ),
    )


def _fvg(
    *,
    direction: str,
    formed_at: datetime,
    low: str,
    high: str,
    index_end: int = 2,
) -> FvgSignal:
    return FvgSignal(
        direction=direction,  # type: ignore[arg-type]
        formed_at=formed_at,
        gap_low=Decimal(low),
        gap_high=Decimal(high),
        gap_size=Decimal(high) - Decimal(low),
        index_start=0,
        index_end=index_end,
        mitigation=FvgMitigation(mitigated=False, mitigated_at=None),
    )


def test_bull_discount_poi_activates(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bull"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bull", formed_at=bars[2].timestamp_utc, low="1.20", high="1.30")],
    )

    result = detect_htf_pois(bars=bars, config=HtfPoiConfig())
    assert len(result.poi_candidates) == 1
    poi = result.poi_candidates[0]
    assert poi.side == "buy"
    assert poi.status == "active"
    assert poi.discount_premium_context == "discount"
    assert poi.activated_at == bars[3].timestamp_utc
    assert poi.dynamic_poi_low == Decimal("1.20")
    assert poi.dynamic_poi_high == Decimal("1.65")
    assert result.active_poi is not None


def test_bear_premium_poi_activates(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bear"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bear", formed_at=bars[2].timestamp_utc, low="1.60", high="1.75")],
    )

    result = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(
            poi_activation_rule="touch",
            require_discount_premium_alignment=True,
        ),
    )
    assert len(result.poi_candidates) == 1
    assert result.poi_candidates[0].side == "sell"
    assert result.poi_candidates[0].status == "active"
    assert result.poi_candidates[0].discount_premium_context == "premium"


def test_alignment_required_blocks_outside_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bull"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bull", formed_at=bars[2].timestamp_utc, low="1.75", high="1.85")],
    )

    result = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(require_discount_premium_alignment=True),
    )
    assert result.poi_candidates == []
    assert result.active_poi is None


def test_activation_rule_changes_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bull"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bull", formed_at=bars[2].timestamp_utc, low="1.20", high="1.30")],
    )

    touch = detect_htf_pois(
        bars=bars, config=HtfPoiConfig(poi_activation_rule="touch", only_unmitigated_fvg=False)
    )
    close_inside = detect_htf_pois(
        bars=bars, config=HtfPoiConfig(poi_activation_rule="close_inside", only_unmitigated_fvg=False)
    )

    assert touch.poi_candidates[0].status == "active"
    assert close_inside.poi_candidates[0].status == "pending"


def test_expiration_from_activation_and_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bull"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bull", formed_at=bars[2].timestamp_utc, low="1.20", high="1.30")],
    )

    from_activation = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(
            poi_activation_rule="touch",
            poi_validity_bars=1,
            poi_expiration_rule="bars_since_activation",
            only_unmitigated_fvg=False,
        ),
    )
    from_creation = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(
            poi_activation_rule="close_inside",
            poi_validity_bars=1,
            poi_expiration_rule="bars_since_creation",
            only_unmitigated_fvg=False,
        ),
    )

    assert from_activation.poi_candidates[0].status == "invalidated"
    assert "expired_bars_since_activation" in from_activation.poi_candidates[0].expiration_reason
    assert from_creation.poi_candidates[0].status == "invalidated"
    assert "expired_before_activation" in from_creation.poi_candidates[0].expiration_reason


def test_bias_mismatch_invalidates_when_both_directions(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bull"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bear", formed_at=bars[2].timestamp_utc, low="1.40", high="1.70")],
    )

    result = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(
            fvg_direction_filter="both",
            require_discount_premium_alignment=False,
            poi_activation_rule="touch",
        ),
    )
    assert len(result.poi_candidates) == 1
    assert result.poi_candidates[0].status == "invalidated"
    assert "bias_mismatch_current" in result.poi_candidates[0].expiration_reason


def test_replay_context_uses_bias_at_fvg_formation(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()

    def _fake_analyze_structure(*, bars, config):  # noqa: ANN001
        # Early chart: bull context. Full chart: bear context.
        if len(bars) <= 3:
            return _structure_result(bias="bull")
        return _structure_result(bias="bear")

    monkeypatch.setattr("indicators.htf_poi.analyze_structure", _fake_analyze_structure)
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bull", formed_at=bars[2].timestamp_utc, low="1.20", high="1.30")],
    )

    replay_on = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(replay_context=True),
    )
    replay_off = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(replay_context=False),
    )

    assert len(replay_on.poi_candidates) == 1
    assert replay_off.poi_candidates == []


def test_dynamic_width_can_be_limited_by_following_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr("indicators.htf_poi.analyze_structure", lambda **_: _structure_result(bias="bull"))
    monkeypatch.setattr(
        "indicators.htf_poi.detect_fvgs",
        lambda **_: [_fvg(direction="bull", formed_at=bars[2].timestamp_utc, low="1.20", high="1.30")],
    )

    limited = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(
            poi_activation_rule="touch",
            max_dynamic_extension_bars=1,
        ),
    )
    unlimited = detect_htf_pois(
        bars=bars,
        config=HtfPoiConfig(
            poi_activation_rule="touch",
            max_dynamic_extension_bars=None,
        ),
    )

    assert limited.poi_candidates[0].dynamic_poi_high == Decimal("1.36")
    assert unlimited.poi_candidates[0].dynamic_poi_high == Decimal("1.65")


@pytest.mark.parametrize(
    ("config", "match"),
    [
        (HtfPoiConfig(max_active_pois=0), "max_active_pois"),
        (HtfPoiConfig(min_gap_size=Decimal("-0.1")), "min_gap_size"),
        (HtfPoiConfig(max_dynamic_extension_bars=0), "max_dynamic_extension_bars"),
        (HtfPoiConfig(dynamic_width_source="invalid"), "dynamic_width_source"),  # type: ignore[arg-type]
    ],
)
def test_detect_htf_pois_validates_config(config: HtfPoiConfig, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        detect_htf_pois(bars=[], config=config)
