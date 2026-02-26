"""Ingestion service orchestrating backfill, sync and reprocess flows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from config.settings import Settings
from db.models.assets import Asset, AssetClass
from ingestion.providers import BinanceProvider, DukascopyProvider, MarketDataProvider
from ingestion.providers.base import ProviderError
from ingestion.repositories import AssetsRepository, CandlesRepository, IngestionStateRepository

logger = logging.getLogger(__name__)

TIMEFRAME = "1m"
LOOKBACK_CORRECTION_MINUTES = 5


@dataclass(frozen=True)
class IngestionSummary:
    """Aggregated execution summary for CLI output."""

    attempted_assets: int
    succeeded_assets: int
    failed_assets: int
    upserted_rows: int
    deleted_rows: int


class IngestionService:
    """Coordinates providers and repositories for ingestion jobs."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._assets_repo = AssetsRepository(session)
        self._candles_repo = CandlesRepository(session)
        self._state_repo = IngestionStateRepository(session)

    def run_backfill(self, asset_id: int | None = None) -> IngestionSummary:
        assets = self._assets_repo.list_active(asset_id)
        now_utc = datetime.now(tz=UTC).replace(tzinfo=None)
        start_utc = now_utc - timedelta(days=self._settings.retention_days)

        return self._run_assets(assets, start_utc, now_utc, apply_retention=False, reprocess=False)

    def run_sync(self, asset_id: int | None = None) -> IngestionSummary:
        assets = self._assets_repo.list_active(asset_id)
        now_utc = datetime.now(tz=UTC).replace(tzinfo=None)
        try:
            self._candles_repo.maintain_monthly_partitions(self._settings.retention_days)
            self._session.commit()
        except Exception:  # noqa: BLE001
            self._session.rollback()
            logger.exception("Partition maintenance failed; continuing with sync")

        attempted = 0
        succeeded = 0
        failed = 0
        total_upserts = 0
        total_deleted = 0

        for asset in assets:
            attempted += 1
            provider = self._provider_for_asset(asset)
            self._state_repo.mark_running(asset.id, TIMEFRAME)

            latest = self._candles_repo.get_latest_timestamp(asset.id, TIMEFRAME)
            if latest is None:
                start_utc = now_utc - timedelta(days=self._settings.retention_days)
            else:
                start_utc = latest - timedelta(minutes=LOOKBACK_CORRECTION_MINUTES)

            try:
                upserts = self._ingest_window(provider, asset, start_utc, now_utc)
                cutoff = now_utc - timedelta(days=self._settings.retention_days)
                deleted = self._candles_repo.delete_older_than(cutoff, TIMEFRAME, asset.id)

                latest_after = self._candles_repo.get_latest_timestamp(asset.id, TIMEFRAME)
                if latest_after is not None:
                    self._state_repo.mark_success(asset.id, latest_after, TIMEFRAME)

                succeeded += 1
                total_upserts += upserts
                total_deleted += deleted
                self._session.commit()
            except Exception as exc:  # noqa: BLE001
                self._session.rollback()
                logger.exception("Sync failed for asset_id=%s", asset.id)
                self._state_repo.mark_failure(asset.id, str(exc), TIMEFRAME)
                self._session.commit()
                failed += 1

        return IngestionSummary(attempted, succeeded, failed, total_upserts, total_deleted)

    def run_reprocess(self, asset_id: int) -> IngestionSummary:
        assets = self._assets_repo.list_active(asset_id)
        if not assets:
            return IngestionSummary(0, 0, 0, 0, 0)

        now_utc = datetime.now(tz=UTC).replace(tzinfo=None)
        start_utc = now_utc - timedelta(days=self._settings.retention_days)

        asset = assets[0]
        self._state_repo.mark_running(asset.id, TIMEFRAME)
        try:
            deleted_rows = self._candles_repo.delete_asset_timeframe(asset.id, TIMEFRAME)
            upserted = self._ingest_window(self._provider_for_asset(asset), asset, start_utc, now_utc)
            latest_after = self._candles_repo.get_latest_timestamp(asset.id, TIMEFRAME)
            if latest_after is not None:
                self._state_repo.mark_success(asset.id, latest_after, TIMEFRAME)
            self._session.commit()
            return IngestionSummary(1, 1, 0, upserted, deleted_rows)
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            logger.exception("Reprocess failed for asset_id=%s", asset.id)
            self._state_repo.mark_failure(asset.id, str(exc), TIMEFRAME)
            self._session.commit()
            return IngestionSummary(1, 0, 1, 0, 0)

    def _run_assets(
        self,
        assets: list[Asset],
        start_utc: datetime,
        end_utc: datetime,
        apply_retention: bool,
        reprocess: bool,
    ) -> IngestionSummary:
        attempted = 0
        succeeded = 0
        failed = 0
        total_upserts = 0
        total_deleted = 0

        for asset in assets:
            attempted += 1
            self._state_repo.mark_running(asset.id, TIMEFRAME)
            try:
                if reprocess:
                    total_deleted += self._candles_repo.delete_asset_timeframe(asset.id, TIMEFRAME)
                upserts = self._ingest_window(self._provider_for_asset(asset), asset, start_utc, end_utc)
                if apply_retention:
                    total_deleted += self._candles_repo.delete_older_than(
                        end_utc - timedelta(days=self._settings.retention_days),
                        TIMEFRAME,
                        asset.id,
                    )

                latest_after = self._candles_repo.get_latest_timestamp(asset.id, TIMEFRAME)
                if latest_after is not None:
                    self._state_repo.mark_success(asset.id, latest_after, TIMEFRAME)
                succeeded += 1
                total_upserts += upserts
                self._session.commit()
            except Exception as exc:  # noqa: BLE001
                self._session.rollback()
                logger.exception("Ingestion failed for asset_id=%s", asset.id)
                self._state_repo.mark_failure(asset.id, str(exc), TIMEFRAME)
                self._session.commit()
                failed += 1

        return IngestionSummary(attempted, succeeded, failed, total_upserts, total_deleted)

    def _provider_for_asset(self, asset: Asset) -> MarketDataProvider:
        if asset.asset_class == AssetClass.FOREX:
            return DukascopyProvider(rate_limit_ms=self._settings.dukascopy_rate_limit_ms)
        if asset.asset_class == AssetClass.CRYPTO:
            return BinanceProvider(rate_limit_ms=self._settings.binance_rate_limit_ms)
        raise ProviderError(f"No provider for asset class {asset.asset_class}")

    def _ingest_window(
        self,
        provider: MarketDataProvider,
        asset: Asset,
        start_utc: datetime,
        end_utc: datetime,
    ) -> int:
        if start_utc >= end_utc:
            return 0

        total_upserts = 0
        cursor = start_utc
        batch_delta = timedelta(minutes=self._settings.batch_size)

        while cursor < end_utc:
            window_end = min(cursor + batch_delta, end_utc)
            candles = provider.fetch_candles(
                symbol=asset.provider_symbol,
                start_utc=cursor,
                end_utc=window_end,
                timeframe=TIMEFRAME,
                limit=self._settings.batch_size,
            )
            total_upserts += self._candles_repo.upsert_candles(asset.id, TIMEFRAME, candles)
            cursor = window_end

        return total_upserts
