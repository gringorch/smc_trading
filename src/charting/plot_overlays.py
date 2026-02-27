"""Overlay rendering from precomputed strategy events."""

from __future__ import annotations

from datetime import timedelta

import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

from strategy.events import Event, EventKind


def _estimate_bar_delta(df):
    if len(df.index) >= 2:
        return df.index[1] - df.index[0]
    return timedelta(minutes=1)


def apply_overlays(ax, events: list[Event], df, forward_bars: int = 50) -> None:
    delta = _estimate_bar_delta(df)

    for event in events:
        if (
            event.kind in {EventKind.BOS, EventKind.CHOCH}
            and event.price is not None
            and event.ts is not None
        ):
            color = "green" if event.direction.value == "bull" else "red"
            ax.axhline(event.price, color=color, linestyle="--", linewidth=0.8, alpha=0.5)
            ax.text(event.ts, event.price, event.kind.value, color=color, fontsize=8)

        if (
            event.kind == EventKind.FVG
            and event.ts is not None
            and event.price_low is not None
            and event.price_high is not None
        ):
            end_ts = event.end_ts or (event.ts + (delta * forward_bars))
            x = mdates.date2num(event.ts)
            width = mdates.date2num(end_ts) - x
            rect = Rectangle(
                (x, event.price_low),
                width,
                event.price_high - event.price_low,
                facecolor="gold" if event.direction.value == "bull" else "purple",
                edgecolor="none",
                alpha=0.15,
            )
            ax.add_patch(rect)

        if (
            event.kind == EventKind.IFVG
            and event.ts is not None
            and event.price_low is not None
            and event.price_high is not None
        ):
            ax.text(event.ts, event.price_high, "IFVG", color="black", fontsize=8)

        if (
            event.kind in {EventKind.FIB_DISCOUNT, EventKind.FIB_PREMIUM}
            and event.price_low is not None
            and event.price_high is not None
        ):
            color = "#b3ffb3" if event.kind == EventKind.FIB_DISCOUNT else "#ffcccc"
            ax.axhspan(event.price_low, event.price_high, color=color, alpha=0.08)

        if (
            event.kind in {EventKind.SWEEP_HIGH, EventKind.SWEEP_LOW}
            and event.ts is not None
            and event.price is not None
        ):
            ax.scatter([event.ts], [event.price], color="orange", s=20)
            ax.text(event.ts, event.price, event.kind.value, color="orange", fontsize=8)
