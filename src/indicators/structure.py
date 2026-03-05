"""Market structure detection utilities: swings, BOS, bias and dealing range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from charting.resampler import OhlcvBar

SwingKind = Literal["high", "low"]
BosSide = Literal["bull", "bear"]
Bias = Literal["bull", "bear", "neutral"]


@dataclass(frozen=True, slots=True)
class StructureConfig:
    swing_left: int = 2
    swing_right: int = 2
    allow_unconfirmed_last_swing: bool = True
    bos_buffer: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class SwingPoint:
    kind: SwingKind
    timestamp_utc: datetime
    price: Decimal
    bar_index: int
    left: int
    right: int
    confirmed: bool


@dataclass(frozen=True, slots=True)
class BosEvent:
    side: BosSide
    triggered_at: datetime
    bar_index: int
    broken_swing_index: int
    close: Decimal
    buffer: Decimal


@dataclass(frozen=True, slots=True)
class DealingRange:
    low: Decimal
    high: Decimal
    mid: Decimal
    discount_zone: tuple[Decimal, Decimal]
    premium_zone: tuple[Decimal, Decimal]
    derived_from_bos: int
    low_source: str
    high_source: str


@dataclass(frozen=True, slots=True)
class StructureState:
    current_bias: Bias
    current_bias_since: datetime | None
    current_dealing_range: DealingRange | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class StructureResult:
    swings: list[SwingPoint]
    bos_events: list[BosEvent]
    state: StructureState


def analyze_structure(
    *, bars: list[OhlcvBar], config: StructureConfig | None = None
) -> StructureResult:
    cfg = config or StructureConfig()
    swings = detect_swings(bars=bars, config=cfg)
    bos_events = detect_bos(bars=bars, swings=swings, config=cfg)
    state = derive_structure_state(bars=bars, swings=swings, bos_events=bos_events)
    return StructureResult(swings=swings, bos_events=bos_events, state=state)


def detect_swings(
    *, bars: list[OhlcvBar], config: StructureConfig | None = None
) -> list[SwingPoint]:
    cfg = config or StructureConfig()
    _validate_config(cfg)
    _validate_monotonic_timestamps(bars)

    total = len(bars)
    min_required = cfg.swing_left + cfg.swing_right + 1
    if total < min_required:
        return _append_tentative_last_swing(bars=bars, swings=[], cfg=cfg)

    swings: list[SwingPoint] = []
    confirmed_end = total - cfg.swing_right
    for i in range(cfg.swing_left, confirmed_end):
        if _is_swing_high(bars=bars, idx=i, left=cfg.swing_left, right=cfg.swing_right):
            swings.append(
                SwingPoint(
                    kind="high",
                    timestamp_utc=bars[i].timestamp_utc,
                    price=bars[i].high,
                    bar_index=i,
                    left=cfg.swing_left,
                    right=cfg.swing_right,
                    confirmed=True,
                )
            )
        if _is_swing_low(bars=bars, idx=i, left=cfg.swing_left, right=cfg.swing_right):
            swings.append(
                SwingPoint(
                    kind="low",
                    timestamp_utc=bars[i].timestamp_utc,
                    price=bars[i].low,
                    bar_index=i,
                    left=cfg.swing_left,
                    right=cfg.swing_right,
                    confirmed=True,
                )
            )

    swings.sort(key=lambda s: (s.bar_index, 0 if s.kind == "high" else 1))
    normalized = _normalize_swing_alternation(swings)
    return _append_tentative_last_swing(bars=bars, swings=normalized, cfg=cfg)


def detect_bos(
    *, bars: list[OhlcvBar], swings: list[SwingPoint], config: StructureConfig | None = None
) -> list[BosEvent]:
    cfg = config or StructureConfig()
    _validate_config(cfg)
    _validate_monotonic_timestamps(bars)

    confirmed = [(idx, swing) for idx, swing in enumerate(swings) if swing.confirmed]
    swing_cursor = 0
    last_high: tuple[int, SwingPoint] | None = None
    last_low: tuple[int, SwingPoint] | None = None
    broken_swings: set[int] = set()
    events: list[BosEvent] = []

    for bar_index, bar in enumerate(bars):
        while swing_cursor < len(confirmed) and confirmed[swing_cursor][1].bar_index < bar_index:
            swing_index, swing = confirmed[swing_cursor]
            if swing.kind == "high":
                last_high = (swing_index, swing)
            else:
                last_low = (swing_index, swing)
            swing_cursor += 1

        if last_high is not None and last_high[0] not in broken_swings:
            broken_level = last_high[1].price + cfg.bos_buffer
            if bar.close > broken_level:
                events.append(
                    BosEvent(
                        side="bull",
                        triggered_at=bar.timestamp_utc,
                        bar_index=bar_index,
                        broken_swing_index=last_high[0],
                        close=bar.close,
                        buffer=cfg.bos_buffer,
                    )
                )
                broken_swings.add(last_high[0])
                continue

        if last_low is not None and last_low[0] not in broken_swings:
            broken_level = last_low[1].price - cfg.bos_buffer
            if bar.close < broken_level:
                events.append(
                    BosEvent(
                        side="bear",
                        triggered_at=bar.timestamp_utc,
                        bar_index=bar_index,
                        broken_swing_index=last_low[0],
                        close=bar.close,
                        buffer=cfg.bos_buffer,
                    )
                )
                broken_swings.add(last_low[0])

    return events


def derive_structure_state(
    *, bars: list[OhlcvBar], swings: list[SwingPoint], bos_events: list[BosEvent]
) -> StructureState:
    if not bos_events:
        return StructureState(
            current_bias="neutral",
            current_bias_since=None,
            current_dealing_range=None,
            reason="no_bos_events",
        )

    if not bars:
        return StructureState(
            current_bias="neutral",
            current_bias_since=None,
            current_dealing_range=None,
            reason="no_bars",
        )

    last_bos_idx = len(bos_events) - 1
    last_bos = bos_events[last_bos_idx]
    bias: Bias = last_bos.side
    dealing_range = _derive_dealing_range(
        bars=bars, swings=swings, bos=last_bos, bos_index=last_bos_idx
    )

    reason = None if dealing_range is not None else "insufficient_swings_for_dealing_range"
    return StructureState(
        current_bias=bias,
        current_bias_since=last_bos.triggered_at,
        current_dealing_range=dealing_range,
        reason=reason,
    )


def _derive_dealing_range(
    *, bars: list[OhlcvBar], swings: list[SwingPoint], bos: BosEvent, bos_index: int
) -> DealingRange | None:
    if bos.bar_index >= len(bars):
        return None

    latest_low = _find_latest_confirmed_swing(swings=swings, target_kind="low")
    latest_high = _find_latest_confirmed_swing(swings=swings, target_kind="high")
    if latest_low is None or latest_high is None:
        return None

    low = latest_low.price
    high = latest_high.price
    low_source = "last_confirmed_swing_low"
    high_source = "last_confirmed_swing_high"

    if high <= low:
        return None

    mid = (low + high) / Decimal("2")
    return DealingRange(
        low=low,
        high=high,
        mid=mid,
        discount_zone=(low, mid),
        premium_zone=(mid, high),
        derived_from_bos=bos_index,
        low_source=low_source,
        high_source=high_source,
    )


def _find_latest_confirmed_swing(
    *, swings: list[SwingPoint], target_kind: SwingKind
) -> SwingPoint | None:
    for swing in reversed(swings):
        if swing.confirmed and swing.kind == target_kind:
            return swing
    return None


def _append_tentative_last_swing(
    *, bars: list[OhlcvBar], swings: list[SwingPoint], cfg: StructureConfig
) -> list[SwingPoint]:
    if not cfg.allow_unconfirmed_last_swing or not bars:
        return swings

    existing_indices = {s.bar_index for s in swings}
    total = len(bars)
    start = max(cfg.swing_left, total - cfg.swing_right)
    if start >= total:
        return swings

    for i in range(total - 1, start - 1, -1):
        if i in existing_indices:
            continue
        right_available = total - i - 1
        if right_available >= cfg.swing_right:
            continue

        tentative_high = _is_swing_high(
            bars=bars, idx=i, left=cfg.swing_left, right=right_available
        )
        tentative_low = _is_swing_low(
            bars=bars, idx=i, left=cfg.swing_left, right=right_available
        )
        if tentative_high:
            swings.append(
                SwingPoint(
                    kind="high",
                    timestamp_utc=bars[i].timestamp_utc,
                    price=bars[i].high,
                    bar_index=i,
                    left=cfg.swing_left,
                    right=cfg.swing_right,
                    confirmed=False,
                )
            )
            break
        if tentative_low:
            swings.append(
                SwingPoint(
                    kind="low",
                    timestamp_utc=bars[i].timestamp_utc,
                    price=bars[i].low,
                    bar_index=i,
                    left=cfg.swing_left,
                    right=cfg.swing_right,
                    confirmed=False,
                )
            )
            break

    swings.sort(key=lambda s: (s.bar_index, 0 if s.kind == "high" else 1))
    return _normalize_swing_alternation(swings)


def _normalize_swing_alternation(swings: list[SwingPoint]) -> list[SwingPoint]:
    if not swings:
        return swings

    normalized: list[SwingPoint] = [swings[0]]
    for current in swings[1:]:
        last = normalized[-1]
        if current.kind != last.kind:
            normalized.append(current)
            continue

        # Keep only the most extreme pivot when two same-kind swings are consecutive.
        if current.kind == "high":
            should_replace = (current.price > last.price) or (
                current.price == last.price and current.bar_index > last.bar_index
            )
        else:
            should_replace = (current.price < last.price) or (
                current.price == last.price and current.bar_index > last.bar_index
            )
        if should_replace:
            normalized[-1] = current

    return normalized


def _is_swing_high(*, bars: list[OhlcvBar], idx: int, left: int, right: int) -> bool:
    ref = bars[idx].high
    left_slice = [bars[j].high for j in range(idx - left, idx)]
    right_slice = [bars[j].high for j in range(idx + 1, idx + right + 1)]
    return all(ref > val for val in left_slice) and all(ref > val for val in right_slice)


def _is_swing_low(*, bars: list[OhlcvBar], idx: int, left: int, right: int) -> bool:
    ref = bars[idx].low
    left_slice = [bars[j].low for j in range(idx - left, idx)]
    right_slice = [bars[j].low for j in range(idx + 1, idx + right + 1)]
    return all(ref < val for val in left_slice) and all(ref < val for val in right_slice)


def _validate_config(cfg: StructureConfig) -> None:
    if cfg.swing_left < 1:
        raise ValueError("swing_left must be >= 1")
    if cfg.swing_right < 1:
        raise ValueError("swing_right must be >= 1")
    if cfg.bos_buffer < 0:
        raise ValueError("bos_buffer must be >= 0")


def _validate_monotonic_timestamps(bars: list[OhlcvBar]) -> None:
    if not bars:
        return
    prev = bars[0].timestamp_utc
    for bar in bars[1:]:
        if bar.timestamp_utc <= prev:
            raise ValueError("bars must be strictly increasing by timestamp_utc")
        prev = bar.timestamp_utc
