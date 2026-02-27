"""Declarative strategy evaluation on precomputed events."""

from __future__ import annotations

from strategy.definitions import StrategyDefinition, TradeIntent
from strategy.events import Event

_POI_KINDS = {"FVG", "SWEEP_HIGH", "SWEEP_LOW", "FIB_DISCOUNT", "FIB_PREMIUM"}


def _event_kind_name(event: Event) -> str:
    return event.kind.value if hasattr(event.kind, "value") else str(event.kind)


def _event_direction_name(event: Event) -> str:
    return event.direction.value if hasattr(event.direction, "value") else str(event.direction)


def _event_price(event: Event) -> float | None:
    if event.price is not None:
        return float(event.price)
    if event.price_low is not None and event.price_high is not None:
        return float(event.price_low + event.price_high) / 2.0
    return None


def _distance_to_poi(trigger_price: float, poi: Event) -> float | None:
    if poi.price_low is not None and poi.price_high is not None:
        low = float(poi.price_low)
        high = float(poi.price_high)
        if low <= trigger_price <= high:
            return 0.0
        return min(abs(trigger_price - low), abs(trigger_price - high))

    if poi.price is not None:
        return abs(trigger_price - float(poi.price))
    return None


def evaluate_strategy(
    events_htf: list[Event],
    events_ltf: list[Event],
    strategy_def: StrategyDefinition,
    *,
    market_state: str | None = None,
) -> list[TradeIntent]:
    if (
        strategy_def.context_filters.allowed_market_states
        and market_state not in strategy_def.context_filters.allowed_market_states
    ):
        return []

    poi_events = [
        event
        for event in events_htf
        if _event_kind_name(event) in strategy_def.context_filters.required_poi_kinds
        or _event_kind_name(event) in _POI_KINDS
    ]

    intents: list[TradeIntent] = []
    for trigger in events_ltf:
        trigger_kind = _event_kind_name(trigger)
        trigger_direction = _event_direction_name(trigger)
        if trigger.ts is None:
            continue

        matched_rule = next(
            (
                rule
                for rule in strategy_def.trigger_rules
                if rule.event_kind == trigger_kind and rule.direction == trigger_direction
            ),
            None,
        )
        if matched_rule is None:
            continue

        trigger_price = _event_price(trigger)
        if trigger_price is None:
            continue

        nearest_poi: Event | None = None
        nearest_distance: float | None = None
        for poi in poi_events:
            distance = _distance_to_poi(trigger_price, poi)
            if distance is None:
                continue
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_poi = poi

        max_distance = strategy_def.context_filters.max_distance_to_poi
        if max_distance is not None and (
            nearest_distance is None or nearest_distance > max_distance
        ):
            continue

        if trigger_direction == "bull":
            sl = trigger_price * (1.0 - strategy_def.risk_rules.stop_loss_pct)
            tp = trigger_price * (1.0 + strategy_def.risk_rules.take_profit_pct)
            side = "long"
        else:
            sl = trigger_price * (1.0 + strategy_def.risk_rules.stop_loss_pct)
            tp = trigger_price * (1.0 - strategy_def.risk_rules.take_profit_pct)
            side = "short"

        intents.append(
            TradeIntent(
                ts=trigger.ts,
                direction=side,
                entry_ref=trigger_price,
                sl=sl,
                tp=tp,
                meta={
                    "trigger_kind": trigger_kind,
                    "trigger_direction": trigger_direction,
                    "matched_rule": {
                        "event_kind": matched_rule.event_kind,
                        "direction": matched_rule.direction,
                    },
                    "nearest_poi_kind": _event_kind_name(nearest_poi)
                    if nearest_poi is not None
                    else None,
                    "nearest_poi_ts": nearest_poi.ts if nearest_poi is not None else None,
                    "distance_to_poi": nearest_distance,
                },
            )
        )

    return intents
