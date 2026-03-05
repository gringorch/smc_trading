from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from typer.testing import CliRunner

from cli import ingestion_commands as cli
from config.settings import Settings


def test_cli_structure_report_writes_html(monkeypatch) -> None:
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

    def _fake_analyze_structure(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            swings=[],
            bos_events=[],
            state=SimpleNamespace(current_bias="neutral"),
        )

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", _FakeService)
    monkeypatch.setattr(
        cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC")
    )
    monkeypatch.setattr(cli, "analyze_structure", _fake_analyze_structure)
    monkeypatch.setattr(
        cli, "build_structure_report_html", lambda **_kwargs: "<html>structure</html>"
    )

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.app,
            [
                "structure-report",
                "--symbol",
                "EURUSD",
                "--timeframe",
                "1h",
                "--candles",
                "20",
                "--swing-left",
                "3",
                "--swing-right",
                "2",
                "--bos-buffer",
                "0.5",
                "--output",
                "out.html",
            ],
        )

        assert result.exit_code == 0
        config = calls["config"]
        assert config.swing_left == 3
        assert config.swing_right == 2
        assert config.bos_buffer == Decimal("0.5")
        with open("out.html", encoding="utf-8") as f:
            assert f.read() == "<html>structure</html>"
        expected = (
            "structure-report: output=out.html symbol=EURUSD "
            "timeframe=1h swings=0 bos=0 bias=neutral"
        )
        assert (
            expected
            in result.stdout
        )
