"""Structure detectors: pivots, BOS/CHOCH, sweeps."""

from __future__ import annotations

from typing import Any

import pandas as pd

from strategy.events import Direction, Event, EventKind


def _ts_at(df: pd.DataFrame, idx: int):
    if "timestamp_utc" in df.columns:
        return df.iloc[idx]["timestamp_utc"]
    return df.index[idx]


def _atr_at(atr: pd.Series | None, idx: int) -> float:
    if atr is None:
        return 0.0
    val = float(atr.iloc[idx])
    return 0.0 if pd.isna(val) else val


def detect_pivots(df: pd.DataFrame, L: int = 2) -> list[Event]:
    highs = df["high"].astype(float).to_list()
    lows = df["low"].astype(float).to_list()
    events: list[Event] = []

    for i in range(L, len(df) - L):
        left_highs = highs[i - L : i]
        right_highs = highs[i + 1 : i + L + 1]
        left_lows = lows[i - L : i]
        right_lows = lows[i + 1 : i + L + 1]

        confirm_index = i + L
        common_meta: dict[str, Any] = {
            "pivot_index": i,
            "confirm_index": confirm_index,
            "pivot_ts": _ts_at(df, i),
            "pivot_id": f"pivot-{i}",
        }

        if highs[i] > max([*left_highs, *right_highs]):
            events.append(
                Event(
                    kind=EventKind.PIVOT_HIGH,
                    direction=Direction.BEAR,
                    ts=_ts_at(df, confirm_index),
                    price=highs[i],
                    meta=common_meta,
                )
            )

        if lows[i] < min([*left_lows, *right_lows]):
            events.append(
                Event(
                    kind=EventKind.PIVOT_LOW,
                    direction=Direction.BULL,
                    ts=_ts_at(df, confirm_index),
                    price=lows[i],
                    meta=common_meta,
                )
            )

    return events


def detect_bos_choch(
    df: pd.DataFrame,
    pivots: list[Event],
    *,
    atr: pd.Series | None = None,
    min_break_atr: float = 0.0,
) -> list[Event]:
    pivot_highs = sorted(
        [p for p in pivots if p.kind == EventKind.PIVOT_HIGH],
        key=lambda p: int(p.meta["confirm_index"]),
    )
    pivot_lows = sorted(
        [p for p in pivots if p.kind == EventKind.PIVOT_LOW],
        key=lambda p: int(p.meta["confirm_index"]),
    )

    events: list[Event] = []
    trend: Direction | None = None
    broken_pivots: set[str] = set()

    high_ptr = 0
    low_ptr = 0
    last_high: Event | None = None
    last_low: Event | None = None

    closes = df["close"].astype(float).to_list()

    for i in range(len(df)):
        while high_ptr < len(pivot_highs) and int(pivot_highs[high_ptr].meta["confirm_index"]) <= i:
            last_high = pivot_highs[high_ptr]
            high_ptr += 1
        while low_ptr < len(pivot_lows) and int(pivot_lows[low_ptr].meta["confirm_index"]) <= i:
            last_low = pivot_lows[low_ptr]
            low_ptr += 1

        close = closes[i]
        atr_i = _atr_at(atr, i)

        broke_high = False
        broke_low = False

        if last_high is not None:
            level = float(last_high.price)
            threshold = min_break_atr * atr_i
            pivot_id = str(last_high.meta["pivot_id"])
            if pivot_id not in broken_pivots and close > level and abs(close - level) >= threshold:
                broke_high = True
                broken_pivots.add(pivot_id)

        if last_low is not None:
            level = float(last_low.price)
            threshold = min_break_atr * atr_i
            pivot_id = str(last_low.meta["pivot_id"])
            if pivot_id not in broken_pivots and close < level and abs(close - level) >= threshold:
                broke_low = True
                broken_pivots.add(pivot_id)

        if broke_high and last_high is not None:
            kind = EventKind.CHOCH if trend == Direction.BEAR else EventKind.BOS
            events.append(
                Event(
                    kind=kind,
                    direction=Direction.BULL,
                    ts=_ts_at(df, i),
                    price=float(last_high.price),
                    meta={
                        "pivot_id": last_high.meta["pivot_id"],
                        "break_index": i,
                        "prev_trend": trend.value if trend else None,
                    },
                )
            )
            trend = Direction.BULL

        if broke_low and last_low is not None:
            kind = EventKind.CHOCH if trend == Direction.BULL else EventKind.BOS
            events.append(
                Event(
                    kind=kind,
                    direction=Direction.BEAR,
                    ts=_ts_at(df, i),
                    price=float(last_low.price),
                    meta={
                        "pivot_id": last_low.meta["pivot_id"],
                        "break_index": i,
                        "prev_trend": trend.value if trend else None,
                    },
                )
            )
            trend = Direction.BEAR

    return events


