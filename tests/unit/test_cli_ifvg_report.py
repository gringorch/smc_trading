from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from typer.testing import CliRunner

from cli import ingestion_commands as cli
from config.settings import Settings


def test_cli_ifvg_report_writes_html(monkeypatch) -> None:
    runner = CliRunner()

    @contextmanager
    def fake_scope():
        yield object()

    class _FakeService:
        def __init__(self, _repo, chart_timezone: str) -> None:
            assert chart_timezone == "UTC"

        def get_price_bars(self, **_kwargs):
            class _Bar:
                timestamp_utc = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

            return [_Bar()]

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", _FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))
    monkeypatch.setattr(cli, "detect_ifvgs", lambda **_kwargs: [])
    monkeypatch.setattr(cli, "build_ifvg_report_html", lambda **_kwargs: "<html>ifvg</html>")

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.app,
            [
                "ifvg-report",
                "--symbol",
                "EURUSD",
                "--ltf-timeframe",
                "1m",
                "--candles",
                "20",
                "--output",
                "out.html",
            ],
        )

        assert result.exit_code == 0
        with open("out.html", encoding="utf-8") as f:
            assert f.read() == "<html>ifvg</html>"
        assert "ifvg-report: output=out.html symbol=EURUSD timeframe=1m signals=0" in result.stdout


def test_cli_ifvg_report_uses_expected_defaults(monkeypatch) -> None:
    runner = CliRunner()
    calls: dict[str, object] = {}

    @contextmanager
    def fake_scope():
        yield object()

    class _FakeService:
        def __init__(self, _repo, chart_timezone: str) -> None:
            assert chart_timezone == "UTC"

        def get_price_bars(self, **_kwargs):
            class _Bar:
                timestamp_utc = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

            return [_Bar()]

    def _fake_detect_ifvgs(**kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", _FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))
    monkeypatch.setattr(cli, "detect_ifvgs", _fake_detect_ifvgs)
    monkeypatch.setattr(cli, "build_ifvg_report_html", lambda **_kwargs: "<html>ifvg</html>")

    with runner.isolated_filesystem():
        result = runner.invoke(cli.app, ["ifvg-report", "--symbol", "EURUSD"])

        assert result.exit_code == 0
        config = calls["config"]
        assert config.min_gap_size == Decimal("0.00005")
        assert config.max_bars_from_fvg_formation_to_inversion == 5
        assert config.displacement_min_body_pct == Decimal("0.7")


def test_cli_ifvg_report_rejects_invalid_timeframe(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))

    result = runner.invoke(
        cli.app,
        ["ifvg-report", "--symbol", "EURUSD", "--ltf-timeframe", "15m"],
    )

    assert result.exit_code == 2
