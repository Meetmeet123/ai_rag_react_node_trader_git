"""
TradeForge AI — Beanie/MongoDB Document Models.

Contains the full domain model for users, strategies, trades, signals,
backtests, model versions, broker configurations, risk settings, and market data.
All models use Beanie ODM on top of Pydantic v2.
"""


import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from beanie import Document, Indexed
from pydantic import BaseModel, EmailStr, Field
from beanie import PydanticObjectId


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StrategyStatus(str, enum.Enum):
    """Lifecycle states for a trading strategy."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAPER = "paper"
    BACKTESTING = "backtesting"
    ARCHIVED = "archived"


class Segment(str, enum.Enum):
    """Market segment classifications."""

    EQUITY = "equity"
    FUTURES = "futures"
    OPTIONS = "options"
    INDEX = "index"


class OrderType(str, enum.Enum):
    """Order type variations supported by Indian brokers."""

    MARKET = "market"
    LIMIT = "limit"
    SL = "sl"           # Stop-loss limit
    SL_M = "sl_m"       # Stop-loss market


class ProductType(str, enum.Enum):
    """Product types for Indian brokerages."""

    MIS = "mis"         # Intraday
    CNC = "cnc"         # Cash & carry (delivery)
    NRML = "nrml"       # Normal (overnight positions)


class TradeDirection(str, enum.Enum):
    """Direction of a trade or signal."""

    BUY = "buy"
    SELL = "sell"


class SignalStatus(str, enum.Enum):
    """Processing states for a generated signal."""

    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    IGNORED = "ignored"


class BrokerName(str, enum.Enum):
    """Supported broker integrations."""

    ANGEL_ONE = "angel_one"
    ZERODHA = "zerodha"
    FYERS = "fyers"
    UPSTOX = "upstox"
    PAPER = "paper"     # Simulated / paper trading


class ModelVersionStatus(str, enum.Enum):
    """Lifecycle states for a trained LLM version."""

    TRAINING = "training"
    READY = "ready"
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"


class UserRole(str, enum.Enum):
    """User roles for access control."""

    USER = "user"
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# Helper base for timestamped documents
# ---------------------------------------------------------------------------


class TimestampedDocument(Document):
    """Abstract base document that adds created_at / updated_at timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        is_abstract = True

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(TimestampedDocument):
    """Application user account."""

    email: Indexed(EmailStr, unique=True)
    username: Indexed(str, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_approved_for_live: bool = False
    last_login: Optional[datetime] = None

    class Settings:
        name = "users"


class Account(TimestampedDocument):
    """Extended account/profile data for a user."""

    user_id: PydanticObjectId
    phone: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    language: str = "en"
    notifications_enabled: bool = True
    preferences: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "accounts"


class Strategy(TimestampedDocument):
    """Trading strategy definition created by user or AI."""

    # Ownership
    user_id: Optional[PydanticObjectId] = None

    name: str
    description: Optional[str] = None

    # The strategy definition as JSON (indicators, conditions, params).
    definition: Dict[str, Any]
    # Auto-generated Python code ready for execution.
    generated_code: Optional[str] = None
    # Natural-language prompt that created this strategy (if AI-generated).
    nl_prompt: Optional[str] = None

    segment: Segment = Segment.EQUITY
    instrument: Indexed(str) = Field(
        ..., description="e.g., RELIANCE, NIFTY50, BANKNIFTY"
    )
    timeframe: str = "15m"

    # Entry / exit conditions stored as JSON.
    entry_conditions: Optional[List[Dict[str, Any]]] = None
    exit_conditions: Optional[List[Dict[str, Any]]] = None

    # --- Risk parameters --------------------------------------------------
    stop_loss_type: str = "fixed_pct"
    stop_loss_value: float = 1.0
    target_type: str = "fixed_pct"
    target_value: float = 2.0

    # --- Position sizing --------------------------------------------------
    position_sizing_type: str = "fixed_qty"
    position_sizing_value: float = 1.0

    status: StrategyStatus = StrategyStatus.DRAFT
    is_ai_generated: bool = False

    # Backtest results summary (updated after each backtest).
    backtest_results: Optional[Dict[str, Any]] = None

    class Settings:
        name = "strategies"


class Trade(TimestampedDocument):
    """Executed trade log — one row per filled order pair (entry + exit)."""

    user_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None
    signal_id: Optional[PydanticObjectId] = None

    symbol: str
    segment: Optional[Segment] = None
    direction: TradeDirection

    entry_price: float
    exit_price: Optional[float] = None
    quantity: int

    entry_time: datetime
    exit_time: Optional[datetime] = None

    # Profit & loss (absolute and percentage).
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

    stop_loss: Optional[float] = None
    target: Optional[float] = None

    # Broker details.
    broker: Optional[BrokerName] = None
    broker_order_id: Optional[str] = None

    is_paper: bool = True
    notes: Optional[str] = None

    class Settings:
        name = "trades"


class Signal(TimestampedDocument):
    """Trading signal generated by a strategy at a point in time."""

    user_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None

    symbol: str
    direction: TradeDirection
    signal_price: float
    executed_price: Optional[float] = None

    quantity: Optional[int] = None
    status: SignalStatus = SignalStatus.PENDING

    # Signal metadata.
    confidence: Optional[float] = Field(
        None, description="0.0 – 1.0 confidence from LLM"
    )
    indicators_snapshot: Optional[Dict[str, Any]] = Field(
        None, description="Indicator values at signal generation time"
    )

    executed_at: Optional[datetime] = None

    class Settings:
        name = "signals"


class BacktestRun(TimestampedDocument):
    """Record of a single backtest execution for a strategy."""

    user_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None

    # Configuration.
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1_000_000.0

    # --- Summary metrics --------------------------------------------------
    total_trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    win_rate: Optional[float] = None

    net_pnl: Optional[float] = None
    net_pnl_pct: Optional[float] = None
    gross_profit: Optional[float] = None
    gross_loss: Optional[float] = None
    profit_factor: Optional[float] = None

    max_drawdown: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None

    avg_profit_per_trade: Optional[float] = None
    avg_loss_per_trade: Optional[float] = None
    avg_holding_period: Optional[float] = Field(
        None, description="Average holding period in hours"
    )

    # --- Detailed results -------------------------------------------------
    equity_curve: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of {date, equity} points"
    )
    drawdown_curve: Optional[List[Dict[str, Any]]] = None
    monthly_returns: Optional[Dict[str, Any]] = None
    trade_log: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of individual trade dicts"
    )

    status: str = "completed"
    error_message: Optional[str] = None

    completed_at: Optional[datetime] = None

    class Settings:
        name = "backtest_runs"


