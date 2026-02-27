from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from charting.resampler import OhlcvBar
from strategy.events import Direction, Event, EventKind, StrategyConfig
from strategy.service import AnalysisResult, analyze_adaptive, analyze_multi_tf


def test_strategy_config_defaults_are_loaded() -> None:
    cfg = StrategyConfig()
    assert cfg.config_htf.min_break_atr["1h"] == 0.25
    assert cfg.config_ltf.trigger_max_distance_to_poi_atr["1m"] == 0.40


def test_analyze_multi_tf_links_ifvg_with_overlapping_poi(monkeypatch) -> None:
    ts = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    bars = [
        OhlcvBar(
            timestamp_utc=ts,
            open=Decimal("1.0"),
            high=Decimal("1.2"),
            low=Decimal("0.9"),
            close=Decimal("1.1"),
            volume=Decimal("1.0"),
        )
    ]

    def fake_analyze(symbol, timeframe, candles, config=None):
        if timeframe == "1h":
            return AnalysisResult(
                events=[
                    Event(
                        kind=EventKind.FVG, direction=Direction.BULL, price_low=1.0, price_high=1.3
                    )
                ],
                bars=bars,
            )
        return AnalysisResult(
            events=[
                Event(kind=EventKind.IFVG, direction=Direction.BEAR, price_low=1.1, price_high=1.2)
            ],
            bars=bars,
        )

    monkeypatch.setattr("strategy.service.analyze", fake_analyze)

    report = analyze_multi_tf("EURUSD", "1h", "3m", 100, 100)
    assert report["counts"]["linked"] == 1


def test_analyze_adaptive_selects_1m_when_trend(monkeypatch) -> None:
    ts = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    bars = [
        OhlcvBar(
            timestamp_utc=ts,
            open=Decimal("1.0"),
            high=Decimal("1.2"),
            low=Decimal("0.9"),
            close=Decimal("1.1"),
            volume=Decimal("1.0"),
        )
    ]

    def fake_analyze(symbol, timeframe, candles, config=None):
        if timeframe == "1h":
            return AnalysisResult(
                events=[Event(kind=EventKind.BOS, direction=Direction.BULL)], bars=bars
            )
        return AnalysisResult(events=[], bars=bars)

    monkeypatch.setattr("strategy.service.analyze", fake_analyze)

    report = analyze_adaptive("EURUSD")
    assert report["market_state"] == "TREND_BULL"
    assert report["selected_ltf"] == "1m"
