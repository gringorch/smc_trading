"""Shared event contracts and strategy configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Direction(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    NONE = "none"


class EventKind(str, Enum):
    PIVOT_HIGH = "PIVOT_HIGH"
    PIVOT_LOW = "PIVOT_LOW"
    BOS = "BOS"
    CHOCH = "CHOCH"
    SWEEP_HIGH = "SWEEP_HIGH"
    SWEEP_LOW = "SWEEP_LOW"
    FVG = "FVG"
    IFVG = "IFVG"
    FIB_PREMIUM = "FIB_PREMIUM"
    FIB_DISCOUNT = "FIB_DISCOUNT"


class MarketState(str, Enum):
    NEUTRAL = "NEUTRAL"
    TREND_BULL = "TREND_BULL"
    TREND_BEAR = "TREND_BEAR"
    CORRECTION_BULL = "CORRECTION_BULL"
    CORRECTION_BEAR = "CORRECTION_BEAR"


@dataclass(frozen=True)
class Event:
    kind: EventKind
    direction: Direction = Direction.NONE
    ts: datetime | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    price: float | None = None
    price_low: float | None = None
    price_high: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HTFConfig:
    pivots_L: int = 2
    min_break_atr: dict[str, float] = field(
        default_factory=lambda: {"4h": 0.30, "1h": 0.25, "15m": 0.20}
    )
    min_fvg_atr: dict[str, float] = field(
        default_factory=lambda: {"4h": 0.25, "1h": 0.20, "15m": 0.15}
    )
    discount_threshold: float = 0.5
    poi_merge_distance: float = 0.0
    poi_max_age: dict[str, int] = field(default_factory=lambda: {"4h": 20, "1h": 48, "15m": 96})
    sweep_lookback_pivots: int = 1
    min_sweep_wick_atr: float = 0.10
    max_reclaim_distance_atr: float = 0.05
    confirm_within_bars: int = 1


@dataclass(frozen=True)
class LTFConfig:
    pivots_L: int = 2
    min_break_atr: dict[str, float] = field(
        default_factory=lambda: {"5m": 0.15, "4m": 0.12, "3m": 0.12, "1m": 0.20}
    )
    min_fvg_atr: dict[str, float] = field(
        default_factory=lambda: {"5m": 0.12, "4m": 0.10, "3m": 0.10, "1m": 0.15}
    )
    ifvg_confirm_mode: str = "close"
    ifvg_min_penetration: float = 0.0
    trigger_max_distance_to_poi_atr: dict[str, float] = field(
        default_factory=lambda: {"5m": 0.60, "3m": 0.60, "1m": 0.40}
    )
    require_displacement_body: bool = True
    min_body_atr_1m: float = 0.20


@dataclass(frozen=True)
class StrategyConfig:
    config_htf: HTFConfig = field(default_factory=HTFConfig)
    config_ltf: LTFConfig = field(default_factory=LTFConfig)
