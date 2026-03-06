from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from indicators.htf_poi import HtfPoiCandidate, HtfPoiConfig, HtfPoiContext
from indicators.structure import DealingRange
from reporting import htf_poi_report


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
            datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
            open_="1.05",
            high="1.25",
            low="1.00",
            close="1.20",
        ),
        _bar(
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
            open_="1.20",
            high="1.30",
            low="1.10",
            close="1.15",
        ),
    ]


def _sample_context() -> HtfPoiContext:
    candidate = HtfPoiCandidate(
        side="buy",
        status="active",
        source_fvg_direction="bull",
        fvg_formed_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        poi_low=Decimal("1.10"),
        poi_high=Decimal("1.20"),
        dynamic_poi_low=Decimal("1.08"),
        dynamic_poi_high=Decimal("1.24"),
        discount_premium_context="discount",
        activated_at=datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        invalidated_at=None,
        expires_at=datetime(2026, 1, 1, 4, 0, tzinfo=UTC),
        activation_reason=["activation_touch", "bias_ok"],
        expiration_reason=[],
        reason=["fvg_selected"],
    )
    return HtfPoiContext(
        current_bias="bull",
        dealing_range=DealingRange(
            low=Decimal("1.0"),
            high=Decimal("1.4"),
            mid=Decimal("1.2"),
            discount_zone=(Decimal("1.0"), Decimal("1.2")),
            premium_zone=(Decimal("1.2"), Decimal("1.4")),
            derived_from_bos=0,
            low_source="last_confirmed_swing_low",
            high_source="last_confirmed_swing_high",
        ),
        poi_candidates=[candidate],
        active_poi=candidate,
    )


def test_build_plotly_chart_html_rejects_empty_bars() -> None:
    with pytest.raises(ValueError, match="no bars provided for plotting"):
        htf_poi_report._build_plotly_chart_html(
            symbol="EURUSD",
            timeframe="1h",
            bars=[],
            context=_sample_context(),
            title="x",
        )


def test_build_htf_poi_report_html_includes_plot_and_table() -> None:
    bars = _sample_bars()
    html = htf_poi_report.build_htf_poi_report_html(
        symbol="EURUSD",
        timeframe="1h",
        candles=120,
        end_utc=bars[-1].timestamp_utc,
        config=HtfPoiConfig(),
        bars=bars,
        context=_sample_context(),
        title="HTF POI Test",
    )

    assert "<!doctype html>" in html
    assert "<title>HTF POI Test</title>" in html
    assert "cdn.plot.ly" in html
    assert "<h3>POIs</h3>" in html
    assert 'class="pill buy"' in html
    assert "htf_poi_config" in html
    assert "expires_at" in html
    assert "activation_touch" in html
    assert "dynamic_poi_high" in html


def test_build_htf_poi_report_html_no_candidates_shows_empty_state() -> None:
    bars = _sample_bars()
    context = HtfPoiContext(
        current_bias="neutral",
        dealing_range=None,
        poi_candidates=[],
        active_poi=None,
    )
    html = htf_poi_report.build_htf_poi_report_html(
        symbol="EURUSD",
        timeframe="1h",
        candles=120,
        end_utc=None,
        config=HtfPoiConfig(),
        bars=bars,
        context=context,
    )
    assert "(no pois)" in html
    assert "&quot;active_poi&quot;: None" in html


def test_htf_poi_report_helpers() -> None:
    assert htf_poi_report._fmt_decimal(Decimal("1.2300")) == "1.23"
    assert htf_poi_report._fmt_ts(datetime(2026, 1, 1, 15, 4, tzinfo=UTC)) == "2026-01-01 15:04"
    rendered = htf_poi_report._json_like({"x": 1})
    assert '"x": 1,' in rendered
