from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from config.settings import Settings
from db.models import AssetClass, IngestionState, IngestionStatus
from ingestion.providers.base import Candle, MarketDataProvider, ProviderError
from ingestion.services.ingestion_service import IngestionService


class SuccessProvider(MarketDataProvider):
    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        ts = end_utc - timedelta(minutes=1)
        return [Candle(ts, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"))]


class FailingProvider(MarketDataProvider):
    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        raise ProviderError("temporary provider failure")


def test_sync_continues_when_one_asset_fails(db_session, seeded_assets, monkeypatch) -> None:
    settings = Settings(DB_PASSWORD="x")
    service = IngestionService(db_session, settings)

    def choose_provider(asset):
        if asset.asset_class == AssetClass.FOREX:
            return FailingProvider()
        return SuccessProvider()

    monkeypatch.setattr(service, "_provider_for_asset", choose_provider)

    result = service.run_sync()
    states = db_session.scalars(select(IngestionState)).all()
    by_asset = {row.asset_id: row for row in states}

    assert result.attempted_assets == 2
    assert result.succeeded_assets == 1
    assert result.failed_assets == 1
    assert by_asset[seeded_assets[0].id].status == IngestionStatus.FAILED
    assert by_asset[seeded_assets[1].id].status == IngestionStatus.SUCCESS
