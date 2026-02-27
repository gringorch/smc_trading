"""Declarative strategy definitions and backtesting contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StrategyTimeframes:
    htf: str
    ltf_default: str
    ltf_trend: str


@dataclass(frozen=True)
class ContextFilters:
    allowed_market_states: tuple[str, ...] = ()
    required_poi_kinds: tuple[str, ...] = ("FVG", "SWEEP_HIGH", "SWEEP_LOW", "FIB_DISCOUNT")
    max_distance_to_poi: float | None = None


@dataclass(frozen=True)
class TriggerRule:
    event_kind: str
    direction: str


@dataclass(frozen=True)
class RiskRules:
    stop_loss_pct: float = 0.003
    take_profit_pct: float = 0.006


@dataclass(frozen=True)
class ExecutionRules:
    entry_mode: str = "next_open"
    fee_bps: float = 0.0
    slippage_bps: float = 0.0


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    version: str
    description: str
    timeframes: StrategyTimeframes
    context_filters: ContextFilters = field(default_factory=ContextFilters)
    trigger_rules: tuple[TriggerRule, ...] = ()
    risk_rules: RiskRules = field(default_factory=RiskRules)
    execution_rules: ExecutionRules = field(default_factory=ExecutionRules)


@dataclass(frozen=True)
class TradeIntent:
    ts: datetime
    direction: str
    entry_ref: float
    sl: float
    tp: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeResult:
    entry_ts: datetime
    entry_price: float
    exit_ts: datetime
    exit_price: float
    direction: str
    qty: float
    pnl_gross: float
    pnl_net: float
    exit_reason: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestSummary:
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    pnl_gross: float
    pnl_net: float
    profit_factor: float
    max_drawdown: float


@dataclass(frozen=True)
class BacktestReport:
    strategy_id: str
    period_start: datetime | None
    period_end: datetime | None
    summary: BacktestSummary
    trades: tuple[TradeResult, ...]


def _require(payload: dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise ValueError(f"missing required key: '{key}'")
    return payload[key]


def _as_tuple_strings(value: Any, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"'{key}' must be a list of strings")
    if not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{key}' must contain only strings")
    return tuple(value)


def parse_strategy_definition(payload: dict[str, Any]) -> StrategyDefinition:
    name = _require(payload, "name")
    version = _require(payload, "version")
    description = payload.get("description", "")
    if (
        not isinstance(name, str)
        or not isinstance(version, str)
        or not isinstance(description, str)
    ):
        raise ValueError("'name', 'version' and 'description' must be strings")

    tf = _require(payload, "timeframes")
    if not isinstance(tf, dict):
        raise ValueError("'timeframes' must be an object")

    timeframes = StrategyTimeframes(
        htf=str(_require(tf, "htf")),
        ltf_default=str(_require(tf, "ltf_default")),
        ltf_trend=str(_require(tf, "ltf_trend")),
    )

    context_raw = payload.get("context_filters", {})
    if not isinstance(context_raw, dict):
        raise ValueError("'context_filters' must be an object")

    context_filters = ContextFilters(
        allowed_market_states=_as_tuple_strings(
            context_raw.get("allowed_market_states", []),
            "context_filters.allowed_market_states",
        ),
        required_poi_kinds=_as_tuple_strings(
            context_raw.get(
                "required_poi_kinds", ["FVG", "SWEEP_HIGH", "SWEEP_LOW", "FIB_DISCOUNT"]
            ),
            "context_filters.required_poi_kinds",
        ),
        max_distance_to_poi=(
            float(context_raw["max_distance_to_poi"])
            if context_raw.get("max_distance_to_poi") is not None
            else None
        ),
    )

    triggers_raw = payload.get("trigger_rules", [])
    if not isinstance(triggers_raw, list) or not triggers_raw:
        raise ValueError("'trigger_rules' must be a non-empty list")

    trigger_rules: list[TriggerRule] = []
    for i, rule in enumerate(triggers_raw):
        if not isinstance(rule, dict):
            raise ValueError(f"trigger_rules[{i}] must be an object")
        trigger_rules.append(
            TriggerRule(
                event_kind=str(_require(rule, "event_kind")),
                direction=str(_require(rule, "direction")),
            )
        )

    risk_raw = payload.get("risk_rules", {})
    if not isinstance(risk_raw, dict):
        raise ValueError("'risk_rules' must be an object")
    risk_rules = RiskRules(
        stop_loss_pct=float(risk_raw.get("stop_loss_pct", 0.003)),
        take_profit_pct=float(risk_raw.get("take_profit_pct", 0.006)),
    )

    exec_raw = payload.get("execution_rules", {})
    if not isinstance(exec_raw, dict):
        raise ValueError("'execution_rules' must be an object")
    execution_rules = ExecutionRules(
        entry_mode=str(exec_raw.get("entry_mode", "next_open")),
        fee_bps=float(exec_raw.get("fee_bps", 0.0)),
        slippage_bps=float(exec_raw.get("slippage_bps", 0.0)),
    )

    return StrategyDefinition(
        name=name,
        version=version,
        description=description,
        timeframes=timeframes,
        context_filters=context_filters,
        trigger_rules=tuple(trigger_rules),
        risk_rules=risk_rules,
        execution_rules=execution_rules,
    )


def load_strategy_definition(path: str | Path) -> StrategyDefinition:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"strategy file not found: {file_path}")

    text = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        payload = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        import yaml

        payload = yaml.safe_load(text)
    else:
        raise ValueError("strategy file must be .json, .yaml, or .yml")

    if not isinstance(payload, dict):
        raise ValueError("strategy file root must be an object")

    return parse_strategy_definition(payload)
