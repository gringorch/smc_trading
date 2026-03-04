from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.fvg import FvgConfig, FvgMitigation, FvgSignal
from reporting import fvg_report


def _bar(ts: datetime, *, o: str, h: str, l: str, c: str) -> OhlcvBar:
    return OhlcvBar(
        timestamp_utc=ts,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal("10"),
    )


def _sample_bars() -> list[OhlcvBar]:
    return [
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), o="1.00", h="1.10", l="0.95", c="1.05"),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), o="1.05", h="1.20", l="1.00", c="1.18"),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), o="1.18", h="1.25", l="1.12", c="1.22"),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), o="1.22", h="1.24", l="1.05", c="1.09"),
    ]


def _sample_signals() -> list[FvgSignal]:
    return [
        FvgSignal(
            direction="bull",
            formed_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            gap_low=Decimal("1.10"),
            gap_high=Decimal("1.12"),
            gap_size=Decimal("0.02"),
            index_start=0,
            index_end=2,
            mitigation=FvgMitigation(
                mitigated=True,
                mitigated_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
            ),
        ),
        FvgSignal(
            direction="bear",
            formed_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
            gap_low=Decimal("1.05"),
            gap_high=Decimal("1.08"),
            gap_size=Decimal("0.03"),
            index_start=1,
            index_end=3,
            mitigation=FvgMitigation(mitigated=False, mitigated_at=None),
        ),
    ]


def test_build_plotly_chart_html_rejects_empty_bars() -> None:
    with pytest.raises(ValueError, match="no bars provided for plotting"):
        fvg_report._build_plotly_chart_html(
            symbol="EURUSD",
            timeframe="1h",
            bars=[],
            signals=[],
            title="x",
        )


def test_build_fvg_report_html_includes_plot_and_table() -> None:
    bars = _sample_bars()
    signals = _sample_signals()
    html = fvg_report.build_fvg_report_html(
        symbol="EURUSD",
        timeframe="1h",
        candles=100,
        end_utc=bars[-1].timestamp_utc,
        config=FvgConfig(direction="both"),
        bars=bars,
        signals=signals,
        title="My Report",
    )

    assert "<!doctype html>" in html
    assert "<title>My Report</title>" in html
    assert "cdn.plot.ly" in html
    assert '"text":"Time (UTC)"' in html
    assert "\"type\":\"category\"" in html
    assert "<h3>Signals</h3>" in html
    assert 'class="pill bull"' in html
    assert 'class="pill bear"' in html
    assert "fvg_config" in html
    assert "mitigated_at" in html


def test_build_fvg_report_html_with_no_signals_shows_empty_state() -> None:
    bars = _sample_bars()
    html = fvg_report.build_fvg_report_html(
        symbol="EURUSD",
        timeframe="1h",
        candles=50,
        end_utc=None,
        config=FvgConfig(direction="bull", mitigation_enabled=False),
        bars=bars,
        signals=[],
    )

    assert "(no signals)" in html
    assert "&quot;end_utc&quot;: None" in html
    assert "&quot;mitigation_enabled&quot;: False" in html


def test_json_like_and_format_helpers() -> None:
    rendered = fvg_report._json_like({"a": 1, "nested": {"x": "y"}})
    assert '"a": 1,' in rendered
    assert '"nested": {' in rendered
    assert "\"x\": 'y'," in rendered
    assert fvg_report._fmt_decimal(Decimal("1.2300")) == "1.23"
    assert fvg_report._fmt_ts(datetime(2026, 1, 1, 15, 4, tzinfo=UTC)) == "2026-01-01 15:04"
