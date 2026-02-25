"""Ingestion state repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from db.models.ingestion_state import IngestionState, IngestionStatus


class IngestionStateRepository:
    """CRUD helpers for ingestion run state."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, asset_id: int, timeframe: str = "1m") -> IngestionState | None:
        stmt = select(IngestionState).where(
            IngestionState.asset_id == asset_id,
            IngestionState.timeframe == timeframe,
        )
        return self._session.scalar(stmt)

    def mark_running(self, asset_id: int, timeframe: str = "1m") -> None:
        self._upsert_status(asset_id, timeframe, IngestionStatus.RUNNING, None, None)

    def mark_success(self, asset_id: int, last_success_ts_utc: datetime, timeframe: str = "1m") -> None:
        self._upsert_status(asset_id, timeframe, IngestionStatus.SUCCESS, last_success_ts_utc, None)

    def mark_failure(self, asset_id: int, error_message: str, timeframe: str = "1m") -> None:
        safe_error = error_message[:2000]
        self._upsert_status(asset_id, timeframe, IngestionStatus.FAILED, None, safe_error)

    def _upsert_status(
        self,
        asset_id: int,
        timeframe: str,
        status: IngestionStatus,
        last_success_ts_utc: datetime | None,
        error_message: str | None,
    ) -> None:
        now_utc = datetime.utcnow()
        values = {
            "asset_id": asset_id,
            "timeframe": timeframe,
            "status": status,
            "last_success_ts_utc": last_success_ts_utc,
            "error_message": error_message,
            "last_attempt_at": now_utc,
            "updated_at": now_utc,
        }

        dialect = self._session.bind.dialect.name
        if dialect == "mysql":
            stmt = mysql_insert(IngestionState).values(values)
            upsert_stmt = stmt.on_duplicate_key_update(
                status=stmt.inserted.status,
                last_success_ts_utc=(
                    stmt.inserted.last_success_ts_utc
                    if last_success_ts_utc is not None
                    else IngestionState.last_success_ts_utc
                ),
                error_message=stmt.inserted.error_message,
                last_attempt_at=stmt.inserted.last_attempt_at,
                updated_at=stmt.inserted.updated_at,
            )
        else:
            stmt = sqlite_insert(IngestionState).values(values)
            set_values = {
                "status": stmt.excluded.status,
                "error_message": stmt.excluded.error_message,
                "last_attempt_at": stmt.excluded.last_attempt_at,
                "updated_at": stmt.excluded.updated_at,
            }
            if last_success_ts_utc is not None:
                set_values["last_success_ts_utc"] = stmt.excluded.last_success_ts_utc

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["asset_id", "timeframe"],
                set_=set_values,
            )

        self._session.execute(upsert_stmt)
