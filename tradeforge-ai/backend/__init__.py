"""
TradeForge AI — Backend Package

Custom LLM Engine for converting natural language trading ideas into
executable strategies. Includes dataset building, fine-tuning pipelines,
and reinforcement learning for trade execution optimization.

Quick Start:
    >>> from core.llm_engine import LLMEngine, StrategyLLM
    >>> engine = LLMEngine()
    >>> strategy = engine.generate_strategy("Buy Nifty when RSI < 30")
    >>> print(strategy.to_json())
"""

__version__ = "0.1.0"
__author__ = "TradeForge AI Team"
