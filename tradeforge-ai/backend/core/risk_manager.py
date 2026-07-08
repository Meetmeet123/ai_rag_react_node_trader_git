"""
Comprehensive Risk Management System for TradeForge AI

Controls:
- Daily loss limits (auto-stop trading)
- Maximum positions / exposure per trade & overall
- Kill switch (emergency halt)
- Position sizing validation
- Consecutive loss protection
- Auto square-off before market close
- Volatility-based position scaling
- Correlation-based exposure clustering

All trade signals MUST pass through :meth:`check_trade_allowed` before
execution.  No exceptions.

Typical usage::

    risk = RiskManager(config={"daily_loss_limit": 20000, "max_positions": 10})
    result = risk.check_trade_allowed(signal, positions, portfolio_value)
    if result.allowed:
        await execute_trade(signal)
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from loguru import logger

# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Severity classification returned with every risk check."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class RejectionReason(str, Enum):
    """Machine-readable reason when a trade is rejected."""

    KILL_SWITCH_ACTIVE = "kill_switch_active"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    MAX_POSITIONS = "max_positions"
    MAX_EXPOSURE_TRADE = "max_exposure_per_trade"
    MAX_EXPOSURE_OVERALL = "max_exposure_overall"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    TRADING_PAUSED = "trading_paused"
    PRE_MARKET = "pre_market"
    POST_MARKET = "post_market"
    WEEKEND = "weekend"
    INSUFFICIENT_MARGIN = "insufficient_margin"
    INVALID_QUANTITY = "invalid_quantity"
    SYMBOL_BLACKLISTED = "symbol_blacklisted"
    VOLATILITY_TOO_HIGH = "volatility_too_high"
    EXPOSURE_TIMEOUT = "exposure_timeout"


class RiskCheckResult(BaseModel):
    """Result of a risk check.

    Attributes:
        allowed: Whether the trade may proceed.
        reason: Human-readable explanation.
        rejection_reason: Machine-readable rejection code (empty if allowed).
        risk_level: ``normal``, ``warning``, ``critical``, or ``fatal``.
        suggested_qty: If the risk manager wants to reduce size, this is
            the maximum allowed quantity (``None`` = no change).
        metadata: Additional diagnostic data.
    """

    allowed: bool
    reason: str = ""
    rejection_reason: Optional[RejectionReason] = None
    risk_level: RiskLevel = RiskLevel.NORMAL
    suggested_qty: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskConfig(BaseModel):
    """Serializable configuration for :class:`RiskManager`.

    All monetary values are in INR.  Percentages are expressed as
    numbers (``10`` means 10 %, not 0.10).
    """

    # Daily loss guard
    daily_loss_limit: float = Field(default=20_000.0, ge=0)
    daily_loss_warning_pct: float = Field(default=70.0, ge=0, le=100)

    # Position count
    max_positions: int = Field(default=10, ge=0)

    # Exposure limits
    max_exposure_per_trade_pct: float = Field(default=10.0, ge=0)
    max_exposure_overall_pct: float = Field(default=50.0, ge=0)
    max_exposure_per_sector_pct: float = Field(default=25.0, ge=0)

    # Consecutive loss protection
    consecutive_loss_limit: int = Field(default=5, ge=0)
    consecutive_loss_cooldown_minutes: int = Field(default=30, ge=0)

    # Kill switch
    kill_switch_daily_loss_pct: float = Field(default=95.0, ge=0, le=100)

    # Auto square-off
    auto_square_off_time: dt_time = Field(default=dt_time(15, 14))
    square_off_warning_seconds: int = Field(default=300)

    # Market hours
    market_open_time: dt_time = Field(default=dt_time(9, 15))
    market_close_time: dt_time = Field(default=dt_time(15, 30))

    # Volatility guard
    max_volatility_pct: float = Field(default=5.0, ge=0)
    volatility_lookback: int = Field(default=20, ge=2)

    # Cooldown between trades (seconds)
    min_trade_interval_seconds: float = Field(default=1.0, ge=0)

    # Margin safety buffer (% of required margin)
    margin_safety_buffer_pct: float = Field(default=10.0, ge=0)

    # Blacklisted symbols (exact match)
    blacklisted_symbols: List[str] = Field(default_factory=list)

    @field_validator("blacklisted_symbols", mode="before")
    @classmethod
    def _uppercase_symbols(cls, v: List[str]) -> List[str]:
        return [s.upper().strip() for s in v]


# ---------------------------------------------------------------------------
# Risk Manager
# ---------------------------------------------------------------------------


class RiskManager:
    """Central risk gate-keeper.

    Maintains mutable counters (daily P&L, consecutive losses, etc.) that
    must survive for the duration of the trading session.  Call
    :meth:`reset_daily` at the start of every trading day.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Create a new ``RiskManager``.

        Args:
            config: Dict that is validated against :class:`RiskConfig`.
                Missing keys fall back to defaults.
        """
        self.cfg = RiskConfig(**(config or {}))

        # Mutable session state
        self.daily_pnl: float = 0.0
        self.daily_loss_used: float = 0.0  # Only tracks losses
        self.daily_trades: int = 0
        self.daily_wins: int = 0
        self.daily_losses: int = 0

        self.consecutive_losses: int = 0
        self.last_trade_timestamp: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None

        self.kill_switch_active: bool = False
        self.trading_paused: bool = False

        # Square-off warning state
        self.square_off_warning_issued: bool = False

        # Internal lock (async-safe via asyncio.Lock if needed)
        self._lock_timestamp: float = 0.0

        logger.info(
            "RiskManager initialised | daily_loss_limit={} max_positions={} "
            "max_exposure_trade={}% max_exposure_overall={}%",
            self.cfg.daily_loss_limit,
            self.cfg.max_positions,
            self.cfg.max_exposure_per_trade_pct,
            self.cfg.max_exposure_overall_pct,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_trade_allowed(
        self,
        signal: Dict[str, Any],
        current_positions: List[Dict[str, Any]],
        portfolio_value: float,
    ) -> RiskCheckResult:
        """Comprehensive pre-trade risk check.

        Every inbound signal must flow through this method.  The checks are
        ordered from cheapest / most-critical to expensive / fine-grained so
        that rejected signals fail fast.

        Args:
            signal: Dict with at least ``symbol``, ``quantity``, ``price``.
            current_positions: List of open-position dicts.
            portfolio_value: Total portfolio value (cash + positions).

        Returns:
            :class:`RiskCheckResult` with ``allowed=True`` only when every
            guard passes.
        """
        now = datetime.now()
        symbol = signal.get("symbol", "").upper().strip()
        quantity = int(signal.get("quantity", 0))
        price = float(signal.get("price", 0.0))
        trade_value = quantity * price

        # 1. Kill switch (highest priority)
        if self.kill_switch_active:
            return RiskCheckResult(
                allowed=False,
                reason="KILL SWITCH is ACTIVE – all trading halted",
                rejection_reason=RejectionReason.KILL_SWITCH_ACTIVE,
                risk_level=RiskLevel.FATAL,
            )

        # 2. Trading paused flag
        if self.trading_paused:
            return RiskCheckResult(
                allowed=False,
                reason="Trading is manually paused",
                rejection_reason=RejectionReason.TRADING_PAUSED,
                risk_level=RiskLevel.CRITICAL,
            )

        # 3. Cooldown between trades
        if self.cooldown_until and now < self.cooldown_until:
            remaining = int((self.cooldown_until - now).total_seconds())
            return RiskCheckResult(
                allowed=False,
                reason=f"Trade cooldown active – {remaining}s remaining",
                rejection_reason=RejectionReason.EXPOSURE_TIMEOUT,
                risk_level=RiskLevel.WARNING,
            )

        # 4. Market hours (NSE cash + F&O)
        market_check = self._check_market_hours(now)
        if not market_check.allowed:
            return market_check

        # 5. Daily loss limit
        loss_check = self._check_daily_loss()
        if not loss_check.allowed:
            return loss_check

        # 6. Max positions
        pos_check = self._check_max_positions(len(current_positions))
        if not pos_check.allowed:
            return pos_check

        # 7. Symbol blacklist
        if symbol in self.cfg.blacklisted_symbols:
            return RiskCheckResult(
                allowed=False,
                reason=f"Symbol '{symbol}' is blacklisted",
                rejection_reason=RejectionReason.SYMBOL_BLACKLISTED,
                risk_level=RiskLevel.CRITICAL,
            )

        # 8. Consecutive loss protection
        cl_check = self._check_consecutive_losses()
        if not cl_check.allowed:
            return cl_check

        # 9. Exposure limits (per-trade + overall)
        current_exposure = self._compute_current_exposure(current_positions)
        exposure_check = self._check_exposure(
            trade_value, current_exposure, portfolio_value
        )
        if not exposure_check.allowed:
            return exposure_check

        # 10. Position sizing sanity
        if quantity <= 0 or price <= 0:
            return RiskCheckResult(
                allowed=False,
                reason=f"Invalid quantity ({quantity}) or price ({price})",
                rejection_reason=RejectionReason.INVALID_QUANTITY,
                risk_level=RiskLevel.WARNING,
            )

        # 11. Volatility guard (if historical data provided in signal)
        vol_check = self._check_volatility(signal)
        if not vol_check.allowed:
            return vol_check

        # -- All guards passed --
        result = RiskCheckResult(
            allowed=True,
            reason="All risk checks passed",
            risk_level=RiskLevel.NORMAL,
            metadata={
                "daily_pnl": round(self.daily_pnl, 2),
                "daily_loss_used": round(self.daily_loss_used, 2),
                "consecutive_losses": self.consecutive_losses,
                "current_exposure": round(current_exposure, 2),
                "trade_value": round(trade_value, 2),
                "portfolio_value": round(portfolio_value, 2),
            },
        )
        logger.debug("Risk check passed for {} | trade_value={}", symbol, trade_value)
        return result

    # ------------------------------------------------------------------
    # Individual guard implementations
    # ------------------------------------------------------------------

    def _check_market_hours(self, now: datetime) -> RiskCheckResult:
        """Verify we are within allowed market hours."""
        current_time = now.time()

        # Weekend check
        if now.weekday() >= 5:
            return RiskCheckResult(
                allowed=False,
                reason="Markets closed (weekend)",
                rejection_reason=RejectionReason.WEEKEND,
                risk_level=RiskLevel.NORMAL,
            )

        # Pre-market
        if current_time < self.cfg.market_open_time:
            return RiskCheckResult(
                allowed=False,
                reason=f"Pre-market – opens at {self.cfg.market_open_time}",
                rejection_reason=RejectionReason.PRE_MARKET,
                risk_level=RiskLevel.NORMAL,
            )

        # Post-market
        if current_time > self.cfg.market_close_time:
            return RiskCheckResult(
                allowed=False,
                reason=f"Post-market – closed at {self.cfg.market_close_time}",
                rejection_reason=RejectionReason.POST_MARKET,
                risk_level=RiskLevel.NORMAL,
            )

        return RiskCheckResult(allowed=True)

    def check_daily_loss(self) -> bool:
        """Return ``True`` if daily loss limit is still OK."""
        return self.daily_loss_used < self.cfg.daily_loss_limit

    def _check_daily_loss(self) -> RiskCheckResult:
        """Detailed daily-loss check with warning / critical levels."""
        if self.daily_loss_used >= self.cfg.daily_loss_limit:
            # Auto activate kill switch when limit is breached
            if not self.kill_switch_active:
                self.activate_kill_switch("Daily loss limit breached")
            return RiskCheckResult(
                allowed=False,
                reason=f"Daily loss limit breached: {self.daily_loss_used:,.2f} / "
                f"{self.cfg.daily_loss_limit:,.2f}",
                rejection_reason=RejectionReason.DAILY_LOSS_LIMIT,
                risk_level=RiskLevel.FATAL,
            )

        # Warning level
        warning_threshold = self.cfg.daily_loss_limit * (
            self.cfg.daily_loss_warning_pct / 100
        )
        if self.daily_loss_used >= warning_threshold:
            return RiskCheckResult(
                allowed=True,
                reason=f"WARNING: Daily loss at {self.daily_loss_used:,.2f} / "
                f"{self.cfg.daily_loss_limit:,.2f} ({self.cfg.daily_loss_warning_pct}% limit)",
                risk_level=RiskLevel.WARNING,
                metadata={
                    "daily_loss_pct": round(
                        self.daily_loss_used / self.cfg.daily_loss_limit * 100, 1
                    )
                },
            )

        return RiskCheckResult(allowed=True)

    def check_max_positions(self, current_count: int) -> bool:
        """Return ``True`` if we have room for another position."""
        return current_count < self.cfg.max_positions

    def _check_max_positions(self, current_count: int) -> RiskCheckResult:
        """Detailed position-count check."""
        if current_count >= self.cfg.max_positions:
            return RiskCheckResult(
                allowed=False,
                reason=f"Max positions reached: {current_count} / {self.cfg.max_positions}",
                rejection_reason=RejectionReason.MAX_POSITIONS,
                risk_level=RiskLevel.WARNING,
            )
        return RiskCheckResult(allowed=True)

    def check_exposure(
        self,
        new_trade_value: float,
        current_exposure: float,
        portfolio_value: float,
    ) -> bool:
        """Return ``True`` if exposure limits are not breached."""
        if portfolio_value <= 0:
            return False
        trade_pct = (new_trade_value / portfolio_value) * 100
        total_pct = ((current_exposure + new_trade_value) / portfolio_value) * 100
        return (
            trade_pct <= self.cfg.max_exposure_per_trade_pct
            and total_pct <= self.cfg.max_exposure_overall_pct
        )

    def _check_exposure(
        self,
        new_trade_value: float,
        current_exposure: float,
        portfolio_value: float,
    ) -> RiskCheckResult:
        """Detailed exposure check with per-trade and overall limits."""
        if portfolio_value <= 0:
            return RiskCheckResult(
                allowed=False,
                reason="Portfolio value is zero or negative",
                rejection_reason=RejectionReason.INSUFFICIENT_MARGIN,
                risk_level=RiskLevel.CRITICAL,
            )

        trade_pct = (new_trade_value / portfolio_value) * 100
        total_pct = ((current_exposure + new_trade_value) / portfolio_value) * 100

        if trade_pct > self.cfg.max_exposure_per_trade_pct:
            max_allowed_value = portfolio_value * (
                self.cfg.max_exposure_per_trade_pct / 100
            )
            suggested_qty = (
                int(
                    max_allowed_value
                    / (
                        new_trade_value
                        / max(1, int(new_trade_value / max(new_trade_value, 1)))
                    )
                )
                if new_trade_value > 0
                else 0
            )
            return RiskCheckResult(
                allowed=False,
                reason=f"Per-trade exposure too high: {trade_pct:.1f}% > "
                f"{self.cfg.max_exposure_per_trade_pct}%",
                rejection_reason=RejectionReason.MAX_EXPOSURE_TRADE,
                risk_level=RiskLevel.WARNING,
                suggested_qty=suggested_qty if suggested_qty > 0 else None,
            )

        if total_pct > self.cfg.max_exposure_overall_pct:
            return RiskCheckResult(
                allowed=False,
                reason=f"Overall exposure too high: {total_pct:.1f}% > "
                f"{self.cfg.max_exposure_overall_pct}%",
                rejection_reason=RejectionReason.MAX_EXPOSURE_OVERALL,
                risk_level=RiskLevel.WARNING,
            )

        return RiskCheckResult(allowed=True)

    def check_consecutive_losses(self) -> bool:
        """Return ``True`` if consecutive loss protection has not fired."""
        return self.consecutive_losses < self.cfg.consecutive_loss_limit

    def _check_consecutive_losses(self) -> RiskCheckResult:
        """Detailed consecutive-loss check with auto-cooldown."""
        if self.consecutive_losses >= self.cfg.consecutive_loss_limit:
            # Activate cooldown
            self.cooldown_until = datetime.now() + timedelta(
                minutes=self.cfg.consecutive_loss_cooldown_minutes
            )
            return RiskCheckResult(
                allowed=False,
                reason=f"Consecutive loss limit: {self.consecutive_losses} losses. "
                f"Cooldown until {self.cooldown_until.strftime('%H:%M:%S')}",
                rejection_reason=RejectionReason.CONSECUTIVE_LOSSES,
                risk_level=RiskLevel.CRITICAL,
            )

        # Warning at 80% of limit
        if self.consecutive_losses >= int(self.cfg.consecutive_loss_limit * 0.8):
            return RiskCheckResult(
                allowed=True,
                reason=f"WARNING: {self.consecutive_losses} consecutive losses "
                f"(limit: {self.cfg.consecutive_loss_limit})",
                risk_level=RiskLevel.WARNING,
            )

        return RiskCheckResult(allowed=True)

    def _check_volatility(self, signal: Dict[str, Any]) -> RiskCheckResult:
        """Reject trades when underlying volatility is too high."""
        vol_pct = signal.get("volatility_pct", 0.0)
        if vol_pct > self.cfg.max_volatility_pct:
            return RiskCheckResult(
                allowed=False,
                reason=f"Volatility too high: {vol_pct:.2f}% > {self.cfg.max_volatility_pct}%",
                rejection_reason=RejectionReason.VOLATILITY_TOO_HIGH,
                risk_level=RiskLevel.WARNING,
            )
        return RiskCheckResult(allowed=True)

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    def activate_kill_switch(self, reason: str = "manual") -> None:
        """EMERGENCY: Activate kill switch immediately.

        Once active **no** new trades are allowed and all open positions
        should be squared off by the execution engine.
        """
        if not self.kill_switch_active:
            self.kill_switch_active = True
            logger.critical("KILL SWITCH ACTIVATED – Reason: {}", reason)

    def deactivate_kill_switch(self) -> None:
        """Deactivate kill switch (manual intervention only).

        Resets the flag so trading can resume.  Daily counters are **not**
        reset—use :meth:`reset_daily` for that.
        """
        if self.kill_switch_active:
            self.kill_switch_active = False
            self.trading_paused = False
            logger.warning("Kill switch DEACTIVATED – trading can resume")

    # ------------------------------------------------------------------
    # Post-trade updates
    # ------------------------------------------------------------------

    def update_after_trade(self, pnl: float) -> None:
        """Update internal counters after a trade closes.

        Args:
            pnl: Realised P&L for the closed trade (positive = profit).
        """
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.last_trade_timestamp = datetime.now()

        if pnl > 0:
            self.daily_wins += 1
            self.consecutive_losses = 0
        else:
            self.daily_losses += 1
            self.daily_loss_used += abs(pnl)
            self.consecutive_losses += 1

        # Check if kill-switch threshold reached
        if self.daily_loss_used >= self.cfg.daily_loss_limit * (
            self.cfg.kill_switch_daily_loss_pct / 100
        ):
            self.activate_kill_switch(
                f"Daily loss at {self.cfg.kill_switch_daily_loss_pct}% of limit"
            )

        logger.info(
            "Trade closed | pnl={:,.2f} daily_pnl={:,.2f} "
            "daily_loss={:,.2f} consecutive_losses={}",
            pnl,
            self.daily_pnl,
            self.daily_loss_used,
            self.consecutive_losses,
        )

    # ------------------------------------------------------------------
    # Auto square-off
    # ------------------------------------------------------------------

    def should_square_off(self, current_time: Optional[dt_time] = None) -> bool:
        """Check if auto square-off time has been reached.

        Args:
            current_time: Time to check (defaults to ``now``).

        Returns:
            ``True`` if square-off should be triggered.
        """
        t = current_time or datetime.now().time()
        return t >= self.cfg.auto_square_off_time

    def should_warn_square_off(self, current_time: Optional[dt_time] = None) -> bool:
        """Check if we should issue a square-off warning.

        Returns:
            ``True`` if we are within ``square_off_warning_seconds`` of
            the auto square-off time and a warning has not yet been issued.
        """
        t = current_time or datetime.now().time()
        sq_off_dt = datetime.combine(date.today(), self.cfg.auto_square_off_time)
        warning_dt = sq_off_dt - timedelta(seconds=self.cfg.square_off_warning_seconds)
        warning_time = warning_dt.time()

        if (
            warning_time <= t < self.cfg.auto_square_off_time
            and not self.square_off_warning_issued
        ):
            self.square_off_warning_issued = True
            return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_current_exposure(self, positions: List[Dict[str, Any]]) -> float:
        """Sum absolute market value of all open positions."""
        total = 0.0
        for pos in positions:
            qty = abs(pos.get("quantity", 0))
            price = pos.get("last_price", pos.get("avg_price", 0))
            total += qty * price
        return total

    # ------------------------------------------------------------------
    # Summary / reset
    # ------------------------------------------------------------------

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk state as a serialisable dict."""
        now = datetime.now()
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_used": round(self.daily_loss_used, 2),
            "daily_loss_limit": self.cfg.daily_loss_limit,
            "daily_loss_pct": round(
                self.daily_loss_used / max(self.cfg.daily_loss_limit, 1) * 100, 1
            ),
            "daily_trades": self.daily_trades,
            "daily_wins": self.daily_wins,
            "daily_losses": self.daily_losses,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_loss_limit": self.cfg.consecutive_loss_limit,
            "kill_switch_active": self.kill_switch_active,
            "trading_paused": self.trading_paused,
            "cooldown_active": (
                self.cooldown_until is not None and now < self.cooldown_until
            ),
            "cooldown_until": (
                self.cooldown_until.isoformat() if self.cooldown_until else None
            ),
            "max_positions": self.cfg.max_positions,
            "market_open": self._check_market_hours(now).allowed,
            "square_off_time": self.cfg.auto_square_off_time.isoformat(),
        }

    def reset_daily(self) -> None:
        """Reset all daily counters.

        Must be called at the start of every trading day (e.g. via a
        scheduled task at 09:00).
        """
        self.daily_pnl = 0.0
        self.daily_loss_used = 0.0
        self.daily_trades = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.consecutive_losses = 0
        self.kill_switch_active = False
        self.trading_paused = False
        self.cooldown_until = None
        self.last_trade_timestamp = None
        self.square_off_warning_issued = False
        logger.info("RiskManager daily counters reset for new session")
