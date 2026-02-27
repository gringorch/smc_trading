from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from typer.testing import CliRunner

from config.settings import Settings
from cli import ingestion_commands as cli


def _summary() -> SimpleNamespace:
    return SimpleNamespace(
        attempted_assets=1,
        succeeded_assets=1,
        failed_assets=0,
        upserted_rows=10,
        deleted_rows=2,
    )


def test_cli_backfill_runs_service_and_prints_summary(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    @contextmanager
    def fake_scope():
        yield object()

    class FakeService:
        def __init__(self, _session, _settings) -> None:
            pass

        def run_backfill(self, asset_id):
            calls["asset_id"] = asset_id
            return _summary()

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "IngestionService", FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", LOG_LEVEL="debug"))

    result = runner.invoke(cli.app, ["backfill", "--asset-id", "7"])

    assert result.exit_code == 0
    assert calls["asset_id"] == 7
    assert "backfill: attempted=1 succeeded=1 failed=0 upserted=10 deleted=2" in result.stdout


def test_cli_sync_runs_service(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    @contextmanager
    def fake_scope():
        yield object()

    class FakeService:
        def __init__(self, _session, _settings) -> None:
            pass

        def run_sync(self, asset_id):
            calls["asset_id"] = asset_id
            return _summary()

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "IngestionService", FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x"))

    result = runner.invoke(cli.app, ["sync"])

    assert result.exit_code == 0
    assert calls["asset_id"] is None
    assert "sync: attempted=1 succeeded=1 failed=0 upserted=10 deleted=2" in result.stdout


def test_cli_reprocess_runs_service(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    @contextmanager
    def fake_scope():
        yield object()

    class FakeService:
        def __init__(self, _session, _settings) -> None:
            pass

        def run_reprocess(self, asset_id):
            calls["asset_id"] = asset_id
            return _summary()

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "IngestionService", FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x"))

    result = runner.invoke(cli.app, ["reprocess", "--asset-id", "9"])

    assert result.exit_code == 0
    assert calls["asset_id"] == 9
    assert "reprocess: attempted=1 succeeded=1 failed=0 upserted=10 deleted=2" in result.stdout


def test_cli_symbols_prints_available_symbols(monkeypatch) -> None:
    runner = CliRunner()

    @contextmanager
    def fake_scope():
        yield object()

    class FakePriceService:
        def __init__(self, _repo, chart_timezone: str) -> None:
            assert chart_timezone == "UTC"

        def list_symbols(self) -> list[str]:
            return ["BTCUSDT", "EURUSD"]

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", FakePriceService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))

    result = runner.invoke(cli.app, ["symbols"])

    assert result.exit_code == 0
    assert "BTCUSDT" in result.stdout
    assert "EURUSD" in result.stdout


def test_cli_plot_price_calls_chart_service(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    @contextmanager
    def fake_scope():
        yield object()

    class FakePriceService:
        def __init__(self, _repo, chart_timezone: str) -> None:
            assert chart_timezone == "UTC"

        def plot_price(self, **kwargs):
            calls.update(kwargs)
            return [object(), object()]

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", FakePriceService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))

    result = runner.invoke(
        cli.app,
        [
            "plot-price",
            "--symbol",
            "EURUSD",
            "--timeframe",
            "3m",
            "--candles",
            "200",
            "--show",
            "False",
        ],
    )

    assert result.exit_code == 0
    assert calls["symbol"] == "EURUSD"
    assert calls["timeframe"] == "3m"
    assert calls["candles"] == 200
    assert calls["show"] is False
    assert "plot-price: symbol=EURUSD timeframe=3m requested=200 returned=2" in result.stdout
