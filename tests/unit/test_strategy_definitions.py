from __future__ import annotations

from strategy.definitions import load_strategy_definition, parse_strategy_definition


def test_parse_strategy_definition_minimal() -> None:
    definition = parse_strategy_definition(
        {
            "name": "ifvg_poi",
            "version": "1.0.0",
            "description": "test",
            "timeframes": {"htf": "1h", "ltf_default": "3m", "ltf_trend": "1m"},
            "trigger_rules": [{"event_kind": "IFVG", "direction": "bull"}],
        }
    )

    assert definition.name == "ifvg_poi"
    assert definition.timeframes.htf == "1h"
    assert definition.trigger_rules[0].event_kind == "IFVG"


def test_load_strategy_definition_yaml(tmp_path) -> None:
    file_path = tmp_path / "strategy.yaml"
    file_path.write_text(
        """
name: sample
version: 1.0.0
description: sample strategy
timeframes:
  htf: 1h
  ltf_default: 3m
  ltf_trend: 1m
trigger_rules:
  - event_kind: IFVG
    direction: bull
""".strip(),
        encoding="utf-8",
    )

    definition = load_strategy_definition(file_path)
    assert definition.name == "sample"
