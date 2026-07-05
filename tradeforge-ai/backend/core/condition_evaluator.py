"""
TradeForge AI — Strategy condition evaluator.

Turns the frontend condition tuples stored on a Strategy document into a
boolean Pandas Series that can be fed directly into BacktestEngine.run().
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core import indicators as ind


def _parse_expr(expr: str) -> Tuple[str, Tuple[float, ...]]:
    """Parse 'SMA(20)' -> ('SMA', (20.0,))."""
    expr = expr.strip()
    match = re.match(r"^(?P<name>[A-Za-z\s]+)(?:\((?P<params>[^)]+)\))?$", expr)
    if not match:
        raise ValueError(f"Invalid indicator expression: {expr}")
    name = match.group("name").strip()
    params_str = match.group("params")
    params: Tuple[float, ...] = ()
    if params_str:
        params = tuple(float(p.strip()) for p in params_str.split(",") if p.strip() != "")
    return name, params


_DEFAULT_PARAMS: Dict[str, Tuple[float, ...]] = {
    "SMA": (20.0,),
    "EMA": (20.0,),
    "WMA": (20.0,),
    "RSI": (14.0,),
    "MACD": (12.0, 26.0, 9.0),
    "Stoch": (14.0, 3.0),
    "BB": (20.0, 2.0),
    "ATR": (14.0,),
    "ADX": (14.0,),
    "CCI": (20.0,),
    "MFI": (14.0,),
    "Supertrend": (10.0, 3.0),
    "PSAR": (0.02, 0.2),
}


def _resolve_series(df: pd.DataFrame, expr: str) -> pd.Series:
    """Resolve an indicator expression to a Pandas Series aligned to df."""
    expr = expr.strip()

    # Special synthetic series
    if expr.lower() == "price":
        return df["close"]
    if expr.lower() == "volume":
        return df["volume"]
    if expr == "VWAP":
        return ind.vwap(df["high"], df["low"], df["close"], df["volume"])
    if expr == "OBV":
        return ind.obv(df["close"], df["volume"])

    # Multi-output shortcuts
    if expr in ("BB Upper", "BB Mid", "BB Lower"):
        upper, mid, lower = ind.bollinger_bands(df["close"])
        return {"BB Upper": upper, "BB Mid": mid, "BB Lower": lower}[expr]
    if expr in ("MACD Line", "MACD Signal", "MACD Hist"):
        line, signal, hist = ind.macd(df["close"])
        return {"MACD Line": line, "MACD Signal": signal, "MACD Hist": hist}[expr]

    name, params = _parse_expr(expr)
    if name in _DEFAULT_PARAMS and not params:
        params = _DEFAULT_PARAMS[name]

    # Single-output indicators
    if name in ("SMA", "EMA", "WMA", "HMA"):
        if len(params) < 1:
            raise ValueError(f"{name} requires a period")
        func = {"SMA": ind.sma, "EMA": ind.ema, "WMA": ind.wma, "HMA": ind.hma}[name]
        return func(df["close"], int(params[0]))
    if name == "RSI":
        return ind.rsi(df["close"], int(params[0]) if params else 14)
    if name == "ATR":
        return ind.atr(df["high"], df["low"], df["close"], int(params[0]) if params else 14)
    if name == "ADX":
        return ind.adx(df["high"], df["low"], df["close"], int(params[0]) if params else 14)
    if name == "CCI":
        return ind.cci(df["high"], df["low"], df["close"], int(params[0]) if params else 20)
    if name == "MFI":
        return ind.mfi(df["high"], df["low"], df["close"], df["volume"], int(params[0]) if params else 14)
    if name == "Stochastic":
        k, _ = ind.stochastic(
            df["high"], df["low"], df["close"],
            int(params[0]) if len(params) > 0 else 14,
            int(params[1]) if len(params) > 1 else 3,
        )
        return k
    if name == "Supertrend":
        upper, lower = ind.supertrend(
            df["high"], df["low"], df["close"],
            int(params[0]) if len(params) > 0 else 10,
            params[1] if len(params) > 1 else 3.0,
        )
        return upper  # use upper band as a proxy

    raise ValueError(f"Unsupported indicator: {expr}")


def _apply_operator(left: pd.Series, right: pd.Series, operator: str) -> pd.Series:
    """Apply a comparison operator between two aligned series."""
    if operator == "crosses_above":
        return (left.shift(1) <= right.shift(1)) & (left > right)
    if operator == "crosses_below":
        return (left.shift(1) >= right.shift(1)) & (left < right)
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == "=":
        return np.isclose(left, right)
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    raise ValueError(f"Unsupported operator: {operator}")


def evaluate_conditions(df: pd.DataFrame, conditions: List[Dict[str, Any]]) -> Optional[pd.Series]:
    """
    Evaluate a list of strategy conditions against a DataFrame.

    Parameters
    ----------
    df:
        DataFrame with lowercase ohlcv columns and a DatetimeIndex.
    conditions:
        List of condition dicts with keys: indicator, operator, value,
        valueType ('indicator' | 'number'), logic ('AND' | 'OR', optional).

    Returns
    -------
    pd.Series or None
        Boolean series aligned to df. Returns None if conditions is empty.
    """
    if not conditions:
        return None

    combined: Optional[pd.Series] = None

    for idx, cond in enumerate(conditions):
        indicator_expr = str(cond.get("indicator", ""))
        operator = str(cond.get("operator", ""))
        value_expr = str(cond.get("value", ""))
        value_type = str(cond.get("valueType", "indicator"))
        logic = str(cond.get("logic", "AND")).upper() if idx > 0 else None

        if not indicator_expr or not operator:
            continue

        left = _resolve_series(df, indicator_expr)

        if value_type == "number":
            right = pd.Series(float(value_expr), index=df.index)
        else:
            right = _resolve_series(df, value_expr) if value_expr else left

        result = _apply_operator(left, right, operator)

        if combined is None:
            combined = result
        elif logic == "OR":
            combined = combined | result
        else:
            combined = combined & result

    return combined
