from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from db.models import MarketCandle
from ingestion.providers.base import Candle
from ingestion.repositories.candles_repository import CandlesRepository


def test_retention_deletes_rows_older_than_cutoff(db_session, seeded_assets) -> None:
    asset = seeded_assets[0]
    repo = CandlesRepository(db_session)

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    old_ts = now - timedelta(days=370)
    new_ts = now - timedelta(days=1)

    old_candle = Candle(old_ts, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"))
    new_candle = Candle(new_ts, Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2"), Decimal("2"))

    repo.upsert_candles(asset.id, "1m", [old_candle, new_candle])
    db_session.commit()

    deleted = repo.delete_older_than(now - timedelta(days=365), asset_id=asset.id)
    db_session.commit()

    assert deleted == 1
    count = db_session.scalar(select(func.count()).select_from(MarketCandle))
    assert count == 1
