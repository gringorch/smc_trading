from __future__ import annotations

from datetime import datetime

from ingestion.repositories.ingestion_state_repository import IngestionStateRepository


def test_get_returns_none_when_state_does_not_exist(db_session) -> None:
    repo = IngestionStateRepository(db_session)
    assert repo.get(asset_id=12345, timeframe="1m") is None


def test_mark_failure_truncates_error_message(db_session, seeded_assets) -> None:
    repo = IngestionStateRepository(db_session)
    asset = seeded_assets[0]
    long_error = "x" * 5000

    repo.mark_running(asset.id, "1m")
    repo.mark_success(asset.id, datetime(2026, 1, 1, 0, 0, 0), "1m")
    repo.mark_failure(asset.id, long_error, "1m")
    db_session.commit()

    state = repo.get(asset.id, "1m")
    assert state is not None
    assert len(state.error_message) == 2000

