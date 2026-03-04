"""Fair Value Gap (FVG) detection utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from charting.resampler import OhlcvBar

FvgDirection = Literal["bull", "bear"]
FvgDirectionFilter = Literal["bull", "bear", "both"]
FvgMitigationRule = Literal["wick", "close"]


@dataclass(frozen=True, slots=True)
class FvgMitigation:
    mitigated: bool
    mitigated_at: datetime | None


@dataclass(frozen=True, slots=True)
class FvgSignal:
    direction: FvgDirection
    formed_at: datetime
    gap_low: Decimal
    gap_high: Decimal
    gap_size: Decimal
    index_start: int
    index_end: int
    mitigation: FvgMitigation


@dataclass(frozen=True, slots=True)
class FvgConfig:
    direction: FvgDirectionFilter = "both"
    min_gap_size: Decimal = Decimal("0")
    mitigation_enabled: bool = True
    mitigation_rule: FvgMitigationRule = "wick"


def detect_fvgs(*, bars: list[OhlcvBar], config: FvgConfig | None = None) -> list[FvgSignal]:
    """Detect 3-candle FVGs on the provided bars.

    Definitions:
    - Bullish FVG: high[i] < low[i+2] => gap is (high[i], low[i+2])
    - Bearish FVG: low[i] > high[i+2] => gap is (high[i+2], low[i])
    """
    if config is None:
        config = FvgConfig()

    if config.direction not in ("bull", "bear", "both"):
        raise ValueError("invalid direction filter")
    if config.mitigation_rule not in ("wick", "close"):
        raise ValueError("invalid mitigation rule")
    if config.min_gap_size < 0:
        raise ValueError("min_gap_size must be >= 0")

    _validate_monotonic_timestamps(bars)

    signals: list[FvgSignal] = []
    for i in range(0, max(0, len(bars) - 2)):
        left = bars[i]
        right = bars[i + 2]

        bull_gap_low = left.high
        bull_gap_high = right.low
        if bull_gap_low < bull_gap_high:
            gap_size = bull_gap_high - bull_gap_low
            if gap_size >= config.min_gap_size and config.direction in ("bull", "both"):
                mitigation = _compute_mitigation(
                    direction="bull",
                    bars=bars,
                    index_end=i + 2,
                    gap_low=bull_gap_low,
                    gap_high=bull_gap_high,
                    enabled=config.mitigation_enabled,
                    rule=config.mitigation_rule,
                )
                signals.append(
                    FvgSignal(
                        direction="bull",
                        formed_at=right.timestamp_utc,
                        gap_low=bull_gap_low,
                        gap_high=bull_gap_high,
                        gap_size=gap_size,
                        index_start=i,
                        index_end=i + 2,
                        mitigation=mitigation,
                    )
                )

        bear_gap_low = right.high
        bear_gap_high = left.low
        if bear_gap_low < bear_gap_high:
            gap_size = bear_gap_high - bear_gap_low
            if gap_size >= config.min_gap_size and config.direction in ("bear", "both"):
                mitigation = _compute_mitigation(
                    direction="bear",
                    bars=bars,
                    index_end=i + 2,
                    gap_low=bear_gap_low,
                    gap_high=bear_gap_high,
                    enabled=config.mitigation_enabled,
                    rule=config.mitigation_rule,
                )
                signals.append(
                    FvgSignal(
                        direction="bear",
                        formed_at=right.timestamp_utc,
                        gap_low=bear_gap_low,
                        gap_high=bear_gap_high,
                        gap_size=gap_size,
                        index_start=i,
                        index_end=i + 2,
                        mitigation=mitigation,
                    )
                )

    return signals


def _validate_monotonic_timestamps(bars: list[OhlcvBar]) -> None:
    if not bars:
        return
    prev = bars[0].timestamp_utc
    for bar in bars[1:]:
        if bar.timestamp_utc <= prev:
            raise ValueError("bars must be strictly increasing by timestamp_utc")
        prev = bar.timestamp_utc


def _compute_mitigation(
    *,
    direction: FvgDirection,
    bars: list[OhlcvBar],
    index_end: int,
    gap_low: Decimal,
    gap_high: Decimal,
    enabled: bool,
    rule: FvgMitigationRule,
) -> FvgMitigation:
    if not enabled:
        return FvgMitigation(mitigated=False, mitigated_at=None)

    # Start scanning AFTER formation candle (i+2), otherwise it would "mitigate" immediately by construction.
    for bar in bars[index_end + 1 :]:
        if _is_mitigated(direction=direction, bar=bar, gap_low=gap_low, gap_high=gap_high, rule=rule):
            return FvgMitigation(mitigated=True, mitigated_at=bar.timestamp_utc)
    return FvgMitigation(mitigated=False, mitigated_at=None)


def _is_mitigated(
    *,
    direction: FvgDirection,
    bar: OhlcvBar,
    gap_low: Decimal,
    gap_high: Decimal,
    rule: FvgMitigationRule,
) -> bool:
    # "Mitigated" here means price enters the gap zone.
    # - Bull gap sits BELOW current price; mitigation typically happens when price trades down into it.
    # - Bear gap sits ABOVE current price; mitigation typically happens when price trades up into it.
    if rule == "wick":
        if direction == "bull":
            return bar.low <= gap_high
        return bar.high >= gap_low

    if direction == "bull":
        return bar.close <= gap_high
    return bar.close >= gap_low

