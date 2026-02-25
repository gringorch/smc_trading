"""Provider exports."""

from ingestion.providers.base import Candle, MarketDataProvider, ProviderError
from ingestion.providers.binance_provider import BinanceProvider
from ingestion.providers.dukascopy_provider import DukascopyProvider

__all__ = [
    "BinanceProvider",
    "Candle",
    "DukascopyProvider",
    "MarketDataProvider",
    "ProviderError",
]
