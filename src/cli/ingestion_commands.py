"""Typer commands for ingestion jobs."""

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import typer

from charting.price_data_repository import PriceDataRepository
from charting.service import PriceChartService
from charting.timeframes import supported_timeframes
from config.settings import get_settings
from db.engine import session_scope
from ingestion.services.ingestion_service import IngestionService
from indicators.fvg import FvgConfig, detect_fvgs
from reporting.fvg_report import build_fvg_report_html

app = typer.Typer(help="Historical market ingestion CLI")


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _print_summary(summary_name: str, summary: object) -> None:
    typer.echo(
        f"{summary_name}: attempted={summary.attempted_assets} "
        f"succeeded={summary.succeeded_assets} failed={summary.failed_assets} "
        f"upserted={summary.upserted_rows} deleted={summary.deleted_rows}"
    )


@app.command("backfill")
def backfill(asset_id: int | None = typer.Option(default=None, help="Asset id (optional)")) -> None:
    """Run historical backfill up to retention window."""
    _configure_logging()
    settings = get_settings()
    with session_scope() as session:
        summary = IngestionService(session, settings).run_backfill(asset_id)
    _print_summary("backfill", summary)


@app.command("sync")
def sync(asset_id: int | None = typer.Option(default=None, help="Asset id (optional)")) -> None:
    """Run incremental sync for configured assets."""
    _configure_logging()
    settings = get_settings()
    with session_scope() as session:
        summary = IngestionService(session, settings).run_sync(asset_id)
    _print_summary("sync", summary)


@app.command("reprocess")
def reprocess(asset_id: int = typer.Option(..., help="Asset id")) -> None:
    """Delete and reload 1m history for one asset."""
    _configure_logging()
    settings = get_settings()
    with session_scope() as session:
        summary = IngestionService(session, settings).run_reprocess(asset_id)
    _print_summary("reprocess", summary)


@app.command("symbols")
def symbols() -> None:
    """List active symbols available for charting."""
    _configure_logging()
    settings = get_settings()
    with session_scope() as session:
        service = PriceChartService(PriceDataRepository(session), chart_timezone=settings.chart_timezone)
        for symbol in service.list_symbols():
            typer.echo(symbol)


@app.command("plot-price")
def plot_price(
    symbol: str = typer.Option(..., help="Asset symbol. Use `symbols` command to list values."),
    timeframe: str = typer.Option(
        "1h", help=f"Target timeframe. Supported: {', '.join(supported_timeframes())}"
    ),
    candles: int = typer.Option(200, help="Number of candles to display (limit)."),
    end: datetime | None = typer.Option(
        default=None, help="Optional end timestamp (ISO8601). Defaults to now UTC."
    ),
    show: bool = typer.Option(True, help="Display chart window."),
    save_path: str | None = typer.Option(None, help="Optional output image file path."),
    include_volume: bool = typer.Option(False, help="Include volume subplot."),
) -> None:
    """Render a candlestick chart from persisted 1m candles."""
    _configure_logging()
    settings = get_settings()
    with session_scope() as session:
        service = PriceChartService(PriceDataRepository(session), chart_timezone=settings.chart_timezone)
        bars = service.plot_price(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            end=end,
            show=show,
            save_path=save_path,
            include_volume=include_volume,
        )

    typer.echo(
        f"plot-price: symbol={symbol} timeframe={timeframe} requested={candles} returned={len(bars)}"
    )


@app.command("fvg-report")
def fvg_report(
    symbol: str = typer.Option(..., help="Asset symbol. Use `symbols` command to list values."),
    timeframe: str = typer.Option(
        "1h", help=f"Target timeframe. Supported: {', '.join(supported_timeframes())}"
    ),
    candles: int = typer.Option(200, help="Number of candles to analyze/display (limit)."),
    end: datetime | None = typer.Option(
        default=None, help="Optional end timestamp (ISO8601). Defaults to latest persisted 1m candle."
    ),
    direction: str = typer.Option("both", help="FVG direction filter: bull, bear, both."),
    min_gap_size: float = typer.Option(0.0, help="Minimum gap size to keep (price units)."),
    mitigation_enabled: bool = typer.Option(True, help="Whether to compute mitigation."),
    mitigation_rule: str = typer.Option("wick", help="Mitigation rule: wick or close."),
    output: str = typer.Option("reports/fvg_report.html", help="Output HTML file path."),
) -> None:
    """Generate an HTML report with FVG overlays and a signals table."""
    _configure_logging()
    settings = get_settings()

    config = FvgConfig(
        direction=direction,  # type: ignore[arg-type]
        min_gap_size=Decimal(str(min_gap_size)),
        mitigation_enabled=mitigation_enabled,
        mitigation_rule=mitigation_rule,  # type: ignore[arg-type]
    )

    with session_scope() as session:
        service = PriceChartService(PriceDataRepository(session), chart_timezone=settings.chart_timezone)
        bars = service.get_price_bars(symbol=symbol, timeframe=timeframe, candles=candles, end=end)

    signals = detect_fvgs(bars=bars, config=config)
    end_display = end or bars[-1].timestamp_utc
    html = build_fvg_report_html(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        end_utc=end_display,
        config=config,
        bars=bars,
        signals=signals,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)

    typer.echo(
        f"fvg-report: output={output_path} symbol={symbol} timeframe={timeframe} signals={len(signals)}"
    )
