from __future__ import annotations

from datetime import datetime

import pytest

from ingestion.providers.base import ProviderError
from ingestion.providers import binance_provider as bp


def test_init_fails_when_client_dependency_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(bp, "Client", None)
    with pytest.raises(ProviderError):
        bp.BinanceProvider()


def test_fetch_candles_validates_timeframe(monkeypatch) -> None:
    class FakeClient:
        KLINE_INTERVAL_1MINUTE = "1m"

        def __init__(self) -> None:
            pass

    monkeypatch.setattr(bp, "Client", FakeClient)
    provider = bp.BinanceProvider(rate_limit_ms=0)

    with pytest.raises(ValueError):
        provider.fetch_candles("BTCUSDT", datetime(2026, 1, 1), datetime(2026, 1, 2), timeframe="5m")


def test_fetch_candles_returns_empty_when_window_invalid(monkeypatch) -> None:
    class FakeClient:
        KLINE_INTERVAL_1MINUTE = "1m"

        def __init__(self) -> None:
            pass

    monkeypatch.setattr(bp, "Client", FakeClient)
    provider = bp.BinanceProvider(rate_limit_ms=0)
    result = provider.fetch_candles("BTCUSDT", datetime(2026, 1, 2), datetime(2026, 1, 2))
    assert result == []


def test_fetch_candles_parses_klines_and_applies_rate_limit(monkeypatch) -> None:
    class FakeClient:
        KLINE_INTERVAL_1MINUTE = "1m"

        def __init__(self) -> None:
            pass

        def get_historical_klines(self, **_kwargs):
            return [
                [1735689600000, "100.1", "101.2", "99.9", "100.5", "12.3"],
            ]

    sleep_calls: list[float] = []
    monkeypatch.setattr(bp, "Client", FakeClient)
    monkeypatch.setattr(bp.time, "sleep", lambda value: sleep_calls.append(value))

    provider = bp.BinanceProvider(rate_limit_ms=250)
    candles = provider.fetch_candles(
        "BTCUSDT",
        datetime(2026, 1, 1, 0, 0, 0),
        datetime(2026, 1, 1, 0, 1, 0),
    )

    assert len(candles) == 1
    assert candles[0].timestamp_utc == datetime(2025, 1, 1, 0, 0, 0)
    assert str(candles[0].open) == "100.1"
    assert sleep_calls == [0.25]


def test_fetch_candles_wraps_binance_errors(monkeypatch) -> None:
    class FakeClient:
        KLINE_INTERVAL_1MINUTE = "1m"

        def __init__(self) -> None:
            pass

        def get_historical_klines(self, **_kwargs):
            raise RuntimeError("network")

    monkeypatch.setattr(bp, "Client", FakeClient)
    provider = bp.BinanceProvider(rate_limit_ms=0)

    with pytest.raises(ProviderError):
        provider.fetch_candles(
            "BTCUSDT",
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 1, 0),
        )

