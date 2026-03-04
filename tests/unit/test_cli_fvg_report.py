from __future__ import annotations

from contextlib import contextmanager

from typer.testing import CliRunner

from config.settings import Settings
from cli import ingestion_commands as cli


def test_cli_fvg_report_writes_html(monkeypatch) -> None:
    runner = CliRunner()

    @contextmanager
    def fake_scope():
        yield object()

    class _FakeService:
        def __init__(self, _repo, chart_timezone: str) -> None:
            assert chart_timezone == "UTC"

        def get_price_bars(self, **_kwargs):
            class _Bar:
                timestamp_utc = "2026-01-01T00:00:00Z"

            return [_Bar()]

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", _FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))
    monkeypatch.setattr(cli, "detect_fvgs", lambda **_kwargs: [])
    monkeypatch.setattr(cli, "build_fvg_report_html", lambda **_kwargs: "<html>ok</html>")

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.app,
            [
                "fvg-report",
                "--symbol",
                "EURUSD",
                "--timeframe",
                "1h",
                "--candles",
                "10",
                "--output",
                "out.html",
            ],
        )

        assert result.exit_code == 0
        with open("out.html", encoding="utf-8") as f:
            assert f.read() == "<html>ok</html>"
        assert "fvg-report: output=out.html symbol=EURUSD timeframe=1h signals=0" in result.stdout


def test_cli_fvg_report_writes_default_output_in_reports_dir(monkeypatch) -> None:
    runner = CliRunner()

    @contextmanager
    def fake_scope():
        yield object()

    class _FakeService:
        def __init__(self, _repo, chart_timezone: str) -> None:
            assert chart_timezone == "UTC"

        def get_price_bars(self, **_kwargs):
            class _Bar:
                timestamp_utc = "2026-01-01T00:00:00Z"

            return [_Bar()]

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", _FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))
    monkeypatch.setattr(cli, "detect_fvgs", lambda **_kwargs: [])
    monkeypatch.setattr(cli, "build_fvg_report_html", lambda **_kwargs: "<html>ok</html>")

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.app,
            [
                "fvg-report",
                "--symbol",
                "EURUSD",
                "--timeframe",
                "1h",
                "--candles",
                "10",
            ],
        )

        assert result.exit_code == 0
        with open("reports/fvg_report.html", encoding="utf-8") as f:
            assert f.read() == "<html>ok</html>"
        assert "fvg-report: output=reports/fvg_report.html symbol=EURUSD timeframe=1h signals=0" in result.stdout
