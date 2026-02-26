"""Ingestion state model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class IngestionStatus(str, Enum):
    """Job status markers."""

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class IngestionState(Base):
    """Per-asset execution status and tracing information."""

    __tablename__ = "ingestion_state"

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True, default="1m")

    status: Mapped[IngestionStatus] = mapped_column(
        SQLEnum(IngestionStatus), nullable=False, default=IngestionStatus.IDLE
    )
    last_success_ts_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )
