from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from config.settings import Settings
from db.models.assets import AssetClass
from ingestion.providers.base import Candle, MarketDataProvider, ProviderError
from ingestion.repositories.candles_repository import CandlesRepository
from ingestion.services.ingestion_service import IngestionService


class EmptyProvider(MarketDataProvider):
    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        return []


class FailingProvider(MarketDataProvider):
    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        raise ProviderError("provider failed")


class CaptureStartProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.start_utc = None

    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        self.start_utc = start_utc
        return []


def test_run_sync_continues_when_partition_maintenance_fails(db_session, seeded_assets, monkeypatch) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    asset = seeded_assets[0]

    def raise_partition_error(*_args, **_kwargs):
        raise RuntimeError("partition error")

    monkeypatch.setattr(service._candles_repo, "maintain_monthly_partitions", raise_partition_error)
    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: EmptyProvider())

    result = service.run_sync(asset_id=asset.id)

    assert result.attempted_assets == 1
    assert result.failed_assets == 0


def test_run_sync_uses_lookback_correction_when_latest_exists(db_session, seeded_assets, monkeypatch) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    asset = seeded_assets[0]
    now_utc = datetime.now(tz=UTC).replace(tzinfo=None)
    latest = now_utc - timedelta(minutes=10)

    CandlesRepository(db_session).upsert_candles(
        asset.id,
        "1m",
        [Candle(latest, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"))],
    )
    db_session.commit()

    provider = CaptureStartProvider()
    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: provider)
    service.run_sync(asset_id=asset.id)

    assert provider.start_utc == latest - timedelta(minutes=5)


def test_run_reprocess_returns_zero_summary_when_asset_does_not_exist(db_session) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    result = service.run_reprocess(asset_id=99999)
    assert result.attempted_assets == 0
    assert result.succeeded_assets == 0
    assert result.failed_assets == 0


def test_run_reprocess_returns_failed_summary_when_provider_fails(
    db_session, seeded_assets, monkeypatch
) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    asset = seeded_assets[0]
    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: FailingProvider())

    result = service.run_reprocess(asset_id=asset.id)

    assert result.attempted_assets == 1
    assert result.failed_assets == 1
    assert result.upserted_rows == 0


def test_provider_for_asset_raises_for_unknown_asset_class(db_session) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    fake_asset = type("FakeAsset", (), {"asset_class": "stocks"})()
    with pytest.raises(ProviderError):
        service._provider_for_asset(fake_asset)


def test_ingest_window_returns_zero_when_start_is_not_before_end(db_session, seeded_assets) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    asset = seeded_assets[1]
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    result = service._ingest_window(EmptyProvider(), asset, now, now)

    assert result == 0


def test_run_assets_reprocess_and_retention_paths(db_session, seeded_assets, monkeypatch) -> None:
    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    asset = seeded_assets[0]
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: EmptyProvider())
    monkeypatch.setattr(service._candles_repo, "delete_asset_timeframe", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(service._candles_repo, "delete_older_than", lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(service._candles_repo, "get_latest_timestamp", lambda *_args, **_kwargs: None)

    summary = service._run_assets(
        assets=[asset],
        start_utc=now - timedelta(minutes=5),
        end_utc=now,
        apply_retention=True,
        reprocess=True,
    )

    assert summary.deleted_rows == 5
    assert summary.succeeded_assets == 1
    assert summary.failed_assets == 0
    assert asset.asset_class in {AssetClass.FOREX, AssetClass.CRYPTO}

