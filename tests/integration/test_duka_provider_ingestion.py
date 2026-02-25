from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from config.settings import Settings
from db.models import AssetClass, MarketCandle
from ingestion.providers.base import Candle, MarketDataProvider
from ingestion.services.ingestion_service import IngestionService


class FakeDukascopyProvider(MarketDataProvider):
    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        ts = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(minutes=1)
        return [Candle(ts, Decimal("1.1"), Decimal("1.2"), Decimal("1.0"), Decimal("1.15"), Decimal("50"))]


def test_forex_ingestion_uses_dukascopy_contract(db_session, seeded_assets, monkeypatch) -> None:
    settings = Settings(DB_PASSWORD="x")
    service = IngestionService(db_session, settings)

    forex_asset = seeded_assets[0]
    assert forex_asset.asset_class == AssetClass.FOREX

    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: FakeDukascopyProvider())
    result = service.run_backfill(asset_id=forex_asset.id)

    count = db_session.scalar(select(func.count()).select_from(MarketCandle))
    assert result.succeeded_assets == 1
    assert count >= 1
