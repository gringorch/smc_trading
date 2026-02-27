from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from strategy.context import build_fib_context, compute_market_state_1h
from strategy.events import Direction, Event, EventKind, MarketState
from strategy.structure import detect_pivots


def _df(close: list[float]) -> pd.DataFrame:
    start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    rows = []
    for i, c in enumerate(close):
        rows.append(
            {
                "timestamp_utc": start + timedelta(minutes=i),
                "open": c,
                "high": c + 0.4,
                "low": c - 0.4,
                "close": c,
                "volume": 1.0,
            }
        )
    return pd.DataFrame(rows).set_index("timestamp_utc", drop=False)


def test_build_fib_context_returns_premium_discount() -> None:
    df = _df([1, 2, 5, 2, 1.5, 2.5, 2.2])
    pivots = detect_pivots(df, L=1)

    events = build_fib_context(df, pivots)

    kinds = {e.kind for e in events}
    assert EventKind.FIB_PREMIUM in kinds
    assert EventKind.FIB_DISCOUNT in kinds


def test_compute_market_state_transitions() -> None:
    events = [
        Event(kind=EventKind.BOS, direction=Direction.BULL),
        Event(kind=EventKind.BOS, direction=Direction.BULL),
        Event(kind=EventKind.CHOCH, direction=Direction.BEAR),
    ]

    assert compute_market_state_1h(events) == MarketState.TREND_BEAR
    assert (
        compute_market_state_1h(
            [Event(kind=EventKind.BOS, direction=Direction.BULL)], fib_retrace=0.6
        )
        == MarketState.CORRECTION_BULL
    )
