"""
TradeForge AI — SQLAlchemy 2.0 ORM Models.

Contains the full domain model for strategies, trades, signals, backtests,
model versions, broker configurations, risk settings, and market data.
All models use SQLAlchemy 2.0 declarative style with proper type hints.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


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


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Strategy(Base):
    """Trading strategy definition created by user or AI.

    Stores the structured definition (indicators, conditions, parameters),
    auto-generated executable code, and backtest performance summaries.
    """

    __tablename__ = "strategies"

    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(200), nullable=False)
    description: Mapped[Optional[str]] = Column(Text)

    # The strategy definition as JSON (indicators, conditions, params).
    definition: Mapped[dict] = Column(JSON, nullable=False)
    # Auto-generated Python code ready for execution.
    generated_code: Mapped[Optional[str]] = Column(Text)
    # Natural-language prompt that created this strategy (if AI-generated).
    nl_prompt: Mapped[Optional[str]] = Column(Text)

    segment: Mapped[Segment] = Column(Enum(Segment), default=Segment.EQUITY)
    instrument: Mapped[str] = Column(
        String(50), nullable=False, comment="e.g., RELIANCE, NIFTY50, BANKNIFTY"
    )
    timeframe: Mapped[str] = Column(String(10), default="15m")

    # Entry / exit conditions stored as JSON.
    entry_conditions: Mapped[Optional[dict]] = Column(JSON)
    exit_conditions: Mapped[Optional[dict]] = Column(JSON)

    # --- Risk parameters --------------------------------------------------
    stop_loss_type: Mapped[str] = Column(
        String(20),
        default="fixed_pct",
        comment="fixed_pct | trailing | atr_based"
    )
    stop_loss_value: Mapped[float] = Column(Float, default=1.0)
    target_type: Mapped[str] = Column(
        String(20),
        default="fixed_pct",
        comment="fixed_pct | trailing | atr_based"
    )
    target_value: Mapped[float] = Column(Float, default=2.0)

    # --- Position sizing --------------------------------------------------
    position_sizing_type: Mapped[str] = Column(
        String(20),
        default="fixed_qty",
        comment="fixed_qty | pct_capital | risk_based"
    )
    position_sizing_value: Mapped[float] = Column(Float, default=1.0)

    status: Mapped[StrategyStatus] = Column(
        Enum(StrategyStatus), default=StrategyStatus.DRAFT
    )
    is_ai_generated: Mapped[bool] = Column(Boolean, default=False)

    # Backtest results summary (updated after each backtest).
    backtest_results: Mapped[Optional[dict]] = Column(JSON)

    # --- Timestamps -------------------------------------------------------
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # --- Relationships ----------------------------------------------------
    trades: Mapped[List["Trade"]] = relationship(
        "Trade", back_populates="strategy", lazy="dynamic"
    )
    backtests: Mapped[List["BacktestRun"]] = relationship(
        "BacktestRun", back_populates="strategy", lazy="dynamic"
    )
    signals: Mapped[List["Signal"]] = relationship(
        "Signal", back_populates="strategy", lazy="dynamic"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Strategy(id={self.id}, name='{self.name}', status='{self.status.value}')>"


class Trade(Base):
    """Executed trade log — one row per filled order pair (entry + exit).

    Tracks P&L, broker details, and links back to the originating strategy
    and signal for end-to-end auditability.
    """

    __tablename__ = "trades"

    id: Mapped[int] = Column(Integer, primary_key=True)
    strategy_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("strategies.id")
    )
    signal_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("signals.id")
    )

    symbol: Mapped[str] = Column(String(50), nullable=False)
    segment: Mapped[Optional[Segment]] = Column(Enum(Segment))
    direction: Mapped[TradeDirection] = Column(
        Enum(TradeDirection), nullable=False
    )

    entry_price: Mapped[float] = Column(Float, nullable=False)
    exit_price: Mapped[Optional[float]] = Column(Float)
    quantity: Mapped[int] = Column(Integer, nullable=False)

    entry_time: Mapped[datetime] = Column(DateTime, nullable=False)
    exit_time: Mapped[Optional[datetime]] = Column(DateTime)

    # Profit & loss (absolute and percentage).
    pnl: Mapped[Optional[float]] = Column(Float)
    pnl_pct: Mapped[Optional[float]] = Column(Float)

    stop_loss: Mapped[Optional[float]] = Column(Float)
    target: Mapped[Optional[float]] = Column(Float)

    # Broker details.
    broker: Mapped[Optional[BrokerName]] = Column(Enum(BrokerName))
    broker_order_id: Mapped[Optional[str]] = Column(String(100))

    is_paper: Mapped[bool] = Column(Boolean, default=True)
    notes: Mapped[Optional[str]] = Column(Text)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    # --- Relationships ----------------------------------------------------
    strategy: Mapped[Optional["Strategy"]] = relationship(
        "Strategy", back_populates="trades"
    )
    signal: Mapped[Optional["Signal"]] = relationship(
        "Signal", back_populates="trade"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Trade(id={self.id}, symbol='{self.symbol}', "
            f"direction='{self.direction.value}', pnl={self.pnl})>"
        )


class Signal(Base):
    """Trading signal generated by a strategy at a point in time.

    Signals are the bridge between strategy logic and execution.  They carry
    a confidence score (when produced by the LLM) and a snapshot of indicator
    values for post-hoc analysis.
    """

    __tablename__ = "signals"

    id: Mapped[int] = Column(Integer, primary_key=True)
    strategy_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("strategies.id")
    )

    symbol: Mapped[str] = Column(String(50), nullable=False)
    direction: Mapped[TradeDirection] = Column(
        Enum(TradeDirection), nullable=False
    )
    signal_price: Mapped[float] = Column(Float, nullable=False)
    executed_price: Mapped[Optional[float]] = Column(Float)

    quantity: Mapped[Optional[int]] = Column(Integer)
    status: Mapped[SignalStatus] = Column(
        Enum(SignalStatus), default=SignalStatus.PENDING
    )

    # Signal metadata.
    confidence: Mapped[Optional[float]] = Column(
        Float, comment="0.0 – 1.0 confidence from LLM"
    )
    indicators_snapshot: Mapped[Optional[dict]] = Column(
        JSON, comment="Indicator values at signal generation time"
    )

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    executed_at: Mapped[Optional[datetime]] = Column(DateTime)

    # --- Relationships ----------------------------------------------------
    strategy: Mapped[Optional["Strategy"]] = relationship(
        "Strategy", back_populates="signals"
    )
    trade: Mapped[Optional["Trade"]] = relationship(
        "Trade", back_populates="signal", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Signal(id={self.id}, symbol='{self.symbol}', "
            f"direction='{self.direction.value}', status='{self.status.value}')>"
        )


class BacktestRun(Base):
    """Record of a single backtest execution for a strategy.

    Stores both high-level summary metrics (win rate, Sharpe, drawdown) and
    granular data (equity curve, trade log) as JSON for chart rendering.
    """

    __tablename__ = "backtest_runs"

    id: Mapped[int] = Column(Integer, primary_key=True)
    strategy_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("strategies.id")
    )

    # Configuration.
    start_date: Mapped[datetime] = Column(DateTime, nullable=False)
    end_date: Mapped[datetime] = Column(DateTime, nullable=False)
    initial_capital: Mapped[float] = Column(Float, default=1_000_000.0)

    # --- Summary metrics --------------------------------------------------
    total_trades: Mapped[Optional[int]] = Column(Integer)
    winning_trades: Mapped[Optional[int]] = Column(Integer)
    losing_trades: Mapped[Optional[int]] = Column(Integer)
    win_rate: Mapped[Optional[float]] = Column(Float)

    net_pnl: Mapped[Optional[float]] = Column(Float)
    net_pnl_pct: Mapped[Optional[float]] = Column(Float)
    gross_profit: Mapped[Optional[float]] = Column(Float)
    gross_loss: Mapped[Optional[float]] = Column(Float)
    profit_factor: Mapped[Optional[float]] = Column(Float)

    max_drawdown: Mapped[Optional[float]] = Column(Float)
    max_drawdown_pct: Mapped[Optional[float]] = Column(Float)
    sharpe_ratio: Mapped[Optional[float]] = Column(Float)

    avg_profit_per_trade: Mapped[Optional[float]] = Column(Float)
    avg_loss_per_trade: Mapped[Optional[float]] = Column(Float)
    avg_holding_period: Mapped[Optional[float]] = Column(
        Float, comment="Average holding period in hours"
    )

    # --- Detailed results -------------------------------------------------
    equity_curve: Mapped[Optional[list]] = Column(
        JSON, comment="List of {date, equity} points"
    )
    drawdown_curve: Mapped[Optional[list]] = Column(JSON)
    monthly_returns: Mapped[Optional[dict]] = Column(JSON)
    trade_log: Mapped[Optional[list]] = Column(
        JSON, comment="List of individual trade dicts"
    )

    status: Mapped[str] = Column(
        String(20), default="completed",
        comment="running | completed | failed"
    )
    error_message: Mapped[Optional[str]] = Column(Text)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime)

    # --- Relationships ----------------------------------------------------
    strategy: Mapped[Optional["Strategy"]] = relationship(
        "Strategy", back_populates="backtests"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BacktestRun(id={self.id}, strategy_id={self.strategy_id}, "
            f"status='{self.status}')>"
        )


class ModelVersion(Base):
    """A versioned snapshot of a fine-tuned LLM.

    Tracks training hyper-parameters, performance metrics, and file-system
    paths so that models can be rolled back or A/B tested.
    """

    __tablename__ = "model_versions"

    id: Mapped[int] = Column(Integer, primary_key=True)
    version_name: Mapped[str] = Column(String(100), nullable=False)
    description: Mapped[Optional[str]] = Column(Text)

    # Training metadata.
    training_data_size: Mapped[Optional[int]] = Column(Integer)
    training_duration_seconds: Mapped[Optional[int]] = Column(Integer)
    epochs_trained: Mapped[Optional[int]] = Column(Integer)
    final_loss: Mapped[Optional[float]] = Column(Float)
    validation_loss: Mapped[Optional[float]] = Column(Float)

    # Model performance metrics.
    accuracy: Mapped[Optional[float]] = Column(Float)
    precision_score: Mapped[Optional[float]] = Column(Float)
    recall_score: Mapped[Optional[float]] = Column(Float)
    f1_score: Mapped[Optional[float]] = Column(Float)

    # File-system artefacts.
    checkpoint_path: Mapped[Optional[str]] = Column(String(500))
    config_path: Mapped[Optional[str]] = Column(String(500))

    status: Mapped[ModelVersionStatus] = Column(
        Enum(ModelVersionStatus), default=ModelVersionStatus.TRAINING
    )
    is_active: Mapped[bool] = Column(
        Boolean, default=False,
        comment="Only one model version should be active at a time"
    )

    # Training trigger audit.
    triggered_by: Mapped[Optional[str]] = Column(
        String(50),
        comment="auto_20min | manual | formula_change"
    )
    formula_snapshot: Mapped[Optional[dict]] = Column(
        JSON,
        comment="Strategy formulas at the time of training"
    )

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ModelVersion(id={self.id}, name='{self.version_name}', "
            f"status='{self.status.value}', active={self.is_active})>"
        )


class TrainingLog(Base):
    """Auto-training execution log — one row per training run.

    Useful for debugging model drift, trigger timing, and convergence issues.
    """

    __tablename__ = "training_logs"

    id: Mapped[int] = Column(Integer, primary_key=True)
    model_version_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("model_versions.id")
    )

    trigger_reason: Mapped[Optional[str]] = Column(
        String(100),
        comment="scheduled_20min | formula_change | manual"
    )
    status: Mapped[Optional[str]] = Column(
        String(20),
        comment="started | completed | failed"
    )

    data_samples: Mapped[Optional[int]] = Column(Integer)
    epochs: Mapped[Optional[int]] = Column(Integer)
    final_loss: Mapped[Optional[float]] = Column(Float)

    error_message: Mapped[Optional[str]] = Column(Text)

    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<TrainingLog(id={self.id}, trigger='{self.trigger_reason}', "
            f"status='{self.status}')>"
        )


class BrokerConfig(Base):
    """Broker API configuration and connection state.

    Stores encrypted credentials (AES-256 in production), access tokens, and
    connection status for each supported broker.
    """

    __tablename__ = "broker_configs"

    id: Mapped[int] = Column(Integer, primary_key=True)
    broker: Mapped[BrokerName] = Column(
        Enum(BrokerName), nullable=False
    )

    # API credentials — encrypt these fields in production!
    api_key: Mapped[Optional[str]] = Column(String(500))
    api_secret: Mapped[Optional[str]] = Column(String(500))
    client_id: Mapped[Optional[str]] = Column(String(100))
    access_token: Mapped[Optional[str]] = Column(String(500))

    is_active: Mapped[bool] = Column(
        Boolean, default=False,
        comment="Whether this broker is the current default"
    )
    is_connected: Mapped[bool] = Column(
        Boolean, default=False,
        comment="Real-time WebSocket/API connection state"
    )

    # Paper mode uses simulated order execution with no real capital.
    is_paper: Mapped[bool] = Column(Boolean, default=False)

    last_connected_at: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BrokerConfig(id={self.id}, broker='{self.broker.value}', "
            f"active={self.is_active}, connected={self.is_connected})>"
        )


class RiskConfig(Base):
    """Risk management settings — singleton-style configuration.

    Defines kill-switch thresholds, exposure limits, and auto square-off
    rules.  Only the latest row is honoured by the trading engine.
    """

    __tablename__ = "risk_configs"

    id: Mapped[int] = Column(Integer, primary_key=True)

    # --- Daily loss guard -------------------------------------------------
    daily_loss_limit: Mapped[float] = Column(Float, default=20_000.0)
    daily_loss_limit_enabled: Mapped[bool] = Column(Boolean, default=True)

    # --- Exposure limits --------------------------------------------------
    max_positions: Mapped[int] = Column(Integer, default=10)
    max_exposure_per_trade_pct: Mapped[float] = Column(
        Float, default=10.0, comment="Max % of capital per trade"
    )
    max_exposure_overall_pct: Mapped[float] = Column(
        Float, default=50.0, comment="Max % of capital across all positions"
    )

    # --- Kill switch & auto square-off ------------------------------------
    kill_switch_enabled: Mapped[bool] = Column(Boolean, default=True)
    auto_square_off_time: Mapped[str] = Column(
        String(10), default="15:15",
        comment="IST time to auto-close all positions"
    )

    consecutive_loss_limit: Mapped[int] = Column(
        Integer, default=5,
        comment="Max consecutive losses before pausing"
    )

    # --- Default risk per trade -------------------------------------------
    default_stop_loss_pct: Mapped[float] = Column(Float, default=1.0)
    default_target_pct: Mapped[float] = Column(Float, default=2.0)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RiskConfig(id={self.id}, max_positions={self.max_positions}, "
            f"daily_limit={self.daily_loss_limit})>"
        )


class MarketData(Base):
    """Historical OHLCV data cache with pre-computed technical indicators.

    Stores bar data along with commonly used indicators (SMA, EMA, RSI,
    MACD, Bollinger Bands, ATR, VWAP) to avoid redundant calculation.
    """

    __tablename__ = "market_data"

    id: Mapped[int] = Column(Integer, primary_key=True)
    symbol: Mapped[str] = Column(String(50), nullable=False)
    timeframe: Mapped[str] = Column(String(10), nullable=False)

    timestamp: Mapped[datetime] = Column(DateTime, nullable=False)
    open: Mapped[float] = Column(Float, nullable=False)
    high: Mapped[float] = Column(Float, nullable=False)
    low: Mapped[float] = Column(Float, nullable=False)
    close: Mapped[float] = Column(Float, nullable=False)
    volume: Mapped[int] = Column(Integer, nullable=False)

    # --- Pre-computed technical indicators --------------------------------
    sma_20: Mapped[Optional[float]] = Column(Float)
    sma_50: Mapped[Optional[float]] = Column(Float)
    ema_20: Mapped[Optional[float]] = Column(Float)
    ema_50: Mapped[Optional[float]] = Column(Float)
    rsi_14: Mapped[Optional[float]] = Column(Float)
    macd: Mapped[Optional[float]] = Column(Float)
    macd_signal: Mapped[Optional[float]] = Column(Float)
    bb_upper: Mapped[Optional[float]] = Column(Float)
    bb_middle: Mapped[Optional[float]] = Column(Float)
    bb_lower: Mapped[Optional[float]] = Column(Float)
    atr_14: Mapped[Optional[float]] = Column(Float)
    vwap: Mapped[Optional[float]] = Column(Float)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<MarketData(symbol='{self.symbol}', tf='{self.timeframe}', "
            f"ts='{self.timestamp}', close={self.close})>"
        )
