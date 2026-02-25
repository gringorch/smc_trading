from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from ingestion.providers.base import Candle
from ingestion.repositories.candles_repository import CandlesRepository


def test_upsert_candles_uses_mysql_branch_when_dialect_is_mysql() -> None:
    session = Mock()
    session.bind.dialect.name = "mysql"
    session.execute.return_value.rowcount = 2
    repo = CandlesRepository(session)
    candles = [Candle(datetime(2026, 1, 1), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"))]

    result = repo.upsert_candles(asset_id=1, timeframe="1m", candles=candles)

    assert result == 2
    assert session.execute.call_count == 1


def test_maintain_partitions_noop_on_non_mysql_dialect() -> None:
    session = Mock()
    session.bind.dialect.name = "sqlite"
    repo = CandlesRepository(session)

    repo.maintain_monthly_partitions(retention_days=365)

    session.execute.assert_not_called()


def test_maintain_partitions_creates_future_and_drops_old_partitions() -> None:
    session = Mock()
    session.bind.dialect.name = "mysql"
    partition_result = Mock()
    partition_result.scalars.return_value.all.return_value = ["pmax", "p200001", "pmeta"]
    session.execute.side_effect = [partition_result, Mock(), Mock(), Mock(), Mock(), Mock()]

    repo = CandlesRepository(session)
    repo.maintain_monthly_partitions(retention_days=30, future_months=1)

    sql_executed = [str(call.args[0]) for call in session.execute.call_args_list[1:]]
    assert any("REORGANIZE PARTITION pmax" in sql for sql in sql_executed)
    assert any("DROP PARTITION p200001" in sql for sql in sql_executed)

