"""Inverse FVG (IFVG) detection utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from charting.resampler import OhlcvBar
from indicators.fvg import FvgConfig, FvgSignal, detect_fvgs

IfvgSide = Literal["buy", "sell"]
DisplacementRule = Literal["body_atr", "body_pct_range"]
EntryModel = Literal["market_on_close", "limit_retest"]
RetestLevel = Literal["gap_mid", "gap_near_edge", "gap_far_edge"]
StopModel = Literal["beyond_sweep_extreme", "beyond_gap_edge"]
TpModel = Literal["rr"]
HtfBias = Literal["bull", "bear"]


@dataclass(frozen=True, slots=True)
class IfvgPoi:
    low: Decimal
    high: Decimal


@dataclass(frozen=True, slots=True)
class IfvgSignal:
    side: IfvgSide
    triggered_at: datetime
    symbol: str | None
    ltf_timeframe: str | None
    htf_timeframe: str | None
    poi: IfvgPoi | None
    origin_fvg: FvgSignal
    reason: list[str]
    entry: Decimal
    stop: Decimal
    tp: Decimal


@dataclass(frozen=True, slots=True)
class IfvgConfig:
    min_gap_size: Decimal = Decimal("0.00005")
    max_bars_from_fvg_formation_to_inversion: int = 5
    inversion_fill_pct: Decimal = Decimal("1.0")
    inversion_buffer: Decimal = Decimal("0")
    displacement_rule: DisplacementRule = "body_pct_range"
    displacement_body_atr_mult: Decimal = Decimal("1.0")
    displacement_min_body_pct: Decimal = Decimal("0.7")
    atr_period: int = 14
    sweep_required: bool = False
    sweep_lookback_bars: int = 10
    max_bars_between_sweep_and_inversion: int = 1
    bias_required: bool = False
    poi_required: bool = False
    poi_low: Decimal | None = None
    poi_high: Decimal | None = None
    entry_model: EntryModel = "market_on_close"
    limit_retest_level: RetestLevel = "gap_mid"
    stop_model: StopModel = "beyond_gap_edge"
    sl_buffer: Decimal = Decimal("0")
    tp_model: TpModel = "rr"
    rr: Decimal = Decimal("2")
    one_signal_per_origin_fvg: bool = True
    cooldown_bars: int = 0


def detect_ifvgs(
    *,
    bars: list[OhlcvBar],
    config: IfvgConfig | None = None,
    symbol: str | None = None,
    ltf_timeframe: str | None = None,
    htf_timeframe: str | None = None,
    htf_bias: HtfBias | None = None,
) -> list[IfvgSignal]:
    """Detect IFVG inversion events and return trade-ready signals."""
    cfg = config or IfvgConfig()
    _validate_config(cfg)

    fvgs = detect_fvgs(
        bars=bars,
        config=FvgConfig(
            direction="both",
            min_gap_size=cfg.min_gap_size,
            mitigation_enabled=False,
        ),
    )
    if not fvgs:
        return []

    atr_values = _compute_sma_atr(bars=bars, period=cfg.atr_period)
    signals: list[IfvgSignal] = []
    emitted_origin_keys: set[tuple[int, int, str]] = set()
    last_signal_idx: int | None = None

    for fvg in fvgs:
        origin_key = (fvg.index_start, fvg.index_end, fvg.direction)
        if cfg.one_signal_per_origin_fvg and origin_key in emitted_origin_keys:
            continue

        side: IfvgSide = "sell" if fvg.direction == "bull" else "buy"
        if not _passes_bias(side=side, htf_bias=htf_bias, required=cfg.bias_required):
            continue

        poi = _active_poi_if_any(cfg)
        if cfg.poi_required and poi is None:
            continue

        first_idx = fvg.index_end + 1
        last_idx = min(len(bars) - 1, fvg.index_end + cfg.max_bars_from_fvg_formation_to_inversion)

        for idx in range(first_idx, last_idx + 1):
            bar = bars[idx]
            if (
                cfg.cooldown_bars > 0
                and last_signal_idx is not None
                and (idx - last_signal_idx) <= cfg.cooldown_bars
            ):
                continue

            if not _is_inversion_close(fvg=fvg, bar=bar, cfg=cfg):
                continue
            if not _passes_displacement(idx=idx, bar=bar, bars=bars, atr_values=atr_values, cfg=cfg):
                continue

            sweep_idx = _latest_sweep_index(
                bars=bars,
                inversion_idx=idx,
                side=side,
                lookback=cfg.sweep_lookback_bars,
                max_distance=cfg.max_bars_between_sweep_and_inversion,
            )
            if cfg.sweep_required and sweep_idx is None:
                continue

            entry = _compute_entry(side=side, fvg=fvg, inversion_bar=bar, cfg=cfg)
            stop = _compute_stop(
                side=side,
                fvg=fvg,
                bars=bars,
                sweep_idx=sweep_idx,
                inversion_idx=idx,
                cfg=cfg,
            )
            tp = _compute_tp(side=side, entry=entry, stop=stop, cfg=cfg)

            reasons = ["inversion_close", "displacement_ok"]
            if sweep_idx is not None:
                reasons.append("sweep_ok")
            if cfg.poi_required:
                reasons.append("poi_ok")
            if cfg.bias_required:
                reasons.append("bias_ok")

            signals.append(
                IfvgSignal(
                    side=side,
                    triggered_at=bar.timestamp_utc,
                    symbol=symbol,
                    ltf_timeframe=ltf_timeframe,
                    htf_timeframe=htf_timeframe,
                    poi=poi,
                    origin_fvg=fvg,
                    reason=reasons,
                    entry=entry,
                    stop=stop,
                    tp=tp,
                )
            )

            last_signal_idx = idx
            if cfg.one_signal_per_origin_fvg:
                emitted_origin_keys.add(origin_key)
                break

    return signals


def _validate_config(cfg: IfvgConfig) -> None:
    if cfg.min_gap_size < 0:
        raise ValueError("min_gap_size must be >= 0")
    if cfg.max_bars_from_fvg_formation_to_inversion < 1:
        raise ValueError("max_bars_from_fvg_formation_to_inversion must be >= 1")
    if not (Decimal("0.1") <= cfg.inversion_fill_pct <= Decimal("1.0")):
        raise ValueError("inversion_fill_pct must be in [0.1, 1.0]")
    if cfg.inversion_buffer < 0:
        raise ValueError("inversion_buffer must be >= 0")
    if cfg.displacement_rule not in ("body_atr", "body_pct_range"):
        raise ValueError("invalid displacement_rule")
    if cfg.displacement_body_atr_mult <= 0:
        raise ValueError("displacement_body_atr_mult must be > 0")
    if not (Decimal("0") <= cfg.displacement_min_body_pct <= Decimal("1")):
        raise ValueError("displacement_min_body_pct must be in [0, 1]")
    if cfg.atr_period < 1:
        raise ValueError("atr_period must be >= 1")
    if cfg.sweep_lookback_bars < 1:
        raise ValueError("sweep_lookback_bars must be >= 1")
    if cfg.max_bars_between_sweep_and_inversion < 1:
        raise ValueError("max_bars_between_sweep_and_inversion must be >= 1")
    if cfg.poi_required and (cfg.poi_low is None or cfg.poi_high is None):
        raise ValueError("poi_required=true requires poi_low and poi_high")
    if cfg.poi_low is not None and cfg.poi_high is not None and cfg.poi_low >= cfg.poi_high:
        raise ValueError("poi_low must be < poi_high")
    if cfg.entry_model not in ("market_on_close", "limit_retest"):
        raise ValueError("invalid entry_model")
    if cfg.limit_retest_level not in ("gap_mid", "gap_near_edge", "gap_far_edge"):
        raise ValueError("invalid limit_retest_level")
    if cfg.stop_model not in ("beyond_sweep_extreme", "beyond_gap_edge"):
        raise ValueError("invalid stop_model")
    if cfg.sl_buffer < 0:
        raise ValueError("sl_buffer must be >= 0")
    if cfg.tp_model != "rr":
        raise ValueError("invalid tp_model")
    if cfg.rr <= 0:
        raise ValueError("rr must be > 0")
    if cfg.cooldown_bars < 0:
        raise ValueError("cooldown_bars must be >= 0")


def _active_poi_if_any(cfg: IfvgConfig) -> IfvgPoi | None:
    if cfg.poi_low is None or cfg.poi_high is None:
        return None
    return IfvgPoi(low=cfg.poi_low, high=cfg.poi_high)


def _passes_bias(*, side: IfvgSide, htf_bias: HtfBias | None, required: bool) -> bool:
    if not required:
        return True
    if htf_bias is None:
        return False
    if htf_bias == "bull":
        return side == "buy"
    return side == "sell"


def _is_inversion_close(*, fvg: FvgSignal, bar: OhlcvBar, cfg: IfvgConfig) -> bool:
    gap_size = fvg.gap_high - fvg.gap_low
    if gap_size <= 0:
        return False

    close = bar.close
    if fvg.direction == "bull":
        fill = _bull_fill(close=close, gap_low=fvg.gap_low, gap_high=fvg.gap_high)
        threshold = fvg.gap_high - (cfg.inversion_fill_pct * gap_size) - cfg.inversion_buffer
        return fill >= cfg.inversion_fill_pct and close <= threshold

    fill = _bear_fill(close=close, gap_low=fvg.gap_low, gap_high=fvg.gap_high)
    threshold = fvg.gap_low + (cfg.inversion_fill_pct * gap_size) + cfg.inversion_buffer
    return fill >= cfg.inversion_fill_pct and close >= threshold


def _bull_fill(*, close: Decimal, gap_low: Decimal, gap_high: Decimal) -> Decimal:
    if close < gap_low:
        return Decimal("1")
    if gap_low <= close <= gap_high:
        return (gap_high - close) / (gap_high - gap_low)
    return Decimal("0")


def _bear_fill(*, close: Decimal, gap_low: Decimal, gap_high: Decimal) -> Decimal:
    if close > gap_high:
        return Decimal("1")
    if gap_low <= close <= gap_high:
        return (close - gap_low) / (gap_high - gap_low)
    return Decimal("0")


def _passes_displacement(
    *,
    idx: int,
    bar: OhlcvBar,
    bars: list[OhlcvBar],
    atr_values: list[Decimal | None],
    cfg: IfvgConfig,
) -> bool:
    body = abs(bar.close - bar.open)
    if cfg.displacement_rule == "body_pct_range":
        bar_range = bar.high - bar.low
        if bar_range <= 0:
            return False
        return (body / bar_range) >= cfg.displacement_min_body_pct

    atr = atr_values[idx]
    if atr is None:
        return False
    return body >= (cfg.displacement_body_atr_mult * atr)


def _compute_sma_atr(*, bars: list[OhlcvBar], period: int) -> list[Decimal | None]:
    if not bars:
        return []
    true_ranges: list[Decimal] = []
    prev_close: Decimal | None = None
    for bar in bars:
        if prev_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        true_ranges.append(tr)
        prev_close = bar.close

    atr_values: list[Decimal | None] = [None] * len(bars)
    rolling_sum = Decimal("0")
    for i, tr in enumerate(true_ranges):
        rolling_sum += tr
        if i >= period:
            rolling_sum -= true_ranges[i - period]
        if i >= period - 1:
            atr_values[i] = rolling_sum / Decimal(period)
    return atr_values


def _latest_sweep_index(
    *,
    bars: list[OhlcvBar],
    inversion_idx: int,
    side: IfvgSide,
    lookback: int,
    max_distance: int,
) -> int | None:
    first_idx = max(lookback, inversion_idx - max_distance)
    for idx in range(inversion_idx - 1, first_idx - 1, -1):
        if _is_sweep_bar(bars=bars, idx=idx, side=side, lookback=lookback):
            return idx
    return None


def _is_sweep_bar(*, bars: list[OhlcvBar], idx: int, side: IfvgSide, lookback: int) -> bool:
    if idx < lookback:
        return False

    window = bars[idx - lookback : idx]
    bar = bars[idx]
    highs = [b.high for b in window]
    lows = [b.low for b in window]

    if side == "sell":
        ref_high = max(highs)
        return bar.high > ref_high and bar.close <= ref_high

    ref_low = min(lows)
    return bar.low < ref_low and bar.close >= ref_low


def _compute_entry(*, side: IfvgSide, fvg: FvgSignal, inversion_bar: OhlcvBar, cfg: IfvgConfig) -> Decimal:
    if cfg.entry_model == "market_on_close":
        return inversion_bar.close

    mid = (fvg.gap_low + fvg.gap_high) / Decimal("2")
    if cfg.limit_retest_level == "gap_mid":
        return mid
    if cfg.limit_retest_level == "gap_near_edge":
        return fvg.gap_high if side == "sell" else fvg.gap_low
    return fvg.gap_low if side == "sell" else fvg.gap_high


def _compute_stop(
    *,
    side: IfvgSide,
    fvg: FvgSignal,
    bars: list[OhlcvBar],
    sweep_idx: int | None,
    inversion_idx: int,
    cfg: IfvgConfig,
) -> Decimal:
    if cfg.stop_model == "beyond_sweep_extreme":
        ref_bar = bars[sweep_idx] if sweep_idx is not None else bars[inversion_idx]
        if side == "sell":
            return ref_bar.high + cfg.sl_buffer
        return ref_bar.low - cfg.sl_buffer

    if side == "sell":
        return fvg.gap_high + cfg.sl_buffer
    return fvg.gap_low - cfg.sl_buffer


def _compute_tp(*, side: IfvgSide, entry: Decimal, stop: Decimal, cfg: IfvgConfig) -> Decimal:
    risk = abs(entry - stop)
    if side == "buy":
        return entry + (cfg.rr * risk)
    return entry - (cfg.rr * risk)
