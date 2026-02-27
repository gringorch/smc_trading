from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from types import ModuleType

import pytest

from charting.price_plotter import render_price_chart
from charting.resampler import OhlcvBar


class _FakeFrame:
    def set_index(self, _name: str):
        return self


class _FakePandas(ModuleType):
    def DataFrame(self, _payload):  # noqa: N802
        return _FakeFrame()


class _FakeFig:
    def __init__(self) -> None:
        self.saved = None

    def savefig(self, path: str) -> None:
        self.saved = path


class _FakeMpf(ModuleType):
    def __init__(self) -> None:
        super().__init__("mplfinance")
        self.calls: list[dict[str, object]] = []

    def plot(self, _frame, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("returnfig"):
            return _FakeFig(), []
        return None


class _FakePyplot(ModuleType):
    def __init__(self) -> None:
        super().__init__("matplotlib.pyplot")
        self.closed = 0

    def close(self, _fig) -> None:
        self.closed += 1


@pytest.fixture()
def fake_plot_modules(monkeypatch):
    fake_pd = _FakePandas("pandas")
    fake_mpf = _FakeMpf()
    fake_plt = _FakePyplot()

    monkeypatch.setitem(sys.modules, "pandas", fake_pd)
    monkeypatch.setitem(sys.modules, "mplfinance", fake_mpf)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", fake_plt)
    yield fake_mpf, fake_plt


def _bars() -> list[OhlcvBar]:
    return [
        OhlcvBar(
            timestamp_utc=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            open=Decimal("1.0"),
            high=Decimal("1.2"),
            low=Decimal("0.9"),
            close=Decimal("1.1"),
            volume=Decimal("10.0"),
        )
    ]


def test_render_price_chart_rejects_empty_bars() -> None:
    with pytest.raises(ValueError, match="no bars available"):
        render_price_chart(
            symbol="EURUSD",
            timeframe="1m",
            bars=[],
            include_volume=False,
            show=False,
            save_path=None,
        )


def test_render_price_chart_show_true_passes_savefig(fake_plot_modules) -> None:
    fake_mpf, _ = fake_plot_modules

    render_price_chart(
        symbol="EURUSD",
        timeframe="1m",
        bars=_bars(),
        include_volume=True,
        show=True,
        save_path="chart.png",
    )

    assert len(fake_mpf.calls) == 1
    assert fake_mpf.calls[0]["savefig"] == "chart.png"
    assert fake_mpf.calls[0]["volume"] is True


def test_render_price_chart_show_false_returns_fig_and_closes(fake_plot_modules) -> None:
    fake_mpf, fake_plt = fake_plot_modules

    render_price_chart(
        symbol="EURUSD",
        timeframe="3m",
        bars=_bars(),
        include_volume=False,
        show=False,
        save_path="out.png",
    )

    assert len(fake_mpf.calls) == 1
    assert fake_mpf.calls[0]["returnfig"] is True
    assert fake_plt.closed == 1
