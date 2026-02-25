"""Test fixtures."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.base import Base
from db.models import Asset, AssetClass


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = local_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_assets(db_session: Session) -> list[Asset]:
    assets = [
        Asset(symbol="EURUSD", asset_class=AssetClass.FOREX, provider_symbol="EURUSD"),
        Asset(symbol="BTCUSDT", asset_class=AssetClass.CRYPTO, provider_symbol="BTCUSDT"),
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets
