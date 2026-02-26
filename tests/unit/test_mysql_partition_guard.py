from unittest.mock import Mock

from ingestion.repositories.candles_repository import CandlesRepository


def test_maintain_partitions_noop_when_table_has_no_pmax_partition() -> None:
    session = Mock()
    session.bind.dialect.name = "mysql"

    partition_result = Mock()
    partition_result.scalars.return_value.all.return_value = []
    session.execute.return_value = partition_result

    repo = CandlesRepository(session)
    repo.maintain_monthly_partitions(retention_days=365, future_months=2)

    assert session.execute.call_count == 1
