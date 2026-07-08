"""
Main RAG Engine for TradeForge AI

Orchestrates the complete RAG pipeline:

    ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
    │ User Query  │────▶│ Query Expand │────▶│ Multi-Source    │
    └─────────────┘     └──────────────┘     │ Retrieval       │
                                             └───────┬─────────┘
                                                     │
                                             ┌───────▼─────────┐
                                             │ Cross-Encoder   │
                                             │ Reranker        │
                                             └───────┬─────────┘
                                                     │
                                             ┌───────▼─────────┐
                                             │ Prompt Builder  │
                                             │ (Jinja2)        │
                                             └───────┬─────────┘
                                                     │
                                             ┌───────▼─────────┐
                                             │ LLM Call        │
                                             │ (external)      │
                                             └─────────────────┘

This is the **single entry point** for all RAG operations in TradeForge AI.

Usage:
    rag = TradeForgeRAG()
    rag.initialize()

    # Strategy generation context
    context = await rag.get_strategy_context(
        user_prompt="Buy when RSI is oversold",
        instrument="NIFTY50",
    )

    # Build RAG-augmented prompt
    prompt = rag.build_rag_prompt("strategy_generation", user_prompt, context)

    # Backtest analysis
    insights = await rag.analyze_backtest(backtest_results)

    # Market analysis
    analysis = await rag.analyze_market("RELIANCE")
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


class TradeForgeRAG:
    """Production RAG engine that orchestrates all retrieval components.

    The engine follows a lazy-initialisation pattern: components are
    created when ``initialize()`` is called, not in ``__init__``.  This
    keeps import-time overhead minimal and allows configuration to be
    changed before startup.

    Parameters
    ----------
    vector_store_dir:
        Directory for ChromaDB persistence.
    embedding_model:
        Sentence-transformer model for bi-encoder embeddings.
    reranker_model:
        Cross-encoder model for reranking.
    device:
        PyTorch device (``"cpu"`` or ``"cuda"``).

    Attributes
    ----------
    vector_store : VectorStore
        ChromaDB-backed vector store with multiple collections.
    document_processor : DocumentProcessor
        Text chunking and formatting pipeline.
    retriever : MultiSourceRetriever
        Multi-source retrieval with query expansion and fusion.
    reranker : Reranker
        Cross-encoder reranker with diversity and freshness.
    prompt_builder : RAGPromptBuilder
        Jinja2 prompt templates with RAG context injection.
    ingestion : RAGIngestionPipeline
        Real-time async data ingestion pipeline.
    regime_detector : MarketRegimeDetector
        Trend / volatility / momentum regime classifier.
    query_expander : QueryExpander
        Trading query expansion with synonyms.

    Example
    -------
    >>> rag = TradeForgeRAG(device="cuda")
    >>> rag.initialize()
    >>> context = await rag.get_strategy_context("RSI mean reversion", "NIFTY50")
    >>> prompt = rag.build_rag_prompt("strategy_generation", "RSI mean reversion", context)
    """

    def __init__(
        self,
        vector_store_dir: str = "./data/chromadb",
        embedding_model: str = "all-MiniLM-L6-v2",
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
    ) -> None:
        self.vector_store_dir = vector_store_dir
        self.embedding_model = embedding_model
        self.reranker_model = reranker_model
        self.device = device

        # Components (initialised in initialize())
        self.vector_store: Optional[Any] = None
        self.document_processor: Optional[Any] = None
        self.query_expander: Optional[Any] = None
        self.retriever: Optional[Any] = None
        self.reranker: Optional[Any] = None
        self.prompt_builder: Optional[Any] = None
        self.ingestion: Optional[Any] = None
        self.regime_detector: Optional[Any] = None

        # Stats
        self._initialized_at: Optional[datetime] = None
        self._queries_served: int = 0
        self._total_query_time_ms: float = 0.0
        self._initialized: bool = False

    # ===================================================================
    # Lifecycle
    # ===================================================================

    def initialize(self) -> None:
        """Initialise all RAG components.

        This method creates and connects:
        * ``VectorStore`` – ChromaDB with persistent storage
        * ``DocumentProcessor`` – text chunking and formatting
        * ``QueryExpander`` – trading query expansion
        * ``MultiSourceRetriever`` – multi-source retrieval engine
        * ``Reranker`` – cross-encoder reranking
        * ``RAGPromptBuilder`` – prompt template renderer
        * ``MarketRegimeDetector`` – regime classification

        The ingestion pipeline is **not** started automatically;
        call ``start_ingestion()`` separately.
        """
        if self._initialized:
            logger.warning("RAG engine already initialized")
            return

        t0 = time.perf_counter()

        # Import here to avoid circular dependencies at module level
        from .document_processor import DocumentProcessor
        from .market_regime_detector import MarketRegimeDetector
        from .prompt_builder import RAGPromptBuilder
        from .query_expander import QueryExpander
        from .reranker import Reranker
        from .retriever import MultiSourceRetriever
        from .vector_store import VectorStore

        logger.info("=" * 60)
        logger.info("Initialising TradeForge RAG Engine")
        logger.info("=" * 60)

        # 1. Vector store
        logger.info(f"[1/7] VectorStore → {self.vector_store_dir}")
        self.vector_store = VectorStore(
            persist_dir=self.vector_store_dir,
            embedding_model=self.embedding_model,
            device=self.device,
        )

        # 2. Document processor
        logger.info("[2/7] DocumentProcessor")
        self.document_processor = DocumentProcessor()

        # 3. Query expander
        logger.info("[3/7] QueryExpander")
        self.query_expander = QueryExpander()

        # 4. Retriever
        logger.info("[4/7] MultiSourceRetriever")
        self.retriever = MultiSourceRetriever(
            vector_store=self.vector_store,
            document_processor=self.document_processor,
            query_expander=self.query_expander,
        )

        # 5. Reranker
        logger.info(f"[5/7] Reranker → {self.reranker_model}")
        self.reranker = Reranker(
            model_name=self.reranker_model,
            device=self.device,
        )

        # 6. Prompt builder
        logger.info("[6/7] RAGPromptBuilder")
        self.prompt_builder = RAGPromptBuilder()

        # 7. Regime detector
        logger.info("[7/7] MarketRegimeDetector")
        self.regime_detector = MarketRegimeDetector()

        self._initialized_at = datetime.utcnow()
        self._initialized = True

        elapsed = (time.perf_counter() - t0) * 1000.0
        logger.info("=" * 60)
        logger.info(f"RAG engine initialized successfully in {elapsed:.1f} ms")
        logger.info("=" * 60)

    def start_ingestion(
        self,
        market_data_source: Optional[Any] = None,
        tracked_symbols: Optional[List[str]] = None,
    ) -> None:
        """Start the real-time ingestion pipeline.

        Parameters
        ----------
        market_data_source:
            Object providing ``get_ohlcv(symbol, timeframe)`` method.
        tracked_symbols:
            Symbols to track for automatic regime updates.
        """
        if not self._initialized:
            raise RuntimeError(
                "RAG engine must be initialized before starting ingestion"
            )

        from .ingestion_pipeline import RAGIngestionPipeline

        self.ingestion = RAGIngestionPipeline(
            vector_store=self.vector_store,
            document_processor=self.document_processor,
            market_data_source=market_data_source,
            regime_detector=self.regime_detector,
            tracked_symbols=tracked_symbols,
        )
        self.ingestion.start()

    def stop_ingestion(self) -> None:
        """Stop the ingestion pipeline."""
        if self.ingestion:
            self.ingestion.stop()

    def close(self) -> None:
        """Clean shutdown of all RAG components."""
        logger.info("Shutting down TradeForge RAG Engine")

        if self.ingestion:
            try:
                self.ingestion.stop()
            except Exception as exc:
                logger.error(f"Error stopping ingestion: {exc}")

        if self.vector_store:
            try:
                self.vector_store.close()
            except Exception as exc:
                logger.error(f"Error closing vector store: {exc}")

        self._initialized = False
        logger.info("RAG engine shutdown complete")

    # ===================================================================
    # Core RAG operations
    # ===================================================================

    async def get_strategy_context(
        self,
        user_prompt: str,
        instrument: str,
        segment: str = "equity",
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """Get full RAG context for strategy generation.

        This is the primary method for enriching a strategy-generation
        request.  It retrieves:

        * Similar strategies (with performance data)
        * Current market regime for the instrument
        * Recent news affecting the instrument
        * Indicator explanations relevant to the query
        * Backtest insights for similar strategies

        Parameters
        ----------
        user_prompt:
            Original user query or strategy description.
        instrument:
            Target instrument (e.g. ``"NIFTY50"``, ``"RELIANCE"``).
        segment:
            Market segment (``"equity"``, ``"futures"``, ``"options"``).
        top_k:
            Maximum number of context items per category.

        Returns
        -------
        dict
            Structured context with keys:
            ``similar_strategies``, ``market_context``, ``recent_news``,
            ``indicator_explanations``, ``backtest_insights``,
            ``market_regime``, ``query``, ``instrument``.

        Raises
        ------
        RuntimeError
            If the engine has not been initialised.
        """
        self._ensure_initialized()
        t0 = time.perf_counter()

        logger.info(
            f"Getting strategy context: prompt='{user_prompt[:60]}...' instrument={instrument}"
        )

        try:
            # Retrieve all context categories concurrently
            results = await self.retriever.retrieve_for_strategy_generation(
                user_prompt=user_prompt,
                instrument=instrument,
                segment=segment,
            )

            # Get current market regime
            regime = None
            try:
                regime_data = await self._get_current_regime(instrument)
                regime = regime_data
            except Exception as exc:
                logger.warning(f"Could not fetch regime for {instrument}: {exc}")

            # Build structured context
            context = {
                "query": user_prompt,
                "instrument": instrument,
                "segment": segment,
                "similar_strategies": self._contexts_to_dicts(
                    results.get("similar_strategies", [])
                )[:top_k],
                "market_context": self._contexts_to_dicts(
                    results.get("market_context", [])
                )[:top_k],
                "recent_news": self._contexts_to_dicts(results.get("recent_news", []))[
                    :top_k
                ],
                "indicator_explanations": self._contexts_to_dicts(
                    results.get("indicator_explanations", [])
                )[:top_k],
                "backtest_insights": self._contexts_to_dicts(
                    results.get("backtest_insights", [])
                )[:top_k],
                "market_regime": regime,
            }

            elapsed = (time.perf_counter() - t0) * 1000.0
            self._queries_served += 1
            self._total_query_time_ms += elapsed

            total_items = sum(
                len(context[k])
                for k in (
                    "similar_strategies",
                    "market_context",
                    "recent_news",
                    "indicator_explanations",
                    "backtest_insights",
                )
            )
            logger.info(f"Strategy context: {total_items} items in {elapsed:.1f} ms")
            return context

        except Exception as exc:
            logger.error(f"Failed to get strategy context: {exc}")
            # Return minimal context on failure
            return {
                "query": user_prompt,
                "instrument": instrument,
                "segment": segment,
                "similar_strategies": [],
                "market_context": [],
                "recent_news": [],
                "indicator_explanations": [],
                "backtest_insights": [],
                "market_regime": None,
                "error": str(exc),
            }

    async def analyze_backtest(
        self,
        backtest_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze backtest results with RAG-enriched context.

        Retrieves similar backtests and market conditions during the
        test period to provide comparative insights.

        Parameters
        ----------
        backtest_results:
            Dict with keys: ``strategy_name``, ``symbol``, ``start_date``,
            ``end_date``, ``timeframe``, ``metrics``, ``monthly_returns``.

        Returns
        -------
        dict
            Structured analysis context with:
            ``prompt`` (ready for LLM), ``similar_backtests``,
            ``market_conditions``.
        """
        self._ensure_initialized()
        t0 = time.perf_counter()

        strategy_name = backtest_results.get("strategy_name", "")
        symbol = backtest_results.get("symbol", "")

        logger.info(f"Analyzing backtest: {strategy_name} on {symbol}")

        try:
            # Retrieve similar backtests
            similar_backtests = await self.retriever.retrieve_backtest_insights(
                strategy_name=strategy_name,
                symbol=symbol,
                top_k=5,
            )

            # Retrieve market context for the test period
            market_context = await self.retriever.retrieve_market_context(
                symbol=symbol,
                lookback_hours=24 * 30,  # ~1 month
            )

            # Build context dict
            rag_context = {
                "similar_backtests": self._contexts_to_dicts(similar_backtests),
                "market_conditions": self._contexts_to_dicts(market_context),
            }

            # Build prompt
            prompt = self.prompt_builder.build_backtest_analysis_prompt(
                backtest_results=backtest_results,
                retrieved_context=rag_context,
            )

            elapsed = (time.perf_counter() - t0) * 1000.0
            self._queries_served += 1
            self._total_query_time_ms += elapsed

            logger.info(f"Backtest analysis context built in {elapsed:.1f} ms")
            return {
                "prompt": prompt,
                "similar_backtests": rag_context["similar_backtests"],
                "market_conditions": rag_context["market_conditions"],
            }

        except Exception as exc:
            logger.error(f"Backtest analysis failed: {exc}")
            return {
                "prompt": "",
                "similar_backtests": [],
                "market_conditions": [],
                "error": str(exc),
            }

    async def analyze_market(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """Analyze current market conditions for a symbol.

        Parameters
        ----------
        symbol:
            Trading symbol to analyse.

        Returns
        -------
        dict
            Market analysis context with:
            ``prompt``, ``market_context``, ``news``, ``regime``.
        """
        self._ensure_initialized()
        t0 = time.perf_counter()

        logger.info(f"Analyzing market: {symbol}")

        try:
            # Get market context
            market_context = await self.retriever.retrieve_market_context(
                symbol=symbol,
                lookback_hours=24 * 7,  # 1 week
            )

            # Get regime
            regime = await self._get_current_regime(symbol)

            # Build context
            rag_context = {
                "news": [],
                "historical_similarities": [],
            }

            # Extract news from market context
            news_items = []
            market_items = []
            for ctx in market_context:
                ctx_dict = self._context_to_dict(ctx)
                if ctx_dict.get("source") == "news_events":
                    news_items.append(ctx_dict)
                else:
                    market_items.append(ctx_dict)

            rag_context["news"] = news_items

            # Build prompt
            price_action = "Current price action analysis not available"
            indicators = "Technical indicator data not available"
            if regime:
                price_action = regime.get("description", price_action)
                ind = regime.get("indicators", {})
                if ind:
                    indicators = " | ".join(f"{k}: {v}" for k, v in ind.items())

            prompt = self.prompt_builder.build_market_analysis_prompt(
                symbol=symbol,
                price_action=price_action,
                indicators=indicators,
                retrieved_context=rag_context,
            )

            elapsed = (time.perf_counter() - t0) * 1000.0
            self._queries_served += 1
            self._total_query_time_ms += elapsed

            logger.info(f"Market analysis context built in {elapsed:.1f} ms")
            return {
                "prompt": prompt,
                "market_context": market_items,
                "news": news_items,
                "regime": regime,
            }

        except Exception as exc:
            logger.error(f"Market analysis failed: {exc}")
            return {
                "prompt": "",
                "market_context": [],
                "news": [],
                "regime": None,
                "error": str(exc),
            }

    async def find_similar_strategies(
        self,
        description: str,
        top_k: int = 5,
        symbol: Optional[str] = None,
        min_win_rate: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Find similar strategies from the database.

        Parameters
        ----------
        description:
            Strategy description to match against.
        top_k:
            Number of similar strategies to return.
        symbol:
            Filter by trading symbol.
        min_win_rate:
            Minimum win rate threshold.

        Returns
        -------
        list[dict]
            Similar strategies with metadata.
        """
        self._ensure_initialized()

        contexts = await self.retriever.retrieve_similar_strategies(
            strategy_description=description,
            top_k=top_k,
            symbol=symbol,
            min_win_rate=min_win_rate,
        )

        return self._contexts_to_dicts(contexts)

    async def get_market_regime(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current market regime with RAG context.

        Parameters
        ----------
        symbol:
            Trading symbol.

        Returns
        -------
        dict or None
            Regime information with description and trading implications.
        """
        self._ensure_initialized()
        return await self._get_current_regime(symbol)

    # ===================================================================
    # Prompt building
    # ===================================================================

    def build_rag_prompt(
        self,
        template_type: str,
        query: str,
        retrieved_context: Dict[str, Any],
        **extra: Any,
    ) -> str:
        """Build a RAG-augmented prompt for an LLM.

        Parameters
        ----------
        template_type:
            Template name: ``"strategy_generation"``, ``"backtest_analysis"``,
            ``"market_analysis"``, ``"strategy_improvement"``,
            ``"risk_assessment"``, ``"strategy_summary"``.
        query:
            Original user query.
        retrieved_context:
            Context dict from one of the retrieval methods.
        **extra:
            Additional template variables.

        Returns
        -------
        str
            Complete prompt string.

        Raises
        ------
        RuntimeError
            If engine not initialised.
        ValueError
            If template_type is unknown.
        """
        self._ensure_initialized()

        if template_type == "strategy_generation":
            instrument = retrieved_context.get("instrument", "")
            segment = retrieved_context.get("segment", "equity")
            return self.prompt_builder.build_strategy_prompt(
                user_prompt=query,
                instrument=instrument,
                retrieved_context=retrieved_context,
                segment=segment,
            )

        elif template_type == "backtest_analysis":
            backtest = extra.get("backtest_results", {})
            return self.prompt_builder.build_backtest_analysis_prompt(
                backtest_results=backtest,
                retrieved_context=retrieved_context,
            )

        elif template_type == "market_analysis":
            symbol = extra.get("symbol", "")
            price_action = extra.get("price_action", "")
            indicators = extra.get("indicators", "")
            return self.prompt_builder.build_market_analysis_prompt(
                symbol=symbol,
                price_action=price_action,
                indicators=indicators,
                retrieved_context=retrieved_context,
            )

        elif template_type == "strategy_improvement":
            strategy = extra.get("strategy", {})
            return self.prompt_builder.build_strategy_improvement_prompt(
                strategy_name=strategy.get("name", ""),
                strategy_description=strategy.get("description", ""),
                entry_conditions=strategy.get("entry_conditions", []),
                exit_conditions=strategy.get("exit_conditions", []),
                stop_loss=strategy.get("stop_loss", {}),
                target=strategy.get("target", {}),
                backtest_summary=extra.get("backtest_summary", ""),
                retrieved_context=retrieved_context,
            )

        elif template_type == "risk_assessment":
            strategy_rules = extra.get("strategy_rules", "")
            strategy_name = extra.get("strategy_name")
            symbol = extra.get("symbol")
            return self.prompt_builder.build_risk_assessment_prompt(
                strategy_rules=strategy_rules,
                retrieved_context=retrieved_context,
                strategy_name=strategy_name,
                symbol=symbol,
            )

        elif template_type == "strategy_summary":
            strategy = extra.get("strategy", {})
            return self.prompt_builder.build_strategy_summary_prompt(strategy)

        else:
            # Generic template lookup
            return self.prompt_builder.build_prompt(
                template_type=template_type,
                **extra,
            )

    # ===================================================================
    # Ingestion helpers
    # ===================================================================

    async def ingest_strategy(self, strategy: Dict[str, Any]) -> bool:
        """Ingest a strategy into the RAG vector store.

        Parameters
        ----------
        strategy:
            Strategy dict with required fields.

        Returns
        -------
        bool
            ``True`` on success.
        """
        self._ensure_initialized()
        if self.ingestion:
            return await self.ingestion.ingest_strategy(strategy)

        # Fallback: direct ingestion
        from .vector_store import Document

        try:
            text = self.document_processor.format_strategy_document(strategy)
            doc = Document(
                id=strategy.get("id", ""),
                content=text,
                metadata={
                    "doc_type": "strategy",
                    "name": strategy.get("name", ""),
                    "instrument": strategy.get("instrument", ""),
                },
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.add_documents("strategies", [doc]),
            )
            return True
        except Exception as exc:
            logger.error(f"Direct strategy ingestion failed: {exc}")
            return False

    async def ingest_backtest(self, backtest: Dict[str, Any]) -> bool:
        """Ingest backtest results into the RAG vector store.

        Parameters
        ----------
        backtest:
            Backtest result dict.

        Returns
        -------
        bool
            ``True`` on success.
        """
        self._ensure_initialized()
        if self.ingestion:
            return await self.ingestion.ingest_backtest_result(backtest)
        return False

    async def ingest_news(self, news_items: List[Dict[str, Any]]) -> int:
        """Ingest news articles into the RAG vector store.

        Parameters
        ----------
        news_items:
            List of news article dicts.

        Returns
        -------
        int
            Number of articles ingested.
        """
        self._ensure_initialized()
        if self.ingestion:
            return await self.ingestion.ingest_news(news_items)
        return 0

    # ===================================================================
    # Statistics
    # ===================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics.

        Returns
        -------
        dict
            Comprehensive statistics including document counts,
            query performance, component status.
        """
        if not self._initialized:
            return {"status": "not_initialized"}

        vector_stats = self.vector_store.get_all_stats() if self.vector_store else {}
        ingestion_stats = self.ingestion.get_stats() if self.ingestion else {}

        avg_query_time = self._total_query_time_ms / max(1, self._queries_served)

        return {
            "status": "initialized",
            "initialized_at": (
                self._initialized_at.isoformat() if self._initialized_at else None
            ),
            "vector_store": {
                "persist_dir": self.vector_store_dir,
                "embedding_model": self.embedding_model,
                "embedding_dim": vector_stats.get("store", {}).get("embedding_dim", 0),
            },
            "reranker": {
                "model": self.reranker_model,
                "config": self.reranker.get_config() if self.reranker else {},
            },
            "collections": vector_stats.get("collections", {}),
            "performance": {
                "queries_served": self._queries_served,
                "total_query_time_ms": round(self._total_query_time_ms, 2),
                "avg_query_time_ms": round(avg_query_time, 2),
            },
            "ingestion": ingestion_stats,
        }

    # ===================================================================
    # Private helpers
    # ===================================================================

    def _ensure_initialized(self) -> None:
        """Raise if the engine has not been initialised."""
        if not self._initialized:
            raise RuntimeError(
                "TradeForgeRAG engine not initialized. Call initialize() first."
            )

    async def _get_current_regime(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch the most recent market regime for a symbol."""
        try:
            from .retriever import RetrievalSource

            results = await self.retriever._search_single_source(
                source=RetrievalSource.MARKET_REGIME,
                query=f"{symbol} market regime",
                top_k=1,
                filters={"symbol": symbol},
                use_hybrid=True,
                time_window_hours=24,
            )

            if results:
                ctx = results[0]
                return {
                    "symbol": symbol,
                    "description": ctx.content,
                    "regime": ctx.metadata.get("regime", "unknown"),
                    "confidence": ctx.metadata.get("confidence", 0),
                    "indicators": {
                        "trend": ctx.metadata.get("trend", ""),
                        "volatility": ctx.metadata.get("volatility", ""),
                        "volume": ctx.metadata.get("volume", ""),
                        "momentum": ctx.metadata.get("momentum", ""),
                    },
                    "price": ctx.metadata.get("price"),
                    "timestamp": ctx.metadata.get("timestamp"),
                }

        except Exception as exc:
            logger.debug(f"Regime lookup failed for {symbol}: {exc}")

        return None

    @staticmethod
    def _context_to_dict(ctx: Any) -> Dict[str, Any]:
        """Convert a RetrievedContext (or dict) to a plain dict."""
        if isinstance(ctx, dict):
            return ctx
        # Handle RetrievedContext dataclass
        return {
            "source": getattr(ctx, "source", "unknown"),
            "content": getattr(ctx, "content", ""),
            "metadata": getattr(ctx, "metadata", {}),
            "relevance_score": getattr(ctx, "relevance_score", 0.0),
            "timestamp": (
                ctx.timestamp.isoformat() if getattr(ctx, "timestamp", None) else None
            ),
            "doc_id": getattr(ctx, "doc_id", ""),
        }

    @classmethod
    def _contexts_to_dicts(cls, contexts: List[Any]) -> List[Dict[str, Any]]:
        """Convert a list of context objects to plain dicts."""
        return [cls._context_to_dict(ctx) for ctx in contexts]

    # ===================================================================
    # Context manager
    # ===================================================================

    async def __aenter__(self):
        self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
