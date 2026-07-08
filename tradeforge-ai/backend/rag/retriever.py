"""
Multi-Source Retriever for TradeForge RAG

Retrieves relevant context from multiple sources simultaneously:
1. Similar strategies – what worked before under comparable conditions?
2. Backtest results – how did those strategies actually perform?
3. Market regime – what is the market doing right now?
4. News events – what just happened that might affect prices?
5. Indicator context – what do the technical indicators imply?
6. Trade history – what trades have been executed recently?
7. Market commentary – published analysis and commentary.

Implements:
* Query expansion with trading-specific synonyms.
* Source-specific retrieval strategies (different top_k, filters).
* Time-decay weighting (recent documents score higher).
* Weighted reciprocal rank fusion across sources.
* Multi-hop retrieval (follow references between documents).
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

from .document_processor import DocumentProcessor
from .query_expander import QueryExpander
from .vector_store import VectorStore

# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class RetrievalSource(Enum):
    """Named sources that the retriever can query."""

    STRATEGIES = "strategies"
    BACKTEST_RESULTS = "backtest_results"
    MARKET_REGIME = "market_regime"
    NEWS_EVENTS = "news_events"
    INDICATOR_CONTEXT = "indicator_context"
    TRADE_HISTORY = "trade_history"
    MARKET_COMMENTARY = "market_commentary"


@dataclass
class RetrievedContext:
    """A single piece of context returned by the retriever.

    Attributes:
        source: Which ``RetrievalSource`` this came from.
        content: The actual text content.
        metadata: Associated metadata (symbol, timestamp, score, etc.).
        relevance_score: Final fused relevance score (after decay & weighting).
        timestamp: Document creation / observation time.
        doc_id: Unique document identifier in the vector store.
    """

    source: RetrievalSource
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    timestamp: Optional[datetime] = None
    doc_id: str = ""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class MultiSourceRetriever:
    """Intelligent multi-source retriever for the TradeForge RAG pipeline.

    The retriever coordinates searches across all vector-store collections,
    fuses the results, and returns a single ranked list of ``RetrievedContext``
    objects.  It is designed to be used from ``async`` code so that multiple
    collection searches can run concurrently.

    Features
    --------
    * **Query expansion** – trading synonyms are injected automatically.
    * **Source weighting** – configurable per-source importance.
    * **Time decay** – newer documents get a relevance boost.
    * **Reciprocal rank fusion** – mathematically sound merging of ranked lists.
    * **Symbol / segment filtering** – narrow results to a specific instrument.

    Parameters
    ----------
    vector_store:
        Initialised ``VectorStore`` instance.
    document_processor:
        ``DocumentProcessor`` for formatting helpers.
    query_expander:
        Optional ``QueryExpander`` (created automatically if ``None``).
    default_top_k:
        Default number of results to retrieve per source.

    Example
    -------
    >>> retriever = MultiSourceRetriever(vector_store, processor)
    >>> contexts = await retriever.retrieve(
    ...     "RSI oversold mean reversion strategy for NIFTY50",
    ...     sources=[RetrievalSource.STRATEGIES, RetrievalSource.INDICATOR_CONTEXT],
    ...     symbol="NIFTY50",
    ...     top_k=10,
    ... )
    """

    # Default importance weights for each source (sum need not be 1.0)
    DEFAULT_SOURCE_WEIGHTS: Dict[RetrievalSource, float] = {
        RetrievalSource.STRATEGIES: 1.0,
        RetrievalSource.BACKTEST_RESULTS: 0.9,
        RetrievalSource.MARKET_REGIME: 1.2,  # current conditions are critical
        RetrievalSource.NEWS_EVENTS: 1.1,
        RetrievalSource.INDICATOR_CONTEXT: 0.7,
        RetrievalSource.TRADE_HISTORY: 0.8,
        RetrievalSource.MARKET_COMMENTARY: 0.9,
    }

    # RRF constant – prevents rank dominance by a single source
    RRF_K: int = 60

    # Time-decay half-life in hours (documents older than this lose 50 % score)
    DECAY_HALF_LIFE_HOURS: float = 24.0

    def __init__(
        self,
        vector_store: "VectorStore",
        document_processor: "DocumentProcessor",
        query_expander: Optional[QueryExpander] = None,
        default_top_k: int = 5,
    ) -> None:
        self.vector_store = vector_store
        self.processor = document_processor
        self.query_expander = query_expander or QueryExpander()
        self.default_top_k = default_top_k

        # Mutable weights – callers can adjust at runtime
        self.source_weights: Dict[RetrievalSource, float] = dict(
            self.DEFAULT_SOURCE_WEIGHTS
        )

    # ===================================================================
    # Core retrieval
    # ===================================================================

    async def retrieve(
        self,
        query: str,
        sources: Optional[List[RetrievalSource]] = None,
        top_k: int = 10,
        time_window_hours: Optional[int] = None,
        symbol: Optional[str] = None,
        segment: Optional[str] = None,
        min_score: float = 0.0,
        use_hybrid: bool = True,
    ) -> List[RetrievedContext]:
        """Retrieve relevant context from one or more sources.

        This is the primary retrieval entry-point.  It expands the query,
        searches every requested collection concurrently, applies time-decay
        weighting, and fuses the results into a single ranked list.

        Parameters
        ----------
        query:
            Raw user query or strategy description.
        sources:
            Which sources to search (default = all).
        top_k:
            Total number of results to return across all sources.
        time_window_hours:
            If set, only documents newer than this many hours are considered.
        symbol:
            Filter by trading symbol (e.g. ``"NIFTY50"``).
        segment:
            Filter by market segment (e.g. ``"equity"``, ``"futures"``).
        min_score:
            Minimum relevance score threshold.
        use_hybrid:
            If ``True`` use hybrid (dense + keyword) search; otherwise pure
            semantic search.

        Returns
        -------
        list[RetrievedContext]
            Ranked list of context objects, highest relevance first.
        """
        t0 = time.perf_counter()
        effective_sources = sources or list(RetrievalSource)
        expanded_query = self.query_expander.expand(query)

        logger.info(
            f"Retrieving: query='{query[:60]}...' expanded='{expanded_query[:80]}...' "
            f"sources={len(effective_sources)} top_k={top_k}"
        )

        # Build per-source filters
        base_filters: Dict[str, Any] = {}
        if symbol:
            base_filters["symbol"] = symbol
        if segment:
            base_filters["segment"] = segment

        # If time_window is set, add a metadata filter for recent documents
        # Note: this requires metadata to have an ISO timestamp field.
        # Not all collections guarantee this, so we also do post-filtering.

        # Launch concurrent searches
        search_tasks = [
            self._search_single_source(
                source=src,
                query=expanded_query,
                top_k=max(top_k, self.default_top_k),
                filters=base_filters if self._source_supports_filter(src) else None,
                use_hybrid=use_hybrid,
                time_window_hours=time_window_hours,
            )
            for src in effective_sources
        ]

        results_by_source = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Collect valid results
        source_results: Dict[str, List[RetrievedContext]] = {}
        for src, result in zip(effective_sources, results_by_source):
            if isinstance(result, Exception):
                logger.error(f"Source '{src.value}' search failed: {result}")
                source_results[src.value] = []
            else:
                source_results[src.value] = result

        # Apply time-decay
        for src_key, contexts in source_results.items():
            source_results[src_key] = self._apply_time_decay(contexts)

        # Fuse everything into one ranked list
        fused = self._fuse_results(source_results, top_k=top_k)

        # Apply minimum score filter
        fused = [ctx for ctx in fused if ctx.relevance_score >= min_score]

        elapsed = (time.perf_counter() - t0) * 1000.0
        logger.info(
            f"Retrieval complete: {len(fused)} contexts in {elapsed:.1f} ms "
            f"from {len(effective_sources)} sources"
        )
        return fused

    # ===================================================================
    # Specialised retrieval methods
    # ===================================================================

    async def retrieve_similar_strategies(
        self,
        strategy_description: str,
        top_k: int = 5,
        symbol: Optional[str] = None,
        min_backtest_pnl: Optional[float] = None,
        min_win_rate: Optional[float] = None,
    ) -> List[RetrievedContext]:
        """Find strategies similar to the given description.

        Parameters
        ----------
        strategy_description:
            Free-text description of the desired strategy.
        top_k:
            Number of similar strategies to return.
        symbol:
            Restrict to a specific symbol.
        min_backtest_pnl:
            Only return strategies with total P&L above this threshold.
        min_win_rate:
            Only return strategies with win rate above this threshold.

        Returns
        -------
        list[RetrievedContext]
            Similar strategies with performance metadata.
        """
        expanded = self.query_expander.expand(strategy_description)
        filters: Dict[str, Any] = {}
        if symbol:
            filters["symbol"] = symbol

        search_method = (
            self.vector_store.hybrid_search
            if hasattr(self.vector_store, "hybrid_search")
            else self.vector_store.search
        )

        result = search_method(
            collection_name=RetrievalSource.STRATEGIES.value,
            query=expanded,
            top_k=top_k * 3,  # over-fetch for post-filtering
            filters=filters if filters else None,
        )

        contexts: List[RetrievedContext] = []
        for doc in result.documents:
            meta = doc.metadata
            # Post-filter on numeric thresholds
            if min_backtest_pnl is not None:
                pnl = meta.get("total_pnl") or meta.get("pnl")
                if pnl is not None and pnl < min_backtest_pnl:
                    continue
            if min_win_rate is not None:
                wr = meta.get("win_rate")
                if wr is not None and wr < min_win_rate:
                    continue

            contexts.append(
                RetrievedContext(
                    source=RetrievalSource.STRATEGIES,
                    content=doc.content,
                    metadata=meta,
                    relevance_score=doc.score,
                    doc_id=doc.id,
                )
            )

        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        logger.info(f"Found {len(contexts[:top_k])} similar strategies")
        return contexts[:top_k]

    async def retrieve_market_context(
        self,
        symbol: str,
        lookback_hours: int = 24,
    ) -> List[RetrievedContext]:
        """Get recent market context for a symbol.

        Combines market regime snapshots, recent news, and indicator
        explanations that are relevant to the symbol's current state.

        Parameters
        ----------
        symbol:
            Trading symbol (e.g. ``"RELIANCE"``).
        lookback_hours:
            How far back to look for news and regime data.

        Returns
        -------
        list[RetrievedContext]
            Market context entries ranked by recency and relevance.
        """
        t0 = time.perf_counter()
        expanded_symbol = self.query_expander.expand(symbol)

        # Concurrent searches across regime + news + commentary
        tasks = [
            self._search_single_source(
                source=RetrievalSource.MARKET_REGIME,
                query=f"{expanded_symbol} market regime trend",
                top_k=3,
                filters={"symbol": symbol},
                use_hybrid=True,
                time_window_hours=lookback_hours,
            ),
            self._search_single_source(
                source=RetrievalSource.NEWS_EVENTS,
                query=f"{expanded_symbol} news market",
                top_k=5,
                filters={"symbols": symbol},
                use_hybrid=True,
                time_window_hours=lookback_hours,
            ),
            self._search_single_source(
                source=RetrievalSource.MARKET_COMMENTARY,
                query=f"{expanded_symbol} analysis outlook",
                top_k=3,
                filters={"symbol": symbol},
                use_hybrid=True,
                time_window_hours=lookback_hours,
            ),
            self._search_single_source(
                source=RetrievalSource.INDICATOR_CONTEXT,
                query=f"{expanded_symbol} technical indicators",
                top_k=3,
                filters=None,
                use_hybrid=False,
                time_window_hours=None,
            ),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_contexts: List[RetrievedContext] = []
        for result in results:
            if isinstance(result, list):
                all_contexts.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Market context sub-search failed: {result}")

        # Apply strong time decay for market context (recency matters most)
        all_contexts = self._apply_time_decay(all_contexts, half_life_hours=6.0)
        all_contexts.sort(key=lambda c: c.relevance_score, reverse=True)

        elapsed = (time.perf_counter() - t0) * 1000.0
        logger.info(
            f"Market context for {symbol}: {len(all_contexts)} items in {elapsed:.1f} ms"
        )
        return all_contexts

    async def retrieve_for_strategy_generation(
        self,
        user_prompt: str,
        instrument: str,
        segment: str = "equity",
    ) -> Dict[str, List[RetrievedContext]]:
        """Retrieve **all** relevant context needed for LLM strategy generation.

        This is the "kitchen sink" method that gathers every type of
        context the prompt builder might need.

        Returns
        -------
        dict
            Structured context with keys:
            ``similar_strategies``, ``market_context``, ``recent_news``,
            ``indicator_explanations``, ``backtest_insights``.
        """
        t0 = time.perf_counter()
        expanded = self.query_expander.expand(user_prompt)

        # Launch all retrievals concurrently
        tasks = {
            "similar_strategies": self.retrieve_similar_strategies(
                strategy_description=expanded,
                top_k=5,
                symbol=instrument,
            ),
            "market_context": self.retrieve_market_context(
                symbol=instrument,
                lookback_hours=24,
            ),
            "recent_news": self._search_single_source(
                source=RetrievalSource.NEWS_EVENTS,
                query=f"{instrument} {expanded} news",
                top_k=5,
                filters={"symbols": instrument},
                use_hybrid=True,
                time_window_hours=48,
            ),
            "indicator_explanations": self._search_single_source(
                source=RetrievalSource.INDICATOR_CONTEXT,
                query=expanded,
                top_k=5,
                filters=None,
                use_hybrid=False,
                time_window_hours=None,
            ),
            "backtest_insights": self._search_single_source(
                source=RetrievalSource.BACKTEST_RESULTS,
                query=f"{instrument} {expanded} backtest performance",
                top_k=5,
                filters={"symbol": instrument},
                use_hybrid=True,
                time_window_hours=None,
            ),
        }

        results: Dict[str, List[RetrievedContext]] = {}
        for key, coro in tasks.items():
            try:
                results[key] = await coro
            except Exception as exc:
                logger.error(f"Context retrieval '{key}' failed: {exc}")
                results[key] = []

        elapsed = (time.perf_counter() - t0) * 1000.0
        total_items = sum(len(v) for v in results.values())
        logger.info(
            f"Strategy generation context: {total_items} items across "
            f"{len(results)} categories in {elapsed:.1f} ms"
        )
        return results

    async def retrieve_backtest_insights(
        self,
        strategy_name: str,
        symbol: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievedContext]:
        """Retrieve backtest results that provide insights for a strategy.

        Parameters
        ----------
        strategy_name:
            Name of the strategy to find backtests for.
        symbol:
            Optional symbol filter.
        top_k:
            Number of backtest results to return.

        Returns
        -------
        list[RetrievedContext]
            Backtest results with performance metrics.
        """
        filters: Dict[str, Any] = {}
        if symbol:
            filters["symbol"] = symbol

        result = self.vector_store.hybrid_search(
            collection_name=RetrievalSource.BACKTEST_RESULTS.value,
            query=strategy_name,
            top_k=top_k * 2,
            filters=filters if filters else None,
        )

        contexts = [
            RetrievedContext(
                source=RetrievalSource.BACKTEST_RESULTS,
                content=doc.content,
                metadata=doc.metadata,
                relevance_score=doc.score,
                doc_id=doc.id,
            )
            for doc in result.documents
        ]
        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts[:top_k]

    async def retrieve_recent_trades(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        top_k: int = 10,
        lookback_hours: int = 168,  # 1 week
    ) -> List[RetrievedContext]:
        """Retrieve recent executed trades for context.

        Parameters
        ----------
        symbol:
            Filter by symbol.
        strategy_name:
            Filter by strategy name.
        top_k:
            Number of trades to return.
        lookback_hours:
            Only trades within this window.

        Returns
        -------
        list[RetrievedContext]
            Recent trades with P&L and metadata.
        """
        filters: Dict[str, Any] = {}
        if symbol:
            filters["symbol"] = symbol
        if strategy_name:
            filters["strategy_name"] = strategy_name

        result = self.vector_store.search(
            collection_name=RetrievalSource.TRADE_HISTORY.value,
            query="recent trades executed",
            top_k=top_k * 2,
            filters=filters if filters else None,
        )

        contexts = [
            RetrievedContext(
                source=RetrievalSource.TRADE_HISTORY,
                content=doc.content,
                metadata=doc.metadata,
                relevance_score=doc.score,
                doc_id=doc.id,
                timestamp=self._parse_timestamp(doc.metadata.get("entry_time")),
            )
            for doc in result.documents
        ]

        # Filter by time window
        if lookback_hours:
            cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
            contexts = [
                ctx
                for ctx in contexts
                if ctx.timestamp is None or ctx.timestamp >= cutoff
            ]

        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts[:top_k]

    # ===================================================================
    # Internal search helpers
    # ===================================================================

    async def _search_single_source(
        self,
        source: RetrievalSource,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
        use_hybrid: bool,
        time_window_hours: Optional[int],
    ) -> List[RetrievedContext]:
        """Execute a search against a single collection.

        This runs in the executor because ChromaDB operations are
        synchronous (CPU-bound embedding + DuckDB I/O).
        """
        loop = asyncio.get_event_loop()

        def _search():
            try:
                if use_hybrid and hasattr(self.vector_store, "hybrid_search"):
                    return self.vector_store.hybrid_search(
                        collection_name=source.value,
                        query=query,
                        top_k=top_k,
                        filters=filters,
                    )
                else:
                    return self.vector_store.search(
                        collection_name=source.value,
                        query=query,
                        top_k=top_k,
                        filters=filters,
                    )
            except Exception as exc:
                logger.error(f"Search on '{source.value}' failed: {exc}")
                # Return empty result on failure so other sources still work
                from .vector_store import SearchResult

                return SearchResult(
                    documents=[],
                    total_found=0,
                    search_time_ms=0.0,
                    collection=source.value,
                )

        result = await loop.run_in_executor(None, _search)

        contexts: List[RetrievedContext] = []
        for doc in result.documents:
            # Parse timestamp from metadata if available
            ts = self._parse_timestamp(doc.metadata.get("timestamp"))
            if ts is None:
                ts = self._parse_timestamp(doc.metadata.get("published_at"))
            if ts is None:
                ts = self._parse_timestamp(doc.metadata.get("entry_time"))
            if ts is None:
                ts = self._parse_timestamp(doc.metadata.get("created_at"))

            contexts.append(
                RetrievedContext(
                    source=source,
                    content=doc.content,
                    metadata=doc.metadata,
                    relevance_score=doc.score,
                    timestamp=ts,
                    doc_id=doc.id,
                )
            )

        # Post-filter by time window if specified
        if time_window_hours:
            cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)
            contexts = [
                ctx
                for ctx in contexts
                if ctx.timestamp is None or ctx.timestamp >= cutoff
            ]

        return contexts

    @staticmethod
    def _source_supports_filter(source: RetrievalSource) -> bool:
        """Check whether a source collection typically has filterable metadata."""
        # All collections support filtering; this is for future optimisation
        return True

    # ===================================================================
    # Fusion & ranking
    # ===================================================================

    def _fuse_results(
        self,
        results_by_source: Dict[str, List[RetrievedContext]],
        top_k: int,
    ) -> List[RetrievedContext]:
        """Fuse per-source ranked lists into a single ranking using
        weighted Reciprocal Rank Fusion (RRF).

        RRF score for document *d*::

            score(d) = Σ_s  w_s / (k + rank_s(d))

        where *w_s* is the source weight and *k* is the RRF constant.
        """
        # Gather all document IDs to compute ranks per source
        all_doc_ids: set = set()
        for contexts in results_by_source.values():
            all_doc_ids.update(ctx.doc_id for ctx in contexts)

        if not all_doc_ids:
            return []

        # Compute RRF score for each document
        doc_scores: Dict[str, float] = {doc_id: 0.0 for doc_id in all_doc_ids}
        doc_contexts: Dict[str, RetrievedContext] = {}

        for source_name, contexts in results_by_source.items():
            try:
                source_enum = RetrievalSource(source_name)
                weight = self.source_weights.get(source_enum, 1.0)
            except ValueError:
                weight = 1.0

            for rank, ctx in enumerate(contexts, start=1):
                rrf_score = weight / (self.RRF_K + rank)
                doc_scores[ctx.doc_id] += rrf_score
                # Keep the best context object for each doc_id
                if ctx.doc_id not in doc_contexts:
                    doc_contexts[ctx.doc_id] = ctx

        # Assign fused scores and sort
        fused: List[RetrievedContext] = []
        for doc_id, score in doc_scores.items():
            ctx = doc_contexts[doc_id]
            ctx.relevance_score = round(score, 6)
            fused.append(ctx)

        fused.sort(key=lambda c: c.relevance_score, reverse=True)
        return fused[:top_k]

    def _apply_time_decay(
        self,
        results: List[RetrievedContext],
        half_life_hours: Optional[float] = None,
    ) -> List[RetrievedContext]:
        """Apply exponential time-decay to relevance scores.

        Newer documents retain more of their original score; older ones
        are penalised.  The decay formula::

            decayed_score = original_score × 2^(-age_hours / half_life)

        Documents without timestamps are not penalised.
        """
        h = half_life_hours or self.DECAY_HALF_LIFE_HOURS
        now = datetime.utcnow()

        for ctx in results:
            if ctx.timestamp is None:
                continue
            age_hours = max(0.0, (now - ctx.timestamp).total_seconds() / 3600.0)
            decay_factor = 2.0 ** (-age_hours / h)
            ctx.relevance_score = round(ctx.relevance_score * decay_factor, 6)

        return results

    # ===================================================================
    # Utilities
    # ===================================================================

    @staticmethod
    def _parse_timestamp(ts: Any) -> Optional[datetime]:
        """Best-effort timestamp parser for various metadata formats."""
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            # Try multiple ISO formats
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.strptime(ts.split("+")[0], fmt)
                except ValueError:
                    continue
        return None

    def set_source_weight(self, source: RetrievalSource, weight: float) -> None:
        """Dynamically adjust the importance of a retrieval source.

        Higher weights cause that source's results to rank higher in
        the fused output.
        """
        if weight < 0:
            raise ValueError("Weight must be non-negative")
        self.source_weights[source] = weight
        logger.info(f"Source '{source.value}' weight set to {weight}")

    def reset_source_weights(self) -> None:
        """Reset all source weights to their defaults."""
        self.source_weights = dict(self.DEFAULT_SOURCE_WEIGHTS)
        logger.info("Source weights reset to defaults")

    def get_source_weights(self) -> Dict[str, float]:
        """Return current source weights as a serialisable dict."""
        return {src.value: w for src, w in self.source_weights.items()}
