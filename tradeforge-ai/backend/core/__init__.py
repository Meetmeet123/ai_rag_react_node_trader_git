"""
TradeForge AI — Core LLM Engine Package

Provides natural-language-to-strategy conversion, backtest analysis,
and trading-aware chat capabilities.

Modules:
    llm_engine: Main LLM engine with StrategyOutput, LLMEngine, and StrategyLLM
"""

from core.llm_engine import (
    Action,
    Condition,
    LLMEngine,
    PositionSizingConfig,
    StopLossConfig,
    StrategyLLM,
    StrategyOutput,
    TargetConfig,
    format_strategy_for_display,
    merge_strategies,
    validate_strategy,
)

__all__ = [
    "LLMEngine",
    "StrategyLLM",
    "StrategyOutput",
    "Condition",
    "StopLossConfig",
    "TargetConfig",
    "PositionSizingConfig",
    "format_strategy_for_display",
    "merge_strategies",
    "validate_strategy",
    "Action",
]
