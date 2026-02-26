from datetime import UTC, datetime

import pandas as pd
import pytest

from ingestion.providers.base import ProviderError
from ingestion.providers.dukascopy_provider import DukascopyProvider


def test_fetch_candles_parses_dataframe_and_normalizes_timestamp(monkeypatch) -> None:
    provider = DukascopyProvider(rate_limit_ms=0)
    index = pd.to_datetime(["2026-02-24T12:34:00Z"], utc=True)
    frame = pd.DataFrame(
        {"open": [1.10], "high": [1.20], "low": [1.00], "close": [1.15], "volume": [50]},
        index=index,
    )

    monkeypatch.setattr("ingestion.providers.dukascopy_provider.dukascopy_python.fetch", lambda **_: frame)

    candles = provider.fetch_candles(
        symbol="EURUSD",
        start_utc=datetime(2026, 2, 24, 12, 0, 0),
        end_utc=datetime(2026, 2, 24, 13, 0, 0),
    )

    assert len(candles) == 1
    assert candles[0].timestamp_utc == datetime(2026, 2, 24, 12, 34, 0)
    assert str(candles[0].open) == "1.1"


def test_fetch_candles_sends_normalized_symbol_and_utc_datetimes(monkeypatch) -> None:
    provider = DukascopyProvider(rate_limit_ms=0)
    captured: dict[str, object] = {}
    empty_frame = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return empty_frame

    monkeypatch.setattr("ingestion.providers.dukascopy_provider.dukascopy_python.fetch", fake_fetch)

    provider.fetch_candles(
        symbol="eurusd",
        start_utc=datetime(2026, 2, 24, 12, 0, 0),
        end_utc=datetime(2026, 2, 24, 12, 5, 0),
        limit=1234,
    )

    assert captured["instrument"] == "EUR/USD"
    assert captured["start"].tzinfo == UTC
    assert captured["end"].tzinfo == UTC
    assert captured["limit"] == 1234


def test_fetch_candles_wraps_provider_errors(monkeypatch) -> None:
    provider = DukascopyProvider(rate_limit_ms=0)

    def fake_fetch(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ingestion.providers.dukascopy_provider.dukascopy_python.fetch", fake_fetch)

    with pytest.raises(ProviderError):
        provider.fetch_candles(
            symbol="EURUSD",
            start_utc=datetime(2026, 2, 24, 12, 0, 0),
            end_utc=datetime(2026, 2, 24, 12, 5, 0),
        )
