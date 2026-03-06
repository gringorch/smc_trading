from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

from typer.testing import CliRunner

from cli import ingestion_commands as cli
from config.settings import Settings


def test_cli_htf_poi_report_yaml_writes_html(monkeypatch) -> None:
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

    def _fake_detect_htf_pois(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(current_bias="bull", poi_candidates=[], active_poi=None, dealing_range=None)

    monkeypatch.setattr(cli, "session_scope", fake_scope)
    monkeypatch.setattr(cli, "PriceChartService", _FakeService)
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(DB_PASSWORD="x", CHART_TIMEZONE="UTC"))
    monkeypatch.setattr(cli, "detect_htf_pois", _fake_detect_htf_pois)
    monkeypatch.setattr(cli, "build_htf_poi_report_html", lambda **_kwargs: "<html>htf-poi</html>")

    with runner.isolated_filesystem():
        with open("cfg.yaml", "w", encoding="utf-8") as f:
            f.write(
                "symbol: EURUSD\n"
                "htf_timeframe: 1h\n"
                "candles: 20\n"
                "output: out.html\n"
                "htf_poi:\n"
                "  poi_activation_rule: close_inside\n"
                "  replay_context: true\n"
            )

        result = runner.invoke(cli.app, ["htf-poi-report-yaml", "--config-file", "cfg.yaml"])

        assert result.exit_code == 0
        assert calls["config"].poi_activation_rule == "close_inside"
        assert calls["config"].replay_context is True
        with open("out.html", encoding="utf-8") as f:
            assert f.read() == "<html>htf-poi</html>"
        assert "htf-poi-report-yaml: output=out.html symbol=EURUSD timeframe=1h" in result.stdout


def test_cli_htf_poi_report_yaml_requires_symbol(monkeypatch) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("cfg.yaml", "w", encoding="utf-8") as f:
            f.write("htf_timeframe: 1h\n")

        result = runner.invoke(cli.app, ["htf-poi-report-yaml", "--config-file", "cfg.yaml"])
        assert result.exit_code != 0
        message = result.stdout
        if result.exception is not None:
            message = f"{message}\n{result.exception}"
        assert ("YAML field 'symbol' is required" in message) or (result.exit_code == 2)
