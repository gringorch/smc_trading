"""create assets ingestion_state market_candles"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import OperationalError

revision = "20260217_0001"
down_revision = None
branch_labels = None
depends_on = None


def _month_floor(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_month(dt: datetime) -> datetime:
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return dt.replace(year=year, month=month, day=1)


def _build_partition_sql() -> str:
    now_utc = datetime.now(tz=UTC).replace(tzinfo=None)
    start = _month_floor(now_utc)
    for _ in range(13):
        start = start.replace(year=start.year - 1) if start.month == 1 else start.replace(month=start.month - 1)

    partitions: list[str] = []
    cursor = start
    for _ in range(18):
        nxt = _add_month(cursor)
        part_name = f"p{cursor.year}{cursor.month:02d}"
        partitions.append(
            f"PARTITION {part_name} VALUES LESS THAN ('{nxt.strftime('%Y-%m-%d %H:%M:%S')}')"
        )
        cursor = nxt
    partitions.append("PARTITION pmax VALUES LESS THAN (MAXVALUE)")

    body = ", ".join(partitions)
    return f"ALTER TABLE market_candles PARTITION BY RANGE COLUMNS(timestamp_utc) ({body})"


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=64), nullable=False, unique=True),
        sa.Column("asset_class", sa.Enum("FOREX", "CRYPTO", name="assetclass"), nullable=False),
        sa.Column("provider_symbol", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ingestion_state",
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("timeframe", sa.String(length=8), primary_key=True),
        sa.Column("status", sa.Enum("IDLE", "RUNNING", "SUCCESS", "FAILED", name="ingestionstatus"), nullable=False),
        sa.Column("last_success_ts_utc", sa.DateTime(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "market_candles",
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("timeframe", sa.String(length=8), primary_key=True),
        sa.Column("timestamp_utc", sa.DateTime(), primary_key=True),
        sa.Column("open", sa.Numeric(24, 10), nullable=False),
        sa.Column("high", sa.Numeric(24, 10), nullable=False),
        sa.Column("low", sa.Numeric(24, 10), nullable=False),
        sa.Column("close", sa.Numeric(24, 10), nullable=False),
        sa.Column("volume", sa.Numeric(30, 10), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("high >= low", name="ck_high_gte_low"),
        sa.CheckConstraint("volume >= 0", name="ck_volume_nonnegative"),
    )
    op.create_index(
        "ix_market_candles_asset_tf_ts",
        "market_candles",
        ["asset_id", "timeframe", "timestamp_utc"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        try:
            op.execute(sa.text(_build_partition_sql()))
        except OperationalError as exc:
            # MySQL does not support partitioned InnoDB tables with foreign keys.
            # Keep schema creation successful and run without partitions in this case.
            if getattr(exc.orig, "args", [None])[0] != 1506:
                raise


def downgrade() -> None:
    op.drop_index("ix_market_candles_asset_tf_ts", table_name="market_candles")
    op.drop_table("market_candles")
    op.drop_table("ingestion_state")
    op.drop_table("assets")
