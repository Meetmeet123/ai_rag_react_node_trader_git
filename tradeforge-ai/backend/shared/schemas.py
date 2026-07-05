"""
Shared Pydantic v2 Schemas for TradeForge AI

All data models used across the pipeline: market data, signals,
training jobs, model versions, portfolio updates, and alerts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ---------------------------------------------------------------------------
# Market Data Schemas
# ---------------------------------------------------------------------------

class TimeFrame(str, Enum):
    """Supported candle timeframes."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    DAY_1 = "1d"


class TickData(BaseModel):
    """A single market tick (trade)."""
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    price: float = Field(..., gt=0)
    quantity: int = Field(..., ge=1)
    side: str = Field(..., pattern=r"^(buy|sell)$")
    symbol: str = Field(..., min_length=1)


class OHLCV(BaseModel):
    """A single OHLCV candle."""
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    symbol: str = Field(default="")
    timeframe: str = Field(default="5m")

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v: float, info) -> float:
        """Ensure high >= low."""
        low = info.data.get("low", 0)
        if low is not None and v < low:
            raise ValueError("high must be >= low")
        return v

    @field_validator("close", "open")
    @classmethod
    def in_range(cls, v: float, info) -> float:
        """Ensure close/open within high-low range."""
        data = info.data
        low = data.get("low", 0)
        high = data.get("high", float("inf"))
        if low is not None and high is not None:
            # At validation time other fields may not be set yet;
            # skip range check if bounds are missing.
            if v < low or v > high:
                raise ValueError(f"{info.field_name} ({v}) must be within low ({low}) and high ({high})")
        return v


class MarketDataRequest(BaseModel):
    """Request schema for fetching historical market data."""
    symbol: str = Field(..., min_length=1)
    from_date: datetime
    to_date: datetime
    timeframe: TimeFrame = TimeFrame.MINUTE_5

    @field_validator("to_date")
    @classmethod
    def to_after_from(cls, v: datetime, info) -> datetime:
        """Ensure to_date > from_date."""
        from_date = info.data.get("from_date")
        if from_date is not None and v <= from_date:
            raise ValueError("to_date must be after from_date")
        return v


# ---------------------------------------------------------------------------
# Trading Signal Schemas
# ---------------------------------------------------------------------------

class SignalAction(str, Enum):
    """Possible trading actions from the model."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"


class ConfidenceLevel(str, Enum):
    """Confidence bucket for a signal."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TradingSignal(BaseModel):
    """A trading signal emitted by the model."""
    model_config = ConfigDict(from_attributes=True)

    signal_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    action: SignalAction
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    timestamp: datetime
    price_at_signal: float = Field(..., gt=0)
    strategy_version: int = Field(..., ge=1)
    # Optional model explanation / reasoning
    reasoning: str = Field(default="")
    # Expected hold duration in minutes
    expected_hold_minutes: Optional[int] = None
    # Stop-loss and take-profit levels
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @field_validator("confidence_level", mode="before")
    @classmethod
    def derive_confidence_level(cls, v: Any, info) -> ConfidenceLevel:
        """Derive confidence level from confidence score if not provided."""
        if isinstance(v, ConfidenceLevel):
            return v
        confidence = info.data.get("confidence", 0.5)
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


# ---------------------------------------------------------------------------
# Model Registry Schemas
# ---------------------------------------------------------------------------

class ModelStatus(str, Enum):
    """Lifecycle status of a model version."""
    TRAINING = "training"
    READY = "ready"
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelMetrics(BaseModel):
    """Performance metrics for a model version."""
    model_config = ConfigDict(from_attributes=True)

    accuracy: float = Field(0.0, ge=0.0, le=1.0)
    precision: float = Field(0.0, ge=0.0, le=1.0)
    recall: float = Field(0.0, ge=0.0, le=1.0)
    f1_score: float = Field(0.0, ge=0.0, le=1.0)
    backtest_pnl: float = Field(0.0)
    backtest_sharpe: float = Field(0.0)
    backtest_max_drawdown: float = Field(0.0)
    # Live trading metrics (updated periodically)
    live_pnl: float = Field(0.0)
    live_trades_count: int = Field(0, ge=0)
    live_win_rate: float = Field(0.0, ge=0.0, le=1.0)


class ModelVersion(BaseModel):
    """Complete model version record (Pydantic mirror of ModelVersionInfo)."""
    model_config = ConfigDict(from_attributes=True)

    version_id: int = Field(..., ge=1)
    version_name: str = Field(..., min_length=1)
    description: str = Field(default="")
    checkpoint_path: str = Field(..., min_length=1)

    # Training info
    training_data_size: int = Field(0, ge=0)
    training_duration_sec: float = Field(0.0, ge=0.0)
    epochs: int = Field(0, ge=0)
    final_loss: float = Field(0.0)
    validation_loss: float = Field(0.0)

    # Performance
    metrics: ModelMetrics = Field(default_factory=ModelMetrics)

    # Status
    status: ModelStatus = ModelStatus.TRAINING
    is_active: bool = False

    # Metadata
    triggered_by: str = Field(default="scheduled_20min")
    formula_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class ModelComparison(BaseModel):
    """Comparison result between two model versions."""
    version_a_id: int
    version_a_name: str
    version_b_id: int
    version_b_name: str
    winner_id: int  # which version is better
    metrics_delta: Dict[str, float]  # b - a
    summary: str


