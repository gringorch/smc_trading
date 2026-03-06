from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from typer.testing import CliRunner

from cli import ingestion_commands as cli
from config.settings import Settings
from indicators.htf_poi import HtfPoiConfig


def test_cli_htf_poi_report_writes_html(monkeypatch) -> None:
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
        result = runner.invoke(
            cli.app,
            [
                "htf-poi-report",
                "--symbol",
                "EURUSD",
                "--htf-timeframe",
                "1h",
                "--candles",
                "20",
                "--swing-left",
                "3",
                "--swing-right",
                "2",
                "--bos-buffer",
                "0.5",
                "--min-gap-size",
                "0.001",
                "--poi-expiration-rule",
                "bars_since_creation",
                "--poi-validity-bars",
                "4",
                "--max-dynamic-extension-bars",
                "3",
                "--dynamic-width-source",
                "body",
                "--output",
                "out.html",
            ],
        )

        assert result.exit_code == 0
        config = calls["config"]
        assert isinstance(config, HtfPoiConfig)
        assert config.swing_left == 3
        assert config.swing_right == 2
        assert config.bos_buffer == Decimal("0.5")
        assert config.min_gap_size == Decimal("0.001")
        assert config.poi_expiration_rule == "bars_since_creation"
        assert config.poi_validity_bars == 4
        assert config.poi_dynamic_width_enabled is True
        assert config.max_dynamic_extension_bars == 3
        assert config.dynamic_width_source == "body"
        assert config.replay_context is True
        with open("out.html", encoding="utf-8") as f:
            assert f.read() == "<html>htf-poi</html>"
        expected = (
            "htf-poi-report: output=out.html symbol=EURUSD timeframe=1h "
            "pois=0 active=0 bias=bull"
        )
        assert expected in result.stdout
