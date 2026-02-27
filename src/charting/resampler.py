"""Resampling utilities for OHLCV bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from charting.timeframes import bucket_start_utc


@dataclass(frozen=True)
class OhlcvBar:
    """Aggregated OHLCV bar."""

    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def resample_ohlcv(rows: list[OhlcvBar], timeframe: str) -> list[OhlcvBar]:
    """Resample sorted 1m rows to requested timeframe, preserving final partial candle."""
    if timeframe == "1m":
        return rows

    by_bucket: dict[datetime, OhlcvBar] = {}
    ordered_buckets: list[datetime] = []

    for row in rows:
        start = bucket_start_utc(row.timestamp_utc, timeframe)
        current = by_bucket.get(start)
        if current is None:
            by_bucket[start] = OhlcvBar(
                timestamp_utc=start,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            ordered_buckets.append(start)
            continue

        by_bucket[start] = OhlcvBar(
            timestamp_utc=start,
            open=current.open,
            high=max(current.high, row.high),
            low=min(current.low, row.low),
            close=row.close,
            volume=current.volume + row.volume,
        )

    return [by_bucket[start] for start in ordered_buckets]