# ---------------------------------------------------------------------------
# Training Pipeline Schemas
# ---------------------------------------------------------------------------

class TrainingStatus(str, Enum):
    """Status of a training job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerReason(str, Enum):
    """Why a training job was started."""
    SCHEDULED_20MIN = "scheduled_20min"
    FORMULA_CHANGE = "formula_change"
    MANUAL = "manual"
    NEW_DATA_THRESHOLD = "new_data_threshold"


class TrainingJob(BaseModel):
    """A single training job record."""
    model_config = ConfigDict(from_attributes=True)

    job_id: int = Field(..., ge=1)
    trigger_reason: TriggerReason = TriggerReason.SCHEDULED_20MIN
    status: TrainingStatus = TrainingStatus.QUEUED
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Dataset info
    data_samples: int = Field(0, ge=0)
    data_sources: List[str] = Field(default_factory=list)

    # Training config
    epochs_planned: int = Field(3, ge=1)
    epochs_trained: int = Field(0, ge=0)
    learning_rate: float = Field(1e-4, gt=0.0)
    batch_size: int = Field(32, ge=1)

    # Results
    final_loss: float = 0.0
    validation_loss: float = 0.0
    best_epoch: int = 0
    checkpoint_path: str = ""
    deployed: bool = False

    # Error tracking
    error_message: str = ""
    consecutive_failure_count: int = Field(0, ge=0)


class TrainingProgressUpdate(BaseModel):
    """Real-time training progress update sent via WebSocket."""
    job_id: int
    epoch: int
    total_epochs: int
    loss: float
    val_loss: float
    learning_rate: float
    elapsed_sec: float
    estimated_remaining_sec: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PipelineStatus(BaseModel):
    """Current status of the auto-training pipeline."""
    is_running: bool = False
    current_job_id: Optional[int] = None
    last_training_time: Optional[datetime] = None
    next_scheduled_run: Optional[datetime] = None
    interval_minutes: int = 20
    total_jobs_completed: int = 0
    total_jobs_failed: int = 0
    consecutive_failures: int = 0
    active_model_version_id: Optional[int] = None
    last_formula_hash: str = ""


# ---------------------------------------------------------------------------
# Portfolio / Position Schemas
# ---------------------------------------------------------------------------

class Position(BaseModel):
    """An open position."""
    model_config = ConfigDict(from_attributes=True)

    position_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    side: str = Field(..., pattern=r"^(long|short)$")
    entry_price: float = Field(..., gt=0)
    quantity: int = Field(..., ge=1)
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    model_version_id: int = Field(..., ge=1)


class PortfolioUpdate(BaseModel):
    """Portfolio snapshot update."""
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_equity: float = 0.0
    cash_balance: float = 0.0
    margin_used: float = 0.0
    open_positions: List[Position] = Field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    num_open_positions: int = 0


# ---------------------------------------------------------------------------
# Alert / Notification Schemas
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    """Severity level for system alerts."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Alert(BaseModel):
    """A system alert / notification."""
    model_config = ConfigDict(from_attributes=True)

    alert_id: str = Field(..., min_length=1)
    severity: AlertSeverity
    category: str = Field(..., min_length=1)  # training, market, system, trade
    title: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# WebSocket Message Schemas
# ---------------------------------------------------------------------------

class WSMessage(BaseModel):
    """Generic WebSocket envelope."""
    namespace: str = Field(..., pattern=r"^(market|signals|training|portfolio|alerts)$")
    event: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SubscribeRequest(BaseModel):
    """Client subscription request."""
    namespace: str = Field(..., pattern=r"^(market|signals|training|portfolio|alerts)$")
    symbols: Optional[List[str]] = None  # filter for market namespace


class UnsubscribeRequest(BaseModel):
    """Client unsubscription request."""
    namespace: str = Field(..., pattern=r"^(market|signals|training|portfolio|alerts)$")


# ---------------------------------------------------------------------------
# Backtest Schemas
# ---------------------------------------------------------------------------

class BacktestConfig(BaseModel):
    """Configuration for a backtest run."""
    start_date: datetime
    end_date: datetime
    symbols: List[str] = Field(default_factory=list)
    initial_capital: float = Field(100_000.0, gt=0)
    commission_pct: float = Field(0.02, ge=0.0)  # 0.02% per trade
    slippage_pct: float = Field(0.01, ge=0.0)   # 0.01% slippage
    model_version_id: int = Field(..., ge=1)


class BacktestResult(BaseModel):
    """Results from a backtest run."""
    model_config = ConfigDict(from_attributes=True)

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: int = 0
    calmar_ratio: float = 0.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
