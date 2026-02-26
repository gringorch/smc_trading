from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from db.models import MarketCandle
from ingestion.providers.base import Candle
from ingestion.repositories.candles_repository import CandlesRepository


def test_upsert_deduplicates_by_asset_timeframe_timestamp(db_session, seeded_assets) -> None:
    asset = seeded_assets[0]
    repo = CandlesRepository(db_session)
    ts = datetime(2026, 1, 1, 0, 0, 0)

    first = Candle(ts, Decimal("1.10"), Decimal("1.20"), Decimal("1.00"), Decimal("1.15"), Decimal("10"))
    second = Candle(ts, Decimal("1.11"), Decimal("1.22"), Decimal("1.01"), Decimal("1.16"), Decimal("12"))

    repo.upsert_candles(asset.id, "1m", [first])
    repo.upsert_candles(asset.id, "1m", [second])
    db_session.commit()

    count = db_session.scalar(select(func.count()).select_from(MarketCandle))
    candle = db_session.scalar(select(MarketCandle))

    assert count == 1
    assert candle.close == Decimal("1.1600000000")
    assert candle.volume == Decimal("12.0000000000")
