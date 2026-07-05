"""
TradeForge AI - Production-Grade RAG (Retrieval-Augmented Generation) System

A comprehensive RAG pipeline for algorithmic trading that combines:
- Multi-source vector retrieval (strategies, backtests, market data, news)
- Hybrid search (semantic + keyword with BM25-style scoring)
- Cross-encoder reranking for optimal result relevance
- Real-time ingestion pipeline for live market data
- Market regime detection for context-aware strategy generation
- Query expansion with trading-specific synonyms

Usage:
    from tradeforge.rag import TradeForgeRAG

    rag = TradeForgeRAG()
    rag.initialize()

    # Get enriched context for strategy generation
    context = await rag.get_strategy_context(
        user_prompt="Buy when RSI is oversold",
        instrument="NIFTY50"
    )

    # Build RAG-augmented prompt for LLM
    prompt = rag.build_rag_prompt("strategy_generation", user_prompt, context)

    # Analyze backtest results with historical context
    insights = await rag.analyze_backtest(backtest_results)

Components:
    VectorStore: ChromaDB-based vector storage with multiple collections
    DocumentProcessor: Text chunking, formatting, and embedding pipeline
    MultiSourceRetriever: Intelligent multi-source retrieval engine
    Reranker: Cross-encoder reranking with diversity and freshness
    RAGPromptBuilder: Jinja2-based prompt construction with RAG context
    RAGIngestionPipeline: Real-time async data ingestion
    MarketRegimeDetector: Trend/volatility/momentum regime classification
    QueryExpander: Trading query expansion with synonyms
    TradeForgeRAG: Main orchestrator bringing all components together
"""

from typing import TYPE_CHECKING

# Core exports - these are the primary interfaces users will interact with
from .rag_engine import TradeForgeRAG

# Supporting components available for advanced use cases
from .vector_store import VectorStore, Document, SearchResult
from .document_processor import DocumentProcessor, ChunkConfig
from .retriever import MultiSourceRetriever, RetrievedContext, RetrievalSource
from .reranker import Reranker
from .prompt_builder import RAGPromptBuilder
from .ingestion_pipeline import RAGIngestionPipeline
from .market_regime_detector import MarketRegimeDetector, MarketRegime
from .query_expander import QueryExpander

# Pydantic models for data validation
from .models import (
    StrategyDocument,
    BacktestDocument,
    MarketRegimeDocument,
    NewsDocument,
    TradeDocument,
    IndicatorDocument,
    RetrievalQuery,
    RAGContext,
    RAGStats,
)

__version__ = "1.0.0"
__author__ = "TradeForge AI"

__all__ = [
    # Main orchestrator
    "TradeForgeRAG",
    # Core components
    "VectorStore",
    "Document",
    "SearchResult",
    "DocumentProcessor",
    "ChunkConfig",
    "MultiSourceRetriever",
    "RetrievedContext",
    "RetrievalSource",
    "Reranker",
    "RAGPromptBuilder",
    "RAGIngestionPipeline",
    "MarketRegimeDetector",
    "MarketRegime",
    "QueryExpander",
    # Pydantic models
    "StrategyDocument",
    "BacktestDocument",
    "MarketRegimeDocument",
    "NewsDocument",
    "TradeDocument",
    "IndicatorDocument",
    "RetrievalQuery",
    "RAGContext",
    "RAGStats",
]


# Convenience function for quick RAG initialization
def create_rag(
    vector_store_dir: str = "./data/chromadb",
    embedding_model: str = "all-MiniLM-L6-v2",
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    device: str = "cpu",
) -> "TradeForgeRAG":
    """
    Create and initialize a TradeForgeRAG instance.

    This is the quickest way to get started with the RAG system.

    Args:
        vector_store_dir: Directory for ChromaDB persistence
        embedding_model: Sentence-transformer model name for embeddings
        reranker_model: Cross-encoder model name for reranking
        device: Compute device ('cpu' or 'cuda')

    Returns:
        Initialized TradeForgeRAG instance

    Example:
        >>> rag = create_rag(device="cuda")
        >>> context = await rag.get_strategy_context("RSI strategy", "NIFTY50")
    """
    rag = TradeForgeRAG(
        vector_store_dir=vector_store_dir,
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        device=device,
    )
    rag.initialize()
    return rag
