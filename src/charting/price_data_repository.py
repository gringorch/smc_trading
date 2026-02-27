"""Database read operations for charting."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from charting.resampler import OhlcvBar
from db.models.assets import Asset
from db.models.market_candles import MarketCandle


class PriceDataRepository:
    """Load symbol metadata and 1m OHLCV rows for plotting."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active_symbols(self) -> list[str]:
        stmt: Select[tuple[str]] = (
            select(Asset.symbol).where(Asset.is_active.is_(True)).order_by(Asset.symbol.asc())
        )
        return list(self._session.scalars(stmt).all())

    def get_asset_id_by_symbol(self, symbol: str) -> int | None:
        stmt = select(Asset.id).where(Asset.symbol == symbol, Asset.is_active.is_(True))
        return self._session.scalar(stmt)

    def load_1m_rows(
        self,
        *,
        asset_id: int,
        start_utc: datetime | None,
        end_utc: datetime,
    ) -> list[OhlcvBar]:
        stmt: Select[tuple[MarketCandle]] = (
            select(MarketCandle)
            .where(
                MarketCandle.asset_id == asset_id,
                MarketCandle.timeframe == "1m",
                MarketCandle.timestamp_utc <= end_utc,
            )
            .order_by(MarketCandle.timestamp_utc.asc())
        )
        if start_utc is not None:
            stmt = stmt.where(MarketCandle.timestamp_utc >= start_utc)

        candles = list(self._session.scalars(stmt).all())
        return [
            OhlcvBar(
                timestamp_utc=candle.timestamp_utc,
                open=Decimal(candle.open),
                high=Decimal(candle.high),
                low=Decimal(candle.low),
                close=Decimal(candle.close),
                volume=Decimal(candle.volume),
            )
            for candle in candles
        ]
