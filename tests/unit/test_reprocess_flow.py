from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from config.settings import Settings
from db.models import MarketCandle
from ingestion.providers.base import Candle, MarketDataProvider
from ingestion.repositories.candles_repository import CandlesRepository
from ingestion.services.ingestion_service import IngestionService


class StaticProvider(MarketDataProvider):
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = candles

    def fetch_candles(self, symbol, start_utc, end_utc, timeframe="1m", limit=1000):
        return [c for c in self._candles if start_utc <= c.timestamp_utc < end_utc]


def test_reprocess_deletes_existing_and_loads_clean_history(db_session, seeded_assets, monkeypatch) -> None:
    asset = seeded_assets[0]
    repo = CandlesRepository(db_session)
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    old_row = Candle(now - timedelta(days=2), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"))
    repo.upsert_candles(asset.id, "1m", [old_row])
    db_session.commit()

    replacement = [
        Candle(now - timedelta(minutes=2), Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2")),
        Candle(now - timedelta(minutes=1), Decimal("3"), Decimal("3"), Decimal("3"), Decimal("3"), Decimal("3")),
    ]

    service = IngestionService(db_session, Settings(DB_PASSWORD="x"))
    monkeypatch.setattr(service, "_provider_for_asset", lambda _asset: StaticProvider(replacement))

    result = service.run_reprocess(asset.id)

    count = db_session.scalar(select(func.count()).select_from(MarketCandle))
    assert result.succeeded_assets == 1
    assert count == 2
