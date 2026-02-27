"""Context detectors: fibonacci zones and 1H market state."""

from __future__ import annotations

import pandas as pd

from strategy.events import Direction, Event, EventKind, MarketState


def build_fib_context(
    df: pd.DataFrame,
    pivots: list[Event],
    *,
    discount_threshold: float = 0.5,
) -> list[Event]:
    if not pivots or len(df) == 0:
        return []

    price_now = float(df["close"].iloc[-1])
    highs = [p for p in pivots if p.kind == EventKind.PIVOT_HIGH]
    lows = [p for p in pivots if p.kind == EventKind.PIVOT_LOW]
    highs = sorted(highs, key=lambda p: int(p.meta["confirm_index"]))
    lows = sorted(lows, key=lambda p: int(p.meta["confirm_index"]))

    selected_high = None
    selected_low = None

    for high in reversed(highs):
        for low in reversed(lows):
            if low.meta["confirm_index"] == high.meta["confirm_index"]:
                continue
            if float(low.price) <= price_now <= float(high.price):
                selected_high = high
                selected_low = low
                break
        if selected_high is not None:
            break

    if selected_high is None or selected_low is None:
        if not highs or not lows:
            return []
        selected_high = highs[-1]
        selected_low = lows[-1]

    low_price = float(selected_low.price)
    high_price = float(selected_high.price)
    if high_price <= low_price:
        return []

    is_bull_range = int(selected_low.meta["confirm_index"]) < int(
        selected_high.meta["confirm_index"]
    )
    midpoint = low_price + (high_price - low_price) * discount_threshold

    if is_bull_range:
        premium_low, premium_high = low_price, midpoint
        discount_low, discount_high = midpoint, high_price
    else:
        premium_low, premium_high = midpoint, high_price
        discount_low, discount_high = low_price, midpoint

    common_meta = {
        "range_low": low_price,
        "range_high": high_price,
        "threshold": discount_threshold,
        "is_bull_range": is_bull_range,
    }

    ts_now = df.iloc[-1]["timestamp_utc"] if "timestamp_utc" in df.columns else df.index[-1]
    return [
        Event(
            kind=EventKind.FIB_PREMIUM,
            direction=Direction.BEAR if is_bull_range else Direction.BULL,
            ts=ts_now,
            price_low=premium_low,
            price_high=premium_high,
            meta=common_meta,
        ),
        Event(
            kind=EventKind.FIB_DISCOUNT,
            direction=Direction.BULL if is_bull_range else Direction.BEAR,
            ts=ts_now,
            price_low=discount_low,
            price_high=discount_high,
            meta=common_meta,
        ),
    ]


def compute_market_state_1h(
    events_1h: list[Event], fib_retrace: float | None = None
) -> MarketState:
    state = MarketState.NEUTRAL

    for event in events_1h:
        if event.kind == EventKind.BOS and event.direction == Direction.BULL:
            if state in {MarketState.NEUTRAL, MarketState.TREND_BULL, MarketState.CORRECTION_BULL}:
                state = MarketState.TREND_BULL
        elif event.kind == EventKind.BOS and event.direction == Direction.BEAR:
            if state in {MarketState.NEUTRAL, MarketState.TREND_BEAR, MarketState.CORRECTION_BEAR}:
                state = MarketState.TREND_BEAR
        elif event.kind == EventKind.CHOCH and event.direction == Direction.BULL:
            state = MarketState.TREND_BULL
        elif event.kind == EventKind.CHOCH and event.direction == Direction.BEAR:
            state = MarketState.TREND_BEAR

    if fib_retrace is None:
        return state

    if state == MarketState.TREND_BULL and fib_retrace >= 0.5:
        return MarketState.CORRECTION_BULL
    if state == MarketState.TREND_BEAR and fib_retrace <= 0.5:
        return MarketState.CORRECTION_BEAR
    return state
