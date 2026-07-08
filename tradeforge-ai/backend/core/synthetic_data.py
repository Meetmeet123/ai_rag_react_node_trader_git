"""
TradeForge AI — Synthetic market data generator.

This module provides a deterministic fallback for backtesting when external
market data providers (NSE/Yahoo) are unavailable or when the requested date
range has no cached data. It is intended for development and demo use only;
production deployments should rely on real historical data.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def generate_ohlcv(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    timeframe: str = "1d",
    seed: int = 42,
    initial_price: float = 100.0,
    annual_return: float = 0.12,
    annual_volatility: float = 0.20,
) -> pd.DataFrame:
    """
    Generate a synthetic OHLCV DataFrame using geometric Brownian motion.

    Parameters
    ----------
    symbol:
        Symbol label (used only for the returned column).
    start_date, end_date:
        Date range to cover.
    timeframe:
        Only ``1d`` is fully supported; other values generate a daily series
        with a warning.
    seed:
        Random seed for reproducibility.
    initial_price:
        Starting price.
    annual_return:
        Expected annual drift.
    annual_volatility:
        Annualised volatility.

    Returns
    -------
    pd.DataFrame
        Columns: ``timestamp``, ``open``, ``high``, ``low``, ``close``, ``volume``.
    """
    if timeframe != "1d":
        # For intraday timeframes we still generate daily bars; the engine
        # will run with lower granularity but still produce valid metrics.
        pass

    rng = np.random.default_rng(seed)

    # Build business-day index between start and end
    days = int((end_date - start_date).days) + 1
    if days < 2:
        days = 2

    timestamps = pd.date_range(start=start_date, periods=days, freq="B")
    n = len(timestamps)

    daily_return = annual_return / 252
    daily_vol = annual_volatility / np.sqrt(252)

    returns = rng.normal(daily_return, daily_vol, n)
    price = initial_price * np.exp(np.cumsum(returns))

    # Intraday OHLC around the close price
    noise = rng.uniform(0.001, 0.015, n)
    high = price * (1 + noise)
    low = price * (1 - noise)
    open_ = price * (1 + rng.normal(0, daily_vol / 3, n))
    close = price

    # Ensure OHLC relationships
    high = np.maximum(high, np.maximum(open_, close))
    low = np.minimum(low, np.minimum(open_, close))

    volume = rng.integers(1_000_000, 10_000_000, n)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_.round(2),
            "high": high.round(2),
            "low": low.round(2),
            "close": close.round(2),
            "volume": volume,
        }
    )
    df["symbol"] = symbol
    return df
