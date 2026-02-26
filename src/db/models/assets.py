"""Assets catalog model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AssetClass(str, Enum):
    """Supported market asset classes."""

    FOREX = "forex"
    CRYPTO = "crypto"


class Asset(Base):
    """Catalog table for tradable assets."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    asset_class: Mapped[AssetClass] = mapped_column(SQLEnum(AssetClass), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )
