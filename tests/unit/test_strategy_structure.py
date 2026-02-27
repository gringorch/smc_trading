from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from strategy.events import Direction, EventKind
from strategy.structure import detect_bos_choch, detect_pivots, detect_sweeps


def _df_from_close(close: list[float]) -> pd.DataFrame:
    rows = []
    start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    for i, c in enumerate(close):
        rows.append(
            {
                "timestamp_utc": start + timedelta(minutes=i),
                "open": c,
                "high": c + 0.6,
                "low": c - 0.6,
                "close": c,
                "volume": 1.0,
            }
        )
    return pd.DataFrame(rows).set_index("timestamp_utc", drop=False)


def test_pivots_are_confirmed_after_l_bars_non_repaint() -> None:
    df = _df_from_close([1, 2, 5, 2, 1, 2, 0.5, 2, 3])
    pivots = detect_pivots(df, L=2)

    high = next(e for e in pivots if e.kind == EventKind.PIVOT_HIGH)
    low = next(e for e in pivots if e.kind == EventKind.PIVOT_LOW)

    assert high.meta["pivot_index"] == 2
    assert high.meta["confirm_index"] == 4
    assert low.meta["pivot_index"] == 6
    assert low.meta["confirm_index"] == 8


def test_bos_and_choch_use_close_breaks() -> None:
    df = _df_from_close([1.0, 2.0, 4.0, 2.0, 1.0, 2.2, 1.2, 2.5, 0.8, 2.0, 4.5, 0.6])
    pivots = detect_pivots(df, L=1)
    atr = pd.Series([1.0] * len(df), index=df.index)

    events = detect_bos_choch(df, pivots, atr=atr, min_break_atr=0.0)

    assert any(e.kind == EventKind.BOS and e.direction == Direction.BULL for e in events)
    assert any(e.kind == EventKind.CHOCH and e.direction == Direction.BEAR for e in events)


def test_sweep_high_requires_reclaim() -> None:
    df = _df_from_close([1.0, 2.0, 5.0, 2.0, 1.5, 3.0, 1.8, 2.1])
    # force a wick sweep over pivot high candle at index 2
    df.iloc[5, df.columns.get_loc("high")] = 5.3
    df.iloc[5, df.columns.get_loc("close")] = 5.2
    df.iloc[6, df.columns.get_loc("close")] = 4.9

    pivots = detect_pivots(df, L=1)
    atr = pd.Series([1.0] * len(df), index=df.index)

    sweeps = detect_sweeps(df, pivots, atr=atr)

    assert any(e.kind == EventKind.SWEEP_HIGH and e.direction == Direction.BEAR for e in sweeps)
