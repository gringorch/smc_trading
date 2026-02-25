from __future__ import annotations

import runpy


def test_main_module_invokes_cli_app(monkeypatch) -> None:
    called = {"value": False}
    monkeypatch.setattr("cli.ingestion_commands.app", lambda: called.__setitem__("value", True))

    runpy.run_module("main", run_name="__main__")

    assert called["value"] is True

