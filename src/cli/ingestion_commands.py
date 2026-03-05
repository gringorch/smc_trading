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
from indicators.ifvg import IfvgConfig, detect_ifvgs
from reporting.fvg_report import build_fvg_report_html
from reporting.ifvg_report import build_ifvg_report_html

app = typer.Typer(help="Historical market ingestion CLI")
_LTF_TIMEFRAMES = {"1m", "2m", "3m", "4m", "5m"}


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


@app.command("ifvg-report")
def ifvg_report(
    symbol: str = typer.Option(..., help="Asset symbol. Use `symbols` command to list values."),
    ltf_timeframe: str = typer.Option("1m", help="LTF timeframe for IFVG detection: 1m-5m."),
    candles: int = typer.Option(500, help="Number of candles to analyze."),
    end: datetime | None = typer.Option(
        default=None, help="Optional end timestamp (ISO8601). Defaults to latest persisted 1m candle."
    ),
    htf_timeframe: str | None = typer.Option(None, help="Optional HTF timeframe metadata."),
    htf_bias: str | None = typer.Option(None, help="Optional HTF bias: bull or bear."),
    min_gap_size: float = typer.Option(0.00005, help="Minimum origin FVG gap size (price units)."),
    max_bars_from_fvg_formation_to_inversion: int = typer.Option(
        5, help="Max bars between FVG formation and inversion event."
    ),
    inversion_fill_pct: float = typer.Option(1.0, help="Inversion fill threshold in [0.1, 1.0]."),
    inversion_buffer: float = typer.Option(0.0, help="Price buffer used in inversion threshold."),
    displacement_rule: str = typer.Option(
        "body_pct_range", help="Displacement rule: body_pct_range or body_atr."
    ),
    body_pct_range: float = typer.Option(
        0.7, help="Minimum body/range ratio when displacement_rule=body_pct_range."
    ),
    displacement_body_atr_mult: float = typer.Option(
        1.0, help="Minimum candle body as ATR multiplier when body_atr is used."
    ),
    atr_period: int = typer.Option(14, help="ATR period for body_atr displacement rule."),
    sweep_required: bool = typer.Option(False, help="Require liquidity sweep before inversion."),
    sweep_lookback_bars: int = typer.Option(10, help="Sweep lookback bars."),
    max_bars_between_sweep_and_inversion: int = typer.Option(
        1, help="Max bars between sweep and inversion."
    ),
    bias_required: bool = typer.Option(False, help="Require htf_bias to align with signal side."),
    poi_required: bool = typer.Option(False, help="Require provided POI range."),
    poi_low: float | None = typer.Option(None, help="POI low bound."),
    poi_high: float | None = typer.Option(None, help="POI high bound."),
    entry_model: str = typer.Option("market_on_close", help="Entry model: market_on_close or limit_retest."),
    limit_retest_level: str = typer.Option(
        "gap_mid", help="Retest level for limit_retest: gap_mid, gap_near_edge, gap_far_edge."
    ),
    stop_model: str = typer.Option(
        "beyond_gap_edge", help="Stop model: beyond_gap_edge or beyond_sweep_extreme."
    ),
    sl_buffer: float = typer.Option(0.0, help="Stop-loss extra buffer."),
    rr: float = typer.Option(2.0, help="Risk/reward ratio for TP."),
    cooldown_bars: int = typer.Option(0, help="Global cooldown bars after each signal."),
    output: str = typer.Option("reports/ifvg_report.html", help="Output HTML file path."),
) -> None:
    """Generate IFVG HTML report from persisted candles."""
    _configure_logging()
    settings = get_settings()

    if ltf_timeframe not in _LTF_TIMEFRAMES:
        raise typer.BadParameter("ltf_timeframe must be one of: 1m, 2m, 3m, 4m, 5m")
    if htf_bias not in (None, "bull", "bear"):
        raise typer.BadParameter("htf_bias must be 'bull' or 'bear'")

    config = IfvgConfig(
        min_gap_size=Decimal(str(min_gap_size)),
        max_bars_from_fvg_formation_to_inversion=max_bars_from_fvg_formation_to_inversion,
        inversion_fill_pct=Decimal(str(inversion_fill_pct)),
        inversion_buffer=Decimal(str(inversion_buffer)),
        displacement_rule=displacement_rule,  # type: ignore[arg-type]
        displacement_min_body_pct=Decimal(str(body_pct_range)),
        displacement_body_atr_mult=Decimal(str(displacement_body_atr_mult)),
        atr_period=atr_period,
        sweep_required=sweep_required,
        sweep_lookback_bars=sweep_lookback_bars,
        max_bars_between_sweep_and_inversion=max_bars_between_sweep_and_inversion,
        bias_required=bias_required,
        poi_required=poi_required,
        poi_low=Decimal(str(poi_low)) if poi_low is not None else None,
        poi_high=Decimal(str(poi_high)) if poi_high is not None else None,
        entry_model=entry_model,  # type: ignore[arg-type]
        limit_retest_level=limit_retest_level,  # type: ignore[arg-type]
        stop_model=stop_model,  # type: ignore[arg-type]
        sl_buffer=Decimal(str(sl_buffer)),
        rr=Decimal(str(rr)),
        cooldown_bars=cooldown_bars,
    )

    with session_scope() as session:
        service = PriceChartService(PriceDataRepository(session), chart_timezone=settings.chart_timezone)
        bars = service.get_price_bars(symbol=symbol, timeframe=ltf_timeframe, candles=candles, end=end)

    signals = detect_ifvgs(
        bars=bars,
        config=config,
        symbol=symbol,
        ltf_timeframe=ltf_timeframe,
        htf_timeframe=htf_timeframe,
        htf_bias=htf_bias,  # type: ignore[arg-type]
    )

    end_display = end or bars[-1].timestamp_utc
    html = build_ifvg_report_html(
        symbol=symbol,
        timeframe=ltf_timeframe,
        candles=candles,
        end_utc=end_display,
        config=config,
        bars=bars,
        signals=signals,
    )

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    typer.echo(
        f"ifvg-report: output={output_path} symbol={symbol} "
        f"timeframe={ltf_timeframe} signals={len(signals)}"
    )
