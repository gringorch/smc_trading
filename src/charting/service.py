"""Application service for price charting."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from charting.price_data_repository import PriceDataRepository
from charting.price_plotter import render_price_chart
from charting.resampler import OhlcvBar, resample_ohlcv
from charting.timeframes import normalize_utc, parse_timeframe

logger = logging.getLogger(__name__)


class PriceChartService:
    """Orchestrate DB fetch, resampling and chart rendering."""

    def __init__(self, repository: PriceDataRepository, chart_timezone: str = "UTC") -> None:
        if chart_timezone.upper() != "UTC":
            raise ValueError("only UTC timezone is supported for charting")
        self._repository = repository

    def list_symbols(self) -> list[str]:
        """Return active symbols sorted alphabetically."""
        return self._repository.list_active_symbols()

    def plot_price(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: int,
        end: datetime | None = None,
        show: bool = True,
        save_path: str | None = None,
        include_volume: bool = False,
    ) -> list[OhlcvBar]:
        """Build and render chart bars; return bars for observability/tests."""
        if candles <= 0:
            raise ValueError("candles must be greater than 0")

        duration = parse_timeframe(timeframe)
        end_utc = normalize_utc(end or datetime.now(UTC))
        # Load a wider window to tolerate missing minutes while preserving final candles count.
        start_utc = end_utc - (duration * candles * 2)

        asset_id = self._repository.get_asset_id_by_symbol(symbol)
        if asset_id is None:
            raise ValueError(f"symbol '{symbol}' not found or inactive")

        source_rows = self._repository.load_1m_rows(asset_id=asset_id, start_utc=start_utc, end_utc=end_utc)
        logger.debug("price_chart source_rows=%s symbol=%s timeframe=%s", len(source_rows), symbol, timeframe)

        resampled = resample_ohlcv(source_rows, timeframe)
        trimmed = resampled[-candles:]

        logger.debug(
            "price_chart resampled_bars=%s returned_bars=%s symbol=%s timeframe=%s",
            len(resampled),
            len(trimmed),
            symbol,
            timeframe,
        )

        render_price_chart(
            symbol=symbol,
            timeframe=timeframe,
            bars=trimmed,
            include_volume=include_volume,
            show=show,
            save_path=save_path,
        )
        return trimmed
