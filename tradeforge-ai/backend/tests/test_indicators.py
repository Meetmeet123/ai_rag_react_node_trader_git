"""Unit tests for the technical indicator library."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import indicators


def _sample_ohlcv(n: int = 60) -> pd.DataFrame:
    """Generate a deterministic OHLCV DataFrame for testing."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n))
    open_ = close - np.random.randn(n) * 0.5
    high = np.maximum(open_, close) + np.random.rand(n) * 2
    low = np.minimum(open_, close) - np.random.rand(n) * 2
    volume = np.random.randint(1_000, 10_000, size=n)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


def test_sma_length_and_nan() -> None:
    df = _sample_ohlcv(30)
    result = indicators.sma(df["close"], 20)
    assert pd.isna(result.iloc[18])
    assert not pd.isna(result.iloc[19])


def test_ema_converges_to_price() -> None:
    series = pd.Series([100.0] * 50)
    result = indicators.ema(series, 20)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_bounds() -> None:
    df = _sample_ohlcv(30)
    result = indicators.rsi(df["close"], 14)
    valid = result.dropna()
    assert ((valid >= 0) & (valid <= 100)).all()


def test_bollinger_band_relationships() -> None:
    df = _sample_ohlcv(40)
    upper, middle, lower = indicators.bollinger_bands(df["close"], 20)
    valid = upper.notna() & middle.notna() & lower.notna()
    assert (upper[valid] >= middle[valid]).all()
    assert (middle[valid] >= lower[valid]).all()


def test_atr_positive() -> None:
    df = _sample_ohlcv(30)
    result = indicators.atr(df["high"], df["low"], df["close"], 14).dropna()
    assert (result > 0).all()


def test_calculate_all_indicators_columns() -> None:
    df = _sample_ohlcv(80)
    result = indicators.calculate_all_indicators(df)
    expected = {
        "sma_20",
        "sma_50",
        "ema_20",
        "ema_50",
        "wma_20",
        "hma_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
        "stoch_k",
        "stoch_d",
        "cci_20",
        "mfi_14",
        "williams_r_14",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "atr_14",
        "keltner_upper",
        "keltner_middle",
        "keltner_lower",
        "supertrend_upper",
        "supertrend_lower",
        "psar",
        "adx",
        "vwap",
        "obv",
        "vwma_20",
    }
    assert expected.issubset(set(result.columns))


def test_calculate_all_indicators_missing_columns() -> None:
    df = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(ValueError):
        indicators.calculate_all_indicators(df)
