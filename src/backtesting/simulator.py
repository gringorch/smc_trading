"""Backtesting simulator from intents to realized trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backtesting.metrics import build_summary
from charting.resampler import OhlcvBar
from strategy.definitions import BacktestReport, StrategyDefinition, TradeIntent, TradeResult


@dataclass(frozen=True)
class SimulationConfig:
    quantity: float = 1.0


def _bar_ts(bar: OhlcvBar) -> datetime:
    return bar.timestamp_utc


def _apply_execution_costs(
    price: float, *, side: str, slippage_bps: float, fee_bps: float
) -> float:
    slip_factor = slippage_bps / 10_000.0
    fee_factor = fee_bps / 10_000.0

    if side == "long":
        return price * (1.0 + slip_factor + fee_factor)
    return price * (1.0 - slip_factor - fee_factor)


def run_backtest(
    intents: list[TradeIntent],
    candles_ltf: list[OhlcvBar],
    strategy_def: StrategyDefinition,
    config: SimulationConfig | None = None,
) -> BacktestReport:
    sim_cfg = config or SimulationConfig()
    trades: list[TradeResult] = []

    sorted_bars = sorted(candles_ltf, key=lambda candle: candle.timestamp_utc)
    if not sorted_bars:
        raise ValueError("candles_ltf cannot be empty")

    for intent in sorted(intents, key=lambda item: item.ts):
        entry_idx = next(
            (i for i, bar in enumerate(sorted_bars) if _bar_ts(bar) >= intent.ts), None
        )
        if entry_idx is None:
            continue

        entry_bar = sorted_bars[entry_idx]
        raw_entry = float(entry_bar.open)
        entry_price = _apply_execution_costs(
            raw_entry,
            side=intent.direction,
            slippage_bps=strategy_def.execution_rules.slippage_bps,
            fee_bps=strategy_def.execution_rules.fee_bps,
        )

        exit_bar = sorted_bars[-1]
        exit_price = float(exit_bar.close)
        exit_reason = "eod"

        for bar in sorted_bars[entry_idx + 1 :]:
            bar_high = float(bar.high)
            bar_low = float(bar.low)

            if intent.direction == "long":
                if bar_low <= intent.sl:
                    exit_bar = bar
                    exit_price = intent.sl
                    exit_reason = "sl"
                    break
                if bar_high >= intent.tp:
                    exit_bar = bar
                    exit_price = intent.tp
                    exit_reason = "tp"
                    break
            else:
                if bar_high >= intent.sl:
                    exit_bar = bar
                    exit_price = intent.sl
                    exit_reason = "sl"
                    break
                if bar_low <= intent.tp:
                    exit_bar = bar
                    exit_price = intent.tp
                    exit_reason = "tp"
                    break

        qty = sim_cfg.quantity
        if intent.direction == "long":
            pnl_gross = (exit_price - entry_price) * qty
        else:
            pnl_gross = (entry_price - exit_price) * qty

        total_fee = (
            (strategy_def.execution_rules.fee_bps / 10_000.0) * (entry_price + exit_price) * qty
        )
        pnl_net = pnl_gross - total_fee

        trades.append(
            TradeResult(
                entry_ts=entry_bar.timestamp_utc,
                entry_price=entry_price,
                exit_ts=exit_bar.timestamp_utc,
                exit_price=exit_price,
                direction=intent.direction,
                qty=qty,
                pnl_gross=pnl_gross,
                pnl_net=pnl_net,
                exit_reason=exit_reason,
                meta={"intent_ts": intent.ts, **intent.meta},
            )
        )

    summary = build_summary(trades)

    return BacktestReport(
        strategy_id=f"{strategy_def.name}:{strategy_def.version}",
        period_start=sorted_bars[0].timestamp_utc if sorted_bars else None,
        period_end=sorted_bars[-1].timestamp_utc if sorted_bars else None,
        summary=summary,
        trades=tuple(trades),
    )
