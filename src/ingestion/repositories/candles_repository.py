"""Market candles repository."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy import text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from db.models.market_candles import MarketCandle
from ingestion.providers.base import Candle


class CandlesRepository:
    """Persistence operations for market candles."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest_timestamp(self, asset_id: int, timeframe: str = "1m") -> datetime | None:
        stmt = select(func.max(MarketCandle.timestamp_utc)).where(
            MarketCandle.asset_id == asset_id,
            MarketCandle.timeframe == timeframe,
        )
        return self._session.scalar(stmt)

    def upsert_candles(self, asset_id: int, timeframe: str, candles: list[Candle]) -> int:
        if not candles:
            return 0

        rows = [
            {
                "asset_id": asset_id,
                "timeframe": timeframe,
                "timestamp_utc": candle.timestamp_utc,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]

        dialect = self._session.bind.dialect.name
        if dialect == "mysql":
            insert_stmt = mysql_insert(MarketCandle).values(rows)
            upsert_stmt = insert_stmt.on_duplicate_key_update(
                open=insert_stmt.inserted.open,
                high=insert_stmt.inserted.high,
                low=insert_stmt.inserted.low,
                close=insert_stmt.inserted.close,
                volume=insert_stmt.inserted.volume,
                ingested_at=func.now(),
            )
        else:
            insert_stmt = sqlite_insert(MarketCandle).values(rows)
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["asset_id", "timeframe", "timestamp_utc"],
                set_={
                    "open": insert_stmt.excluded.open,
                    "high": insert_stmt.excluded.high,
                    "low": insert_stmt.excluded.low,
                    "close": insert_stmt.excluded.close,
                    "volume": insert_stmt.excluded.volume,
                    "ingested_at": func.now(),
                },
            )

        result = self._session.execute(upsert_stmt)
        return int(result.rowcount or 0)

    def delete_older_than(
        self, cutoff_utc: datetime, timeframe: str = "1m", asset_id: int | None = None
    ) -> int:
        conditions = [MarketCandle.timeframe == timeframe, MarketCandle.timestamp_utc < cutoff_utc]
        if asset_id is not None:
            conditions.append(MarketCandle.asset_id == asset_id)

        stmt = delete(MarketCandle).where(*conditions)
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    def delete_asset_timeframe(self, asset_id: int, timeframe: str = "1m") -> int:
        stmt = delete(MarketCandle).where(
            MarketCandle.asset_id == asset_id,
            MarketCandle.timeframe == timeframe,
        )
        result = self._session.execute(stmt)
        return int(result.rowcount or 0)

    def maintain_monthly_partitions(self, retention_days: int, future_months: int = 3) -> None:
        """Create future partitions and drop partitions outside retention on MySQL."""
        if self._session.bind.dialect.name != "mysql":
            return

        now = datetime.utcnow()
        cutoff = now - timedelta(days=retention_days)
        existing = self._session.execute(
            text(
                """
                SELECT PARTITION_NAME
                FROM INFORMATION_SCHEMA.PARTITIONS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'market_candles'
                  AND PARTITION_NAME IS NOT NULL
                """
            )
        ).scalars().all()
        existing_set = set(existing)
        if "pmax" not in existing_set:
            # Table is not partitioned (or partitioning is unsupported in current schema).
            return

        def month_floor(dt: datetime) -> datetime:
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        def add_month(dt: datetime) -> datetime:
            year = dt.year + (1 if dt.month == 12 else 0)
            month = 1 if dt.month == 12 else dt.month + 1
            return dt.replace(year=year, month=month, day=1)

        cursor = month_floor(now)
        for _ in range(future_months + 1):
            part_name = f"p{cursor.year}{cursor.month:02d}"
            if part_name not in existing_set:
                next_month = add_month(cursor)
                self._session.execute(
                    text(
                        f"ALTER TABLE market_candles REORGANIZE PARTITION pmax INTO ("
                        f"PARTITION {part_name} VALUES LESS THAN ('{next_month:%Y-%m-%d %H:%M:%S}'), "
                        "PARTITION pmax VALUES LESS THAN (MAXVALUE))"
                    )
                )
            cursor = add_month(cursor)

        for part_name in existing_set:
            if not part_name.startswith("p") or part_name == "pmax":
                continue
            try:
                year = int(part_name[1:5])
                month = int(part_name[5:7])
            except ValueError:
                continue
            partition_month = datetime(year, month, 1)
            if partition_month < month_floor(cutoff):
                self._session.execute(text(f"ALTER TABLE market_candles DROP PARTITION {part_name}"))
