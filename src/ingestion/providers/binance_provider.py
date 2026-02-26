"""Binance market data provider."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

from ingestion.providers.base import Candle, MarketDataProvider, ProviderError

try:
    from binance.client import Client
except Exception:  # pragma: no cover
    Client = None


class BinanceProvider(MarketDataProvider):
    """Fetch 1m candles from Binance REST API."""

    def __init__(self, rate_limit_ms: int = 250) -> None:
        if Client is None:
            raise ProviderError("python-binance dependency is not available")
        self._client = Client()
        self._rate_limit_ms = max(rate_limit_ms, 0)

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
        if start_utc >= end_utc:
            return []

        try:
            klines = self._client.get_historical_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1MINUTE,
                start_str=str(int(start_utc.timestamp() * 1000)),
                end_str=str(int(end_utc.timestamp() * 1000)),
                limit=limit,
            )
        except Exception as exc:
            raise ProviderError(f"Binance request failed for {symbol}: {exc}") from exc

        candles: list[Candle] = []
        for k in klines:
            ts = datetime.fromtimestamp(k[0] / 1000, tz=UTC).replace(tzinfo=None)
            candles.append(
                Candle(
                    timestamp_utc=ts,
                    open=Decimal(k[1]),
                    high=Decimal(k[2]),
                    low=Decimal(k[3]),
                    close=Decimal(k[4]),
                    volume=Decimal(k[5]),
                )
            )

        if self._rate_limit_ms:
            time.sleep(self._rate_limit_ms / 1000)
        return candles
