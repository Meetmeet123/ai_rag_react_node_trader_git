"""
Document Processor for TradeForge RAG

Handles:
- Text chunking with sentence-aware splitting and overlap
- Strategy document formatting (dict → rich text for embedding)
- Backtest result summarisation
- Market data / regime context extraction
- News article formatting
- Embedding-ready text generation
- Deterministic document ID computation

Every formatter converts a raw data structure into a human-readable,
semantically rich paragraph that is ideal for sentence-transformer
embedding and downstream retrieval.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .models import (
    BacktestDocument,
    BacktestMetrics,
    IndicatorDocument,
    MarketRegimeDocument,
    NewsDocument,
    StrategyDocument,
    TradeDocument,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ChunkConfig:
    """Controls how raw text is split into overlapping chunks.

    Attributes:
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between adjacent chunks.
        min_chunk_size: Chunks shorter than this are merged with neighbours.
    """

    chunk_size: int = 512
    chunk_overlap: int = 128
    min_chunk_size: int = 100


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class DocumentProcessor:
    """Transforms heterogeneous trading data into RAG-ready documents.

    The processor handles four broad categories:

    1. **Chunking** – splits long texts into sentence-aware overlapping
       chunks so that no semantic unit is broken mid-sentence.
    2. **Formatting** – converts structured dicts / Pydantic models into
       rich narrative paragraphs optimised for embedding similarity.
    3. **ID generation** – produces deterministic, collision-resistant IDs
       so that the same logical document always maps to the same vector.
    4. **Batch helpers** – convenience wrappers that emit fully-formed
       ``Document`` objects ready for ``VectorStore.add_documents()``.

    Parameters
    ----------
    chunk_config:
        ``ChunkConfig`` instance (defaults are sensible for MiniLM).

    Example
    -------
    >>> processor = DocumentProcessor()
    >>> chunks = processor.chunk_text(long_strategy_description)
    >>> doc_text = processor.format_strategy_document(strategy_dict)
    """

    # Common indicator names used for entity extraction
    _INDICATOR_NAMES = {
        "rsi", "macd", "sma", "ema", "vwap", "atr", "bb", "bollinger",
        "stochastic", "cci", "adx", "obv", "mfi", "williams", "roc",
        "adx", "dmi", "parabolic", "sar", "ichimoku", "fibonacci",
        "pivot", "support", "resistance", "trendline", "volume",
        "momentum", "divergence", "breakout", "reversal",
    }

    _INDIAN_INDICES = {
        "nifty", "nifty50", "nifty 50", "sensex", "banknifty",
        "nifty bank", "finnifty", "nifty financial", "midcap",
        "smallcap", "nifty it", "nifty pharma", "nifty auto",
        "nifty metal", "nifty energy", "nifty fmcg", "nifty realty",
    }

    def __init__(self, chunk_config: Optional[ChunkConfig] = None) -> None:
        self.config = chunk_config or ChunkConfig()

    # ===================================================================
    # 1. Chunking
    # ===================================================================

    def chunk_text(
        self,
        text: str,
        source_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Split *text* into overlapping sentence-aware chunks.

        The algorithm:
        1. Split on sentence boundaries (``.!?`` followed by whitespace).
        2. Greedily accumulate sentences until *chunk_size* is reached.
        3. Carry over the last *chunk_overlap* characters to the next chunk.
        4. Merge trailing chunks shorter than *min_chunk_size*.

        Parameters
        ----------
        text:
            Source text (may be very long).
        source_metadata:
            Metadata dict attached to every chunk (e.g. ``strategy_id``).

        Returns
        -------
        list[dict]
            Each dict has keys ``content``, ``chunk_index``, ``total_chunks``,
            and merged *source_metadata*.
        """
        if not text or not text.strip():
            return []

        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        chunks: List[str] = []
        current_chunk = ""

        for sent in sentences:
            candidate = current_chunk + (" " if current_chunk else "") + sent
            if len(candidate) <= self.config.chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Overlap: start the new chunk with the tail of the previous one
                if current_chunk and self.config.chunk_overlap > 0:
                    overlap_text = current_chunk[-self.config.chunk_overlap :]
                    # Find a word boundary for clean overlap
                    overlap_text = overlap_text.lstrip()
                    current_chunk = overlap_text + " " + sent
                else:
                    current_chunk = sent

        if current_chunk:
            chunks.append(current_chunk.strip())

        # Merge last chunk if too small
        if len(chunks) >= 2 and len(chunks[-1]) < self.config.min_chunk_size:
            chunks[-2] = chunks[-2] + " " + chunks[-1]
            chunks.pop()

        source_metadata = source_metadata or {}
        return [
            {
                "content": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **source_metadata,
            }
            for i, chunk in enumerate(chunks)
        ]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text on sentence boundaries while preserving the delimiter."""
        # Split on .!? followed by whitespace or end-of-string
        pattern = r"(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$"
        parts = re.split(pattern, text.strip())
        return [p.strip() for p in parts if p.strip()]

    # ===================================================================
    # 2. Formatters – structured data → rich text
    # ===================================================================

    def format_strategy_document(self, strategy: Dict[str, Any]) -> str:
        """Convert a strategy dictionary into an embedding-friendly narrative.

        The output is a dense paragraph that includes every meaningful field
        so that semantic retrieval can match on strategy name, instrument,
        indicators, rules, and performance alike.

        Expected keys (all optional except *name*):
            name, description, instrument, segment, timeframe,
            entry_conditions, exit_conditions,
            stop_loss, target, position_sizing,
            win_rate, total_pnl, sharpe_ratio, max_drawdown,
            total_trades, tags.

        Returns
        -------
        str
            Rich text paragraph suitable for embedding.
        """
        parts: List[str] = []

        name = strategy.get("name", "Unnamed Strategy")
        parts.append(f"Strategy: {name}")

        if strategy.get("description"):
            parts.append(f"Description: {strategy['description']}")

        instrument = strategy.get("instrument", "Unknown Instrument")
        segment = strategy.get("segment", "equity")
        timeframe = strategy.get("timeframe", "15m")
        parts.append(
            f"Instrument: {instrument} | Segment: {segment} | Timeframe: {timeframe}"
        )

        # Entry conditions
        entry_conds = strategy.get("entry_conditions", [])
        if entry_conds:
            entries = []
            for ec in entry_conds:
                indicator = ec.get("indicator", "?")
                period = ec.get("period", "")
                condition = ec.get("condition", "")
                value = ec.get("value", "")
                entries.append(
                    f"{indicator}{f'({period})' if period else ''} {condition} {value}"
                )
            parts.append(f"Entry Conditions: {'; '.join(entries)}")

        # Exit conditions
        exit_conds = strategy.get("exit_conditions", [])
        if exit_conds:
            exits = []
            for xc in exit_conds:
                indicator = xc.get("indicator", "")
                condition = xc.get("condition", "")
                value = xc.get("value", "")
                exits.append(
                    f"{indicator + ' ' if indicator else ''}{condition} {value}"
                )
            parts.append(f"Exit Conditions: {'; '.join(exits)}")

        # Risk management
        sl = strategy.get("stop_loss")
        if sl:
            parts.append(
                f"Stop Loss: {sl.get('type', 'fixed')} = {sl.get('value', '')}"
                f"{' (trailing)' if sl.get('trailing') else ''}"
            )

        tgt = strategy.get("target")
        if tgt:
            parts.append(
                f"Target: {tgt.get('type', 'fixed')} = {tgt.get('value', '')}"
                f"{f' (RRR {tgt.get('rrr')})' if tgt.get('rrr') else ''}"
            )

        pos = strategy.get("position_sizing")
        if pos:
            parts.append(
                f"Position Sizing: {pos.get('type', 'fixed')} = {pos.get('value', '')}"
            )

        # Performance metrics
        perf_parts = []
        if strategy.get("win_rate") is not None:
            perf_parts.append(f"Win Rate: {strategy['win_rate']:.1f}%")
        if strategy.get("total_pnl") is not None:
            perf_parts.append(f"P&L: Rs.{strategy['total_pnl']:,.2f}")
        if strategy.get("sharpe_ratio") is not None:
            perf_parts.append(f"Sharpe: {strategy['sharpe_ratio']:.2f}")
        if strategy.get("max_drawdown") is not None:
            perf_parts.append(f"Max DD: {strategy['max_drawdown']:.2f}%")
        if strategy.get("total_trades"):
            perf_parts.append(f"Trades: {strategy['total_trades']}")
        if perf_parts:
            parts.append("Performance: " + ", ".join(perf_parts))

        # Tags
        tags = strategy.get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")

        return "\n".join(parts)

    def format_backtest_document(self, backtest: Dict[str, Any]) -> str:
        """Convert backtest result dictionary into rich embedding text.

        Expected keys:
            strategy_name, symbol, start_date, end_date, timeframe,
            total_trades, winning_trades, losing_trades,
            win_rate, total_pnl, avg_profit, avg_loss,
            profit_factor, sharpe_ratio, max_drawdown_pct,
            best_trade, worst_trade, monthly_returns, parameter_values.

        Returns
        -------
        str
            Human-readable backtest summary for embedding.
        """
        parts: List[str] = []

        parts.append(
            f"Backtest: {backtest.get('strategy_name', 'Unknown')} "
            f"on {backtest.get('symbol', 'Unknown')}"
        )

        start = backtest.get("start_date", "?")
        end = backtest.get("end_date", "?")
        tf = backtest.get("timeframe", "?")
        parts.append(f"Period: {start} to {end} | Timeframe: {tf}")

        total = backtest.get("total_trades", 0)
        wins = backtest.get("winning_trades", 0)
        losses = backtest.get("losing_trades", 0)
        parts.append(f"Trades: {total} (Wins: {wins}, Losses: {losses})")

        metrics = []
        if backtest.get("win_rate") is not None:
            metrics.append(f"Win Rate: {backtest['win_rate']:.1f}%")
        if backtest.get("total_pnl") is not None:
            metrics.append(f"P&L: Rs.{backtest['total_pnl']:,.2f}")
        if backtest.get("avg_profit") is not None:
            metrics.append(f"Avg Profit: Rs.{backtest['avg_profit']:,.2f}")
        if backtest.get("avg_loss") is not None:
            metrics.append(f"Avg Loss: Rs.{backtest['avg_loss']:,.2f}")
        if backtest.get("profit_factor") is not None:
            metrics.append(f"Profit Factor: {backtest['profit_factor']:.2f}")
        if backtest.get("sharpe_ratio") is not None:
            metrics.append(f"Sharpe: {backtest['sharpe_ratio']:.2f}")
        if backtest.get("max_drawdown_pct") is not None:
            metrics.append(f"Max Drawdown: {backtest['max_drawdown_pct']:.2f}%")
        if backtest.get("best_trade") is not None:
            metrics.append(f"Best Trade: Rs.{backtest['best_trade']:,.2f}")
        if backtest.get("worst_trade") is not None:
            metrics.append(f"Worst Trade: Rs.{backtest['worst_trade']:,.2f}")
        if metrics:
            parts.append(" | ".join(metrics))

        # Monthly breakdown
        monthly = backtest.get("monthly_returns", {})
        if monthly:
            parts.append("Monthly Returns:")
            for month, ret in sorted(monthly.items()):
                parts.append(f"  {month}: {ret:+.2f}%")

        # Parameters used
        params = backtest.get("parameter_values", {})
        if params:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            parts.append(f"Parameters: {param_str}")

        return "\n".join(parts)

    def format_market_regime_document(
        self,
        symbol: str,
        price: float,
        indicators: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Format current market conditions as a context-rich paragraph.

        Parameters
        ----------
        symbol:
            Trading symbol (e.g. ``"NIFTY50"``).
        price:
            Current price / LTP.
        indicators:
            Dict with keys such as ``rsi``, ``sma_20``, ``sma_50``,
            ``macd``, ``macd_signal``, ``atr``, ``bb_upper``, ``bb_lower``,
            ``volume``, ``volume_avg``, ``adx``.
        timestamp:
            Observation time (defaults to ``datetime.utcnow()``).

        Returns
        -------
        str
            Human-readable regime description for embedding.

        Example
        -------
        >>> text = processor.format_market_regime_document(
        ...     "NIFTY50", 22450.0,
        ...     {"rsi_14": 32, "sma_20": 22500, "macd": -15, "volume": 1.2}
        ... )
        """
        ts = timestamp or datetime.utcnow()
        parts: List[str] = []

        parts.append(f"Market Snapshot for {symbol} at Rs.{price:.2f} ({ts.isoformat()})")

        # RSI interpretation
        rsi = indicators.get("rsi_14") or indicators.get("rsi")
        if rsi is not None:
            if rsi < 30:
                state = "oversold – potential buy zone"
            elif rsi > 70:
                state = "overbought – potential sell zone"
            else:
                state = "neutral zone"
            parts.append(f"RSI(14): {rsi:.1f} ({state})")

        # Moving averages
        sma20 = indicators.get("sma_20")
        sma50 = indicators.get("sma_50")
        sma200 = indicators.get("sma_200")
        if sma20:
            rel = "above" if price > sma20 else "below"
            parts.append(f"SMA 20: {sma20:.2f} (price {rel})")
        if sma50:
            rel = "above" if price > sma50 else "below"
            parts.append(f"SMA 50: {sma50:.2f} (price {rel})")
        if sma200:
            rel = "above" if price > sma200 else "below"
            trend = "bullish" if price > sma200 else "bearish"
            parts.append(f"SMA 200: {sma200:.2f} (price {rel}, long-term {trend})")

        # Golden / Death cross
        if sma20 and sma50:
            cross = "Golden Cross" if sma20 > sma50 else "Death Cross"
            parts.append(f"MA Cross: {cross} (SMA20 vs SMA50)")

        # MACD
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                cross_state = "bullish crossover"
            elif macd < macd_signal:
                cross_state = "bearish crossover"
            else:
                cross_state = "neutral"
            parts.append(f"MACD: {macd:.2f} vs Signal {macd_signal:.2f} ({cross_state})")

        # ATR / Volatility
        atr = indicators.get("atr") or indicators.get("atr_14")
        if atr is not None:
            atr_pct = (atr / price) * 100 if price > 0 else 0
            vol_level = "high" if atr_pct > 2 else "moderate" if atr_pct > 1 else "low"
            parts.append(f"ATR(14): {atr:.2f} ({atr_pct:.2f}% of price, {vol_level} volatility)")

        # Bollinger Bands
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        bb_middle = indicators.get("bb_middle") or indicators.get("sma_20")
        if bb_upper and bb_lower:
            bb_width = ((bb_upper - bb_lower) / bb_middle * 100) if bb_middle else 0
            squeeze = "Squeeze" if bb_width < 5 else "Wide"
            parts.append(f"Bollinger: Upper {bb_upper:.2f}, Lower {bb_lower:.2f} ({squeeze}, width {bb_width:.1f}%)")

        # Volume
        volume = indicators.get("volume")
        vol_avg = indicators.get("volume_avg") or indicators.get("volume_sma_20")
        if volume and vol_avg:
            ratio = volume / vol_avg
            v_state = "above average" if ratio > 1.2 else "below average" if ratio < 0.8 else "normal"
            parts.append(f"Volume: {volume:,.0f} vs avg {vol_avg:,.0f} ({ratio:.1f}x, {v_state})")

        # ADX
        adx = indicators.get("adx") or indicators.get("adx_14")
        if adx is not None:
            trend_strength = "strong" if adx > 25 else "weak" if adx < 20 else "moderate"
            parts.append(f"ADX(14): {adx:.1f} ({trend_strength} trend)")

        # VWAP
        vwap = indicators.get("vwap")
        if vwap:
            rel = "above VWAP (bullish)" if price > vwap else "below VWAP (bearish)"
            parts.append(f"VWAP: {vwap:.2f} ({rel})")

        return "\n".join(parts)

    def format_news_document(self, news_item: Dict[str, Any]) -> str:
        """Format a news article dict into embedding-friendly text.

        Expected keys:
            title, summary, source, published_at, symbols, sentiment,
            sentiment_score, category.

        Returns
        -------
        str
            Formatted news text.
        """
        parts: List[str] = []

        title = news_item.get("title", "Untitled")
        parts.append(f"News: {title}")

        if news_item.get("summary"):
            parts.append(f"Summary: {news_item['summary']}")

        source = news_item.get("source", "")
        published = news_item.get("published_at", "")
        if source or published:
            parts.append(f"Source: {source} | Published: {published}")

        symbols = news_item.get("symbols", [])
        if symbols:
            parts.append(f"Affects: {', '.join(symbols)}")

        sentiment = news_item.get("sentiment")
        score = news_item.get("sentiment_score")
        if sentiment:
            score_str = f" ({score:+.2f})" if score is not None else ""
            parts.append(f"Sentiment: {sentiment}{score_str}")

        category = news_item.get("category")
        if category:
            parts.append(f"Category: {category}")

        return "\n".join(parts)

    def format_trade_document(self, trade: Dict[str, Any]) -> str:
        """Format an executed trade dict into embedding-friendly text.

        Expected keys:
            trade_id, symbol, strategy_name, side, entry_price,
            exit_price, quantity, entry_time, exit_time, pnl,
            stop_loss, target, status.

        Returns
        -------
        str
            Formatted trade text.
        """
        parts: List[str] = []

        side = trade.get("side", "UNKNOWN")
        symbol = trade.get("symbol", "UNKNOWN")
        qty = trade.get("quantity", 0)
        parts.append(f"Trade: {side} {symbol} x{qty}")

        strategy = trade.get("strategy_name", "")
        if strategy:
            parts.append(f"Strategy: {strategy}")

        entry_price = trade.get("entry_price")
        entry_time = trade.get("entry_time", "")
        if entry_price:
            parts.append(f"Entry: Rs.{entry_price:.2f} at {entry_time}")

        exit_price = trade.get("exit_price")
        exit_time = trade.get("exit_time")
        if exit_price:
            parts.append(f"Exit: Rs.{exit_price:.2f} at {exit_time}")

        pnl = trade.get("pnl")
        if pnl is not None:
            pnl_sign = "+" if pnl >= 0 else ""
            parts.append(f"P&L: Rs.{pnl_sign}{pnl:,.2f}")

        pnl_pct = trade.get("pnl_pct")
        if pnl_pct is not None:
            parts.append(f"Return: {pnl_pct:+.2f}%")

        sl = trade.get("stop_loss")
        if sl:
            parts.append(f"Stop Loss: Rs.{sl:.2f}")

        tgt = trade.get("target")
        if tgt:
            parts.append(f"Target: Rs.{tgt:.2f}")

        status = trade.get("status", "unknown")
        parts.append(f"Status: {status}")

        return "\n".join(parts)

    def format_indicator_document(self, indicator: Dict[str, Any]) -> str:
        """Format a technical indicator reference dict into embedding text.

        Expected keys:
            name, full_name, category, description, best_for,
            interpretation, common_periods, signals.

        Returns
        -------
        str
            Formatted indicator reference text.
        """
        parts: List[str] = []

        name = indicator.get("name", "Unknown")
        full_name = indicator.get("full_name", "")
        parts.append(f"Indicator: {name}{f' ({full_name})' if full_name else ''}")

        category = indicator.get("category", "")
        if category:
            parts.append(f"Category: {category}")

        if indicator.get("description"):
            parts.append(f"Description: {indicator['description']}")

        if indicator.get("best_for"):
            parts.append(f"Best Used For: {indicator['best_for']}")

        if indicator.get("interpretation"):
            parts.append(f"How to Interpret: {indicator['interpretation']}")

        periods = indicator.get("common_periods", [])
        if periods:
            parts.append(f"Common Periods: {', '.join(str(p) for p in periods)}")

        signals = indicator.get("signals", [])
        if signals:
            parts.append(f"Common Signals: {', '.join(signals)}")

        return "\n".join(parts)

    # ===================================================================
    # 3. ID generation
    # ===================================================================

    @staticmethod
    def compute_doc_id(content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Compute a deterministic document ID from content + metadata.

        Uses MD5 so that re-ingesting the same logical document produces
        the same ID, enabling natural upsert semantics.

        Parameters
        ----------
        content:
            Document text content.
        metadata:
            Optional metadata dict (sorted keys for determinism).

        Returns
        -------
        str
            32-character hex MD5 digest.
        """
        payload = content + json.dumps(metadata or {}, sort_keys=True, default=str)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    # ===================================================================
    # 4. Convenience – build Document objects from models
    # ===================================================================

    def strategy_to_document(self, strategy: StrategyDocument) -> "Document":
        """Convert a ``StrategyDocument`` Pydantic model to a RAG ``Document``."""
        from .vector_store import Document as VSDocument

        text = strategy.to_embedding_text()
        return VSDocument(
            id=strategy.id or self.compute_doc_id(text, strategy.metadata),
            content=text,
            metadata={
                "doc_type": "strategy",
                "name": strategy.name,
                "instrument": strategy.instrument,
                "segment": strategy.segment.value,
                "timeframe": strategy.timeframe.value,
                "win_rate": strategy.win_rate,
                "total_pnl": strategy.total_pnl,
                "sharpe_ratio": strategy.sharpe_ratio,
                "tags": strategy.tags,
                **strategy.metadata,
            },
        )

    def backtest_to_document(self, backtest: BacktestDocument) -> "Document":
        """Convert a ``BacktestDocument`` Pydantic model to a RAG ``Document``."""
        from .vector_store import Document as VSDocument

        text = backtest.to_embedding_text()
        return VSDocument(
            id=backtest.id or self.compute_doc_id(text, backtest.metadata),
            content=text,
            metadata={
                "doc_type": "backtest_result",
                "strategy_name": backtest.strategy_name,
                "strategy_id": backtest.strategy_id,
                "symbol": backtest.symbol,
                "timeframe": backtest.timeframe.value,
                "total_trades": backtest.metrics.total_trades,
                "win_rate": backtest.metrics.win_rate,
                "total_pnl": backtest.metrics.total_pnl,
                **backtest.metadata,
            },
        )

    def regime_to_document(self, regime: MarketRegimeDocument) -> "Document":
        """Convert a ``MarketRegimeDocument`` to a RAG ``Document``."""
        from .vector_store import Document as VSDocument

        text = regime.to_embedding_text()
        return VSDocument(
            id=regime.id or self.compute_doc_id(text, regime.metadata),
            content=text,
            metadata={
                "doc_type": "market_regime",
                "symbol": regime.symbol,
                "regime": regime.regime,
                "confidence": regime.confidence,
                "timestamp": regime.timestamp.isoformat(),
                **regime.metadata,
            },
        )

    def news_to_document(self, news: NewsDocument) -> "Document":
        """Convert a ``NewsDocument`` to a RAG ``Document``."""
        from .vector_store import Document as VSDocument

        text = news.to_embedding_text()
        return VSDocument(
            id=news.id or self.compute_doc_id(text, news.metadata),
            content=text,
            metadata={
                "doc_type": "news_event",
                "title": news.title,
                "source": news.source,
                "symbols": news.symbols,
                "sentiment": news.sentiment,
                "sentiment_score": news.sentiment_score,
                "published_at": news.published_at.isoformat(),
                **news.metadata,
            },
        )

    def trade_to_document(self, trade: TradeDocument) -> "Document":
        """Convert a ``TradeDocument`` to a RAG ``Document``."""
        from .vector_store import Document as VSDocument

        text = trade.to_embedding_text()
        return VSDocument(
            id=trade.id or self.compute_doc_id(text, trade.metadata),
            content=text,
            metadata={
                "doc_type": "trade_history",
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "strategy_name": trade.strategy_name,
                "side": trade.side,
                "status": trade.status,
                "pnl": trade.pnl,
                "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                **trade.metadata,
            },
        )

    def indicator_to_document(self, indicator: IndicatorDocument) -> "Document":
        """Convert an ``IndicatorDocument`` to a RAG ``Document``."""
        from .vector_store import Document as VSDocument

        text = indicator.to_embedding_text()
        return VSDocument(
            id=indicator.id or self.compute_doc_id(text, indicator.metadata),
            content=text,
            metadata={
                "doc_type": "indicator_context",
                "name": indicator.name,
                "category": indicator.category,
                **indicator.metadata,
            },
        )

    # ===================================================================
    # 5. Batch helpers
    # ===================================================================

    def process_strategy_batch(
        self, strategies: List[Dict[str, Any]]
    ) -> List["Document"]:
        """Convert a batch of strategy dicts into ``Document`` objects."""
        from .vector_store import Document as VSDocument

        docs: List[VSDocument] = []
        for s in strategies:
            text = self.format_strategy_document(s)
            docs.append(
                VSDocument(
                    id=s.get("id") or self.compute_doc_id(text, s.get("metadata", {})),
                    content=text,
                    metadata={
                        "doc_type": "strategy",
                        "name": s.get("name", ""),
                        "instrument": s.get("instrument", ""),
                        **s.get("metadata", {}),
                    },
                )
            )
        return docs

    def process_backtest_batch(
        self, backtests: List[Dict[str, Any]]
    ) -> List["Document"]:
        """Convert a batch of backtest dicts into ``Document`` objects."""
        from .vector_store import Document as VSDocument

        docs: List[VSDocument] = []
        for b in backtests:
            text = self.format_backtest_document(b)
            docs.append(
                VSDocument(
                    id=b.get("id") or self.compute_doc_id(text, b.get("metadata", {})),
                    content=text,
                    metadata={
                        "doc_type": "backtest_result",
                        "strategy_name": b.get("strategy_name", ""),
                        "symbol": b.get("symbol", ""),
                        **b.get("metadata", {}),
                    },
                )
            )
        return docs

    def process_news_batch(self, news_items: List[Dict[str, Any]]) -> List["Document"]:
        """Convert a batch of news dicts into ``Document`` objects."""
        from .vector_store import Document as VSDocument

        docs: List[VSDocument] = []
        for n in news_items:
            text = self.format_news_document(n)
            docs.append(
                VSDocument(
                    id=n.get("id") or self.compute_doc_id(text, n.get("metadata", {})),
                    content=text,
                    metadata={
                        "doc_type": "news_event",
                        "title": n.get("title", ""),
                        "source": n.get("source", ""),
                        "symbols": n.get("symbols", []),
                        **n.get("metadata", {}),
                    },
                )
            )
        return docs

    # ===================================================================
    # 6. Entity extraction helpers
    # ===================================================================

    def extract_trading_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract trading-relevant entities from free text.

        Returns a dict with keys ``indicators``, ``symbols``, ``actions``,
        ``timeframes``.
        """
        lowered = text.lower()
        words = set(re.findall(r"[a-z][a-z0-9]*", lowered))

        indicators = [w.upper() for w in words if w in self._INDICATOR_NAMES]
        symbols = [w.upper() for w in words if w.upper() in {s.upper() for s in self._INDIAN_INDICES}]

        actions = []
        if any(w in lowered for w in ("buy", "long", "purchase", "accumulate")):
            actions.append("BUY")
        if any(w in lowered for w in ("sell", "short", "exit", "cover")):
            actions.append("SELL")

        timeframes = []
        tf_map = {
            "intraday": "INTRADAY",
            "swing": "SWING",
            "positional": "POSITIONAL",
            "scalping": "SCALPING",
            "long term": "LONG_TERM",
            "short term": "SHORT_TERM",
        }
        for keyword, label in tf_map.items():
            if keyword in lowered:
                timeframes.append(label)

        return {
            "indicators": list(set(indicators)),
            "symbols": list(set(symbols)),
            "actions": actions,
            "timeframes": timeframes,
        }
