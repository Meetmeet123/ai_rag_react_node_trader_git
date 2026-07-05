"""
Real-Time Ingestion Pipeline for TradeForge RAG

Continuously feeds new data into the vector store so that retrieval
always works with fresh information:

* **New strategies** → ``strategies`` collection (event-driven)
* **Backtest results** → ``backtest_results`` collection (event-driven)
* **Market regime snapshots** → ``market_regime`` collection (every 5 min)
* **News articles** → ``news_events`` collection (every 15 min)
* **Executed trades** → ``trade_history`` collection (event-driven)
* **Market commentary** → ``market_commentary`` collection (on publish)

The pipeline uses ``APScheduler`` for scheduled tasks and exposes
async methods for event-driven ingestion from the trading engine.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from .document_processor import DocumentProcessor
from .market_regime_detector import MarketRegimeDetector
from .models import (
    BacktestDocument,
    MarketRegimeDocument,
    NewsDocument,
    StrategyDocument,
    TradeDocument,
)
from .vector_store import Document, VectorStore


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RAGIngestionPipeline:
    """Continuous ingestion pipeline for the TradeForge RAG vector store.

    The pipeline operates in two modes:

    1. **Scheduled** – periodic jobs that poll external data sources:
       * Market regime update every 5 minutes (market hours only)
       * News ingestion every 15 minutes

    2. **Event-driven** – async methods called by the trading engine:
       * ``ingest_strategy()`` – when a strategy is created/updated
       * ``ingest_backtest_result()`` – when a backtest completes
       * ``ingest_trade()`` – when a trade is executed
       * ``ingest_news()`` – when news is received via WebSocket/API

    Parameters
    ----------
    vector_store:
        Initialised ``VectorStore`` instance.
    document_processor:
        ``DocumentProcessor`` for formatting raw data.
    market_data_source:
        Callable or object that provides current OHLCV data.  Must have a
        ``get_ohlcv(symbol, timeframe)`` method or be ``None`` (scheduled
        regime updates will be skipped).
    scheduler:
        Optional ``AsyncIOScheduler`` instance (created automatically).
    regime_detector:
        Optional ``MarketRegimeDetector`` (created automatically).
    tracked_symbols:
        List of symbols to track for regime updates.

    Example
    -------
    >>> pipeline = RAGIngestionPipeline(vector_store, processor, market_source)
    >>> pipeline.start()
    >>> await pipeline.ingest_strategy(strategy_dict)
    >>> await pipeline.ingest_backtest_result(backtest_dict)
    >>> pipeline.stop()
    """

    # Indian market hours (UTC+5:30)
    MARKET_OPEN_HOUR = 9    # 9:15 AM IST
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15  # 3:30 PM IST
    MARKET_CLOSE_MINUTE = 30

    def __init__(
        self,
        vector_store: VectorStore,
        document_processor: DocumentProcessor,
        market_data_source: Optional[Any] = None,
        scheduler: Optional[AsyncIOScheduler] = None,
        regime_detector: Optional[MarketRegimeDetector] = None,
        tracked_symbols: Optional[List[str]] = None,
    ) -> None:
        self.vector_store = vector_store
        self.processor = document_processor
        self.market = market_data_source
        self.regime_detector = regime_detector or MarketRegimeDetector()
        self.scheduler = scheduler or AsyncIOScheduler()
        self.tracked_symbols: Set[str] = set(tracked_symbols or ["NIFTY50"])

        # Internal state
        self._last_regime_update: Optional[datetime] = None
        self._last_news_update: Optional[datetime] = None
        self._is_running: bool = False
        self._ingestion_count: Dict[str, int] = {
            "strategies": 0,
            "backtests": 0,
            "regime": 0,
            "news": 0,
            "trades": 0,
            "commentary": 0,
        }

    # ===================================================================
    # Lifecycle
    # ===================================================================

    def start(self) -> None:
        """Start the scheduled ingestion jobs.

        Registers:
        * Market regime update every 5 minutes
        * News ingestion every 15 minutes
        """
        if self._is_running:
            logger.warning("Ingestion pipeline already running")
            return

        # Market regime – every 5 minutes
        self.scheduler.add_job(
            self._scheduled_regime_update,
            IntervalTrigger(minutes=5),
            id="market_regime",
            name="Market Regime Update",
            replace_existing=True,
        )

        # News – every 15 minutes
        self.scheduler.add_job(
            self._scheduled_news_update,
            IntervalTrigger(minutes=15),
            id="news_ingestion",
            name="News Ingestion",
            replace_existing=True,
        )

        # Cleanup old documents – daily
        self.scheduler.add_job(
            self._scheduled_cleanup,
            IntervalTrigger(hours=24),
            id="cleanup",
            name="Old Document Cleanup",
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        logger.info(
            f"RAG ingestion pipeline started – tracking {len(self.tracked_symbols)} symbols"
        )

    def stop(self) -> None:
        """Stop all scheduled ingestion jobs."""
        if not self._is_running:
            return
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as exc:
            logger.error(f"Error shutting down scheduler: {exc}")
        self._is_running = False
        logger.info("RAG ingestion pipeline stopped")

    def add_tracked_symbol(self, symbol: str) -> None:
        """Add a symbol to the regime tracking list."""
        self.tracked_symbols.add(symbol.upper())
        logger.info(f"Added tracking for {symbol}")

    def remove_tracked_symbol(self, symbol: str) -> None:
        """Remove a symbol from the regime tracking list."""
        self.tracked_symbols.discard(symbol.upper())
        logger.info(f"Removed tracking for {symbol}")

    # ===================================================================
    # Event-driven ingestion
    # ===================================================================

    async def ingest_strategy(self, strategy: Dict[str, Any]) -> bool:
        """Ingest a strategy into the vector store.

        Parameters
        ----------
        strategy:
            Strategy dict with keys: ``name``, ``description``, ``instrument``,
            ``segment``, ``timeframe``, ``entry_conditions``, ``exit_conditions``,
            ``stop_loss``, ``target``, ``position_sizing``, plus optional
            performance fields.

        Returns
        -------
        bool
            ``True`` on success.
        """
        try:
            # Format and create document
            text = self.processor.format_strategy_document(strategy)
            doc_id = strategy.get("id") or self.processor.compute_doc_id(
                text, {"name": strategy.get("name", "")}
            )

            doc = Document(
                id=doc_id,
                content=text,
                metadata={
                    "doc_type": "strategy",
                    "name": strategy.get("name", ""),
                    "instrument": strategy.get("instrument", ""),
                    "segment": strategy.get("segment", "equity"),
                    "timeframe": strategy.get("timeframe", "15m"),
                    "win_rate": strategy.get("win_rate"),
                    "total_pnl": strategy.get("total_pnl"),
                    "sharpe_ratio": strategy.get("sharpe_ratio"),
                    "max_drawdown": strategy.get("max_drawdown"),
                    "tags": strategy.get("tags", []),
                    "ingested_at": datetime.utcnow().isoformat(),
                },
            )

            # Upsert (insert or update)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.upsert_documents("strategies", [doc]),
            )

            self._ingestion_count["strategies"] += 1
            logger.info(f"Ingested strategy: {strategy.get('name', 'unknown')} ({doc_id})")
            return True

        except Exception as exc:
            logger.error(f"Failed to ingest strategy: {exc}")
            return False

    async def ingest_backtest_result(self, backtest: Dict[str, Any]) -> bool:
        """Ingest backtest results into the vector store.

        Parameters
        ----------
        backtest:
            Backtest dict with keys: ``strategy_name``, ``strategy_id``,
            ``symbol``, ``start_date``, ``end_date``, ``timeframe``,
            ``metrics`` (dict), ``monthly_returns``, ``parameter_values``.

        Returns
        -------
        bool
            ``True`` on success.
        """
        try:
            text = self.processor.format_backtest_document(backtest)
            doc_id = backtest.get("id") or self.processor.compute_doc_id(
                text, {"strategy_name": backtest.get("strategy_name", "")}
            )

            metrics = backtest.get("metrics", {})
            doc = Document(
                id=doc_id,
                content=text,
                metadata={
                    "doc_type": "backtest_result",
                    "strategy_name": backtest.get("strategy_name", ""),
                    "strategy_id": backtest.get("strategy_id", ""),
                    "symbol": backtest.get("symbol", ""),
                    "timeframe": backtest.get("timeframe", "15m"),
                    "total_trades": metrics.get("total_trades", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    "total_pnl": metrics.get("total_pnl", 0),
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                    "profit_factor": metrics.get("profit_factor", 0),
                    "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                    "start_date": str(backtest.get("start_date", "")),
                    "end_date": str(backtest.get("end_date", "")),
                    "ingested_at": datetime.utcnow().isoformat(),
                },
            )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.upsert_documents("backtest_results", [doc]),
            )

            self._ingestion_count["backtests"] += 1
            logger.info(
                f"Ingested backtest: {backtest.get('strategy_name', 'unknown')} "
                f"on {backtest.get('symbol', '')}"
            )
            return True

        except Exception as exc:
            logger.error(f"Failed to ingest backtest: {exc}")
            return False

    async def ingest_news(self, news_items: List[Dict[str, Any]]) -> int:
        """Ingest news articles into the vector store.

        Parameters
        ----------
        news_items:
            List of news dicts, each with: ``title``, ``summary``, ``source``,
            ``published_at``, ``symbols``, ``sentiment``, ``sentiment_score``.

        Returns
        -------
        int
            Number of articles successfully ingested.
        """
        if not news_items:
            return 0

        count = 0
        docs: List[Document] = []

        for item in news_items:
            try:
                text = self.processor.format_news_document(item)
                doc_id = item.get("id") or self.processor.compute_doc_id(
                    text, {"title": item.get("title", "")}
                )

                doc = Document(
                    id=doc_id,
                    content=text,
                    metadata={
                        "doc_type": "news_event",
                        "title": item.get("title", ""),
                        "source": item.get("source", ""),
                        "symbols": item.get("symbols", []),
                        "sentiment": item.get("sentiment", ""),
                        "sentiment_score": item.get("sentiment_score"),
                        "published_at": (
                            item.get("published_at") or datetime.utcnow().isoformat()
                        ),
                        "category": item.get("category", ""),
                        "ingested_at": datetime.utcnow().isoformat(),
                    },
                )
                docs.append(doc)
            except Exception as exc:
                logger.warning(f"Skipping news item due to error: {exc}")

        if docs:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.vector_store.upsert_documents("news_events", docs),
                )
                count = len(docs)
                self._ingestion_count["news"] += count
                logger.info(f"Ingested {count} news articles")
            except Exception as exc:
                logger.error(f"Failed to ingest news batch: {exc}")

        return count

    async def ingest_trade(self, trade: Dict[str, Any]) -> bool:
        """Ingest an executed trade into the vector store.

        Parameters
        ----------
        trade:
            Trade dict with keys: ``trade_id``, ``symbol``, ``strategy_name``,
            ``strategy_id``, ``side``, ``entry_price``, ``exit_price``,
            ``quantity``, ``entry_time``, ``exit_time``, ``pnl``, ``status``.

        Returns
        -------
        bool
            ``True`` on success.
        """
        try:
            text = self.processor.format_trade_document(trade)
            doc_id = trade.get("id") or trade.get("trade_id") or self.processor.compute_doc_id(
                text, {"trade_id": trade.get("trade_id", "")}
            )

            doc = Document(
                id=doc_id,
                content=text,
                metadata={
                    "doc_type": "trade_history",
                    "trade_id": trade.get("trade_id", ""),
                    "symbol": trade.get("symbol", ""),
                    "strategy_name": trade.get("strategy_name", ""),
                    "strategy_id": trade.get("strategy_id", ""),
                    "side": trade.get("side", ""),
                    "entry_price": trade.get("entry_price"),
                    "exit_price": trade.get("exit_price"),
                    "quantity": trade.get("quantity"),
                    "pnl": trade.get("pnl"),
                    "pnl_pct": trade.get("pnl_pct"),
                    "status": trade.get("status", "open"),
                    "entry_time": str(trade.get("entry_time", "")),
                    "exit_time": str(trade.get("exit_time", "")),
                    "ingested_at": datetime.utcnow().isoformat(),
                },
            )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.upsert_documents("trade_history", [doc]),
            )

            self._ingestion_count["trades"] += 1
            logger.info(
                f"Ingested trade: {trade.get('side', '')} {trade.get('symbol', '')} "
                f"x{trade.get('quantity', 0)}"
            )
            return True

        except Exception as exc:
            logger.error(f"Failed to ingest trade: {exc}")
            return False

    async def ingest_market_regime(
        self,
        symbol: str,
        price: float,
        indicators: Dict[str, Any],
    ) -> bool:
        """Ingest a market regime snapshot into the vector store.

        This is called either by the scheduled job or directly when
        fresh indicator data is available.

        Parameters
        ----------
        symbol:
            Trading symbol.
        price:
            Current price.
        indicators:
            Dict of indicator values (rsi, sma_20, macd, etc.).

        Returns
        -------
        bool
            ``True`` on success.
        """
        try:
            # Format as rich text
            text = self.processor.format_market_regime_document(
                symbol=symbol,
                price=price,
                indicators=indicators,
                timestamp=datetime.utcnow(),
            )

            # Detect regime
            import pandas as pd
            df_data = {"close": [price]}
            for k, v in indicators.items():
                df_data[k] = [v]
            df = pd.DataFrame(df_data)
            regime_result = self.regime_detector.detect(df)

            doc_id = self.processor.compute_doc_id(
                text, {"symbol": symbol, "timestamp": datetime.utcnow().isoformat()}
            )

            doc = Document(
                id=doc_id,
                content=text,
                metadata={
                    "doc_type": "market_regime",
                    "symbol": symbol,
                    "price": price,
                    "regime": regime_result["regime"].value,
                    "confidence": regime_result["confidence"],
                    "trend": regime_result["indicators"]["trend"],
                    "volatility": regime_result["indicators"]["volatility"],
                    "volume": regime_result["indicators"]["volume"],
                    "momentum": regime_result["indicators"]["momentum"],
                    "timestamp": datetime.utcnow().isoformat(),
                    **{k: v for k, v in indicators.items() if isinstance(v, (int, float, str, bool))},
                },
            )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.upsert_documents("market_regime", [doc]),
            )

            self._ingestion_count["regime"] += 1
            self._last_regime_update = datetime.utcnow()
            logger.debug(
                f"Ingested regime for {symbol}: {regime_result['regime'].value} "
                f"({regime_result['confidence']:.0%} confidence)"
            )
            return True

        except Exception as exc:
            logger.error(f"Failed to ingest market regime for {symbol}: {exc}")
            return False

    async def ingest_indicator_reference(
        self,
        indicators: List[Dict[str, Any]],
    ) -> int:
        """Bulk-ingest technical indicator reference documents.

        This is typically called once at setup time to populate the
        ``indicator_context`` collection.

        Parameters
        ----------
        indicators:
            List of indicator dicts with keys: ``name``, ``full_name``,
            ``category``, ``description``, ``best_for``, ``interpretation``,
            ``common_periods``, ``signals``.

        Returns
        -------
        int
            Number of indicators ingested.
        """
        docs: List[Document] = []
        for ind in indicators:
            try:
                text = self.processor.format_indicator_document(ind)
                doc_id = ind.get("id") or self.processor.compute_doc_id(
                    text, {"name": ind.get("name", "")}
                )
                doc = Document(
                    id=doc_id,
                    content=text,
                    metadata={
                        "doc_type": "indicator_context",
                        "name": ind.get("name", ""),
                        "category": ind.get("category", ""),
                        **{k: v for k, v in ind.items() if k not in ("name", "category", "description")},
                    },
                )
                docs.append(doc)
            except Exception as exc:
                logger.warning(f"Skipping indicator due to error: {exc}")

        if docs:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.upsert_documents("indicator_context", docs),
            )
            logger.info(f"Ingested {len(docs)} indicator references")
            return len(docs)
        return 0

    async def ingest_market_commentary(
        self,
        commentary_items: List[Dict[str, Any]],
    ) -> int:
        """Ingest market commentary / analysis documents.

        Parameters
        ----------
        commentary_items:
            List of dicts with: ``title``, ``content``, ``author``,
            ``symbol``, ``published_at``.

        Returns
        -------
        int
            Number of items ingested.
        """
        docs: List[Document] = []
        for item in commentary_items:
            try:
                content = item.get("content", "")
                title = item.get("title", "")
                text = f"Market Commentary: {title}\n\n{content}"
                doc_id = item.get("id") or self.processor.compute_doc_id(
                    text, {"title": title}
                )
                doc = Document(
                    id=doc_id,
                    content=text,
                    metadata={
                        "doc_type": "market_commentary",
                        "title": title,
                        "author": item.get("author", ""),
                        "symbol": item.get("symbol", ""),
                        "published_at": item.get("published_at", datetime.utcnow().isoformat()),
                        "ingested_at": datetime.utcnow().isoformat(),
                    },
                )
                docs.append(doc)
            except Exception as exc:
                logger.warning(f"Skipping commentary item: {exc}")

        if docs:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.vector_store.upsert_documents("market_commentary", docs),
            )
            self._ingestion_count["commentary"] += len(docs)
            logger.info(f"Ingested {len(docs)} commentary items")
            return len(docs)
        return 0

    # ===================================================================
    # Bulk historical ingestion
    # ===================================================================

    async def bulk_ingest_historical_regime(
        self,
        symbol: str,
        ohlcv_data: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """Bulk ingest historical OHLCV data and generate regime labels.

        Parameters
        ----------
        symbol:
            Trading symbol.
        ohlcv_data:
            List of OHLCV dicts: ``{timestamp, open, high, low, close, volume}``.
        batch_size:
            Number of rows to process per batch.

        Returns
        -------
        int
            Number of regime snapshots ingested.
        """
        try:
            import pandas as pd

            df = pd.DataFrame(ohlcv_data)
            if df.empty:
                return 0

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").set_index("timestamp")

            # Compute SMAs
            df["sma_20"] = df["close"].rolling(20).mean()
            df["sma_50"] = df["close"].rolling(50).mean()

            # Detect regimes using rolling window
            regimes = self.regime_detector.detect_series(df, window=20)

            # Ingest in batches
            docs: List[Document] = []
            count = 0
            for regime in regimes:
                idx = regime["index"]
                row = df.iloc[idx]
                price = float(row["close"])

                text = (
                    f"Historical Market Regime for {symbol} at Rs.{price:.2f}\n"
                    f"Regime: {regime['regime'].value}\n"
                    f"Confidence: {regime['confidence']:.0%}\n"
                    f"Trend: {regime['indicators']['trend']}\n"
                    f"Volatility: {regime['indicators']['volatility']}\n"
                    f"Volume: {regime['indicators']['volume']}\n"
                    f"Momentum: {regime['indicators']['momentum']}"
                )

                ts = regime.get("datetime", datetime.utcnow().isoformat())
                doc_id = self.processor.compute_doc_id(text, {"symbol": symbol, "timestamp": ts})

                doc = Document(
                    id=doc_id,
                    content=text,
                    metadata={
                        "doc_type": "market_regime",
                        "symbol": symbol,
                        "price": price,
                        "regime": regime["regime"].value,
                        "confidence": regime["confidence"],
                        "timestamp": ts,
                    },
                )
                docs.append(doc)

                if len(docs) >= batch_size:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda d=docs: self.vector_store.upsert_documents("market_regime", d),
                    )
                    count += len(docs)
                    docs = []

            # Final batch
            if docs:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.vector_store.upsert_documents("market_regime", docs),
                )
                count += len(docs)

            self._ingestion_count["regime"] += count
            logger.info(f"Bulk ingested {count} historical regime snapshots for {symbol}")
            return count

        except Exception as exc:
            logger.error(f"Failed to bulk ingest historical regime: {exc}")
            return 0

    # ===================================================================
    # Scheduled jobs
    # ===================================================================

    async def _scheduled_regime_update(self) -> None:
        """Update market regime for all tracked symbols.

        This job runs every 5 minutes during market hours.
        """
        if not self.market:
            return

        # Check if market is open (simple time-based check)
        now = datetime.utcnow()
        # Convert to IST (UTC+5:30)
        ist_hour = (now.hour + 5) % 24 + (now.minute + 30) // 60
        ist_minute = (now.minute + 30) % 60

        # Skip outside market hours (9:15 - 15:30 IST)
        # Simplified: only run during what should be market hours
        if not (9 <= ist_hour < 16):
            return

        for symbol in self.tracked_symbols:
            try:
                # Fetch latest OHLCV
                ohlcv = await self._fetch_ohlcv(symbol)
                if ohlcv is None:
                    continue

                price = ohlcv.get("close", 0)
                indicators = {k: v for k, v in ohlcv.items() if k != "timestamp"}

                await self.ingest_market_regime(symbol, price, indicators)

            except Exception as exc:
                logger.error(f"Scheduled regime update failed for {symbol}: {exc}")

        self._last_regime_update = datetime.utcnow()

    async def _scheduled_news_update(self) -> None:
        """Fetch and ingest latest news.

        This job runs every 15 minutes.
        """
        # Placeholder – actual implementation depends on news data source
        logger.debug("Scheduled news update (no news source configured)")
        self._last_news_update = datetime.utcnow()

    async def _scheduled_cleanup(self) -> None:
        """Remove old documents to prevent collection bloat.

        Keeps the most recent 10,000 documents per collection.
        """
        try:
            # This is a placeholder – ChromaDB doesn't have a simple
            # "delete oldest N" API.  In production you'd implement this
            # with a timestamp-based filter.
            logger.info("Document cleanup completed (no-op in current implementation)")
        except Exception as exc:
            logger.error(f"Cleanup failed: {exc}")

    # ===================================================================
    # Data source helpers
    # ===================================================================

    async def _fetch_ohlcv(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch latest OHLCV data from the market data source.

        Returns a dict with indicator values or ``None`` on failure.
        """
        if self.market is None:
            return None

        try:
            loop = asyncio.get_event_loop()
            # Try async first
            if asyncio.iscoroutinefunction(self.market.get_ohlcv):
                return await self.market.get_ohlcv(symbol, timeframe="5m")
            else:
                return await loop.run_in_executor(
                    None,
                    lambda: self.market.get_ohlcv(symbol, timeframe="5m"),
                )
        except Exception as exc:
            logger.debug(f"Failed to fetch OHLCV for {symbol}: {exc}")
            return None

    # ===================================================================
    # Stats
    # ===================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Return ingestion pipeline statistics."""
        return {
            "is_running": self._is_running,
            "tracked_symbols": list(self.tracked_symbols),
            "ingestion_counts": dict(self._ingestion_count),
            "last_regime_update": self._last_regime_update.isoformat() if self._last_regime_update else None,
            "last_news_update": self._last_news_update.isoformat() if self._last_news_update else None,
        }
