"""Market candles model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class MarketCandle(Base):
    """Unified table for all asset OHLCV 1m candles."""

    __tablename__ = "market_candles"

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True, default="1m")
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), primary_key=True)

    open: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("high >= low", name="ck_high_gte_low"),
        CheckConstraint("volume >= 0", name="ck_volume_nonnegative"),
        Index("ix_market_candles_asset_tf_ts", "asset_id", "timeframe", "timestamp_utc"),
    )
