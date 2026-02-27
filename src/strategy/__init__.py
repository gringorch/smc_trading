"""Strategy package for SMC event detection."""

from strategy.definitions import (
    BacktestReport,
    BacktestSummary,
    StrategyDefinition,
    TradeIntent,
    TradeResult,
    load_strategy_definition,
    parse_strategy_definition,
)
from strategy.engine import evaluate_strategy
from strategy.events import Event, EventKind, MarketState, StrategyConfig
from strategy.service import AnalysisResult, analyze, analyze_adaptive, analyze_multi_tf

__all__ = [
    "AnalysisResult",
    "BacktestReport",
    "BacktestSummary",
    "Event",
    "EventKind",
    "MarketState",
    "StrategyConfig",
    "StrategyDefinition",
    "TradeIntent",
    "TradeResult",
    "evaluate_strategy",
    "load_strategy_definition",
    "parse_strategy_definition",
    "analyze",
    "analyze_adaptive",
    "analyze_multi_tf",
]