class ModelVersion(TimestampedDocument):
    """A versioned snapshot of a fine-tuned LLM."""

    version_name: Indexed(str, unique=True)
    description: Optional[str] = None

    # Training metadata.
    training_data_size: Optional[int] = None
    training_duration_seconds: Optional[int] = None
    epochs_trained: Optional[int] = None
    final_loss: Optional[float] = None
    validation_loss: Optional[float] = None

    # Model performance metrics.
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall_score: Optional[float] = None
    f1_score: Optional[float] = None

    # File-system artefacts.
    checkpoint_path: Optional[str] = None
    config_path: Optional[str] = None

    status: ModelVersionStatus = ModelVersionStatus.TRAINING
    is_active: bool = Field(
        default=False,
        description="Only one model version should be active at a time",
    )

    # Training trigger audit.
    triggered_by: Optional[str] = Field(
        None, description="auto_20min | manual | formula_change"
    )
    formula_snapshot: Optional[Dict[str, Any]] = Field(
        None, description="Strategy formulas at the time of training"
    )

    completed_at: Optional[datetime] = None

    class Settings:
        name = "model_versions"


class TrainingLog(TimestampedDocument):
    """Auto-training execution log — one row per training run."""

    model_version_id: Optional[PydanticObjectId] = None

    trigger_reason: Optional[str] = Field(
        None, description="scheduled_20min | formula_change | manual"
    )
    status: Optional[str] = Field(
        None, description="started | completed | failed"
    )

    data_samples: Optional[int] = None
    epochs: Optional[int] = None
    final_loss: Optional[float] = None

    error_message: Optional[str] = None

    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "training_logs"


class BrokerConfig(TimestampedDocument):
    """Broker API configuration and connection state."""

    user_id: Optional[PydanticObjectId] = None
    broker: BrokerName

    # API credentials — encrypt these fields in production!
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    client_id: Optional[str] = None
    access_token: Optional[str] = None

    is_active: bool = Field(
        default=False,
        description="Whether this broker is the current default",
    )
    is_connected: bool = Field(
        default=False,
        description="Real-time WebSocket/API connection state",
    )

    # Paper mode uses simulated order execution with no real capital.
    is_paper: bool = False

    last_connected_at: Optional[datetime] = None

    class Settings:
        name = "broker_configs"


class RiskConfig(TimestampedDocument):
    """Risk management settings — per-user configuration."""

    user_id: Optional[PydanticObjectId] = None

    # --- Daily loss guard -------------------------------------------------
    daily_loss_limit: float = 20_000.0
    daily_loss_limit_enabled: bool = True

    # --- Exposure limits --------------------------------------------------
    max_positions: int = 10
    max_exposure_per_trade_pct: float = Field(
        default=10.0, description="Max % of capital per trade"
    )
    max_exposure_overall_pct: float = Field(
        default=50.0, description="Max % of capital across all positions"
    )

    # --- Kill switch & auto square-off ------------------------------------
    kill_switch_enabled: bool = True
    auto_square_off_time: str = "15:15"

    consecutive_loss_limit: int = Field(
        default=5,
        description="Max consecutive losses before pausing",
    )

    # --- Default risk per trade -------------------------------------------
    default_stop_loss_pct: float = 1.0
    default_target_pct: float = 2.0

    class Settings:
        name = "risk_configs"


class MarketData(Document):
    """Historical OHLCV data cache with pre-computed technical indicators."""

    symbol: Indexed(str)
    timeframe: Indexed(str)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    # --- Pre-computed technical indicators --------------------------------
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    vwap: Optional[float] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "market_data"
