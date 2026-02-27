from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from charting.resampler import OhlcvBar
from charting.service import PriceChartService


class FakeRepo:
    def __init__(self, rows: list[OhlcvBar]) -> None:
        self.rows = rows
        self.last_end_utc = None

    def list_active_symbols(self) -> list[str]:
        return ["EURUSD"]

    def get_asset_id_by_symbol(self, symbol: str) -> int | None:
        if symbol == "EURUSD":
            return 1
        return None

    def get_latest_1m_timestamp(self, asset_id: int):
        assert asset_id == 1
        if not self.rows:
            return None
        return self.rows[-1].timestamp_utc

    def load_1m_rows(self, *, asset_id: int, start_utc, end_utc) -> list[OhlcvBar]:
        assert asset_id == 1
        self.last_end_utc = end_utc
        return [row for row in self.rows if row.timestamp_utc <= end_utc]


def _rows(start: datetime, count: int) -> list[OhlcvBar]:
    values: list[OhlcvBar] = []
    for i in range(count):
        px = Decimal(200 + i)
        values.append(
            OhlcvBar(
                timestamp_utc=start + timedelta(minutes=i),
                open=px,
                high=px + Decimal("0.3"),
                low=px - Decimal("0.2"),
                close=px + Decimal("0.1"),
                volume=Decimal("2.0"),
            )
        )
    return values


def test_plot_price_returns_exact_number_of_candles(monkeypatch) -> None:
    captured = {}

    def fake_render_price_chart(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("charting.service.render_price_chart", fake_render_price_chart)

    service = PriceChartService(FakeRepo(_rows(datetime(2026, 1, 1, 10, 0, tzinfo=UTC), 40)))
    bars = service.plot_price(symbol="EURUSD", timeframe="5m", candles=3, show=False)

    assert len(bars) == 3
    assert len(captured["bars"]) == 3


def test_plot_price_defaults_end_to_latest_persisted_timestamp(monkeypatch) -> None:
    monkeypatch.setattr("charting.service.render_price_chart", lambda **_: None)
    rows = _rows(datetime(2026, 1, 1, 10, 0, tzinfo=UTC), 10)
    repo = FakeRepo(rows)
    service = PriceChartService(repo)

    service.plot_price(symbol="EURUSD", timeframe="1m", candles=2, show=False)

    assert repo.last_end_utc == rows[-1].timestamp_utc


def test_plot_price_includes_partial_last_candle(monkeypatch) -> None:
    captured = {}

    def fake_render_price_chart(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("charting.service.render_price_chart", fake_render_price_chart)

    start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    service = PriceChartService(FakeRepo(_rows(start, 17)))
    bars = service.plot_price(
        symbol="EURUSD",
        timeframe="15m",
        candles=2,
        end=start + timedelta(minutes=16),
        show=False,
    )

    assert len(bars) == 2
    assert bars[-1].timestamp_utc == datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
    assert bars[-1].close == Decimal("216.1")
    assert captured["show"] is False


def test_plot_price_raises_for_unknown_symbol(monkeypatch) -> None:
    monkeypatch.setattr("charting.service.render_price_chart", lambda **_: None)
    service = PriceChartService(FakeRepo([]))

    with pytest.raises(ValueError, match="not found"):
        service.plot_price(symbol="UNKNOWN", timeframe="1h", candles=2, show=False)


def test_plot_price_raises_when_symbol_has_no_persisted_candles(monkeypatch) -> None:
    monkeypatch.setattr("charting.service.render_price_chart", lambda **_: None)
    service = PriceChartService(FakeRepo([]))

    with pytest.raises(ValueError, match="no persisted 1m candles"):
        service.plot_price(symbol="EURUSD", timeframe="1h", candles=2, show=False)
