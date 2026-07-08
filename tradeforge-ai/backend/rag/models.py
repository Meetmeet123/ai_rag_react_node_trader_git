"""
Pydantic v2 Models for TradeForge RAG System

Defines all data models used across the RAG pipeline including:
- Document models for each collection type
- Query and context models
- Response models with validation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TradingSegment(str, Enum):
    """Indian market trading segments"""

    EQUITY = "equity"
    FUTURES = "futures"
    OPTIONS = "options"
    CURRENCY = "currency"
    COMMODITY = "commodity"
    INDEX = "index"


class TimeFrame(str, Enum):
    """Supported trading timeframes"""

    SCALPING_1M = "1m"
    SCALPING_5M = "5m"
    INTRADAY_15M = "15m"
    INTRADAY_30M = "30m"
    INTRADAY_1H = "1h"
    SWING_4H = "4h"
    SWING_DAILY = "1d"
    POSITION_WEEKLY = "1w"
    MONTHLY = "1M"


class DocumentType(str, Enum):
    """Types of documents stored in RAG"""

    STRATEGY = "strategy"
    BACKTEST_RESULT = "backtest_result"
    MARKET_REGIME = "market_regime"
    NEWS_EVENT = "news_event"
    TRADE_HISTORY = "trade_history"
    INDICATOR_CONTEXT = "indicator_context"
    MARKET_COMMENTARY = "market_commentary"


class BaseDocument(BaseModel):
    """Base document model with common fields"""

    id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Document text content")
    doc_type: DocumentType = Field(..., description="Document type")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = Field(default=None)
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = {"arbitrary_types_allowed": True}


class EntryCondition(BaseModel):
    """Strategy entry condition"""

    indicator: str = Field(..., description="Indicator name (e.g., RSI, SMA)")
    period: int = Field(..., ge=1, le=500, description="Indicator period")
    condition: str = Field(
        ..., description="Condition (e.g., above, below, crosses_above)"
    )
    value: float = Field(..., description="Threshold value")


class ExitCondition(BaseModel):
    """Strategy exit condition"""

    indicator: Optional[str] = Field(default=None)
    period: Optional[int] = Field(default=None, ge=1, le=500)
    condition: str = Field(..., description="Exit condition type")
    value: float = Field(..., description="Exit threshold")


class StopLossConfig(BaseModel):
    """Stop loss configuration"""

    type: str = Field(..., description="fixed, atr_based, percentage")
    value: float = Field(..., ge=0.0, description="Stop loss value")
    trailing: bool = Field(default=False)
    activation_pnl: Optional[float] = Field(default=None)


class TargetConfig(BaseModel):
    """Profit target configuration"""

    type: str = Field(..., description="fixed, atr_based, rrr_based")
    value: float = Field(..., ge=0.0)
    rrr: Optional[float] = Field(default=None, description="Risk-reward ratio")


class PositionSizing(BaseModel):
    """Position sizing configuration"""

    type: str = Field(..., description="fixed_quantity, capital_percentage, risk_based")
    value: float = Field(..., ge=0.0)
    max_position_size: Optional[float] = Field(default=None)


class StrategyDocument(BaseDocument):
    """Trading strategy document for RAG storage"""

    doc_type: DocumentType = DocumentType.STRATEGY
    name: str = Field(..., description="Strategy name")
    description: str = Field(..., description="Strategy description")
    instrument: str = Field(
        ..., description="Trading instrument (e.g., NIFTY50, RELIANCE)"
    )
    segment: TradingSegment = Field(default=TradingSegment.EQUITY)
    timeframe: TimeFrame = Field(default=TimeFrame.INTRADAY_15M)
    entry_conditions: List[EntryCondition] = Field(default_factory=list)
    exit_conditions: List[ExitCondition] = Field(default_factory=list)
    stop_loss: Optional[StopLossConfig] = Field(default=None)
    target: Optional[TargetConfig] = Field(default=None)
    position_sizing: Optional[PositionSizing] = Field(default=None)
    win_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    total_pnl: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    max_drawdown: Optional[float] = Field(default=None)
    total_trades: int = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)

    def to_embedding_text(self) -> str:
        """Convert strategy to rich text for embedding"""
        entry_texts = [
            f"{e.indicator}({e.period}) {e.condition} {e.value}"
            for e in self.entry_conditions
        ]
        exit_texts = [
            f"{e.indicator or ''} {e.condition} {e.value}" for e in self.exit_conditions
        ]
        parts = [
            f"Strategy: {self.name}",
            f"Description: {self.description}",
            f"Instrument: {self.instrument}",
            f"Segment: {self.segment.value}",
            f"Timeframe: {self.timeframe.value}",
            f"Entry: {'; '.join(entry_texts)}",
            f"Exit: {'; '.join(exit_texts)}",
            f"Stop Loss: {self.stop_loss.type if self.stop_loss else 'N/A'} "
            f"{self.stop_loss.value if self.stop_loss else ''}",
            f"Target: {self.target.type if self.target else 'N/A'} "
            f"{self.target.value if self.target else ''}",
            f"Win Rate: {self.win_rate}%" if self.win_rate else "",
            f"P&L: ₹{self.total_pnl}" if self.total_pnl else "",
            f"Tags: {', '.join(self.tags)}" if self.tags else "",
        ]
        return "\n".join(filter(None, parts))


class BacktestMetrics(BaseModel):
    """Backtest performance metrics"""

    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=100.0)
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = Field(ge=0.0)
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_amount: float = 0.0
    total_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    calmar_ratio: float = 0.0
    expectancy: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_holding_period: str = ""


class BacktestDocument(BaseDocument):
    """Backtest result document for RAG storage"""

    doc_type: DocumentType = DocumentType.BACKTEST_RESULT
    strategy_name: str = Field(..., description="Strategy that was backtested")
    strategy_id: str = Field(..., description="Reference to strategy document")
    symbol: str = Field(..., description="Backtest symbol")
    start_date: datetime = Field(...)
    end_date: datetime = Field(...)
    timeframe: TimeFrame = Field(default=TimeFrame.INTRADAY_15M)
    metrics: BacktestMetrics = Field(...)
    monthly_returns: Dict[str, float] = Field(default_factory=dict)
    parameter_values: Dict[str, Any] = Field(default_factory=dict)

    def to_embedding_text(self) -> str:
        """Convert backtest to rich text for embedding"""
        m = self.metrics
        return (
            f"Backtest: {self.strategy_name} on {self.symbol}\n"
            f"Period: {self.start_date.date()} to {self.end_date.date()}\n"
            f"Timeframe: {self.timeframe.value}\n"
            f"Trades: {m.total_trades} "
            f"(Win: {m.winning_trades}, Loss: {m.losing_trades})\n"
            f"Win Rate: {m.win_rate:.1f}%\n"
            f"P&L: ₹{m.total_pnl:,.2f}\n"
            f"Sharpe: {m.sharpe_ratio:.2f}\n"
            f"Max Drawdown: {m.max_drawdown_pct:.2f}%\n"
            f"Profit Factor: {m.profit_factor:.2f}\n"
            f"Expectancy: ₹{m.expectancy:.2f}\n"
            f"Parameters: {self.parameter_values}"
        )


class MarketRegimeDocument(BaseDocument):
    """Market regime document for RAG storage"""

    doc_type: DocumentType = DocumentType.MARKET_REGIME
    symbol: str = Field(...)
    regime: str = Field(..., description="Detected market regime")
    confidence: float = Field(ge=0.0, le=1.0)
    trend: str = Field(default="")
    volatility: str = Field(default="")
    volume_regime: str = Field(default="")
    momentum: str = Field(default="")
    price: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_embedding_text(self) -> str:
        return (
            f"Market Regime for {self.symbol} at {self.price:.2f}\n"
            f"Regime: {self.regime} (confidence: {self.confidence:.0%})\n"
            f"Trend: {self.trend}\n"
            f"Volatility: {self.volatility}\n"
            f"Volume: {self.volume_regime}\n"
            f"Momentum: {self.momentum}"
        )


class NewsDocument(BaseDocument):
    """News event document for RAG storage"""

    doc_type: DocumentType = DocumentType.NEWS_EVENT
    title: str = Field(...)
    summary: str = Field(default="")
    source: str = Field(default="")
    url: Optional[str] = Field(default=None)
    published_at: datetime = Field(default_factory=datetime.utcnow)
    symbols: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = Field(default=None)
    sentiment_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    category: Optional[str] = Field(default=None)

    def to_embedding_text(self) -> str:
        return (
            f"News: {self.title}\n"
            f"Summary: {self.summary}\n"
            f"Source: {self.source}\n"
            f"Symbols: {', '.join(self.symbols)}\n"
            f"Sentiment: {self.sentiment} ({self.sentiment_score})\n"
            f"Category: {self.category}"
        )


class TradeDocument(BaseDocument):
    """Executed trade document for RAG storage"""

    doc_type: DocumentType = DocumentType.TRADE_HISTORY
    trade_id: str = Field(...)
    symbol: str = Field(...)
    strategy_name: str = Field(...)
    strategy_id: str = Field(...)
    side: str = Field(..., description="BUY or SELL")
    entry_price: float = Field(gt=0.0)
    exit_price: Optional[float] = Field(default=None)
    quantity: int = Field(gt=0)
    entry_time: datetime = Field(...)
    exit_time: Optional[datetime] = Field(default=None)
    pnl: Optional[float] = Field(default=None)
    pnl_pct: Optional[float] = Field(default=None)
    status: str = Field(default="open", description="open, closed, stopped")
    stop_loss: Optional[float] = Field(default=None)
    target: Optional[float] = Field(default=None)
    segment: TradingSegment = Field(default=TradingSegment.EQUITY)

    def to_embedding_text(self) -> str:
        return (
            f"Trade: {self.side} {self.symbol} x{self.quantity}\n"
            f"Strategy: {self.strategy_name}\n"
            f"Entry: ₹{self.entry_price:.2f} at {self.entry_time}\n"
            f"Status: {self.status}\n"
            f"P&L: ₹{self.pnl:,.2f}"
            if self.pnl
            else ""
        )


class IndicatorDocument(BaseDocument):
    """Technical indicator reference document"""

    doc_type: DocumentType = DocumentType.INDICATOR_CONTEXT
    name: str = Field(...)
    full_name: str = Field(default="")
    category: str = Field(..., description="trend, momentum, volatility, volume")
    description: str = Field(...)
    best_for: str = Field(default="")
    interpretation: str = Field(default="")
    common_periods: List[int] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)

    def to_embedding_text(self) -> str:
        return (
            f"Indicator: {self.name} ({self.full_name})\n"
            f"Category: {self.category}\n"
            f"Description: {self.description}\n"
            f"Best For: {self.best_for}\n"
            f"Interpretation: {self.interpretation}\n"
            f"Common Periods: {self.common_periods}\n"
            f"Signals: {', '.join(self.signals)}"
        )


class RetrievalQuery(BaseModel):
    """Structured retrieval query"""

    original_query: str = Field(...)
    expanded_query: Optional[str] = Field(default=None)
    sources: List[str] = Field(
        default_factory=lambda: ["strategies", "market_regime", "news_events"]
    )
    top_k: int = Field(default=10, ge=1, le=100)
    symbol: Optional[str] = Field(default=None)
    segment: Optional[str] = Field(default=None)
    time_window_hours: Optional[int] = Field(default=None, ge=1)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    filters: Dict[str, Any] = Field(default_factory=dict)


class RAGContext(BaseModel):
    """Complete RAG context for a query"""

    query: str = Field(...)
    similar_strategies: List[Dict[str, Any]] = Field(default_factory=list)
    market_context: List[Dict[str, Any]] = Field(default_factory=list)
    recent_news: List[Dict[str, Any]] = Field(default_factory=list)
    indicator_explanations: List[Dict[str, Any]] = Field(default_factory=list)
    backtest_insights: List[Dict[str, Any]] = Field(default_factory=list)
    trade_history: List[Dict[str, Any]] = Field(default_factory=list)
    market_regime: Optional[Dict[str, Any]] = Field(default=None)
    total_sources: int = Field(default=0)
    retrieval_time_ms: float = Field(default=0.0)
    regime_info: Optional[Dict[str, Any]] = Field(default=None)


class RAGStats(BaseModel):
    """RAG system statistics"""

    vector_store_dir: str = Field(...)
    embedding_model: str = Field(...)
    reranker_model: str = Field(...)
    device: str = Field(...)
    collection_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    total_documents: int = Field(default=0)
    total_collections: int = Field(default=0)
    embedding_dimension: int = Field(default=0)
    uptime_seconds: float = Field(default=0.0)
    queries_served: int = Field(default=0)
    avg_query_time_ms: float = Field(default=0.0)
    last_ingestion: Optional[datetime] = Field(default=None)
    initialized_at: Optional[datetime] = Field(default=None)