def detect_sweeps(
    df: pd.DataFrame,
    pivots: list[Event],
    *,
    atr: pd.Series,
    min_sweep_wick_atr: float = 0.10,
    max_reclaim_distance_atr: float = 0.05,
    confirm_within_bars: int = 1,
) -> list[Event]:
    events: list[Event] = []
    highs = df["high"].astype(float).to_list()
    lows = df["low"].astype(float).to_list()
    closes = df["close"].astype(float).to_list()

    pivot_highs = sorted(
        [p for p in pivots if p.kind == EventKind.PIVOT_HIGH],
        key=lambda p: int(p.meta["confirm_index"]),
    )
    pivot_lows = sorted(
        [p for p in pivots if p.kind == EventKind.PIVOT_LOW],
        key=lambda p: int(p.meta["confirm_index"]),
    )

    last_high: Event | None = None
    last_low: Event | None = None
    high_ptr = 0
    low_ptr = 0

    for i in range(len(df)):
        while high_ptr < len(pivot_highs) and int(pivot_highs[high_ptr].meta["confirm_index"]) <= i:
            last_high = pivot_highs[high_ptr]
            high_ptr += 1
        while low_ptr < len(pivot_lows) and int(pivot_lows[low_ptr].meta["confirm_index"]) <= i:
            last_low = pivot_lows[low_ptr]
            low_ptr += 1

        atr_i = _atr_at(atr, i)
        if atr_i <= 0:
            continue

        if last_high is not None:
            level = float(last_high.price)
            min_wick = min_sweep_wick_atr * atr_i
            reclaim = max_reclaim_distance_atr * atr_i
            if highs[i] > level + min_wick:
                confirmed_index = None
                if closes[i] <= level + reclaim:
                    confirmed_index = i
                elif (
                    confirm_within_bars >= 1
                    and i + 1 < len(df)
                    and closes[i + 1] <= level + reclaim
                ):
                    confirmed_index = i + 1

                if confirmed_index is not None:
                    events.append(
                        Event(
                            kind=EventKind.SWEEP_HIGH,
                            direction=Direction.BEAR,
                            ts=_ts_at(df, confirmed_index),
                            price=level,
                            meta={
                                "pivot_id": last_high.meta["pivot_id"],
                                "confirm_bar_index": confirmed_index,
                                "wick_excess": highs[i] - level,
                                "atr": atr_i,
                            },
                        )
                    )

        if last_low is not None:
            level = float(last_low.price)
            min_wick = min_sweep_wick_atr * atr_i
            reclaim = max_reclaim_distance_atr * atr_i
            if lows[i] < level - min_wick:
                confirmed_index = None
                if closes[i] >= level - reclaim:
                    confirmed_index = i
                elif (
                    confirm_within_bars >= 1
                    and i + 1 < len(df)
                    and closes[i + 1] >= level - reclaim
                ):
                    confirmed_index = i + 1

                if confirmed_index is not None:
                    events.append(
                        Event(
                            kind=EventKind.SWEEP_LOW,
                            direction=Direction.BULL,
                            ts=_ts_at(df, confirmed_index),
                            price=level,
                            meta={
                                "pivot_id": last_low.meta["pivot_id"],
                                "confirm_bar_index": confirmed_index,
                                "wick_excess": level - lows[i],
                                "atr": atr_i,
                            },
                        )
                    )

    return events
