"""Provider abstractions for market data ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Candle:
    """Canonical candle record in UTC."""

    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class ProviderError(RuntimeError):
    """Raised when provider fetch fails."""


class MarketDataProvider(ABC):
    """Contract for any 1m OHLCV provider."""

    @abstractmethod
    def fetch_candles(
        self,
        symbol: str,
        start_utc: datetime,
        end_utc: datetime,
        timeframe: str = "1m",
        limit: int = 1000,
    ) -> list[Candle]:
        """Return candles for the requested UTC window."""
