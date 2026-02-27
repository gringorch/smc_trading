from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from strategy.events import Direction, EventKind
from strategy.imbalance import detect_fvg, detect_ifvg


def _df(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    payload = []
    for i, (open_, high, low, close) in enumerate(rows):
        payload.append(
            {
                "timestamp_utc": start + timedelta(minutes=i),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1.0,
            }
        )
    return pd.DataFrame(payload).set_index("timestamp_utc", drop=False)


def test_detect_fvg_three_candle_rule() -> None:
    df = _df(
        [
            (1.0, 1.2, 0.8, 1.1),
            (1.1, 1.3, 1.0, 1.2),
            (1.4, 1.6, 1.35, 1.5),
        ]
    )

    events = detect_fvg(df)

    assert len(events) == 1
    assert events[0].kind == EventKind.FVG
    assert events[0].direction == Direction.BULL
    assert events[0].price_low == 1.2
    assert events[0].price_high == 1.35


def test_detect_ifvg_on_close_invalidation() -> None:
    df = _df(
        [
            (1.0, 1.2, 0.8, 1.1),
            (1.1, 1.3, 1.0, 1.2),
            (1.4, 1.6, 1.35, 1.5),
            (1.3, 1.35, 1.1, 1.15),
        ]
    )
    fvg = detect_fvg(df)

    ifvg = detect_ifvg(df, fvg)

    assert len(ifvg) == 1
    assert ifvg[0].kind == EventKind.IFVG
    assert ifvg[0].direction == Direction.BEAR
