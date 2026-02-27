from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from charting.price_data_repository import PriceDataRepository
from db.models import AssetClass, MarketCandle
from db.models.assets import Asset


def test_repository_latest_timestamp_and_row_loading(db_session) -> None:
    asset = Asset(symbol="EURUSD", asset_class=AssetClass.FOREX, provider_symbol="EURUSD")
    db_session.add(asset)
    db_session.flush()

    db_session.add_all(
        [
            MarketCandle(
                asset_id=asset.id,
                timeframe="1m",
                timestamp_utc=datetime(2026, 1, 1, 10, 0),
                open=Decimal("1.0"),
                high=Decimal("1.1"),
                low=Decimal("0.9"),
                close=Decimal("1.05"),
                volume=Decimal("10"),
            ),
            MarketCandle(
                asset_id=asset.id,
                timeframe="1m",
                timestamp_utc=datetime(2026, 1, 1, 10, 1),
                open=Decimal("1.05"),
                high=Decimal("1.2"),
                low=Decimal("1.0"),
                close=Decimal("1.15"),
                volume=Decimal("15"),
            ),
        ]
    )
    db_session.commit()

    repo = PriceDataRepository(db_session)
    latest = repo.get_latest_1m_timestamp(asset.id)
    rows = repo.load_1m_rows(
        asset_id=asset.id,
        start_utc=datetime(2026, 1, 1, 10, 1),
        end_utc=datetime(2026, 1, 1, 10, 1),
    )

    assert latest == datetime(2026, 1, 1, 10, 1)
    assert len(rows) == 1
    assert rows[0].close == Decimal("1.1500000000")


def test_repository_latest_timestamp_none_when_missing(db_session) -> None:
    asset = Asset(symbol="BTCUSDT", asset_class=AssetClass.CRYPTO, provider_symbol="BTCUSDT")
    db_session.add(asset)
    db_session.commit()

    repo = PriceDataRepository(db_session)

    assert repo.get_latest_1m_timestamp(asset.id) is None
