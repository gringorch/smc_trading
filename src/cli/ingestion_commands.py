"""Typer commands for ingestion jobs."""

import logging

import typer

from config.settings import get_settings
from db.engine import session_scope
from ingestion.services.ingestion_service import IngestionService

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
