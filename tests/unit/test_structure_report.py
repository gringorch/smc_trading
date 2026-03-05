from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.structure import BosEvent, DealingRange, StructureConfig, StructureState, SwingPoint
from reporting import structure_report


def _bar(ts: datetime, *, open_: str, high: str, low: str, close: str) -> OhlcvBar:
    return OhlcvBar(
        timestamp_utc=ts,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def _sample_bars() -> list[OhlcvBar]:
    return [
        _bar(
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            open_="1.00",
            high="1.10",
            low="0.95",
            close="1.05",
        ),
        _bar(
            datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            open_="1.05",
            high="1.50",
            low="1.00",
            close="1.20",
        ),
        _bar(
            datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            open_="1.20",
            high="1.40",
            low="0.90",
            close="1.30",
        ),
    ]


def test_build_plotly_chart_html_rejects_empty_bars() -> None:
    with pytest.raises(ValueError, match="no bars provided for plotting"):
        structure_report._build_plotly_chart_html(
            symbol="EURUSD",
            timeframe="1h",
            bars=[],
            swings=[],
            bos_events=[],
            state=StructureState(
                current_bias="neutral",
                current_bias_since=None,
                current_dealing_range=None,
            ),
            title="x",
        )


def test_build_structure_report_html_includes_plot_and_tables() -> None:
    bars = _sample_bars()
    swings = [
        SwingPoint(
            kind="high",
            timestamp_utc=bars[1].timestamp_utc,
            price=Decimal("1.50"),
            bar_index=1,
            left=2,
            right=2,
            confirmed=True,
        ),
        SwingPoint(
            kind="low",
            timestamp_utc=bars[2].timestamp_utc,
            price=Decimal("0.90"),
            bar_index=2,
            left=2,
            right=2,
            confirmed=False,
        ),
    ]
    bos_events = [
        BosEvent(
            side="bull",
            triggered_at=bars[2].timestamp_utc,
            bar_index=2,
            broken_swing_index=0,
            close=Decimal("1.30"),
            buffer=Decimal("0"),
        )
    ]
    state = StructureState(
        current_bias="bull",
        current_bias_since=bars[2].timestamp_utc,
        current_dealing_range=DealingRange(
            low=Decimal("0.90"),
            high=Decimal("1.40"),
            mid=Decimal("1.15"),
            discount_zone=(Decimal("0.90"), Decimal("1.15")),
            premium_zone=(Decimal("1.15"), Decimal("1.40")),
            derived_from_bos=0,
            low_source="last_confirmed_swing_low",
            high_source="last_confirmed_swing_high",
        ),
    )

    html = structure_report.build_structure_report_html(
        symbol="EURUSD",
        timeframe="1h",
        candles=100,
        end_utc=bars[-1].timestamp_utc,
        config=StructureConfig(),
        bars=bars,
        swings=swings,
        bos_events=bos_events,
        state=state,
        title="Structure Test",
    )

    assert "<!doctype html>" in html
    assert "<title>Structure Test</title>" in html
    assert "cdn.plot.ly" in html
    assert "<h3>Swings</h3>" in html
    assert "<h3>BOS events</h3>" in html
    assert "structure_config" in html
    assert "DR.high (last_confirmed_swing_high)" in html
    assert "DR.low (last_confirmed_swing_low)" in html
    assert 'class="pill bull"' in html


def test_structure_report_helpers() -> None:
    assert structure_report._fmt_decimal(Decimal("1.2300")) == "1.23"
    assert structure_report._fmt_ts(datetime(2026, 1, 1, 15, 4, tzinfo=UTC)) == "2026-01-01 15:04"
    rendered = structure_report._json_like({"x": 1})
    assert '"x": 1,' in rendered
