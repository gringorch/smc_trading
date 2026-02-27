"""Backtesting metrics aggregation."""

from __future__ import annotations

from strategy.definitions import BacktestSummary, TradeResult


def _max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        drawdown = peak - value
        max_dd = max(max_dd, drawdown)
    return max_dd


def build_summary(trades: list[TradeResult]) -> BacktestSummary:
    total = len(trades)
    wins = sum(1 for trade in trades if trade.pnl_net > 0)
    losses = sum(1 for trade in trades if trade.pnl_net < 0)

    gross_profit = sum(trade.pnl_net for trade in trades if trade.pnl_net > 0)
    gross_loss = abs(sum(trade.pnl_net for trade in trades if trade.pnl_net < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    pnl_gross = sum(trade.pnl_gross for trade in trades)
    pnl_net = sum(trade.pnl_net for trade in trades)
    win_rate = (wins / total) if total > 0 else 0.0

    equity = 0.0
    equity_curve = [0.0]
    for trade in trades:
        equity += trade.pnl_net
        equity_curve.append(equity)

    return BacktestSummary(
        total_trades=total,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        pnl_gross=pnl_gross,
        pnl_net=pnl_net,
        profit_factor=profit_factor,
        max_drawdown=_max_drawdown(equity_curve),
    )
