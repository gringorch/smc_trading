from __future__ import annotations

from datetime import UTC, datetime

from strategy.definitions import parse_strategy_definition
from strategy.engine import evaluate_strategy
from strategy.events import Direction, Event, EventKind


def test_evaluate_strategy_generates_intent() -> None:
    definition = parse_strategy_definition(
        {
            "name": "ifvg_poi",
            "version": "1.0.0",
            "description": "test",
            "timeframes": {"htf": "1h", "ltf_default": "3m", "ltf_trend": "1m"},
            "context_filters": {"required_poi_kinds": ["FVG"]},
            "trigger_rules": [{"event_kind": "IFVG", "direction": "bull"}],
        }
    )

    ts = datetime(2026, 1, 1, tzinfo=UTC)
    htf_events = [
        Event(kind=EventKind.FVG, direction=Direction.BULL, ts=ts, price_low=1.0, price_high=1.2),
    ]
    ltf_events = [
        Event(kind=EventKind.IFVG, direction=Direction.BULL, ts=ts, price_low=1.1, price_high=1.15),
    ]

    intents = evaluate_strategy(htf_events, ltf_events, definition)

    assert len(intents) == 1
    assert intents[0].direction == "long"
