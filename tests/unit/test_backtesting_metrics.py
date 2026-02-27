from __future__ import annotations

from datetime import UTC, datetime

from backtesting.metrics import build_summary
from strategy.definitions import TradeResult


def test_build_summary_computes_win_rate() -> None:
    trades = [
        TradeResult(
            entry_ts=datetime(2026, 1, 1, tzinfo=UTC),
            entry_price=1.0,
            exit_ts=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            exit_price=1.1,
            direction="long",
            qty=1.0,
            pnl_gross=0.1,
            pnl_net=0.09,
            exit_reason="tp",
            meta={},
        ),
        TradeResult(
            entry_ts=datetime(2026, 1, 1, tzinfo=UTC),
            entry_price=1.0,
            exit_ts=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            exit_price=0.9,
            direction="long",
            qty=1.0,
            pnl_gross=-0.1,
            pnl_net=-0.11,
            exit_reason="sl",
            meta={},
        ),
    ]

    summary = build_summary(trades)

    assert summary.total_trades == 2
    assert summary.win_rate == 0.5
