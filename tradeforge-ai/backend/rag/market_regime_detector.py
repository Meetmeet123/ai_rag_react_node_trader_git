"""
Market Regime Detector for TradeForge RAG

Identifies the current market regime from OHLCV + indicator data using:
* Trend analysis (ADX, SMA alignment, price vs. moving averages)
* Volatility analysis (ATR, Bollinger Band width)
* Volume analysis (relative to average, trend confirmation)
* Momentum analysis (RSI, MACD)
* Pattern detection (breakout, reversal signals)

Detectable regimes:
  STRONG_UPTREND, UPTREND, RANGING, DOWNTREND, STRONG_DOWNTREND,
  VOLATILE, LOW_LIQUIDITY, BREAKOUT, REVERSAL

The regime output is embedded and stored in the ``market_regime``
collection so that the RAG retriever can match strategies to current
market conditions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MarketRegime(Enum):
    """Discrete market regimes that the detector can identify."""

    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGING = "ranging"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    VOLATILE = "volatile"
    LOW_LIQUIDITY = "low_liquidity"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MarketRegimeDetector:
    """Detects market regime from OHLCV DataFrames with technical indicators.

    The detector computes sub-scores for trend, volatility, volume, and
    momentum, then combines them into an overall regime classification with
    a confidence score.

    Parameters
    ----------
    adx_threshold_strong:
        ADX value above which a trend is considered strong.
    adx_threshold_weak:
        ADX value below which a trend is considered weak / ranging.
    atr_volatile_pct:
        ATR as % of price above which the market is considered volatile.
    volume_confirmation_ratio:
        Volume / average ratio above which volume confirms a move.
    bb_squeeze_pct:
        Bollinger Band width % below which a squeeze is detected.

    Example
    -------
    >>> detector = MarketRegimeDetector()
    >>> regime = detector.detect(df)
    >>> print(regime["regime"], regime["confidence"])
    MarketRegime.STRONG_UPTREND 0.82
    """

    def __init__(
        self,
        adx_threshold_strong: float = 25.0,
        adx_threshold_weak: float = 20.0,
        atr_volatile_pct: float = 2.0,
        volume_confirmation_ratio: float = 1.2,
        bb_squeeze_pct: float = 5.0,
    ) -> None:
        self.adx_threshold_strong = adx_threshold_strong
        self.adx_threshold_weak = adx_threshold_weak
        self.atr_volatile_pct = atr_volatile_pct
        self.volume_confirmation_ratio = volume_confirmation_ratio
        self.bb_squeeze_pct = bb_squeeze_pct

    # ===================================================================
    # Main detection
    # ===================================================================

    def detect(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect market regime from an OHLCV DataFrame.

        The DataFrame must contain at minimum ``close`` prices.  Optional
        columns that improve accuracy:
        ``open``, ``high``, ``low``, ``volume``,
        ``adx`` (or ``adx_14``), ``atr`` (or ``atr_14``),
        ``rsi`` (or ``rsi_14``), ``macd``, ``macd_signal``,
        ``sma_20``, ``sma_50``, ``sma_200``,
        ``bb_upper``, ``bb_lower``, ``bb_middle``,
        ``vwap``.

        Parameters
        ----------
        df:
            OHLCV DataFrame with indicators.  Index may be datetime or
            integer.  The **last row** represents the most recent data.

        Returns
        -------
        dict
            {
                "regime": MarketRegime,
                "confidence": float (0.0 … 1.0),
                "indicators": {
                    "trend": str,
                    "volatility": str,
                    "volume": str,
                    "momentum": str,
                },
                "description": str,        # human-readable
                "trading_implications": str,  # actionable advice
                "raw_scores": dict,        # sub-component scores
                "timestamp": str,
            }
        """
        if df.empty:
            logger.warning("Empty DataFrame passed to regime detector")
            return self._empty_result()

        last = df.iloc[-1]
        price = float(last.get("close", 0))
        if price <= 0:
            logger.warning("Invalid price in DataFrame")
            return self._empty_result()

        # Sub-detections
        trend = self._detect_trend(df, price)
        volatility = self._detect_volatility(df, price)
        volume = self._detect_volume_regime(df)
        momentum = self._detect_momentum(df)

        # Pattern detection (breakout / reversal)
        pattern = self._detect_patterns(df, price)

        # Combine into overall regime
        regime, confidence, raw_scores = self._combine_signals(
            trend=trend,
            volatility=volatility,
            volume=volume,
            momentum=momentum,
            pattern=pattern,
            price=price,
        )

        description = self._build_description(
            regime, trend, volatility, volume, momentum, price
        )
        implications = self.get_trading_implications(regime)

        return {
            "regime": regime,
            "confidence": round(confidence, 4),
            "indicators": {
                "trend": trend,
                "volatility": volatility,
                "volume": volume,
                "momentum": momentum,
            },
            "description": description,
            "trading_implications": implications,
            "raw_scores": {k: round(v, 4) for k, v in raw_scores.items()},
            "timestamp": datetime.utcnow().isoformat(),
        }

    def detect_series(
        self,
        df: pd.DataFrame,
        window: int = 20,
    ) -> List[Dict[str, Any]]:
        """Detect regime for every row using a rolling window.

        This is useful for historical regime labelling and backtesting.

        Parameters
        ----------
        df:
            Full OHLCV DataFrame.
        window:
            Minimum number of rows needed for detection.

        Returns
        -------
        list[dict]
            One regime dict per row (from index ``window-1`` onwards).
        """
        results = []
        for i in range(window - 1, len(df)):
            subset = df.iloc[max(0, i - window + 1) : i + 1]
            regime = self.detect(subset)
            regime["index"] = i
            if isinstance(df.index, pd.DatetimeIndex):
                regime["datetime"] = df.index[i].isoformat()
            results.append(regime)
        return results

    # ===================================================================
    # Sub-detectors
    # ===================================================================

    def _detect_trend(self, df: pd.DataFrame, price: float) -> str:
        """Detect trend direction and strength.

        Uses ADX (if available) and SMA alignment.  Returns one of:
        ``"strong_uptrend"``, ``"uptrend"``, ``"ranging"``,
        ``"downtrend"``, ``"strong_downtrend"``.
        """
        last = df.iloc[-1]

        # ADX-based detection
        adx = last.get("adx") or last.get("adx_14")
        if adx is not None and not np.isnan(adx):
            adx = float(adx)
            # Determine direction from SMAs or price action
            sma20 = last.get("sma_20")
            sma50 = last.get("sma_50")
            sma200 = last.get("sma_200")

            # SMA alignment check
            sma_bullish = False
            sma_bearish = False
            if sma20 and sma50 and sma200:
                sma_bullish = sma20 > sma50 > sma200
                sma_bearish = sma20 < sma50 < sma200
            elif sma20 and sma50:
                sma_bullish = sma20 > sma50
                sma_bearish = sma20 < sma50
            elif price:
                if sma20:
                    sma_bullish = price > sma20
                    sma_bearish = price < sma20

            if adx >= self.adx_threshold_strong:
                if sma_bullish:
                    return "strong_uptrend"
                elif sma_bearish:
                    return "strong_downtrend"
                else:
                    # Strong ADX but mixed SMAs → strong trend in recent direction
                    recent_change = df["close"].iloc[-5:].pct_change().mean() * 100
                    if recent_change > 0:
                        return "strong_uptrend"
                    else:
                        return "strong_downtrend"
            elif adx >= self.adx_threshold_weak:
                if sma_bullish or (sma20 and price > sma20):
                    return "uptrend"
                elif sma_bearish or (sma20 and price < sma20):
                    return "downtrend"
                else:
                    return "ranging"
            else:
                return "ranging"

        # Fallback: simple SMA-based detection
        sma20 = last.get("sma_20")
        sma50 = last.get("sma_50")
        if sma20 and sma50:
            if price > sma20 > sma50:
                return "uptrend"
            elif price < sma20 < sma50:
                return "downtrend"
            else:
                return "ranging"
        elif sma20:
            return "uptrend" if price > sma20 else "downtrend"

        # Ultimate fallback: price momentum
        if len(df) >= 10:
            recent_return = (price / df["close"].iloc[-10] - 1) * 100
            if recent_return > 2:
                return "uptrend"
            elif recent_return < -2:
                return "downtrend"
        return "ranging"

    def _detect_volatility(self, df: pd.DataFrame, price: float) -> str:
        """Detect volatility regime.

        Returns: ``"high"``, ``"moderate"``, ``"low"``, ``"extreme"``,
        ``"squeeze"``.
        """
        last = df.iloc[-1]

        # ATR-based
        atr = last.get("atr") or last.get("atr_14")
        if atr is not None and not np.isnan(atr) and price > 0:
            atr_pct = (float(atr) / price) * 100
            if atr_pct > self.atr_volatile_pct * 2:
                return "extreme"
            elif atr_pct > self.atr_volatile_pct:
                return "high"
            elif atr_pct > self.atr_volatile_pct * 0.5:
                return "moderate"
            else:
                return "low"

        # Bollinger Band width
        bb_upper = last.get("bb_upper")
        bb_lower = last.get("bb_lower")
        bb_middle = last.get("bb_middle") or last.get("sma_20")
        if bb_upper and bb_lower and bb_middle and bb_middle > 0:
            bb_width = ((bb_upper - bb_lower) / bb_middle) * 100
            if bb_width < self.bb_squeeze_pct:
                return "squeeze"
            elif bb_width > 10:
                return "high"
            elif bb_width > 5:
                return "moderate"
            else:
                return "low"

        # Fallback: standard deviation of returns
        if len(df) >= 20:
            returns = df["close"].pct_change().dropna()
            vol = returns.std() * 100  # % std dev
            if vol > 3:
                return "high"
            elif vol > 1.5:
                return "moderate"
            else:
                return "low"

        return "moderate"

    def _detect_volume_regime(self, df: pd.DataFrame) -> str:
        """Detect volume characteristics.

        Returns: ``"above_average"``, ``"below_average"``, ``"average"``,
        ``"surge"``, ``"drying_up"``.
        """
        last = df.iloc[-1]
        volume = last.get("volume")

        if volume is None or np.isnan(volume):
            return "unknown"

        volume = float(volume)

        # Need history for average
        if len(df) >= 20 and "volume" in df.columns:
            vol_sma = df["volume"].rolling(20).mean().iloc[-1]
            if not np.isnan(vol_sma) and vol_sma > 0:
                ratio = volume / vol_sma
                if ratio > 2.0:
                    return "surge"
                elif ratio >= self.volume_confirmation_ratio:
                    return "above_average"
                elif ratio < 0.5:
                    return "drying_up"
                elif ratio < 0.8:
                    return "below_average"
                else:
                    return "average"

        return "unknown"

    def _detect_momentum(self, df: pd.DataFrame) -> str:
        """Detect momentum state.

        Returns: ``"bullish"``, ``"bearish"``, ``"neutral"``,
        ``"overbought"``, ``"oversold"``.
        """
        last = df.iloc[-1]

        # RSI-based
        rsi = last.get("rsi") or last.get("rsi_14")
        if rsi is not None and not np.isnan(rsi):
            rsi = float(rsi)
            if rsi > 70:
                return "overbought"
            elif rsi < 30:
                return "oversold"
            elif rsi > 55:
                return "bullish"
            elif rsi < 45:
                return "bearish"
            else:
                return "neutral"

        # MACD-based
        macd = last.get("macd")
        macd_signal = last.get("macd_signal")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal and macd > 0:
                return "bullish"
            elif macd < macd_signal and macd < 0:
                return "bearish"
            else:
                return "neutral"

        # Fallback: price momentum
        if len(df) >= 10:
            recent_return = (df["close"].iloc[-1] / df["close"].iloc[-10] - 1) * 100
            if recent_return > 3:
                return "bullish"
            elif recent_return < -3:
                return "bearish"

        return "neutral"

    def _detect_patterns(
        self, df: pd.DataFrame, price: float
    ) -> Dict[str, Any]:
        """Detect special patterns: breakout, reversal, squeeze.

        Returns a dict with pattern flags and confidence.
        """
        result = {
            "breakout": False,
            "reversal": False,
            "squeeze": False,
            "breakout_confidence": 0.0,
            "reversal_confidence": 0.0,
        }

        if len(df) < 20:
            return result

        last = df.iloc[-1]

        # Breakout: price breaks above/below recent range
        recent_high = df["high"].iloc[-20:-1].max()
        recent_low = df["low"].iloc[-20:-1].min()
        prev_close = df["close"].iloc[-2]

        if recent_high > 0 and price > recent_high * 1.005:
            result["breakout"] = True
            result["breakout_confidence"] = min(1.0, (price / recent_high - 1) * 100)
        elif recent_low > 0 and price < recent_low * 0.995:
            result["breakout"] = True
            result["breakout_confidence"] = min(1.0, (1 - price / recent_low) * 100)

        # Squeeze: narrow Bollinger Bands
        bb_upper = last.get("bb_upper")
        bb_lower = last.get("bb_lower")
        bb_middle = last.get("bb_middle") or last.get("sma_20")
        if bb_upper and bb_lower and bb_middle and bb_middle > 0:
            bb_width = ((bb_upper - bb_lower) / bb_middle) * 100
            if bb_width < self.bb_squeeze_pct:
                result["squeeze"] = True

        # Reversal: momentum divergence
        rsi = last.get("rsi") or last.get("rsi_14")
        if rsi is not None:
            rsi_prev = df["rsi"].iloc[-5] if "rsi" in df.columns else None
            if rsi_prev is not None:
                # Price makes higher high but RSI makes lower high → bearish divergence
                price_change = (price / df["close"].iloc[-5] - 1) * 100
                rsi_change = float(rsi) - float(rsi_prev)
                if price_change > 1 and rsi_change < -2:
                    result["reversal"] = True
                    result["reversal_confidence"] = min(1.0, abs(rsi_change) / 10)
                elif price_change < -1 and rsi_change > 2:
                    result["reversal"] = True
                    result["reversal_confidence"] = min(1.0, abs(rsi_change) / 10)

        return result

    # ===================================================================
    # Signal combination
    # ===================================================================

    def _combine_signals(
        self,
        trend: str,
        volatility: str,
        volume: str,
        momentum: str,
        pattern: Dict[str, Any],
        price: float,
    ) -> Tuple[MarketRegime, float, Dict[str, float]]:
        """Combine sub-signals into a final regime + confidence.

        Returns ``(regime, confidence, raw_scores)``.
        """
        # Build score vector
        scores: Dict[str, float] = {}

        # Trend score (+2 strong up, +1 up, 0 range, -1 down, -2 strong down)
        trend_scores = {
            "strong_uptrend": 2.0,
            "uptrend": 1.0,
            "ranging": 0.0,
            "downtrend": -1.0,
            "strong_downtrend": -2.0,
        }
        scores["trend"] = trend_scores.get(trend, 0.0)

        # Volatility score (positive = more volatile)
        vol_scores = {
            "extreme": 2.0,
            "high": 1.0,
            "moderate": 0.0,
            "low": -0.5,
            "squeeze": -1.0,
        }
        scores["volatility"] = vol_scores.get(volatility, 0.0)

        # Volume score (positive = confirming)
        vol_confirm = {
            "surge": 1.5,
            "above_average": 0.5,
            "average": 0.0,
            "below_average": -0.5,
            "drying_up": -1.0,
            "unknown": 0.0,
        }
        scores["volume"] = vol_confirm.get(volume, 0.0)

        # Momentum score
        mom_scores = {
            "bullish": 1.0,
            "overbought": 0.5,
            "neutral": 0.0,
            "oversold": -0.5,
            "bearish": -1.0,
        }
        scores["momentum"] = mom_scores.get(momentum, 0.0)

        # Pattern bonuses
        scores["breakout"] = 1.5 if pattern["breakout"] else 0.0
        scores["reversal"] = 1.0 if pattern["reversal"] else 0.0
        scores["squeeze"] = 0.5 if pattern["squeeze"] else 0.0

        # Composite score
        composite = (
            scores["trend"] * 0.35
            + scores["momentum"] * 0.25
            + scores["volatility"] * 0.15
            + scores["volume"] * 0.10
            + scores["breakout"] * 0.10
            + scores["reversal"] * 0.05
        )

        # Map composite to regime
        if pattern["breakout"] and pattern["breakout_confidence"] > 0.5:
            if composite > 0.5:
                regime = MarketRegime.BREAKOUT
            else:
                regime = MarketRegime.BREAKOUT
            confidence = pattern["breakout_confidence"]
        elif pattern["reversal"] and pattern["reversal_confidence"] > 0.4:
            regime = MarketRegime.REVERSAL
            confidence = pattern["reversal_confidence"]
        elif scores["volatility"] >= 1.5:
            regime = MarketRegime.VOLATILE
            confidence = min(1.0, 0.5 + scores["volatility"] * 0.1)
        elif composite >= 1.5:
            regime = MarketRegime.STRONG_UPTREND
            confidence = min(1.0, composite / 2.5)
        elif composite >= 0.5:
            regime = MarketRegime.UPTREND
            confidence = min(1.0, 0.5 + composite * 0.2)
        elif composite <= -1.5:
            regime = MarketRegime.STRONG_DOWNTREND
            confidence = min(1.0, abs(composite) / 2.5)
        elif composite <= -0.5:
            regime = MarketRegime.DOWNTREND
            confidence = min(1.0, 0.5 + abs(composite) * 0.2)
        else:
            # Check for ranging vs. low liquidity
            if scores["volatility"] < -0.5 and scores["volume"] < -0.5:
                regime = MarketRegime.LOW_LIQUIDITY
                confidence = 0.6
            else:
                regime = MarketRegime.RANGING
                confidence = 0.5 + abs(composite) * 0.1

        confidence = max(0.1, min(1.0, confidence))
        return regime, confidence, scores

    # ===================================================================
    # Descriptions
    # ===================================================================

    def _build_description(
        self,
        regime: MarketRegime,
        trend: str,
        volatility: str,
        volume: str,
        momentum: str,
        price: float,
    ) -> str:
        """Build a human-readable regime description."""
        parts = [
            f"Market regime: {regime.value.replace('_', ' ').title()}",
            f"Price: Rs.{price:,.2f}",
            f"Trend: {trend}",
            f"Volatility: {volatility}",
            f"Volume: {volume}",
            f"Momentum: {momentum}",
        ]
        return " | ".join(parts)

    def get_regime_description(self, regime: MarketRegime) -> str:
        """Return a human-readable description of a market regime."""
        descriptions = {
            MarketRegime.STRONG_UPTREND: (
                "The market is in a strong uptrend with high ADX, "
                "bullish SMA alignment, and positive momentum. "
                "Trend-following strategies are likely to perform well."
            ),
            MarketRegime.UPTREND: (
                "The market is trending upward with moderate strength. "
                "Pullback entries and trend-following approaches may work."
            ),
            MarketRegime.RANGING: (
                "The market is moving sideways without a clear directional bias. "
                "Mean-reversion and range-bound strategies are appropriate."
            ),
            MarketRegime.DOWNTREND: (
                "The market is in a downtrend. Short-selling or "
                "defensive positioning is recommended."
            ),
            MarketRegime.STRONG_DOWNTREND: (
                "The market is in a strong downtrend with high selling pressure. "
                "Avoid long positions; short-selling or staying in cash is advised."
            ),
            MarketRegime.VOLATILE: (
                "The market is experiencing high volatility. "
                "Wider stops and reduced position sizes are recommended. "
                "Breakout strategies may capture large moves."
            ),
            MarketRegime.LOW_LIQUIDITY: (
                "Low liquidity and tight ranges detected. "
                "Spreads may be wide; reduce position sizes and avoid market orders."
            ),
            MarketRegime.BREAKOUT: (
                "Price has broken out of a recent trading range. "
                "Momentum strategies and breakout entries are favourable."
            ),
            MarketRegime.REVERSAL: (
                "Momentum divergence suggests a potential trend reversal. "
                "Consider contrarian entries or tightening stops on existing positions."
            ),
        }
        return descriptions.get(regime, "Unknown market regime.")

    def get_trading_implications(self, regime: MarketRegime) -> str:
        """Return trading recommendations for a given regime."""
        implications = {
            MarketRegime.STRONG_UPTREND: (
                "FAVOUR: Long positions, trend-following, moving average crossovers. "
                "AVOID: Short-selling, mean-reversion. "
                "RISK: Enter on pullbacks to SMA 20/50. Use trailing stops."
            ),
            MarketRegime.UPTREND: (
                "FAVOUR: Long positions on dips, breakout entries. "
                "AVOID: Aggressive shorting. "
                "RISK: Watch for weakening momentum; tighten stops if ADX declines."
            ),
            MarketRegime.RANGING: (
                "FAVOUR: Mean-reversion (RSI, Bollinger Bands), range trading. "
                "AVOID: Trend-following, breakout entries (likely false). "
                "RISK: Define clear support/resistance; use tight stops near boundaries."
            ),
            MarketRegime.DOWNTREND: (
                "FAVOUR: Short positions, put options, defensive stocks. "
                "AVOID: Fresh longs, averaging down. "
                "RISK: Beware of short-covering rallies; use SMA 20 as resistance."
            ),
            MarketRegime.STRONG_DOWNTREND: (
                "FAVOUR: Shorts, cash preservation, hedging. "
                "AVOID: All long exposure. "
                "RISK: Extreme volatility; use very wide stops for shorts or stay out."
            ),
            MarketRegime.VOLATILE: (
                "FAVOUR: Breakout strategies, option straddles/strangles, reduced size. "
                "AVOID: Large positions, tight stops (whipsaw risk). "
                "RISK: Use ATR-based stops; reduce position size by 50% minimum."
            ),
            MarketRegime.LOW_LIQUIDITY: (
                "FAVOUR: Limit orders only, patience, wider timeframes. "
                "AVOID: Market orders, large positions, scalping. "
                "RISK: Slippage can be significant; reduce size and use limit orders."
            ),
            MarketRegime.BREAKOUT: (
                "FAVOUR: Momentum entries, volume-confirmed breakouts. "
                "AVOID: Pre-emptive entries (risk of false breakout). "
                "RISK: Wait for close above/below level; confirm with volume surge."
            ),
            MarketRegime.REVERSAL: (
                "FAVOUR: Contrarian entries, tightening stops, profit-taking. "
                "AVOID: Adding to trend-following positions. "
                "RISK: Reversals can fail; wait for confirmation candlestick patterns."
            ),
        }
        return implications.get(regime, "No specific recommendations available.")

    # ===================================================================
    # Utilities
    # ===================================================================

    def _empty_result(self) -> Dict[str, Any]:
        """Return a safe default when detection cannot proceed."""
        return {
            "regime": MarketRegime.RANGING,
            "confidence": 0.0,
            "indicators": {
                "trend": "unknown",
                "volatility": "unknown",
                "volume": "unknown",
                "momentum": "unknown",
            },
            "description": "Insufficient data for regime detection",
            "trading_implications": self.get_trading_implications(MarketRegime.RANGING),
            "raw_scores": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_all_regime_descriptions(self) -> Dict[str, str]:
        """Return descriptions for all regimes."""
        return {
            r.value: self.get_regime_description(r)
            for r in MarketRegime
        }

    def get_all_trading_implications(self) -> Dict[str, str]:
        """Return trading implications for all regimes."""
        return {
            r.value: self.get_trading_implications(r)
            for r in MarketRegime
        }
