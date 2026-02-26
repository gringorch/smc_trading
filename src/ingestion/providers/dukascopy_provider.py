"""Dukascopy market data provider."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ingestion.providers.base import Candle, MarketDataProvider, ProviderError

import dukascopy_python



class DukascopyProvider(MarketDataProvider):
    """Fetch 1m candles from Dukascopy via python package."""

    def __init__(self, rate_limit_ms: int = 250) -> None:
        self._rate_limit_ms = max(rate_limit_ms, 0)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if "/" in normalized:
            return normalized
        if len(normalized) == 6 and normalized.isalpha():
            return f"{normalized[:3]}/{normalized[3:]}"
        return normalized

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @staticmethod
    def _to_naive_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(UTC).replace(tzinfo=None)

    def fetch_candles(
        self,
        symbol: str,
        start_utc: datetime,
        end_utc: datetime,
        timeframe: str = "1m",
        limit: int = 1000,
    ) -> list[Candle]:
        if timeframe != "1m":
            raise ValueError("Only 1m timeframe is supported")
        else:
            interval = dukascopy_python.INTERVAL_MIN_1
        if start_utc >= end_utc:
            return []

        normalized_symbol = self._normalize_symbol(symbol)
        start = self._ensure_utc(start_utc)
        end = self._ensure_utc(end_utc)

        try:
            raw_rows = dukascopy_python.fetch(
                instrument=normalized_symbol,
                interval=interval,
                offer_side=dukascopy_python.OFFER_SIDE_ASK,
                start=start,
                end=end,
                limit=min(limit, 30_000),
            )
        except Exception as exc:
            raise ProviderError(f"Dukascopy request failed for {symbol}: {exc}") from exc

        candles: list[Candle] = []
        # dukascopy_python.fetch returns a DataFrame indexed by timestamp.
        if hasattr(raw_rows, "iterrows"):
            for ts, row in raw_rows.iterrows():
                candles.append(
                    Candle(
                        timestamp_utc=self._to_naive_utc(ts.to_pydatetime()),
                        open=Decimal(str(row["open"])),
                        high=Decimal(str(row["high"])),
                        low=Decimal(str(row["low"])),
                        close=Decimal(str(row["close"])),
                        volume=Decimal(str(row.get("volume", "0"))),
                    )
                )
        else:
            # Defensive fallback for alternate package output shapes.
            for row in raw_rows:
                row_data: dict[str, Any] = row if isinstance(row, dict) else dict(row)
                ts = self._to_naive_utc(row_data["timestamp"])
                candles.append(
                    Candle(
                        timestamp_utc=ts,
                        open=Decimal(str(row_data["open"])),
                        high=Decimal(str(row_data["high"])),
                        low=Decimal(str(row_data["low"])),
                        close=Decimal(str(row_data["close"])),
                        volume=Decimal(str(row_data.get("volume", "0"))),
                    )
                )

        if self._rate_limit_ms:
            time.sleep(self._rate_limit_ms / 1000)
        return candles
