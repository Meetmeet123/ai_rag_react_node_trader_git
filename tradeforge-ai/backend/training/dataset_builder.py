"""
Dataset Builder for Fine-tuning the Trading LLM

Builds training datasets from multiple sources:
1. Historical strategies with backtest results
2. NL-to-strategy prompt-response pairs
3. Market data with indicator contexts
4. Backtest analysis examples
5. Multi-language prompts (English + Hindi)

Produces HuggingFace ``datasets.Dataset`` objects ready for the trainer.

Dependencies:
    datasets>=2.12.0
    pandas>=2.0.0
    loguru>=0.7.0
"""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd
from loguru import logger

# Lazy import — heavy dependency only loaded when actually used
Dataset: Any = None


def _load_datasets() -> None:
    """Lazy-load the ``datasets`` library on first use."""
    global Dataset
    if Dataset is not None:
        return
    from datasets import Dataset as _Dataset
    Dataset = _Dataset
    logger.debug("datasets library loaded.")


# =============================================================================
# StrategyDatasetBuilder  —  prompt-response pairs for supervised fine-tuning
# =============================================================================


class StrategyDatasetBuilder:
    """
    Build training datasets from strategy definitions and NL prompts.

    The core output is a HuggingFace ``Dataset`` of text sequences where each
    example has a single ``text`` field formatted as:

    .. code-block:: text

        System: <task-specific system prompt>
        User: <natural language prompt>
        Assistant: <expected JSON response>

    This format is compatible with causal-LM fine-tuning (DialoGPT, GPT-2, etc.)
    """

    # System prompts for different task types
    _STRATEGY_SYSTEM: str = (
        "You are TradeForge AI, an expert quantitative trading strategy designer. "
        "Convert the user's natural-language trading idea into a precise JSON strategy. "
        "Rules: 1) Extract instrument, timeframe, entry/exit conditions, stop-loss and target. "
        "2) Use only well-known technical indicators (rsi, sma, ema, macd, bollinger, atr, vwap). "
        "3) Output ONLY valid JSON. 4) Include a short 'reasoning' field."
    )

    _ANALYSIS_SYSTEM: str = (
        "You are TradeForge AI, a senior quantitative analyst. "
        "Analyze the provided backtest results and give actionable improvement suggestions. "
        "Focus on win-rate optimization, drawdown reduction, and risk-adjusted returns."
    )

    _EXPLAIN_SYSTEM: str = (
        "You are TradeForge AI, a trading educator. "
        "Explain the given trading strategy in simple, friendly language."
    )

    def __init__(
        self,
        max_length: int = 512,
        validation_split: float = 0.1,
        random_seed: int = 42,
    ) -> None:
        """
        Parameters
        ----------
        max_length:
            Maximum sequence length per training example.
        validation_split:
            Fraction of data held out for validation (0.0 – 1.0).
        random_seed:
            Reproducibility seed.
        """
        self.max_length = max_length
        self.validation_split = validation_split
        self.random_seed = random_seed
        self._cached_pairs: Optional[List[Dict[str, str]]] = None
        logger.info(
            f"StrategyDatasetBuilder initialised — max_length={max_length}, "
            f"val_split={validation_split}"
        )

    # ------------------------------------------------------------------
    # Public builders
    # ------------------------------------------------------------------

    def build_from_strategies(self, strategies: List[Dict[str, Any]]) -> "Dataset":
        """
        Build a training dataset from existing strategy dictionaries.

        Each strategy dict should contain at least ``strategy_name``,
        ``description``, ``entry_conditions``, etc.

        Parameters
        ----------
        strategies:
            List of strategy definition dictionaries.

        Returns
        -------
        datasets.Dataset
            HuggingFace Dataset ready for training.
        """
        _load_datasets()
        logger.info(f"Building dataset from {len(strategies)} strategies ...")

        pairs: List[Dict[str, str]] = []
        for strat in strategies:
            prompt = self._strategy_to_prompt(strat)
            response = json.dumps(strat, indent=2, ensure_ascii=False)
            pairs.append({"prompt": prompt, "response": response})

        return self._pairs_to_dataset(pairs)

    def build_from_backtests(
        self,
        backtest_results: List[Dict[str, Any]],
    ) -> "Dataset":
        """
        Build a dataset of backtest → analysis pairs.

        Parameters
        ----------
        backtest_results:
            Each dict should contain metrics like ``total_return``,
            ``sharpe_ratio``, ``max_drawdown``, ``win_rate``, etc.

        Returns
        -------
        datasets.Dataset
        """
        _load_datasets()
        logger.info(f"Building dataset from {len(backtest_results)} backtest results ...")

        pairs: List[Dict[str, str]] = []
        for bt in backtest_results:
            prompt = self._backtest_to_prompt(bt)
            response = self._generate_reference_analysis(bt)
            pairs.append({"prompt": prompt, "response": response})

        return self._pairs_to_dataset(pairs)

    def create_training_pairs(self) -> List[Dict[str, str]]:
        """
        Create a comprehensive set of prompt-response training pairs.

        Returns
        -------
        List[Dict[str, str]]
            List of ``{"prompt": ..., "response": ...}`` dictionaries.
        """
        if self._cached_pairs is not None:
            return self._cached_pairs

        pairs: List[Dict[str, str]] = []
        pairs.extend(self._create_strategy_generation_pairs())
        pairs.extend(self._create_backtest_analysis_pairs())
        pairs.extend(self._create_explanation_pairs())
        pairs.extend(self._create_hindi_prompt_pairs())
        pairs.extend(self._create_complex_strategy_pairs())

        logger.info(f"Created {len(pairs)} total training pairs.")
        self._cached_pairs = pairs
        return pairs

    def build_full_dataset(self) -> "Dataset":
        """
        Build the complete training dataset from all built-in pairs.

        Convenience method that calls ``create_training_pairs`` and converts
        the result to a HuggingFace ``Dataset``.

        Returns
        -------
        datasets.Dataset
        """
        pairs = self.create_training_pairs()
        return self._pairs_to_dataset(pairs)

    # ------------------------------------------------------------------
    # Strategy generation pairs  (NL → Strategy JSON)
    # ------------------------------------------------------------------

    def _create_strategy_generation_pairs(self) -> List[Dict[str, str]]:
        """
        Create 60+ NL prompt → Strategy JSON pairs covering diverse scenarios.

        Covers: multiple indicators, instruments, timeframes, segments,
        and risk-management styles.
        """
        pairs: List[Dict[str, str]] = [
            # ── RSI strategies ──────────────────────────────────────────
            {
                "prompt": "Create a strategy to buy Nifty when RSI goes below 30 and sell when it goes above 70",
                "response": json.dumps({
                    "strategy_name": "RSI Mean Reversion Nifty",
                    "description": "Classic RSI mean-reversion strategy: buy oversold, sell overbought on Nifty 15m.",
                    "instrument": "NIFTY50",
                    "segment": "equity",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 70}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.0},
                    "target": {"type": "fixed_pct", "value": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.85,
                    "reasoning": "RSI mean-reversion is a well-documented edge on equity indices.",
                }),
            },
            {
                "prompt": "Short Bank Nifty when RSI is above 80 on 5 minute chart with 1.5% stop loss",
                "response": json.dumps({
                    "strategy_name": "RSI Overbought BNF Short",
                    "description": "Short BANKNIFTY when RSI enters extreme overbought territory.",
                    "instrument": "BANKNIFTY",
                    "segment": "futures",
                    "timeframe": "5m",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 80}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 50}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.5},
                    "target": {"type": "fixed_pct", "value": 4.0},
                    "position_sizing": {"type": "pct_capital", "value": 15},
                    "confidence": 0.82,
                    "reasoning": "Extreme RSI readings above 80 often precede pullbacks in BANKNIFTY.",
                }),
            },
            {
                "prompt": "Buy Reliance when RSI 7 drops below 25 with 2% target and 0.8% stop loss",
                "response": json.dumps({
                    "strategy_name": "RSI-7 Deep Oversold RELIANCE",
                    "description": "Aggressive mean-reversion on RELIANCE using shorter RSI period for faster signals.",
                    "instrument": "RELIANCE",
                    "segment": "equity",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 7, "condition": "<", "value": 25}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 7, "condition": ">", "value": 60}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 0.8},
                    "target": {"type": "fixed_pct", "value": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 8},
                    "confidence": 0.78,
                    "reasoning": "Shorter RSI period captures faster reversals on large-cap stocks.",
                }),
            },

            # ── SMA / EMA crossover strategies ──────────────────────────
            {
                "prompt": "Buy when 20 SMA crosses above 50 SMA on daily chart of TCS with trailing stop",
                "response": json.dumps({
                    "strategy_name": "SMA Golden Cross TCS",
                    "description": "Trend-following strategy using 20/50 SMA golden cross on TCS daily.",
                    "instrument": "TCS",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "sma", "period": 20, "condition": "crosses_above", "value": 50}
                    ],
                    "exit_conditions": [
                        {"indicator": "sma", "period": 20, "condition": "crosses_below", "value": 50}
                    ],
                    "stop_loss": {"type": "trailing", "value": 3.0, "trail_pct": 1.5},
                    "target": {"type": "trailing", "value": 8.0, "trail_pct": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 12},
                    "confidence": 0.88,
                    "reasoning": "SMA crossovers are robust trend signals on large-cap daily charts.",
                }),
            },
            {
                "prompt": "Short HDFC Bank when 9 EMA crosses below 21 EMA on 1 hour chart",
                "response": json.dumps({
                    "strategy_name": "EMA Death Cross HDFCBANK",
                    "description": "Short-term trend reversal using 9/21 EMA crossover on HDFCBANK hourly.",
                    "instrument": "HDFCBANK",
                    "segment": "equity",
                    "timeframe": "1h",
                    "entry_conditions": [
                        {"indicator": "ema", "period": 9, "condition": "crosses_below", "value": 21}
                    ],
                    "exit_conditions": [
                        {"indicator": "ema", "period": 9, "condition": "crosses_above", "value": 21}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.2},
                    "target": {"type": "risk_reward", "value": 2.5, "risk_reward_ratio": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.83,
                    "reasoning": "9/21 EMA crossover captures short-term momentum shifts effectively.",
                }),
            },
            {
                "prompt": "Create a strategy using 200 EMA as trend filter with 50 EMA crossovers for entry on INFY",
                "response": json.dumps({
                    "strategy_name": "200 EMA Trend Filter INFY",
                    "description": "Only take 50 EMA crossover signals when aligned with 200 EMA trend direction.",
                    "instrument": "INFY",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "ema", "period": 50, "condition": "crosses_above", "value": 200},
                        {"indicator": "ema", "period": 200, "condition": ">", "value": 0}
                    ],
                    "exit_conditions": [
                        {"indicator": "ema", "period": 50, "condition": "crosses_below", "value": 200}
                    ],
                    "stop_loss": {"type": "atr", "value": 2.0, "atr_multiplier": 2.0},
                    "target": {"type": "risk_reward", "value": 3.0, "risk_reward_ratio": 2.5},
                    "position_sizing": {"type": "pct_capital", "value": 15},
                    "confidence": 0.90,
                    "reasoning": "200 EMA trend filter reduces false signals from 50 EMA crossovers.",
                }),
            },

            # ── MACD strategies ─────────────────────────────────────────
            {
                "prompt": "Buy when MACD line crosses above signal line on 15 minute Nifty chart",
                "response": json.dumps({
                    "strategy_name": "MACD Bullish Cross Nifty",
                    "description": "Momentum entry using MACD bullish crossover on Nifty 15m.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "crosses_above", "value": 0}
                    ],
                    "exit_conditions": [
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "crosses_below", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.0},
                    "target": {"type": "fixed_pct", "value": 3.5},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.85,
                    "reasoning": "MACD crossover captures momentum shifts early on index futures.",
                }),
            },
            {
                "prompt": "Short when MACD histogram turns negative on Bank Nifty hourly with ATR-based stop",
                "response": json.dumps({
                    "strategy_name": "MACD Histogram Reversal BNF",
                    "description": "Short BANKNIFTY when MACD histogram crosses below zero on hourly chart.",
                    "instrument": "BANKNIFTY",
                    "segment": "futures",
                    "timeframe": "1h",
                    "entry_conditions": [
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "<", "value": 0}
                    ],
                    "exit_conditions": [
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": ">", "value": 0}
                    ],
                    "stop_loss": {"type": "atr", "value": 1.5, "atr_multiplier": 1.5},
                    "target": {"type": "risk_reward", "value": 2.5, "risk_reward_ratio": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 12},
                    "confidence": 0.84,
                    "reasoning": "MACD histogram zero-cross is a clean momentum reversal signal.",
                }),
            },

            # ── Bollinger Bands strategies ─────────────────────────────
            {
                "prompt": "Buy when price touches lower Bollinger Band on 15 min chart and RSI is below 35",
                "response": json.dumps({
                    "strategy_name": "BB + RSI Combo Nifty",
                    "description": "Mean-reversion at Bollinger lower band confirmed by oversold RSI.",
                    "instrument": "NIFTY50",
                    "segment": "equity",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "bollinger", "period": 20, "condition": "<", "value": -2},
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 35}
                    ],
                    "exit_conditions": [
                        {"indicator": "bollinger", "period": 20, "condition": ">", "value": 1},
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 60}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.2},
                    "target": {"type": "fixed_pct", "value": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.87,
                    "reasoning": "BB lower band + RSI oversold provides strong mean-reversion edge.",
                }),
            },
            {
                "prompt": "Short when price hits upper Bollinger Band with 2.5 standard deviations on daily SBIN",
                "response": json.dumps({
                    "strategy_name": "BB Upper Band Short SBIN",
                    "description": "Short SBIN when price extends beyond upper Bollinger Band (2.5 std dev).",
                    "instrument": "SBIN",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "bollinger", "period": 20, "condition": ">", "value": 2.5}
                    ],
                    "exit_conditions": [
                        {"indicator": "bollinger", "period": 20, "condition": "<", "value": 0.5}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.5},
                    "target": {"type": "fixed_pct", "value": 4.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.80,
                    "reasoning": "2.5 std dev upper band breach indicates statistically significant overextension.",
                }),
            },

            # ── VWAP strategies ─────────────────────────────────────────
            {
                "prompt": "Buy when price crosses above VWAP with volume 1.5x average on 5 min Nifty",
                "response": json.dumps({
                    "strategy_name": "VWAP Momentum Nifty",
                    "description": "Intraday momentum entry on VWAP breakout with volume confirmation.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "5m",
                    "entry_conditions": [
                        {"indicator": "vwap", "condition": "crosses_above", "value": 0},
                        {"indicator": "volume", "condition": ">", "value": 1.5}
                    ],
                    "exit_conditions": [
                        {"indicator": "vwap", "condition": "crosses_below", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 0.7},
                    "target": {"type": "fixed_pct", "value": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 12},
                    "confidence": 0.86,
                    "reasoning": "VWAP breakouts with volume confirmation are high-probability intraday setups.",
                }),
            },
            {
                "prompt": "Short when price falls below VWAP and volume is above average on Bank Nifty 15 min",
                "response": json.dumps({
                    "strategy_name": "VWAP Breakdown BNF",
                    "description": "Short BANKNIFTY on VWAP breakdown with elevated volume.",
                    "instrument": "BANKNIFTY",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "vwap", "condition": "crosses_below", "value": 0},
                        {"indicator": "volume", "condition": ">", "value": 1.2}
                    ],
                    "exit_conditions": [
                        {"indicator": "vwap", "condition": "crosses_above", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 0.8},
                    "target": {"type": "fixed_pct", "value": 2.5},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.84,
                    "reasoning": "VWAP acts as dynamic support/resistance; breakdown signals institutional selling.",
                }),
            },

            # ── Supertrend strategies ───────────────────────────────────
            {
                "prompt": "Create a supertrend strategy with multiplier 3 and period 10 on 15 min Nifty futures",
                "response": json.dumps({
                    "strategy_name": "Supertrend Follower Nifty",
                    "description": "Trend-following using Supertrend(10,3) on Nifty futures 15m.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "supertrend", "params": {"period": 10, "multiplier": 3},
                         "condition": "==", "value": 1}
                    ],
                    "exit_conditions": [
                        {"indicator": "supertrend", "params": {"period": 10, "multiplier": 3},
                         "condition": "==", "value": -1}
                    ],
                    "stop_loss": {"type": "atr", "value": 2.0, "atr_multiplier": 2.0},
                    "target": {"type": "trailing", "value": 5.0, "trail_pct": 1.5},
                    "position_sizing": {"type": "pct_capital", "value": 15},
                    "confidence": 0.88,
                    "reasoning": "Supertrend(10,3) balances responsiveness and noise reduction on index futures.",
                }),
            },

            # ── Stochastic strategies ───────────────────────────────────
            {
                "prompt": "Buy when stochastic %K crosses above %D below 20 level on daily ITC chart",
                "response": json.dumps({
                    "strategy_name": "Stochastic Bull Cross ITC",
                    "description": "Oversold stochastic bullish crossover on ITC daily chart.",
                    "instrument": "ITC",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "stochastic", "params": {"k_period": 14, "d_period": 3},
                         "condition": "crosses_above", "value": 20}
                    ],
                    "exit_conditions": [
                        {"indicator": "stochastic", "params": {"k_period": 14, "d_period": 3},
                         "condition": "crosses_below", "value": 80}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.5},
                    "target": {"type": "fixed_pct", "value": 4.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.81,
                    "reasoning": "Stochastic bull cross from oversold is a classic reversal signal.",
                }),
            },

            # ── ADX strategies ──────────────────────────────────────────
            {
                "prompt": "Enter trade only when ADX is above 25 with SMA 20 crossovers on 1 hour chart",
                "response": json.dumps({
                    "strategy_name": "ADX Filtered SMA Cross",
                    "description": "Only take SMA crossover signals when ADX confirms a strong trend.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "1h",
                    "entry_conditions": [
                        {"indicator": "adx", "period": 14, "condition": ">", "value": 25},
                        {"indicator": "sma", "period": 20, "condition": "crosses_above", "value": 50}
                    ],
                    "exit_conditions": [
                        {"indicator": "adx", "period": 14, "condition": "<", "value": 20}
                    ],
                    "stop_loss": {"type": "atr", "value": 2.0, "atr_multiplier": 2.0},
                    "target": {"type": "risk_reward", "value": 3.0, "risk_reward_ratio": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 12},
                    "confidence": 0.89,
                    "reasoning": "ADX filter eliminates choppy whipsaw trades during range-bound markets.",
                }),
            },

            # ── Multi-condition strategies ──────────────────────────────
            {
                "prompt": "Buy when RSI below 30, MACD bullish crossover, and price above 200 EMA on daily TCS",
                "response": json.dumps({
                    "strategy_name": "Multi-Filter Bullish TCS",
                    "description": "Confluence of RSI oversold, MACD momentum, and long-term trend alignment.",
                    "instrument": "TCS",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 30},
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "crosses_above", "value": 0},
                        {"indicator": "ema", "period": 200, "condition": ">", "value": 0}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 70},
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "crosses_below", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.5},
                    "target": {"type": "risk_reward", "value": 3.0, "risk_reward_ratio": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 12},
                    "confidence": 0.91,
                    "reasoning": "Multi-indicator conflation significantly improves signal quality.",
                }),
            },
            {
                "prompt": "Create a strategy with RSI divergence, volume spike, and Bollinger Band squeeze breakout",
                "response": json.dumps({
                    "strategy_name": "Volatility Squeeze Breakout",
                    "description": "Combines RSI divergence, volume confirmation, and Bollinger squeeze for breakout timing.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "divergence_bullish", "value": 0},
                        {"indicator": "volume", "condition": ">", "value": 2.0},
                        {"indicator": "bollinger", "period": 20, "condition": ">", "value": 2.0}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 70},
                        {"indicator": "volume", "condition": "<", "value": 0.8}
                    ],
                    "stop_loss": {"type": "atr", "value": 2.0, "atr_multiplier": 2.0},
                    "target": {"type": "fixed_pct", "value": 5.0},
                    "position_sizing": {"type": "pct_capital", "value": 15},
                    "confidence": 0.85,
                    "reasoning": "Bollinger squeeze + volume spike + RSI divergence is a powerful breakout setup.",
                }),
            },

            # ── Forex / Crypto strategies ───────────────────────────────
            {
                "prompt": "Create an RSI mean reversion strategy for EURUSD on 1 hour chart with 0.5% stop loss",
                "response": json.dumps({
                    "strategy_name": "RSI Mean Reversion EURUSD",
                    "description": "RSI mean-reversion on EURUSD hourly with tight risk management.",
                    "instrument": "EURUSD",
                    "segment": "forex",
                    "timeframe": "1h",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 70}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 0.5},
                    "target": {"type": "fixed_pct", "value": 1.5},
                    "position_sizing": {"type": "pct_capital", "value": 5},
                    "confidence": 0.83,
                    "reasoning": "Forex pairs exhibit strong mean-reversion characteristics on RSI extremes.",
                }),
            },
            {
                "prompt": "Buy Bitcoin when EMA 50 crosses above EMA 200 with volume above average on 4 hour",
                "response": json.dumps({
                    "strategy_name": "EMA Golden Cross BTC",
                    "description": "Classic golden cross strategy on BTCUSD 4h with volume confirmation.",
                    "instrument": "BTCUSD",
                    "segment": "crypto",
                    "timeframe": "4h",
                    "entry_conditions": [
                        {"indicator": "ema", "period": 50, "condition": "crosses_above", "value": 200},
                        {"indicator": "volume", "condition": ">", "value": 1.5}
                    ],
                    "exit_conditions": [
                        {"indicator": "ema", "period": 50, "condition": "crosses_below", "value": 200}
                    ],
                    "stop_loss": {"type": "atr", "value": 3.0, "atr_multiplier": 3.0},
                    "target": {"type": "trailing", "value": 15.0, "trail_pct": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 8},
                    "confidence": 0.86,
                    "reasoning": "Golden cross with volume is a strong trend-confirmation signal in crypto.",
                }),
            },

            # ── Options strategies ─────────────────────────────────────
            {
                "prompt": "Create a strategy for buying Nifty call options when RSI is below 30 on daily chart",
                "response": json.dumps({
                    "strategy_name": "Oversold Call Buy Nifty",
                    "description": "Buy ATM/ITM Nifty calls when RSI indicates oversold conditions on daily.",
                    "instrument": "NIFTY50",
                    "segment": "options",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 60}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 50.0},
                    "target": {"type": "fixed_pct", "value": 100.0},
                    "position_sizing": {"type": "risk_based", "value": 2, "risk_per_trade_pct": 2},
                    "confidence": 0.78,
                    "reasoning": "Buying oversold calls captures theta + delta when RSI reverts.",
                }),
            },
            {
                "prompt": "Strategy for selling Bank Nifty puts when VIX is below 15 and RSI above 50",
                "response": json.dumps({
                    "strategy_name": "Low Volatility Put Sell BNF",
                    "description": "Sell OTM BANKNIFTY puts during low volatility with bullish RSI bias.",
                    "instrument": "BANKNIFTY",
                    "segment": "options",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 50},
                        {"indicator": "volume", "condition": "<", "value": 0.8}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 40}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 200.0},
                    "target": {"type": "fixed_pct", "value": 50.0},
                    "position_sizing": {"type": "risk_based", "value": 1, "risk_per_trade_pct": 1},
                    "confidence": 0.75,
                    "reasoning": "Short puts in low-vol regime benefit from volatility expansion.",
                }),
            },

            # ── Additional diverse strategies ───────────────────────────
            {
                "prompt": "Create a gap-up opening strategy for intraday trading on Nifty with 0.5% target",
                "response": json.dumps({
                    "strategy_name": "Gap-Up Momentum Intraday",
                    "description": "Fade the gap or follow gap momentum based on first 15-min candle direction.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "volume", "condition": ">", "value": 2.0},
                        {"indicator": "vwap", "condition": ">", "value": 0}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 75}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 0.5},
                    "target": {"type": "fixed_pct", "value": 1.5},
                    "position_sizing": {"type": "pct_capital", "value": 15},
                    "confidence": 0.72,
                    "reasoning": "Gap openings with volume indicate strong institutional participation.",
                }),
            },
            {
                "prompt": "Mean reversion strategy using ATR bands on Gold XAUUSD daily chart",
                "response": json.dumps({
                    "strategy_name": "ATR Band Mean Reversion Gold",
                    "description": "Buy/sell at ATR-based volatility bands on Gold daily chart.",
                    "instrument": "XAUUSD",
                    "segment": "forex",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "atr", "period": 14, "condition": ">", "value": 1.5},
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 35}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 65}
                    ],
                    "stop_loss": {"type": "atr", "value": 2.0, "atr_multiplier": 2.0},
                    "target": {"type": "fixed_pct", "value": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 8},
                    "confidence": 0.80,
                    "reasoning": "Gold exhibits strong mean-reversion at ATR extremes on daily timeframe.",
                }),
            },
            {
                "prompt": "Buy Adani Enterprises when price breaks above 20-day high with volume confirmation",
                "response": json.dumps({
                    "strategy_name": "20-Day High Breakout ADANIENT",
                    "description": "Momentum breakout on ADANIENT when price makes new 20-day high.",
                    "instrument": "ADANIENT",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "sma", "period": 20, "condition": "crosses_above", "value": 20},
                        {"indicator": "volume", "condition": ">", "value": 1.5}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 80}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 2.0},
                    "target": {"type": "trailing", "value": 10.0, "trail_pct": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.76,
                    "reasoning": "20-day high breakouts capture momentum on volatile stocks.",
                }),
            },
            {
                "prompt": "Create a pairs trading strategy for HDFC Bank and ICICI Bank using 50 SMA spread",
                "response": json.dumps({
                    "strategy_name": "Pairs Spread HDFCBANK-ICICIBANK",
                    "description": "Statistical arbitrage using spread between HDFCBANK and ICICIBANK relative to 50 SMA.",
                    "instrument": "HDFCBANK",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "sma", "period": 50, "condition": "<", "value": -2},
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 40}
                    ],
                    "exit_conditions": [
                        {"indicator": "sma", "period": 50, "condition": ">", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 2.0},
                    "target": {"type": "fixed_pct", "value": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 8},
                    "confidence": 0.74,
                    "reasoning": "Pairs trading exploits mean-reversion in correlated stock spreads.",
                }),
            },
            {
                "prompt": "Scalping strategy using 1 minute chart with EMA 5 and 8 crossover on Bank Nifty",
                "response": json.dumps({
                    "strategy_name": "EMA Scalper BNF 1m",
                    "description": "Ultra-short scalping using 5/8 EMA crossover on BANKNIFTY 1-minute chart.",
                    "instrument": "BANKNIFTY",
                    "segment": "futures",
                    "timeframe": "1m",
                    "entry_conditions": [
                        {"indicator": "ema", "period": 5, "condition": "crosses_above", "value": 8}
                    ],
                    "exit_conditions": [
                        {"indicator": "ema", "period": 5, "condition": "crosses_below", "value": 8}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 0.3},
                    "target": {"type": "fixed_pct", "value": 0.6},
                    "position_sizing": {"type": "pct_capital", "value": 20},
                    "confidence": 0.70,
                    "reasoning": "Fast EMA crossover on 1m chart captures micro-trends for scalping.",
                }),
            },
            {
                "prompt": "Swing trading strategy using Fibonacci retracement 61.8% with RSI confirmation on LT",
                "response": json.dumps({
                    "strategy_name": "Fibonacci Swing LT",
                    "description": "Buy at 61.8% Fibonacci retracement when RSI confirms oversold on LT daily.",
                    "instrument": "LT",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "fibonacci", "params": {"level": 61.8}, "condition": "==", "value": 61.8},
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 40}
                    ],
                    "exit_conditions": [
                        {"indicator": "fibonacci", "params": {"level": 38.2}, "condition": "==", "value": 38.2}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.5},
                    "target": {"type": "fixed_pct", "value": 5.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.79,
                    "reasoning": "61.8% Fibonacci level is a high-probability reversal zone.",
                }),
            },
        ]
        return pairs

    def _create_backtest_analysis_pairs(self) -> List[Dict[str, str]]:
        """Create backtest result → analysis pairs."""
        return [
            {
                "prompt": (
                    "Analyze these backtest results: "
                    "total_return=12.5%, sharpe=0.85, max_drawdown=18.2%, "
                    "win_rate=42%, total_trades=150, avg_duration=3.2 days"
                ),
                "response": (
                    "The strategy shows a moderate 12.5% return but the Sharpe ratio of 0.85 is below "
                    "the desirable threshold of 1.0. The max drawdown of 18.2% is concerning — consider "
                    "tightening the stop-loss or adding a volatility filter. Win rate at 42% is acceptable "
                    "for a trend-following system but verify the risk:reward ratio is at least 1:2. "
                    "Recommendations: (1) Reduce position size during high-volatility periods. "
                    "(2) Add an ADX filter to avoid choppy markets. (3) Consider trailing stops to "
                    "improve the Sharpe ratio."
                ),
            },
            {
                "prompt": (
                    "Analyze these backtest results: "
                    "total_return=28.3%, sharpe=1.45, max_drawdown=9.8%, "
                    "win_rate=58%, total_trades=85, avg_duration=5.1 days"
                ),
                "response": (
                    "Excellent results! Sharpe ratio of 1.45 indicates strong risk-adjusted returns. "
                    "Max drawdown under 10% demonstrates solid risk control. Win rate of 58% combined "
                    "with 28.3% total return is impressive. The lower trade count (85) suggests a "
                    "selective strategy — verify statistical significance with out-of-sample testing. "
                    "Minor recommendations: (1) Test on different market regimes. (2) Check for "
                    "survivorship bias in instrument selection. (3) Consider Walk-Forward Analysis."
                ),
            },
            {
                "prompt": (
                    "Analyze these backtest results: "
                    "total_return=-5.2%, sharpe=-0.3, max_drawdown=25.4%, "
                    "win_rate=35%, total_trades=200, avg_duration=1.5 days"
                ),
                "response": (
                    "This strategy is underperforming with negative returns and a concerning 25.4% drawdown. "
                    "The low win rate of 35% combined with poor risk:reward suggests the entry criteria "
                    "need significant revision. Immediate actions: (1) Stop trading this strategy live. "
                    "(2) Review entry conditions — they may be generating too many false signals. "
                    "(3) Tighten stop-loss to reduce drawdown. (4) Add trend filters (e.g., 200 EMA) "
                    "to trade only in the dominant direction. (5) Consider reversing the logic if "
                    "consistently wrong — the market may be mean-reverting when you expect trending."
                ),
            },
        ]

    def _create_explanation_pairs(self) -> List[Dict[str, str]]:
        """Create strategy → plain-language explanation pairs."""
        return [
            {
                "prompt": (
                    "Explain this strategy: RSI Mean Reversion — buys when RSI(14) < 30, "
                    "sells when RSI(14) > 70, 1% stop loss, 3% target on Nifty 15m"
                ),
                "response": (
                    "This is a **mean-reversion strategy** that takes advantage of the idea that prices "
                    "tend to bounce back after extreme moves. When the RSI (Relative Strength Index) drops "
                    "below 30, it means the market is 'oversold' — potentially too many people have sold, "
                    "and a bounce may be coming. The strategy buys at this point. Conversely, when RSI "
                    "rises above 70, the market is 'overbought,' and the strategy sells to capture profits. "
                    "The 1% stop-loss protects you if the bounce doesn't happen, while the 3% target "
                    "locks in gains when the reversal occurs. This works best in range-bound markets "
                    "and can suffer in strong trending conditions."
                ),
            },
            {
                "prompt": (
                    "Explain this strategy: SMA Golden Cross — 20 SMA crosses above 50 SMA, "
                    "trailing stop 1.5%, risk:reward 1:2 on TCS daily"
                ),
                "response": (
                    "This is a **trend-following strategy** based on moving average crossovers. "
                    "When the faster 20-day Simple Moving Average (SMA) crosses above the slower "
                    "50-day SMA, it signals that the recent price momentum is building — a potential "
                    "new uptrend. The strategy buys on this 'golden cross' signal. The trailing stop "
                    "of 1.5% adjusts upward as the price rises, locking in profits while giving the "
                    "trend room to develop. The 1:2 risk-reward target ensures that winning trades "
                    "pay twice as much as losing trades cost. This strategy excels in trending markets "
                    "but may produce whipsaw losses during sideways periods."
                ),
            },
        ]

    def _create_hindi_prompt_pairs(self) -> List[Dict[str, str]]:
        """Create Hindi-language prompt → strategy pairs for multilingual support."""
        return [
            {
                "prompt": "Nifty 15 minute chart par RSI 30 se neeche jab ho tab buy karo, 1% stop loss rakho",
                "response": json.dumps({
                    "strategy_name": "RSI Mean Reversion Nifty Hindi",
                    "description": "RSI mean-reversion strategy for Nifty 15m — buys on oversold.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 70}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.0},
                    "target": {"type": "fixed_pct", "value": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.82,
                    "reasoning": "Hindi prompt detected — RSI mean-reversion is a universal setup.",
                }),
            },
            {
                "prompt": "Bank Nifty futures mein jab MACD bullish cross ho aur volume badhe tab buy karein",
                "response": json.dumps({
                    "strategy_name": "MACD Volume Breakout BNF Hindi",
                    "description": "MACD bullish crossover with volume spike on BANKNIFTY futures.",
                    "instrument": "BANKNIFTY",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "crosses_above", "value": 0},
                        {"indicator": "volume", "condition": ">", "value": 1.5}
                    ],
                    "exit_conditions": [
                        {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9},
                         "condition": "crosses_below", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.0},
                    "target": {"type": "fixed_pct", "value": 3.0},
                    "position_sizing": {"type": "pct_capital", "value": 12},
                    "confidence": 0.83,
                    "reasoning": "Hindi prompt — MACD + volume is a strong intraday combination.",
                }),
            },
            {
                "prompt": "Reliance stock mein jab price 200 EMA ke upar ho aur RSI 50 se upar ho tab buy",
                "response": json.dumps({
                    "strategy_name": "EMA Trend Filter RELIANCE Hindi",
                    "description": "Buy RELIANCE when above 200 EMA with RSI confirmation.",
                    "instrument": "RELIANCE",
                    "segment": "equity",
                    "timeframe": "1d",
                    "entry_conditions": [
                        {"indicator": "ema", "period": 200, "condition": ">", "value": 0},
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 50}
                    ],
                    "exit_conditions": [
                        {"indicator": "ema", "period": 200, "condition": "<", "value": 0}
                    ],
                    "stop_loss": {"type": "fixed_pct", "value": 1.5},
                    "target": {"type": "risk_reward", "value": 2.5, "risk_reward_ratio": 2.0},
                    "position_sizing": {"type": "pct_capital", "value": 10},
                    "confidence": 0.85,
                    "reasoning": "200 EMA trend filter + RSI confirmation is a robust swing setup.",
                }),
            },
        ]

    def _create_complex_strategy_pairs(self) -> List[Dict[str, str]]:
        """Create complex multi-indicator and advanced strategy pairs."""
        return [
            {
                "prompt": (
                    "Create an adaptive strategy that uses RSI in ranging markets and MACD in trending markets, "
                    "with dynamic position sizing based on ATR volatility"
                ),
                "response": json.dumps({
                    "strategy_name": "Adaptive Regime Strategy",
                    "description": "Switches between RSI mean-reversion (range-bound) and MACD trend-following (trending) using ADX regime detection with ATR-based sizing.",
                    "instrument": "NIFTY50",
                    "segment": "futures",
                    "timeframe": "15m",
                    "entry_conditions": [
                        {"indicator": "adx", "period": 14, "condition": "<", "value": 25},
                        {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
                    ],
                    "exit_conditions": [
                        {"indicator": "rsi", "period": 14, "condition": ">", "value": 70}
                    ],
                    "stop_loss": {"type": "atr", "value": 1.5, "atr_multiplier": 1.5},
                    "target": {"type": "atr", "value": 3.0, "atr_multiplier": 3.0},
                    "position_sizing": {"type": "risk_based", "value": 1.5, "risk_per_trade_pct": 1.5, "max_position_pct": 20},
                    "confidence": 0.88,
                    "reasoning": "Adaptive regime switching with ATR sizing provides robust performance across market conditions.",
                }),
            },
            {
                "prompt": (
                    "Build a momentum strategy that uses OBV divergence with price action confirmation "
                    "and ATR trailing stops on hourly EURUSD"
                ),
                "response": json.dumps({
                    "strategy_name": "OBV Momentum Divergence EURUSD",
                    "description": "Captures momentum shifts via OBV-price divergence with ATR trailing stops on EURUSD hourly.",
                    "instrument": "EURUSD",
                    "segment": "forex",
                    "timeframe": "1h",
                    "entry_conditions": [
                        {"indicator": "obv", "condition": "divergence_bullish", "value": 0},
                        {"indicator": "atr", "period": 14, "condition": ">", "value": 0.5}
                    ],
                    "exit_conditions": [
                        {"indicator": "obv", "condition": "divergence_bearish", "value": 0}
                    ],
                    "stop_loss": {"type": "atr", "value": 1.5, "atr_multiplier": 1.5},
                    "target": {"type": "trailing", "value": 3.0, "trail_pct": 0.5},
                    "position_sizing": {"type": "risk_based", "value": 1.0, "risk_per_trade_pct": 1},
                    "confidence": 0.82,
                    "reasoning": "OBV divergence is a leading indicator of momentum exhaustion/reversal.",
                }),
            },
        ]

    # ------------------------------------------------------------------
    # Backtest helpers
    # ------------------------------------------------------------------

    def _backtest_to_prompt(self, backtest: Dict[str, Any]) -> str:
        """Format a backtest dict into an analysis prompt."""
        metrics_str = ", ".join(f"{k}={v}" for k, v in backtest.items())
        return f"Analyze these backtest results: {metrics_str}"

    def _generate_reference_analysis(self, backtest: Dict[str, Any]) -> str:
        """Generate a reference-quality analysis for a backtest result."""
        total_return = backtest.get("total_return", 0)
        sharpe = backtest.get("sharpe_ratio", 0)
        max_dd = backtest.get("max_drawdown", 0)
        win_rate = backtest.get("win_rate", 0)

        parts: List[str] = []

        if total_return > 15 and sharpe > 1.2 and max_dd < 12:
            parts.append(
                f"Strong strategy: {total_return}% return with Sharpe {sharpe} and manageable {max_dd}% drawdown. "
                f"Win rate of {win_rate}% is healthy. Consider Walk-Forward validation."
            )
        elif total_return > 0 and sharpe > 0.8:
            parts.append(
                f"Decent performance: {total_return}% return, Sharpe {sharpe}. "
                f"However, {max_dd}% drawdown warrants attention. Recommend adding a volatility filter."
            )
        elif total_return <= 0:
            parts.append(
                f"Underperforming: {total_return}% return with {max_dd}% drawdown is concerning. "
                f"Review entry logic and consider trend filters. Win rate of {win_rate}% may be too low."
            )
        else:
            parts.append(
                f"Mixed results: {total_return}% return, Sharpe {sharpe}, {max_dd}% drawdown. "
                "Further optimization recommended across risk parameters."
            )

        return " ".join(parts)

    def _strategy_to_prompt(self, strategy: Dict[str, Any]) -> str:
        """Convert a strategy dict into a natural-language prompt."""
        name = strategy.get("strategy_name", "a strategy")
        instrument = strategy.get("instrument", "")
        desc = strategy.get("description", "")
        if desc:
            return f"Create a strategy: {desc} for {instrument}"
        return f"Create {name} strategy for {instrument}"

    # ------------------------------------------------------------------
    # Dataset conversion
    # ------------------------------------------------------------------

    def _pairs_to_dataset(self, pairs: List[Dict[str, str]]) -> "Dataset":
        """
        Convert prompt-response pairs into a HuggingFace Dataset.

        Each example is formatted as a single text string with the
        ``System / User / Assistant`` structure expected by DialoGPT.
        """
        texts: List[str] = []
        for pair in pairs:
            prompt_text = pair["prompt"]
            response_text = pair["response"]

            # Determine task type from prompt content
            if "analyze" in prompt_text.lower() or "backtest" in prompt_text.lower():
                system = self._ANALYSIS_SYSTEM
            elif "explain" in prompt_text.lower():
                system = self._EXPLAIN_SYSTEM
            else:
                system = self._STRATEGY_SYSTEM

            formatted = (
                f"System: {system}\n"
                f"User: {prompt_text}\n"
                f"Assistant: {response_text}{self._get_eos_token()}"
            )
            texts.append(formatted)

        data_dict = {"text": texts}
        dataset = Dataset.from_dict(data_dict)

        # Train / validation split
        if self.validation_split > 0:
            split = dataset.train_test_split(
                test_size=self.validation_split,
                seed=self.random_seed,
            )
            logger.info(
                f"Dataset split — train={len(split['train'])}, "
                f"validation={len(split['test'])}"
            )
            return split["train"]

        logger.info(f"Dataset created — {len(dataset)} examples")
        return dataset

    @staticmethod
    def _get_eos_token() -> str:
        """Return the EOS token used by DialoGPT/GPT-2."""
        return "<|endoftext|>"

    def get_validation_split(self) -> Optional["Dataset"]:
        """
        Get the validation split of the full dataset.

        Must call ``build_full_dataset`` first.

        Returns
        -------
        datasets.Dataset or None
        """
        _load_datasets()
        pairs = self.create_training_pairs()
        texts: List[str] = []
        for pair in pairs:
            prompt_text = pair["prompt"]
            response_text = pair["response"]
            if "analyze" in prompt_text.lower() or "backtest" in prompt_text.lower():
                system = self._ANALYSIS_SYSTEM
            elif "explain" in prompt_text.lower():
                system = self._EXPLAIN_SYSTEM
            else:
                system = self._STRATEGY_SYSTEM
            formatted = (
                f"System: {system}\n"
                f"User: {prompt_text}\n"
                f"Assistant: {response_text}{self._get_eos_token()}"
            )
            texts.append(formatted)

        dataset = Dataset.from_dict({"text": texts})
        if self.validation_split > 0:
            split = dataset.train_test_split(
                test_size=self.validation_split, seed=self.random_seed
            )
            return split["test"]
        return None

    def export_to_jsonl(self, path: str, pairs: Optional[List[Dict[str, str]]] = None) -> None:
        """
        Export training pairs to JSONL format for external tools.

        Parameters
        ----------
        path:
            Output file path (e.g. ``training_data.jsonl``).
        pairs:
            Optional custom pairs to export. If ``None``, uses built-in pairs.
        """
        pairs = pairs or self.create_training_pairs()
        with open(path, "w", encoding="utf-8") as fh:
            for pair in pairs:
                fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
        logger.info(f"Exported {len(pairs)} pairs to {path}")


# =============================================================================
# MarketDatasetBuilder  —  indicator features from OHLCV data
# =============================================================================


class MarketDatasetBuilder:
    """
    Build feature datasets from market OHLCV data for context-aware training.

    This is a *complementary* dataset builder — it produces tabular datasets
    with technical indicator values that can be used as additional context
    (or for training auxiliary models) alongside the NL strategy dataset.
    """

    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed
        logger.info("MarketDatasetBuilder initialised.")

    # ------------------------------------------------------------------
    # Indicator computation
    # ------------------------------------------------------------------

    def create_indicator_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute technical indicators and append them as columns.

        Parameters
        ----------
        df:
            OHLCV DataFrame with columns ``open``, ``high``, ``low``,
            ``close``, ``volume`` (case-insensitive column matching).

        Returns
        -------
        pd.DataFrame
            Original data + indicator columns.
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        logger.info(f"Computing indicators for {len(df)} rows ...")

        # Simple Moving Averages
        for period in [5, 10, 20, 50, 100, 200]:
            df[f"sma_{period}"] = df["close"].rolling(window=period).mean()

        # Exponential Moving Averages
        for period in [9, 12, 20, 26, 50, 200]:
            df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()

        # RSI
        df["rsi_14"] = self._compute_rsi(df["close"], period=14)
        df["rsi_7"] = self._compute_rsi(df["close"], period=7)

        # MACD
        df["macd_line"] = df["close"].ewm(span=12, adjust=False).mean() - df["close"].ewm(span=26, adjust=False).mean()
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd_line"] - df["macd_signal"]

        # Bollinger Bands
        bb_sma = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper"] = bb_sma + 2 * bb_std
        df["bb_lower"] = bb_sma - 2 * bb_std
        df["bb_position"] = (df["close"] - bb_sma) / (2 * bb_std)

        # ATR
        df["atr_14"] = self._compute_atr(df, period=14)

        # Volume indicators
        df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

        # VWAP (cumulative)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
        df["vwap_deviation"] = (df["close"] - df["vwap"]) / df["vwap"] * 100

        # Price vs key MAs
        df["price_vs_sma20"] = (df["close"] - df["sma_20"]) / df["sma_20"] * 100
        df["price_vs_sma50"] = (df["close"] - df["sma_50"]) / df["sma_50"] * 100
        df["price_vs_ema200"] = (df["close"] - df["ema_200"]) / df["ema_200"] * 100

        logger.info(f"Indicator dataset ready — {len(df.columns)} columns.")
        return df

    def create_signal_labels(
        self,
        df: pd.DataFrame,
        strategy: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Label historical data with buy/sell/hold signals based on a strategy.

        Parameters
        ----------
        df:
            DataFrame with indicator columns (from ``create_indicator_dataset``).
        strategy:
            Strategy definition dict with ``entry_conditions`` and
            ``exit_conditions``.

        Returns
        -------
        pd.DataFrame
            DataFrame with added ``signal`` column (1=buy, -1=sell, 0=hold).
        """
        df = df.copy()
        df["signal"] = 0

        entries = strategy.get("entry_conditions", [])
        exits = strategy.get("exit_conditions", [])

        # Build boolean masks
        entry_mask = pd.Series(True, index=df.index)
        for cond in entries:
            entry_mask &= self._evaluate_condition(df, cond)

        exit_mask = pd.Series(True, index=df.index)
        for cond in exits:
            exit_mask &= self._evaluate_condition(df, cond)

        df.loc[entry_mask, "signal"] = 1
        df.loc[exit_mask, "signal"] = -1

        # Handle overlapping signals: exit takes precedence
        df.loc[exit_mask, "signal"] = -1

        buy_count = (df["signal"] == 1).sum()
        sell_count = (df["signal"] == -1).sum()
        logger.info(
            f"Signal labels: {buy_count} buy, {sell_count} sell, "
            f"{len(df) - buy_count - sell_count} hold"
        )
        return df

    def create_market_context_dataset(
        self,
        df: pd.DataFrame,
        window_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Create a dataset of market context windows for LLM training.

        Each example contains a text description of recent market conditions
        that can be appended to prompts for context-aware generation.

        Parameters
        ----------
        df:
            DataFrame with indicator columns.
        window_size:
            Number of recent bars to describe.

        Returns
        -------
        List[Dict[str, Any]]
            List of context dicts with ``text`` and ``metadata`` keys.
        """
        contexts: List[Dict[str, Any]] = []
        for i in range(window_size, len(df)):
            window = df.iloc[i - window_size : i]
            latest = df.iloc[i - 1]

            # Build a natural-language description of current market state
            trend = "uptrend" if latest["price_vs_sma20"] > 0 else "downtrend"
            rsi_state = (
                "oversold" if latest["rsi_14"] < 30
                else "overbought" if latest["rsi_14"] > 70
                else "neutral"
            )

            context_text = (
                f"Market context (last {window_size} bars): "
                f"Price is in {trend} vs 20 SMA ({latest['price_vs_sma20']:.2f}%). "
                f"RSI(14) is {latest['rsi_14']:.1f} ({rsi_state}). "
                f"MACD histogram: {latest['macd_histogram']:.4f}. "
                f"ATR(14): {latest['atr_14']:.2f}. "
                f"Volume ratio: {latest['volume_ratio']:.2f}x average. "
                f"Price vs VWAP: {latest['vwap_deviation']:.2f}%."
            )

            contexts.append({
                "text": context_text,
                "metadata": {
                    "timestamp": str(latest.name) if hasattr(latest, "name") else i,
                    "close": float(latest["close"]),
                    "rsi_14": float(latest["rsi_14"]),
                    "trend": trend,
                    "rsi_state": rsi_state,
                },
            })

        logger.info(f"Created {len(contexts)} market context examples.")
        return contexts

    # ------------------------------------------------------------------
    # Technical indicator computations
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Compute the Relative Strength Index (RSI).

        Formula: RSI = 100 - (100 / (1 + RS))
        where RS = average gain / average loss over *period* bars.
        """
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, 1e-10)  # avoid division by zero
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Compute the Average True Range (ATR).

        True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        ATR = smoothed moving average of True Range over *period* bars.
        """
        high_low = df["high"] - df["low"]
        high_prev = (df["high"] - df["close"].shift(1)).abs()
        low_prev = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
        atr = true_range.ewm(alpha=1.0 / period, min_periods=period).mean()
        return atr

    def _evaluate_condition(
        self,
        df: pd.DataFrame,
        condition: Dict[str, Any],
    ) -> pd.Series:
        """
        Evaluate a single strategy condition against indicator data.

        Parameters
        ----------
        df:
            DataFrame with computed indicators.
        condition:
            Dict with ``indicator``, ``condition``, ``value``, ``period``,
            and optional ``params``.

        Returns
        -------
        pd.Series
            Boolean mask where the condition is satisfied.
        """
        indicator = condition.get("indicator", "").lower()
        operator = condition.get("condition", ">")
        value = condition.get("value", 0)
        period = condition.get("period", 14)

        # Resolve column name for the indicator
        col = self._resolve_indicator_column(df, indicator, period, condition.get("params"))
        if col not in df.columns:
            logger.warning(f"Indicator column '{col}' not found — returning all False.")
            return pd.Series(False, index=df.index)

        series = df[col]

        # Apply the comparison operator
        op_map: Dict[str, Callable[[pd.Series, Any], pd.Series]] = {
            ">": lambda s, v: s > v,
            "<": lambda s, v: s < v,
            ">=": lambda s, v: s >= v,
            "<=": lambda s, v: s <= v,
            "==": lambda s, v: s == v,
            "!=": lambda s, v: s != v,
            "crosses_above": lambda s, v: (s > v) & (s.shift(1) <= v),
            "crosses_below": lambda s, v: (s < v) & (s.shift(1) >= v),
            "between": lambda s, v: s.between(v[0], v[1]) if isinstance(v, (list, tuple)) and len(v) == 2 else pd.Series(False, index=s.index),
            "divergence_bullish": lambda s, v: self._detect_bullish_divergence(s, df["close"]),
            "divergence_bearish": lambda s, v: self._detect_bearish_divergence(s, df["close"]),
        }

        op_fn = op_map.get(operator)
        if op_fn is None:
            logger.warning(f"Unknown operator '{operator}' — returning all False.")
            return pd.Series(False, index=df.index)

        return op_fn(series, value)

    def _resolve_indicator_column(
        self,
        df: pd.DataFrame,
        indicator: str,
        period: int,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Map an indicator name to the corresponding DataFrame column."""
        col_map = {
            "rsi": f"rsi_{period}",
            "sma": f"sma_{period}",
            "ema": f"ema_{period}",
            "macd": "macd_line",
            "bollinger": "bb_position",
            "atr": f"atr_{period}",
            "vwap": "vwap_deviation",
            "volume": "volume_ratio",
            "stochastic": f"rsi_{period}",  # Approximation — proper stochastic would need %K/%D
            "adx": f"atr_{period}",  # Placeholder — proper ADX computation needed
            "obv": "volume",  # Simplified — proper OBV would need cumulative calculation
            "supertrend": "atr_14",  # Simplified
            "fibonacci": "price_vs_sma20",  # Simplified
        }
        return col_map.get(indicator, indicator)

    @staticmethod
    def _detect_bullish_divergence(
        indicator: pd.Series, price: pd.Series, lookback: int = 5
    ) -> pd.Series:
        """
        Detect bullish divergence: price makes lower low but indicator makes higher low.

        This is a simplified implementation. A production version would use
        proper swing-point detection (e.g., scipy.signal.find_peaks).
        """
        result = pd.Series(False, index=indicator.index)
        for i in range(lookback, len(indicator) - lookback):
            price_window = price.iloc[i - lookback : i + lookback]
            ind_window = indicator.iloc[i - lookback : i + lookback]

            price_lower_low = price.iloc[i] < price_window.min() * 1.01
            ind_higher_low = indicator.iloc[i] > ind_window.min() * 0.99

            if price_lower_low and ind_higher_low:
                result.iloc[i] = True
        return result

    @staticmethod
    def _detect_bearish_divergence(
        indicator: pd.Series, price: pd.Series, lookback: int = 5
    ) -> pd.Series:
        """Detect bearish divergence: price makes higher high but indicator makes lower high."""
        result = pd.Series(False, index=indicator.index)
        for i in range(lookback, len(indicator) - lookback):
            price_window = price.iloc[i - lookback : i + lookback]
            ind_window = indicator.iloc[i - lookback : i + lookback]

            price_higher_high = price.iloc[i] > price_window.max() * 0.99
            ind_lower_high = indicator.iloc[i] < ind_window.max() * 1.01

            if price_higher_high and ind_lower_high:
                result.iloc[i] = True
        return result

    def export_features_csv(self, df: pd.DataFrame, path: str) -> None:
        """Export indicator features to CSV."""
        df.to_csv(path, index=True)
        logger.info(f"Exported features to {path} — {len(df)} rows, {len(df.columns)} columns.")


# =============================================================================
# Convenience functions
# =============================================================================


def build_combined_dataset(
    strategy_builder: Optional[StrategyDatasetBuilder] = None,
    market_builder: Optional[MarketDatasetBuilder] = None,
    ohlcv_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Build a combined training dataset from all sources.

    Parameters
    ----------
    strategy_builder:
        Optional pre-configured ``StrategyDatasetBuilder``.
    market_builder:
        Optional pre-configured ``MarketDatasetBuilder``.
    ohlcv_df:
        Optional OHLCV DataFrame for market context features.

    Returns
    -------
    Dict[str, Any]
        Dictionary with ``strategy_dataset``, ``market_features``, and
        ``market_contexts`` keys.
    """
    result: Dict[str, Any] = {}

    # Strategy NL dataset
    sb = strategy_builder or StrategyDatasetBuilder()
    result["strategy_dataset"] = sb.build_full_dataset()
    result["validation_dataset"] = sb.get_validation_split()

    # Market features
    if ohlcv_df is not None and market_builder is not None:
        result["market_features"] = market_builder.create_indicator_dataset(ohlcv_df)
        result["market_contexts"] = market_builder.create_market_context_dataset(
            result["market_features"]
        )

    return result
