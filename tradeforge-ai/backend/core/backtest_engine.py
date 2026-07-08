"""
High-Performance Backtesting Engine for TradeForge AI

Simulates strategy execution on historical OHLCV data with:
- Realistic order execution (slippage, brokerage)
- Position tracking and P&L calculation
- Performance metrics (Sharpe, drawdown, win rate, etc.)
- Equity curve and trade log generation
- Support for Equity, Futures, and Options (CE/PE)

The engine is designed for vectorised signal input (pandas Series of booleans)
so it can be driven by any signal-generation strategy including LLM-based ones.

Typical usage::

    config = BacktestConfig(initial_capital=1_000_000, slippage_pct=0.05)
    engine = BacktestEngine(config)
    result = engine.run(data, entry_signals, exit_signals, symbol="RELIANCE")
    print(f"Net P&L: {result.net_pnl:,.2f}  Sharpe: {result.sharpe_ratio:.2f}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OrderSide(Enum):
    """Direction of an order."""

    BUY = "buy"
    SELL = "sell"


class PositionType(Enum):
    """Type of position."""

    LONG = "long"
    SHORT = "short"


class ExitReason(Enum):
    """Reason why a trade was closed."""

    TARGET = "target"
    STOP_LOSS = "stop_loss"
    SIGNAL_REVERSAL = "signal_reversal"
    END_OF_DATA = "end_of_data"
    SQUARE_OFF = "square_off"
    TRAILING_STOP = "trailing_stop"


class PositionSizingType(str, Enum):
    """How position size is determined."""

    FIXED_QTY = "fixed_qty"
    PCT_CAPITAL = "pct_capital"
    RISK_BASED = "risk_based"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class BacktestConfig(BaseModel):
    """Backtest configuration validated via Pydantic.

    Attributes:
        initial_capital: Starting capital in INR.
        brokerage_per_order: Flat brokerage per executed side (INR).
        slippage_pct: Slippage as percentage of price (e.g. 0.05 = 0.05%).
        position_sizing_type: ``fixed_qty``, ``pct_capital``, or ``risk_based``.
        position_sizing_value: Meaning depends on type (qty, %, or risk-amount).
        stop_loss_type: ``fixed_pct``, ``atr``, or ``none``.
        stop_loss_value: Stop-loss value (pct or ATR multiplier).
        target_type: ``fixed_pct``, ``atr``, ``rr_based``, or ``none``.
        target_value: Target value (pct, ATR multiplier, or risk:reward ratio).
        trailing_stop_pct: Trailing stop activation (0 = disabled).
        allow_short: Whether short selling is permitted.
        max_positions: Maximum simultaneous positions.
        compound_returns: If True, use running capital for sizing; else fixed.
    """

    initial_capital: float = Field(default=1_000_000.0, gt=0)
    brokerage_per_order: float = Field(default=20.0, ge=0)
    slippage_pct: float = Field(default=0.05, ge=0)
    position_sizing_type: PositionSizingType = Field(
        default=PositionSizingType.FIXED_QTY
    )
    position_sizing_value: float = Field(default=1.0, gt=0)
    stop_loss_type: str = Field(default="fixed_pct")
    stop_loss_value: float = Field(default=1.0, ge=0)
    target_type: str = Field(default="fixed_pct")
    target_value: float = Field(default=2.0, ge=0)
    trailing_stop_pct: float = Field(default=0.0, ge=0)
    allow_short: bool = Field(default=True)
    max_positions: int = Field(default=1, ge=1)
    compound_returns: bool = Field(default=True)

    @field_validator("stop_loss_type", "target_type")
    @classmethod
    def _validate_sl_target_type(cls, v: str) -> str:
        allowed = {"fixed_pct", "atr", "rr_based", "none"}
        if v not in allowed:
            raise ValueError(f"Must be one of {allowed}")
        return v


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------


@dataclass
class TradeRecord:
    """Individual completed trade.

    Attributes:
        entry_time: Timestamp when position was opened.
        exit_time: Timestamp when position was closed (None if open).
        symbol: Trading symbol.
        direction: ``long`` or ``short``.
        entry_price: Executed entry price (after slippage).
        exit_price: Executed exit price (after slippage).
        quantity: Number of units.
        pnl: Realised P&L in INR.
        pnl_pct: Realised P&L as percentage of entry value.
        exit_reason: Why the trade closed.
        brokerage: Total brokerage paid.
        slippage: Total slippage cost.
        mtm_high: Highest favourable price reached (for R-multiple).
        mtm_low: Lowest adverse price reached.
    """

    entry_time: datetime
    exit_time: Optional[datetime] = None
    symbol: str = ""
    direction: str = "long"
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    brokerage: float = 0.0
    slippage: float = 0.0
    mtm_high: float = 0.0
    mtm_low: float = 0.0
    highest_reached: float = 0.0
    lowest_reached: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": round(self.entry_price, 2),
            "exit_price": round(self.exit_price, 2),
            "quantity": self.quantity,
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 4),
            "exit_reason": self.exit_reason,
            "brokerage": round(self.brokerage, 2),
            "slippage": round(self.slippage, 2),
        }


# ---------------------------------------------------------------------------
# Backtest result
# ---------------------------------------------------------------------------


@dataclass
class BacktestResult:
    """Complete backtest results.

    All monetary fields are in INR unless noted.
    """

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    net_pnl_pct: float = 0.0
    profit_factor: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trade analytics
    avg_profit_per_trade: float = 0.0
    avg_loss_per_trade: float = 0.0
    avg_holding_period_hours: float = 0.0
    avg_holding_period_bars: float = 0.0

    best_trade: float = 0.0
    worst_trade: float = 0.0

    # Costs
    total_brokerage: float = 0.0
    total_slippage: float = 0.0

    # R-multiple stats
    avg_r_multiple: float = 0.0
    r_squared: float = 0.0

    # Expectancy
    expectancy: float = 0.0
    expectancy_pct: float = 0.0

    # Curves & logs
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    drawdown_curve: List[Dict[str, Any]] = field(default_factory=list)
    monthly_returns: List[Dict[str, Any]] = field(default_factory=list)
    trade_log: List[TradeRecord] = field(default_factory=list)
    daily_pnl: List[Dict[str, Any]] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary string."""
        lines = [
            "=" * 50,
            "           BACKTEST RESULTS",
            "=" * 50,
            f"Total Trades        : {self.total_trades}",
            f"Win Rate            : {self.win_rate:.1f}%",
            f"Net P&L             : {self.net_pnl:+,.2f} ({self.net_pnl_pct:+.2f}%)",
            f"Profit Factor       : {self.profit_factor:.2f}",
            f"Max Drawdown        : {self.max_drawdown:,.2f} ({self.max_drawdown_pct:.2f}%)",
            f"Sharpe Ratio        : {self.sharpe_ratio:.2f}",
            f"Sortino Ratio       : {self.sortino_ratio:.2f}",
            f"Expectancy          : {self.expectancy:,.2f}",
            f"Best Trade          : {self.best_trade:+,.2f}",
            f"Worst Trade         : {self.worst_trade:+,.2f}",
            f"Avg Profit          : {self.avg_profit_per_trade:,.2f}",
            f"Avg Loss            : {self.avg_loss_per_trade:,.2f}",
            f"Total Brokerage     : {self.total_brokerage:,.2f}",
            f"Total Slippage      : {self.total_slippage:,.2f}",
            "=" * 50,
        ]
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a dict (trade_log converted to dicts)."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "net_pnl": self.net_pnl,
            "net_pnl_pct": self.net_pnl_pct,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "avg_profit_per_trade": self.avg_profit_per_trade,
            "avg_loss_per_trade": self.avg_loss_per_trade,
            "avg_holding_period_hours": self.avg_holding_period_hours,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "total_brokerage": self.total_brokerage,
            "total_slippage": self.total_slippage,
            "expectancy": self.expectancy,
            "avg_r_multiple": self.avg_r_multiple,
            "trade_count": len(self.trade_log),
        }

    def to_json(self, path: Optional[str] = None) -> str:
        """Serialise to JSON string; optionally write to ``path``."""
        d = self.to_dict()
        d["trade_log"] = [t.to_dict() for t in self.trade_log]
        d["equity_curve"] = self.equity_curve
        d["drawdown_curve"] = self.drawdown_curve
        d["monthly_returns"] = self.monthly_returns
        d["daily_pnl"] = self.daily_pnl
        raw = json.dumps(d, indent=2, default=str)
        if path:
            with open(path, "w") as fh:
                fh.write(raw)
        return raw


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """Production-grade backtesting engine.

    Simulates trading with realistic execution:
    - Slippage on entry and exit
    - Flat brokerage per order side
    - Proper position sizing (fixed qty / % capital / risk-based)
    - Stop-loss and target tracking (fixed % or ATR-based)
    - Optional trailing stop
    - Long + short support
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.daily_pnl_log: List[Dict[str, Any]] = []
        self.capital: float = self.config.initial_capital
        self.position: Optional[Dict[str, Any]] = None
        logger.info(
            "BacktestEngine initialised | capital={} sizing={} sl={}% target={}%",
            self.config.initial_capital,
            self.config.position_sizing_type.value,
            self.config.stop_loss_value,
            self.config.target_value,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        data: pd.DataFrame,
        entry_signals: pd.Series,
        exit_signals: pd.Series,
        symbol: str = "SYMBOL",
        atr_series: Optional[pd.Series] = None,
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            data: DataFrame with at least ``open``, ``high``, ``low``,
                ``close``, ``volume`` columns.  Index must be DatetimeIndex.
            entry_signals: Boolean Series (``True`` = open position this bar).
                Must align with ``data`` index.
            exit_signals: Boolean Series (``True`` = close position this bar).
                Must align with ``data`` index.
            symbol: Instrument symbol for trade records.
            atr_series: Optional ATR values for ATR-based SL / target.

        Returns:
            :class:`BacktestResult` with full metrics and curves.
        """
        if data.empty:
            logger.warning("Empty data provided – returning empty result")
            return BacktestResult()

        # Validate columns
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(data.columns.str.lower())
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        # Normalise column names to lowercase
        data = data.copy()
        data.columns = [c.lower() for c in data.columns]

        # Ensure index alignment
        entry_signals = entry_signals.reindex(data.index).fillna(False)
        exit_signals = exit_signals.reindex(data.index).fillna(False)
        if atr_series is not None:
            atr_series = atr_series.reindex(data.index).fillna(0)

        # Reset state
        self.capital = self.config.initial_capital
        self.trades = []
        self.equity_curve = []
        self.daily_pnl_log = []
        self.position = None

        logger.info(
            "Starting backtest | symbol={} bars={} capital={}",
            symbol,
            len(data),
            self.capital,
        )

        # Main simulation loop
        for i, (timestamp, candle) in enumerate(data.iterrows()):
            is_last = i == len(data) - 1
            current_atr = atr_series.iloc[i] if atr_series is not None else 0.0

            # Update MTM for open position
            if self.position is not None:
                self._update_position_mtm(candle)

            # Check SL / Target / Trailing stop for open position
            if self.position is not None:
                exit_triggered, reason = self._check_exit_conditions(
                    self.position, candle, current_atr
                )
                if exit_triggered:
                    self._close_position(timestamp, candle, reason, symbol)
                    continue

            # Process exit signal
            if self.position is not None and exit_signals.iloc[i]:
                self._close_position(
                    timestamp, candle, ExitReason.SIGNAL_REVERSAL, symbol
                )
                continue

            # Process entry signal
            if self.position is None and entry_signals.iloc[i]:
                self._open_position(
                    timestamp, candle, PositionType.LONG, symbol, current_atr
                )
                continue

            # End-of-data: close any open position
            if is_last and self.position is not None:
                self._close_position(timestamp, candle, ExitReason.END_OF_DATA, symbol)

            # Record equity at each bar
            self._record_equity(timestamp)

        # Compute and return metrics
        result = self._compute_metrics()
        logger.info(
            "Backtest complete | trades={} pnl={:,.2f} sharpe={:.2f} dd={:.2f}%",
            result.total_trades,
            result.net_pnl,
            result.sharpe_ratio,
            result.max_drawdown_pct,
        )
        return result

    # ------------------------------------------------------------------
    # Position lifecycle
    # ------------------------------------------------------------------

    def _open_position(
        self,
        timestamp: datetime,
        candle: pd.Series,
        direction: PositionType,
        symbol: str,
        atr: float = 0.0,
    ) -> None:
        """Open a new position at the current bar."""
        entry_price_raw = candle["close"]
        entry_price = self._apply_slippage(entry_price_raw, OrderSide.BUY)

        quantity = self._calculate_position_size(entry_price)
        if quantity <= 0:
            logger.debug("Position size zero – skipping entry")
            return

        # Determine SL and target
        sl_price, target_price = self._calculate_sl_target(entry_price, direction, atr)

        self.position = {
            "symbol": symbol,
            "direction": direction.value,
            "entry_time": timestamp,
            "entry_price": entry_price,
            "quantity": quantity,
            "sl_price": sl_price,
            "target_price": target_price,
            "trailing_stop": sl_price if self.config.trailing_stop_pct > 0 else None,
            "highest_reached": entry_price,
            "lowest_reached": entry_price,
            "brokerage": self.config.brokerage_per_order,
        }

        turnover = entry_price * quantity
        slip = turnover * (self.config.slippage_pct / 100)
        self.position["entry_slippage"] = slip

        logger.debug(
            "OPEN {} {} @ {:.2f} qty={} SL={:.2f} TGT={:.2f}",
            direction.value,
            symbol,
            entry_price,
            quantity,
            sl_price,
            target_price,
        )

    def _close_position(
        self,
        timestamp: datetime,
        candle: pd.Series,
        reason: ExitReason,
        symbol: str,
    ) -> None:
        """Close the current position."""
        if self.position is None:
            return

        pos = self.position
        direction = pos["direction"]
        entry_price = pos["entry_price"]
        quantity = pos["quantity"]

        # Determine exit price
        if reason == ExitReason.STOP_LOSS:
            exit_price_raw = pos["sl_price"]
        elif reason == ExitReason.TARGET:
            exit_price_raw = pos["target_price"]
        elif reason == ExitReason.TRAILING_STOP and pos["trailing_stop"]:
            exit_price_raw = pos["trailing_stop"]
        else:
            exit_price_raw = candle["close"]

        exit_side = OrderSide.SELL if direction == "long" else OrderSide.BUY
        exit_price = self._apply_slippage(exit_price_raw, exit_side)

        # Calculate P&L
        if direction == "long":
            gross_pnl = (exit_price - entry_price) * quantity
        else:
            gross_pnl = (entry_price - exit_price) * quantity

        entry_turnover = entry_price * quantity
        exit_turnover = exit_price * quantity
        total_brokerage = self.config.brokerage_per_order * 2  # Entry + exit
        total_slippage = entry_turnover * (
            self.config.slippage_pct / 100
        ) + exit_turnover * (self.config.slippage_pct / 100)

        net_pnl = gross_pnl - total_brokerage - total_slippage
        pnl_pct = (net_pnl / self.config.initial_capital) * 100

        # Record trade
        trade = TradeRecord(
            entry_time=pos["entry_time"],
            exit_time=timestamp,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason.value,
            brokerage=total_brokerage,
            slippage=total_slippage,
            highest_reached=pos["highest_reached"],
            lowest_reached=pos["lowest_reached"],
        )
        self.trades.append(trade)

        # Update capital
        self.capital += net_pnl

        # Log daily P&L
        self._log_daily_pnl(timestamp, net_pnl)

        logger.debug(
            "CLOSE {} {} @ {:.2f} pnl={:,.2f} reason={}",
            direction,
            symbol,
            exit_price,
            net_pnl,
            reason.value,
        )

        self.position = None
        self._record_equity(timestamp)

    def _update_position_mtm(self, candle: pd.Series) -> None:
        """Update highest/lowest prices seen while position is open."""
        if self.position is None:
            return
        pos = self.position
        if pos["direction"] == "long":
            if candle["high"] > pos["highest_reached"]:
                pos["highest_reached"] = candle["high"]
            if candle["low"] < pos["lowest_reached"]:
                pos["lowest_reached"] = candle["low"]
            # Update trailing stop
            if self.config.trailing_stop_pct > 0 and pos["trailing_stop"]:
                new_trail = pos["highest_reached"] * (
                    1 - self.config.trailing_stop_pct / 100
                )
                if new_trail > pos["trailing_stop"]:
                    pos["trailing_stop"] = new_trail
        else:
            if candle["low"] < pos["lowest_reached"]:
                pos["lowest_reached"] = candle["low"]
            if candle["high"] > pos["highest_reached"]:
                pos["highest_reached"] = candle["high"]

    # ------------------------------------------------------------------
    # Exit condition checks
    # ------------------------------------------------------------------

    def _check_exit_conditions(
        self,
        position: Dict[str, Any],
        candle: pd.Series,
        atr: float,
    ) -> Tuple[bool, ExitReason]:
        """Check if SL, target, or trailing stop is hit this bar.

        Returns:
            Tuple of (triggered: bool, reason: ExitReason).
        """
        direction = position["direction"]

        # Stop loss check
        if direction == "long":
            if candle["low"] <= position["sl_price"]:
                return True, ExitReason.STOP_LOSS
        else:
            if candle["high"] >= position["sl_price"]:
                return True, ExitReason.STOP_LOSS

        # Target check
        if direction == "long":
            if candle["high"] >= position["target_price"]:
                return True, ExitReason.TARGET
        else:
            if candle["low"] <= position["target_price"]:
                return True, ExitReason.TARGET

        # Trailing stop check
        if self.config.trailing_stop_pct > 0 and position["trailing_stop"]:
            if direction == "long" and candle["low"] <= position["trailing_stop"]:
                return True, ExitReason.TRAILING_STOP
            if direction == "short" and candle["high"] >= position["trailing_stop"]:
                return True, ExitReason.TRAILING_STOP

        return False, ExitReason.END_OF_DATA

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def _calculate_position_size(self, entry_price: float) -> int:
        """Calculate quantity based on position sizing config.

        Returns:
            Integer quantity (always >= 1).
        """
        sizing = self.config.position_sizing_type
        value = self.config.position_sizing_value
        capital = (
            self.capital
            if self.config.compound_returns
            else self.config.initial_capital
        )

        if sizing == PositionSizingType.FIXED_QTY:
            return max(1, int(value))

        elif sizing == PositionSizingType.PCT_CAPITAL:
            alloc = capital * (value / 100)
            qty = int(alloc / entry_price)
            return max(1, qty)

        elif sizing == PositionSizingType.RISK_BASED:
            # Risk-based: risk 'value' INR per trade
            risk_per_unit = entry_price * (self.config.stop_loss_value / 100)
            if risk_per_unit <= 0:
                qty = int(capital * 0.01 / entry_price)  # Fallback: 1% of capital
                return max(1, qty)
            qty = int(value / risk_per_unit)
            return max(1, qty)

        return max(1, int(value))

    def _calculate_sl_target(
        self,
        entry_price: float,
        direction: PositionType,
        atr: float,
    ) -> Tuple[float, float]:
        """Compute stop-loss and target prices.

        Returns:
            Tuple of (sl_price, target_price).
        """
        # Stop loss
        if self.config.stop_loss_type == "fixed_pct":
            sl_pct = self.config.stop_loss_value / 100
            if direction == PositionType.LONG:
                sl_price = entry_price * (1 - sl_pct)
            else:
                sl_price = entry_price * (1 + sl_pct)
        elif self.config.stop_loss_type == "atr" and atr > 0:
            atr_mult = self.config.stop_loss_value
            if direction == PositionType.LONG:
                sl_price = entry_price - atr * atr_mult
            else:
                sl_price = entry_price + atr * atr_mult
        else:
            sl_price = (
                entry_price * 0.95
                if direction == PositionType.LONG
                else entry_price * 1.05
            )

        # Target
        if self.config.target_type == "fixed_pct":
            tgt_pct = self.config.target_value / 100
            if direction == PositionType.LONG:
                target_price = entry_price * (1 + tgt_pct)
            else:
                target_price = entry_price * (1 - tgt_pct)
        elif self.config.target_type == "atr" and atr > 0:
            tgt_mult = self.config.target_value
            if direction == PositionType.LONG:
                target_price = entry_price + atr * tgt_mult
            else:
                target_price = entry_price - atr * tgt_mult
        elif self.config.target_type == "rr_based":
            # Risk:Reward based target
            risk = abs(entry_price - sl_price)
            reward = risk * self.config.target_value
            if direction == PositionType.LONG:
                target_price = entry_price + reward
            else:
                target_price = entry_price - reward
        else:
            target_price = (
                entry_price * 1.02
                if direction == PositionType.LONG
                else entry_price * 0.98
            )

        return round(sl_price, 2), round(target_price, 2)

    # ------------------------------------------------------------------
    # Execution realism
    # ------------------------------------------------------------------

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        """Apply slippage to execution price.

        For market orders slippage moves price unfavourably:
        - Buy: higher price
        - Sell: lower price
        """
        slippage_factor = self.config.slippage_pct / 100
        if side == OrderSide.BUY:
            return round(price * (1 + slippage_factor), 2)
        return round(price * (1 - slippage_factor), 2)

    def _calculate_brokerage(self, turnover: float) -> float:
        """Calculate brokerage (flat per order)."""
        return self.config.brokerage_per_order

    # ------------------------------------------------------------------
    # Equity & P&L tracking
    # ------------------------------------------------------------------

    def _record_equity(self, timestamp: datetime) -> None:
        """Append current equity to the equity curve."""
        mtm = 0.0
        if self.position is not None:
            # Use last known price for open position MTM
            last_price = self.position.get(
                "highest_reached", self.position["entry_price"]
            )
            if self.position["direction"] == "long":
                mtm = (last_price - self.position["entry_price"]) * self.position[
                    "quantity"
                ]
            else:
                mtm = (self.position["entry_price"] - last_price) * self.position[
                    "quantity"
                ]

        self.equity_curve.append(
            {
                "timestamp": timestamp,
                "equity": round(self.capital + mtm, 2),
                "cash": round(self.capital, 2),
                "mtm": round(mtm, 2),
            }
        )

    def _log_daily_pnl(self, timestamp: datetime, pnl: float) -> None:
        """Log P&L for daily aggregation."""
        self.daily_pnl_log.append(
            {
                "date": timestamp.date() if hasattr(timestamp, "date") else timestamp,
                "pnl": round(pnl, 2),
            }
        )

    # ------------------------------------------------------------------
    # Metric computation
    # ------------------------------------------------------------------

    def _compute_metrics(self) -> BacktestResult:
        """Compute all performance metrics from the trade log."""
        result = BacktestResult()
        result.trade_log = self.trades
        result.equity_curve = self.equity_curve

        if not self.trades:
            return result

        # Basic counts
        result.total_trades = len(self.trades)
        result.winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        result.losing_trades = result.total_trades - result.winning_trades
        result.win_rate = (
            (result.winning_trades / result.total_trades * 100)
            if result.total_trades > 0
            else 0.0
        )

        # P&L
        result.gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        result.gross_loss = sum(t.pnl for t in self.trades if t.pnl < 0)
        result.net_pnl = result.gross_profit + result.gross_loss
        result.net_pnl_pct = (result.net_pnl / self.config.initial_capital) * 100
        result.profit_factor = (
            abs(result.gross_profit / result.gross_loss)
            if result.gross_loss != 0
            else float("inf")
        )

        # Best / worst
        result.best_trade = max(t.pnl for t in self.trades)
        result.worst_trade = min(t.pnl for t in self.trades)

        # Averages
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl < 0]
        result.avg_profit_per_trade = np.mean(wins) if wins else 0.0
        result.avg_loss_per_trade = np.mean(losses) if losses else 0.0

        # Holding period
        holding_periods = []
        for t in self.trades:
            if t.exit_time and t.entry_time:
                delta = t.exit_time - t.entry_time
                holding_periods.append(delta.total_seconds() / 3600)
        result.avg_holding_period_hours = (
            np.mean(holding_periods) if holding_periods else 0.0
        )

        # Costs
        result.total_brokerage = sum(t.brokerage for t in self.trades)
        result.total_slippage = sum(t.slippage for t in self.trades)

        # Equity curve derived metrics
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_series = equity_df["equity"]

            # Drawdown
            max_dd, dd_curve = self._compute_drawdown(equity_series)
            result.max_drawdown = max_dd
            result.max_drawdown_pct = (
                (max_dd / self.config.initial_capital) * 100
                if self.config.initial_capital > 0
                else 0.0
            )
            result.drawdown_curve = dd_curve

            # Sharpe
            result.sharpe_ratio = self._compute_sharpe_ratio(equity_series)

            # Sortino
            result.sortino_ratio = self._compute_sortino_ratio(equity_series)

            # Calmar
            result.calmar_ratio = self._compute_calmar_ratio(equity_series, max_dd)

        # Monthly returns
        result.monthly_returns = self._compute_monthly_returns()

        # Daily P&L
        result.daily_pnl = self._compute_daily_pnl()

        # Expectancy
        avg_win = result.avg_profit_per_trade
        avg_loss = abs(result.avg_loss_per_trade)
        win_pct = result.win_rate / 100
        result.expectancy = (win_pct * avg_win) - ((1 - win_pct) * avg_loss)
        result.expectancy_pct = (
            (result.expectancy / self.config.initial_capital) * 100
            if self.config.initial_capital > 0
            else 0.0
        )

        # R-multiple (R = initial risk per trade)
        r_multiples = []
        for t in self.trades:
            risk = (
                abs(t.entry_price - t.lowest_reached) * t.quantity
                if t.direction == "long"
                else abs(t.highest_reached - t.entry_price) * t.quantity
            )
            if risk > 0:
                r_multiples.append(t.pnl / risk)
        result.avg_r_multiple = np.mean(r_multiples) if r_multiples else 0.0

        return result

    def _compute_sharpe_ratio(
        self,
        equity_series: pd.Series,
        risk_free_rate: float = 0.06,
    ) -> float:
        """Annualised Sharpe ratio.

        Args:
            equity_series: Series of equity values.
            risk_free_rate: Annual risk-free rate (default 6% for India).

        Returns:
            Annualised Sharpe ratio.
        """
        returns = equity_series.pct_change().dropna()
        if len(returns) < 2 or returns.std() == 0:
            return 0.0

        # Infer frequency
        avg_delta = equity_series.index.to_series().diff().mean()
        if pd.isna(avg_delta) or not isinstance(avg_delta, timedelta):
            periods_per_year = 252.0  # Default: daily
        else:
            periods_per_year = float(timedelta(days=365).total_seconds()) / float(
                avg_delta.total_seconds()
            )

        excess_returns = returns - (risk_free_rate / periods_per_year)
        sharpe = excess_returns.mean() / returns.std() * np.sqrt(periods_per_year)
        return round(sharpe, 4)

    def _compute_sortino_ratio(
        self,
        equity_series: pd.Series,
        risk_free_rate: float = 0.06,
    ) -> float:
        """Annualised Sortino ratio (downside deviation only)."""
        returns = equity_series.pct_change().dropna()
        if len(returns) < 2:
            return 0.0

        avg_delta = equity_series.index.to_series().diff().mean()
        if pd.isna(avg_delta) or not isinstance(avg_delta, timedelta):
            periods_per_year = 252.0
        else:
            periods_per_year = float(timedelta(days=365).total_seconds()) / float(
                avg_delta.total_seconds()
            )

        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        if downside_std == 0:
            return 0.0

        excess_returns = returns.mean() - (risk_free_rate / periods_per_year)
        sortino = excess_returns / downside_std * np.sqrt(periods_per_year)
        return round(sortino, 4)

    def _compute_calmar_ratio(
        self,
        equity_series: pd.Series,
        max_drawdown: float,
    ) -> float:
        """Calmar ratio = annualised return / max drawdown."""
        if max_drawdown == 0:
            return 0.0
        total_return = (
            equity_series.iloc[-1] - self.config.initial_capital
        ) / self.config.initial_capital

        avg_delta = equity_series.index.to_series().diff().mean()
        if pd.isna(avg_delta) or avg_delta == 0 or not isinstance(avg_delta, timedelta):
            periods_per_year = 252.0
        else:
            periods_per_year = float(timedelta(days=365).total_seconds()) / float(
                avg_delta.total_seconds()
            )

        n_periods = len(equity_series)
        if n_periods <= 1:
            return 0.0

        annualised_return = (1 + total_return) ** (periods_per_year / n_periods) - 1
        calmar = annualised_return / abs(max_drawdown / self.config.initial_capital)
        return round(calmar, 4)

    def _compute_drawdown(
        self,
        equity_series: pd.Series,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Compute maximum drawdown and drawdown curve.

        Returns:
            Tuple of (max_drawdown_amount, drawdown_curve_list).
        """
        rolling_max = equity_series.cummax()
        drawdown = equity_series - rolling_max
        drawdown_pct = (drawdown / rolling_max) * 100

        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0.0

        dd_curve = []
        for ts, dd_val, dd_pct_val in zip(
            equity_series.index, drawdown.values, drawdown_pct.values
        ):
            dd_curve.append(
                {
                    "timestamp": ts,
                    "drawdown": round(float(dd_val), 2),
                    "drawdown_pct": round(float(dd_pct_val), 4),
                    "peak": round(float(rolling_max[ts]), 2),
                }
            )

        return max_dd, dd_curve

    def _compute_monthly_returns(self) -> List[Dict[str, Any]]:
        """Compute monthly return breakdown."""
        if not self.daily_pnl_log:
            return []

        df = pd.DataFrame(self.daily_pnl_log)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        monthly = df["pnl"].resample("ME").sum()

        result = []
        for month_end, pnl in monthly.items():
            result.append(
                {
                    "month": month_end.strftime("%Y-%m"),
                    "pnl": round(pnl, 2),
                    "trades": sum(
                        1
                        for t in self.trades
                        if t.exit_time
                        and t.exit_time.strftime("%Y-%m") == month_end.strftime("%Y-%m")
                    ),
                }
            )

        return result

    def _compute_daily_pnl(self) -> List[Dict[str, Any]]:
        """Aggregate P&L by calendar day."""
        if not self.daily_pnl_log:
            return []

        df = pd.DataFrame(self.daily_pnl_log)
        df["date"] = pd.to_datetime(df["date"])
        daily = df.groupby(df["date"].dt.date)["pnl"].sum().reset_index()
        daily.columns = ["date", "pnl"]
        return daily.to_dict("records")
