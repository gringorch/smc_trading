from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.fvg import FvgMitigation, FvgSignal
from indicators.ifvg import IfvgConfig, IfvgSignal
from reporting import ifvg_report


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


def _sample_signal() -> IfvgSignal:
    return IfvgSignal(
        side="sell",
        triggered_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        symbol="EURUSD",
        ltf_timeframe="1m",
        htf_timeframe=None,
        poi=None,
        origin_fvg=FvgSignal(
            direction="bull",
            formed_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            gap_low=Decimal("1.10"),
            gap_high=Decimal("1.12"),
            gap_size=Decimal("0.02"),
            index_start=0,
            index_end=2,
            mitigation=FvgMitigation(mitigated=False, mitigated_at=None),
        ),
        reason=["inversion_close", "displacement_ok"],
        entry=Decimal("1.09"),
        stop=Decimal("1.12"),
        tp=Decimal("1.03"),
    )


def test_build_plotly_chart_html_rejects_empty_bars() -> None:
    with pytest.raises(ValueError, match="no bars provided for plotting"):
        ifvg_report._build_plotly_chart_html(
            symbol="EURUSD",
            timeframe="1m",
            bars=[],
            signals=[],
            title="x",
        )


def test_build_ifvg_report_html_includes_plot_and_table() -> None:
    bars = _sample_bars()
    signal = _sample_signal()
    html = ifvg_report.build_ifvg_report_html(
        symbol="EURUSD",
        timeframe="1m",
        candles=50,
        end_utc=bars[-1].timestamp_utc,
        config=IfvgConfig(),
        bars=bars,
        signals=[signal],
        title="IFVG Test",
    )

    assert "<!doctype html>" in html
    assert "<title>IFVG Test</title>" in html
    assert "cdn.plot.ly" in html
    assert "<h3>Signals</h3>" in html
    assert 'class="pill sell"' in html
    assert "ifvg_config" in html
    assert "origin_fvg_direction" in html


def test_build_ifvg_report_html_no_signals_shows_empty_state() -> None:
    bars = _sample_bars()
    html = ifvg_report.build_ifvg_report_html(
        symbol="EURUSD",
        timeframe="1m",
        candles=50,
        end_utc=None,
        config=IfvgConfig(displacement_min_body_pct=Decimal("0.7")),
        bars=bars,
        signals=[],
    )

    assert "(no signals)" in html
    assert "&quot;signals&quot;: 0" in html
    assert "&quot;end_utc&quot;: None" in html


def test_ifvg_report_helper_formatters() -> None:
    assert ifvg_report._fmt_decimal(Decimal("1.2300")) == "1.23"
    assert ifvg_report._fmt_ts(datetime(2026, 1, 1, 15, 4, tzinfo=UTC)) == "2026-01-01 15:04"
    rendered = ifvg_report._json_like({"x": 1, "nested": {"a": "b"}})
    assert '"x": 1,' in rendered
    assert '"nested": {' in rendered
