from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backtesting.simulator import run_backtest
from charting.resampler import OhlcvBar
from strategy.definitions import TradeIntent, parse_strategy_definition


def _candles() -> list[OhlcvBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = [1.00, 1.01, 1.03, 1.05, 1.04]
    bars = []
    for i, value in enumerate(values):
        bars.append(
            OhlcvBar(
                timestamp_utc=start + timedelta(minutes=i),
                open=Decimal(str(value)),
                high=Decimal(str(value + 0.01)),
                low=Decimal(str(value - 0.01)),
                close=Decimal(str(value)),
                volume=Decimal("1"),
            )
        )
    return bars


def test_run_backtest_returns_trade_results() -> None:
    strategy = parse_strategy_definition(
        {
            "name": "ifvg_poi",
            "version": "1.0.0",
            "description": "test",
            "timeframes": {"htf": "1h", "ltf_default": "3m", "ltf_trend": "1m"},
            "trigger_rules": [{"event_kind": "IFVG", "direction": "bull"}],
        }
    )

    intent = TradeIntent(
        ts=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        direction="long",
        entry_ref=1.01,
        sl=0.99,
        tp=1.04,
        meta={},
    )

    report = run_backtest([intent], _candles(), strategy)

    assert report.summary.total_trades == 1
    assert report.trades[0].exit_reason in {"tp", "sl", "eod"}
