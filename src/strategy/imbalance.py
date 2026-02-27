"""Imbalance detectors: FVG and IFVG."""

from __future__ import annotations

import pandas as pd

from strategy.events import Direction, Event, EventKind


def _ts_at(df: pd.DataFrame, idx: int):
    if "timestamp_utc" in df.columns:
        return df.iloc[idx]["timestamp_utc"]
    return df.index[idx]


def detect_fvg(
    df: pd.DataFrame, *, atr: pd.Series | None = None, min_fvg_atr: float = 0.0
) -> list[Event]:
    highs = df["high"].astype(float).to_list()
    lows = df["low"].astype(float).to_list()
    events: list[Event] = []

    for i in range(2, len(df)):
        atr_i = 0.0 if atr is None or pd.isna(atr.iloc[i]) else float(atr.iloc[i])

        if highs[i - 2] < lows[i]:
            zone_low = highs[i - 2]
            zone_high = lows[i]
            if (zone_high - zone_low) >= (min_fvg_atr * atr_i):
                events.append(
                    Event(
                        kind=EventKind.FVG,
                        direction=Direction.BULL,
                        ts=_ts_at(df, i),
                        start_ts=_ts_at(df, i - 2),
                        price_low=zone_low,
                        price_high=zone_high,
                        meta={"event_index": i, "start_index": i - 2},
                    )
                )

        if lows[i - 2] > highs[i]:
            zone_low = highs[i]
            zone_high = lows[i - 2]
            if (zone_high - zone_low) >= (min_fvg_atr * atr_i):
                events.append(
                    Event(
                        kind=EventKind.FVG,
                        direction=Direction.BEAR,
                        ts=_ts_at(df, i),
                        start_ts=_ts_at(df, i - 2),
                        price_low=zone_low,
                        price_high=zone_high,
                        meta={"event_index": i, "start_index": i - 2},
                    )
                )

    return events


def detect_ifvg(
    df: pd.DataFrame, fvg_events: list[Event], *, confirm_mode: str = "close"
) -> list[Event]:
    if confirm_mode != "close":
        raise ValueError("only confirm_mode='close' is supported")

    closes = df["close"].astype(float).to_list()
    events: list[Event] = []

    for fvg in fvg_events:
        start_index = int(fvg.meta.get("event_index", -1)) + 1
        if start_index <= 0:
            continue

        for i in range(start_index, len(df)):
            close = closes[i]
            if fvg.direction == Direction.BULL and close < float(fvg.price_low):
                events.append(
                    Event(
                        kind=EventKind.IFVG,
                        direction=Direction.BEAR,
                        ts=_ts_at(df, i),
                        price_low=fvg.price_low,
                        price_high=fvg.price_high,
                        meta={
                            "source_fvg_ts": fvg.ts,
                            "source_fvg_index": fvg.meta.get("event_index"),
                        },
                    )
                )
                break

            if fvg.direction == Direction.BEAR and close > float(fvg.price_high):
                events.append(
                    Event(
                        kind=EventKind.IFVG,
                        direction=Direction.BULL,
                        ts=_ts_at(df, i),
                        price_low=fvg.price_low,
                        price_high=fvg.price_high,
                        meta={
                            "source_fvg_ts": fvg.ts,
                            "source_fvg_index": fvg.meta.get("event_index"),
                        },
                    )
                )
                break

    return events
