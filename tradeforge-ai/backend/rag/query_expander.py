"""
Query Expansion & Optimisation for TradeForge RAG

Expands terse user queries into verbose, retrieval-friendly strings by:
* Injecting trading-terminology synonyms (RSI → relative strength index …).
* Adding indicator-specific signal keywords (oversold, overbought, divergence …).
* Expanding instrument / segment aliases (Nifty → NIFTY50 …).
* Extracting structured entities for downstream filtering.
* Handling Hindi-English mixed queries common in Indian retail trading.

The expanded query is what gets embedded and sent to the vector store;
the original query is preserved for the cross-encoder reranker.
"""

import re
from typing import Dict, List, Optional, Set

from loguru import logger


class QueryExpander:
    """Expands trading-oriented natural-language queries for better retrieval.

    The expansion pipeline runs in this order:
    1. **Entity extraction** – pull out indicators, symbols, actions, timeframes.
    2. **Synonym injection** – append known synonyms for each detected entity.
    3. **Instrument normalisation** – map colloquial names to canonical symbols.
    4. **Signal enrichment** – add indicator-specific signal phrases.
    5. **Hindi hint translation** – translate common Hindi trading terms.

    Parameters
    ----------
    max_expansion_terms:
        Hard cap on the number of extra tokens appended (prevents query
        bloat which can dilute vector similarity).

    Example
    -------
    >>> expander = QueryExpander()
    >>> expanded = expander.expand("RSI buy signal on Nifty")
    >>> print(expanded)
    RSI buy signal on Nifty relative strength index momentum oversold
    below 30 mean reversion NIFTY50 index
    """

    # ------------------------------------------------------------------
    # Static synonym tables
    # ------------------------------------------------------------------

    INDICATOR_SYNONYMS: Dict[str, List[str]] = {
        "rsi": [
            "relative strength index",
            "momentum",
            "overbought",
            "oversold",
            "mean reversion",
            "divergence",
        ],
        "sma": [
            "simple moving average",
            "moving average",
            "trend",
            "trend following",
        ],
        "ema": [
            "exponential moving average",
            "moving average",
            "trend",
            "smoothed",
        ],
        "wma": ["weighted moving average", "moving average", "trend"],
        "macd": [
            "moving average convergence divergence",
            "trend",
            "momentum",
            "crossover",
            "histogram",
        ],
        "bb": [
            "bollinger bands",
            "volatility",
            "standard deviation",
            "squeeze",
            "bandwidth",
        ],
        "atr": [
            "average true range",
            "volatility",
            "stop loss",
            "position sizing",
        ],
        "vwap": [
            "volume weighted average price",
            "institutional",
            "anchor",
            "intraday",
        ],
        "adx": ["average directional index", "trend strength", "dmi"],
        "cci": ["commodity channel index", "cyclical", "overbought", "oversold"],
        "obv": ["on balance volume", "volume flow", "accumulation distribution"],
        "mfi": ["money flow index", "volume weighted rsi", "overbought", "oversold"],
        "stochastic": [
            "stochastic oscillator",
            "%k",
            "%d",
            "overbought",
            "oversold",
            "momentum",
        ],
        "williams": [
            "williams %r",
            "overbought",
            "oversold",
            "momentum",
        ],
        "parabolic": ["parabolic sar", "sar", "trend reversal", "trailing stop"],
        "ichimoku": [
            "ichimoku cloud",
            "tenkan",
            "kijun",
            "senkou",
            "cloud",
            "trend",
        ],
        "pivot": ["pivot points", "support", "resistance", "levels"],
        "fibonacci": ["fibonacci retracement", "fibonacci extension", "golden ratio", "levels"],
        "doji": ["doji candlestick", "reversal", "indecision"],
        "engulfing": ["engulfing pattern", "bullish engulfing", "bearish engulfing", "reversal"],
        "hammer": ["hammer candlestick", "inverted hammer", "bottom reversal"],
    }

    INSTRUMENT_ALIASES: Dict[str, str] = {
        # Indian indices
        "nifty": "NIFTY50",
        "nifty 50": "NIFTY50",
        "nifty50": "NIFTY50",
        "sensex": "SENSEX",
        "banknifty": "BANKNIFTY",
        "nifty bank": "BANKNIFTY",
        "bank nifty": "BANKNIFTY",
        "finnifty": "FINNIFTY",
        "nifty financial": "FINNIFTY",
        "midcap": "NIFTYMIDCAP",
        "nifty midcap": "NIFTYMIDCAP",
        "smallcap": "NIFTYSMALLCAP",
        "nifty it": "NIFTYIT",
        "nifty pharma": "NIFTYPHARMA",
        "nifty auto": "NIFTYAUTO",
        "nifty metal": "NIFTYMETAL",
        "nifty energy": "NIFTYENERGY",
        "nifty fmcg": "NIFTYFMCG",
        "nifty realty": "NIFTYREALTY",
        # Popular stocks
        "reliance": "RELIANCE",
        "tcs": "TCS",
        "infosys": "INFY",
        "hdfc bank": "HDFCBANK",
        "hdfcbank": "HDFCBANK",
        "icici bank": "ICICIBANK",
        "icicibank": "ICICIBANK",
        "sb i": "SBIN",
        "sbi": "SBIN",
        "bharti airtel": "BHARTIARTL",
        "bhartiartl": "BHARTIARTL",
        "itc": "ITC",
        "larsen": "LT",
        "ltim": "LTIM",
        "hul": "HINDUNILVR",
        "hindustan unilever": "HINDUNILVR",
        "axis bank": "AXISBANK",
        "axisbank": "AXISBANK",
        "kotak bank": "KOTAKBANK",
        "kotakbank": "KOTAKBANK",
        "bajaj finance": "BAJFINANCE",
        "bajajfinance": "BAJFINANCE",
        "asian paints": "ASIANPAINT",
        "asianpaint": "ASIANPAINT",
        "maruti": "MARUTI",
        "titan": "TITAN",
    }

    ACTION_SYNONYMS: Dict[str, List[str]] = {
        "buy": ["long", "purchase", "accumulate", "go long", "entry buy"],
        "sell": ["short", "exit", "cover", "go short", "entry sell", "liquidate"],
        "hold": ["maintain position", "do nothing", "stay invested"],
    }

    TIMEFRAME_SYNONYMS: Dict[str, List[str]] = {
        "intraday": ["day trading", "same day", "daily", "within session"],
        "swing": ["short term", "few days", "multi-day", "positional short"],
        "positional": ["medium term", "hold for weeks", "longer term"],
        "scalping": ["very short", "minutes", "quick trade", "micro"],
    }

    # Common Hindi trading terms → English
    HINDI_TERMS: Dict[str, str] = {
        "kharido": "buy",
        "becho": "sell",
        "upar": "up",
        "neeche": "down",
        "teji": "bullish",
        "mandi": "bearish",
        "jordaar": "strong",
        "kamjor": "weak",
        "jama": "accumulate",
        "rupaye": "rupees",
        "paise": "paisa",
        "badlav": "change",
        "sambhal": "hold",
        "nikalo": "exit",
    }

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, max_expansion_terms: int = 25) -> None:
        self.max_expansion_terms = max_expansion_terms

        # Flat lookup: indicator name → list of synonyms (lowercase keys)
        self._indicator_synonyms_lc: Dict[str, List[str]] = {
            k.lower(): v for k, v in self.INDICATOR_SYNONYMS.items()
        }
        # Also add full-name mappings
        for key, syns in self.INDICATOR_SYNONYMS.items():
            for syn in syns:
                if syn not in self._indicator_synonyms_lc:
                    self._indicator_synonyms_lc[syn.lower()] = [key.lower()] + [
                        s for s in syns if s.lower() != syn.lower()
                    ]

        self._instrument_aliases_lc: Dict[str, str] = {
            k.lower(): v for k, v in self.INSTRUMENT_ALIASES.items()
        }

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def expand(self, query: str) -> str:
        """Expand *query* with synonyms and contextual terms.

        The returned string is the **expanded query** that should be
        embedded and used for vector retrieval.  The original query should
        still be passed to the reranker for best results.

        Parameters
        ----------
        query:
            Raw user query (may be terse, e.g. ``"RSI < 30 buy"``).

        Returns
        -------
        str
            Expanded, retrieval-optimised query string.
        """
        if not query or not query.strip():
            return query

        original = query.strip()
        logger.debug(f"Expanding query: {original}")

        # Step 1 – translate any Hindi hints
        translated = self.translate_hindi_hints(original)

        # Step 2 – extract entities
        entities = self.extract_entities(translated)

        # Step 3 – start building expansion tokens
        expansion_tokens: List[str] = []

        # Indicator synonyms
        for ind in entities.get("indicators", []):
            ind_lower = ind.lower()
            if ind_lower in self._indicator_synonyms_lc:
                synonyms = self._indicator_synonyms_lc[ind_lower]
                expansion_tokens.extend(s.lower() for s in synonyms)

        # Instrument normalisation
        for sym in entities.get("symbols", []):
            sym_lower = sym.lower()
            if sym_lower in self._instrument_aliases_lc:
                canonical = self._instrument_aliases_lc[sym_lower]
                if canonical.lower() not in translated.lower():
                    expansion_tokens.append(canonical)

        # Action synonyms
        for action in entities.get("actions", []):
            action_lower = action.lower()
            if action_lower in self.ACTION_SYNONYMS:
                expansion_tokens.extend(self.ACTION_SYNONYMS[action_lower])

        # Timeframe synonyms
        for tf in entities.get("timeframes", []):
            tf_lower = tf.lower()
            if tf_lower in self.TIMEFRAME_SYNONYMS:
                expansion_tokens.extend(self.TIMEFRAME_SYNONYMS[tf_lower])

        # Step 4 – add indicator-specific signal keywords
        expansion_tokens.extend(
            self._add_signal_keywords(entities.get("indicators", []), translated)
        )

        # Step 5 – deduplicate and cap
        seen: Set[str] = set(t.lower() for t in translated.split())
        filtered_tokens: List[str] = []
        for token in expansion_tokens:
            tl = token.lower()
            if tl not in seen and len(filtered_tokens) < self.max_expansion_terms:
                seen.add(tl)
                filtered_tokens.append(token)

        if not filtered_tokens:
            logger.debug("No expansion terms added")
            return translated

        expanded = f"{translated} {' '.join(filtered_tokens)}"
        logger.debug(f"Expanded query ({len(filtered_tokens)} terms added): {expanded[:120]}...")
        return expanded

    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract trading-relevant entities from *query*.

        Returns
        -------
        dict
            Keys: ``indicators``, ``symbols``, ``actions``, ``timeframes``.
        """
        lowered = query.lower()
        words = set(re.findall(r"[a-z][a-z0-9_%]*", lowered))

        # Indicators – match against synonym keys
        indicators: Set[str] = set()
        for ind_key in self._indicator_synonyms_lc:
            # Match whole word or common prefix
            if ind_key in lowered:
                # Extract the canonical short form
                canonical = ind_key.upper()
                indicators.add(canonical)

        # Also check for full names
        for ind_key, syns in self.INDICATOR_SYNONYMS.items():
            for syn in syns:
                if syn.lower() in lowered:
                    indicators.add(ind_key.upper())

        # Symbols / instruments
        symbols: Set[str] = set()
        for alias, canonical in self.INSTRUMENT_ALIASES.items():
            if alias.lower() in lowered:
                symbols.add(canonical)

        # Actions
        actions: Set[str] = set()
        for action_word in ("buy", "sell", "hold", "long", "short", "exit", "cover"):
            if action_word in lowered:
                if action_word in ("buy", "long", "accumulate"):
                    actions.add("buy")
                elif action_word in ("sell", "short", "exit", "cover"):
                    actions.add("sell")
                elif action_word == "hold":
                    actions.add("hold")

        # Timeframes
        timeframes: Set[str] = set()
        for tf_word in ("intraday", "swing", "positional", "scalping", "long term", "short term"):
            if tf_word in lowered:
                timeframes.add(tf_word.replace(" ", "_"))

        return {
            "indicators": sorted(indicators),
            "symbols": sorted(symbols),
            "actions": sorted(actions),
            "timeframes": sorted(timeframes),
        }

    def translate_hindi_hints(self, query: str) -> str:
        """Replace common Hindi trading terms with English equivalents.

        This is a lightweight best-effort translation for mixed-language
        queries common among Indian retail traders.

        Parameters
        ----------
        query:
            Query string that may contain Hindi words.

        Returns
        -------
        str
            Query with Hindi terms replaced by English.
        """
        if not query:
            return query

        result = query
        for hindi, english in self.HINDI_TERMS.items():
            # Word-boundary aware replacement
            pattern = r"\b" + re.escape(hindi) + r"\b"
            result = re.sub(pattern, english, result, flags=re.IGNORECASE)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _add_signal_keywords(indicators: List[str], query: str) -> List[str]:
        """Add indicator-specific signal phrases based on what was detected.

        For example, if RSI is mentioned and the query hints at 'buy',
        add 'oversold below 30'.  If the query hints at 'sell', add
        'overbought above 70'.
        """
        lowered = query.lower()
        is_buy = any(w in lowered for w in ("buy", "long", "purchase", "accumulate", "kharido"))
        is_sell = any(w in lowered for w in ("sell", "short", "exit", "becho"))

        extra: List[str] = []
        for ind in indicators:
            ind_lc = ind.lower()
            if ind_lc == "rsi":
                if is_buy:
                    extra.extend(["oversold", "below 30", "bullish divergence"])
                elif is_sell:
                    extra.extend(["overbought", "above 70", "bearish divergence"])
                else:
                    extra.extend(["momentum", "overbought", "oversold"])

            elif ind_lc in ("macd",):
                if is_buy:
                    extra.extend(["bullish crossover", "positive histogram", "above signal"])
                elif is_sell:
                    extra.extend(["bearish crossover", "negative histogram", "below signal"])
                else:
                    extra.extend(["crossover", "histogram", "signal line"])

            elif ind_lc in ("sma", "ema"):
                if is_buy:
                    extra.extend(["price above", "golden cross", "bullish trend"])
                elif is_sell:
                    extra.extend(["price below", "death cross", "bearish trend"])
                else:
                    extra.extend(["trend", "moving average crossover"])

            elif ind_lc == "bb":
                if is_buy:
                    extra.extend(["lower band touch", "band squeeze", "mean reversion"])
                elif is_sell:
                    extra.extend(["upper band touch", "overbought band", "breakout"])
                else:
                    extra.extend(["volatility", "band width", "squeeze"])

            elif ind_lc == "stochastic":
                if is_buy:
                    extra.extend(["%k below 20", "oversold", "bullish crossover"])
                elif is_sell:
                    extra.extend(["%k above 80", "overbought", "bearish crossover"])
                else:
                    extra.extend(["%k", "%d", "overbought", "oversold"])

            elif ind_lc == "vwap":
                if is_buy:
                    extra.extend(["price above vwap", "institutional buying", "bullish"])
                elif is_sell:
                    extra.extend(["price below vwap", "institutional selling", "bearish"])
                else:
                    extra.extend(["intraday anchor", "volume weighted"])

        return extra

    def get_expansion_summary(self, query: str) -> Dict[str, any]:
        """Return a diagnostic dict showing what expansion was performed.

        Useful for debugging retrieval quality.
        """
        entities = self.extract_entities(query)
        translated = self.translate_hindi_hints(query)
        expanded = self.expand(query)
        return {
            "original": query,
            "translated": translated if translated != query else None,
            "expanded": expanded,
            "entities_detected": entities,
            "expansion_length": len(expanded.split()),
            "original_length": len(query.split()),
        }
