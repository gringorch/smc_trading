from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from config.settings import Settings
from db.models import AssetClass, MarketCandle
from ingestion.providers.base import Candle, MarketDataProvider
from ingestion.services.ingestion_service import IngestionService


class FakeBinanceProvider(MarketDataProvider):
    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        ts = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(minutes=1)
        return [Candle(ts, Decimal("100"), Decimal("105"), Decimal("99"), Decimal("101"), Decimal("7"))]


def test_crypto_ingestion_uses_binance_contract(db_session, seeded_assets, monkeypatch) -> None:
    settings = Settings(DB_PASSWORD="x")
    service = IngestionService(db_session, settings)

    crypto_asset = seeded_assets[1]
    assert crypto_asset.asset_class == AssetClass.CRYPTO

    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: FakeBinanceProvider())
    result = service.run_backfill(asset_id=crypto_asset.id)

    count = db_session.scalar(select(func.count()).select_from(MarketCandle))
    assert result.succeeded_assets == 1
    assert count >= 1
