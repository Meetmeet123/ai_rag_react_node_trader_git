"""
Trade Execution API Routes

- POST /signal -- Submit trade signal
- GET /positions -- Get current positions
- GET /portfolio -- Get portfolio summary
- POST /close-position -- Close a specific position
- POST /close-all -- Close all positions (kill switch)
- GET /orders -- Get order history
- GET /health -- Execution engine health check
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from core.execution_engine import ExecutionEngine, TradeSignal, SignalDirection
from core.risk_manager import RiskManager

router = APIRouter()

# Module-level singletons (injected from main.py)
_engine: Optional[ExecutionEngine] = None
_risk: Optional[RiskManager] = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SignalRequest(BaseModel):
    """Request body for submitting a trade signal."""

    symbol: str = Field(..., min_length=1, description="Trading symbol")
    direction: str = Field(..., description="buy or sell")
    quantity: int = Field(..., gt=0, description="Number of shares/lots")
    strategy_id: str = Field(default="", description="Originating strategy ID")
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Model confidence"
    )
    price: float = Field(
        default=0.0, ge=0.0, description="Expected price (0 for market)"
    )
    order_type: str = Field(default="market", description="market | limit | sl")
    product_type: str = Field(default="mis", description="mis | cnc | nrml")


class SignalResponse(BaseModel):
    """Response for a submitted trade signal."""

    success: bool
    order_id: Optional[str] = None
    message: str
    risk_result: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None


class PositionResponse(BaseModel):
    """Response model for a single position."""

    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    entry_time: Optional[str]
    strategy_id: int


class PortfolioResponse(BaseModel):
    """Portfolio summary response."""

    mode: str
    halted: bool
    halt_reason: str
    position_count: int
    positions: Dict[str, Any]
    total_unrealized_pnl: float
    total_realized_pnl: float
    daily_stats: Dict[str, Any]
    total_signals_processed: int
    total_trades_executed: int
    risk_summary: Dict[str, Any]


class ClosePositionRequest(BaseModel):
    """Request body for closing a position."""

    symbol: str = Field(..., description="Symbol of position to close")
    reason: str = Field(default="manual", description="Reason for closing")


class CloseAllResponse(BaseModel):
    """Response for closing all positions."""

    success: bool
    message: str
    closed_count: int
    results: List[Dict[str, Any]]


class ExecutionHealthResponse(BaseModel):
    """Execution engine health status."""

    status: str
    broker_connected: bool
    halted: bool
    mode: str
    positions: int
    pending_orders: int
    daily_stats: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_engine() -> ExecutionEngine:
    """Get the global execution engine instance (injected from main.py)."""
    global _engine
    if _engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Execution engine not initialized",
        )
    return _engine


def _get_risk() -> RiskManager:
    """Get the global risk manager instance (injected from main.py)."""
    global _risk
    if _risk is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Risk manager not initialized",
        )
    return _risk


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/signal",
    response_model=SignalResponse,
    summary="Submit trade signal",
    description="Submit a trade signal for execution. Passes through risk checks before routing to broker.",
)
async def submit_signal(request: SignalRequest) -> SignalResponse:
    """Submit a trade signal for execution."""
    try:
        engine = _get_engine()

        # Validate direction
        direction = request.direction.lower()
        if direction not in ("buy", "sell"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid direction '{direction}'. Must be 'buy' or 'sell'.",
            )

        signal = TradeSignal(
            symbol=request.symbol.upper().strip(),
            direction=SignalDirection(direction),
            quantity=request.quantity,
            price=request.price,
            confidence=request.confidence,
            strategy_id=request.strategy_id,
        )

        result = await engine.on_signal(signal)

        return SignalResponse(
            success=result.get("success", False),
            order_id=result.get("order_id"),
            message=result.get("message", ""),
            risk_result=result.get("risk_result"),
            latency_ms=result.get("latency_ms"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Signal submission failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signal submission failed: {exc}",
        )


@router.get(
    "/positions",
    response_model=Dict[str, Any],
    summary="Get current positions",
    description="Get all currently open positions with unrealized P&L.",
)
async def get_positions() -> Dict[str, Any]:
    """Get current open positions."""
    try:
        engine = _get_engine()
        positions = {
            sym: {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_price": round(p.avg_price, 2),
                "current_price": round(p.current_price, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "realized_pnl": round(p.realized_pnl, 2),
                "entry_time": p.entry_time.isoformat() if p.entry_time else None,
                "strategy_id": p.strategy_id,
            }
            for sym, p in engine.active_positions.items()
        }

        return {
            "count": len(positions),
            "positions": positions,
            "total_unrealized": round(
                sum(p["unrealized_pnl"] for p in positions.values()), 2
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get positions: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get positions: {exc}",
        )


@router.get(
    "/portfolio",
    response_model=PortfolioResponse,
    summary="Get portfolio summary",
    description="Get complete portfolio summary including positions, P&L, daily stats, and risk summary.",
)
async def get_portfolio() -> PortfolioResponse:
    """Get portfolio summary."""
    try:
        engine = _get_engine()
        summary = engine.get_portfolio_summary()

        return PortfolioResponse(**summary)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get portfolio: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio: {exc}",
        )


@router.post(
    "/close-position",
    response_model=SignalResponse,
    summary="Close a position",
    description="Close a specific open position by symbol.",
)
async def close_position(request: ClosePositionRequest) -> SignalResponse:
    """Close a specific position."""
    try:
        engine = _get_engine()

        result = await engine.close_position(
            symbol=request.symbol.upper().strip(),
            reason=request.reason,
        )

        return SignalResponse(
            success=getattr(result, "is_complete", False),
            order_id=getattr(result, "order_id", None),
            message=getattr(result, "message", f"Position {request.symbol} closed"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to close position: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close position: {exc}",
        )


@router.post(
    "/close-all",
    response_model=CloseAllResponse,
    summary="Close all positions (kill switch)",
    description="EMERGENCY: Close ALL open positions immediately. This is the kill switch.",
)
async def close_all_positions() -> CloseAllResponse:
    """EMERGENCY: Close all positions (kill switch)."""
    try:
        engine = _get_engine()

        results = await engine.close_all_positions(reason="kill_switch")

        closed_count = sum(1 for r in results if getattr(r, "is_complete", False))

        logger.critical(
            "KILL SWITCH activated — {} positions closed",
            closed_count,
        )

        return CloseAllResponse(
            success=True,
            message=f"Kill switch activated — {closed_count} positions closed",
            closed_count=closed_count,
            results=[
                {
                    "order_id": getattr(r, "order_id", ""),
                    "status": getattr(r, "status", "unknown"),
                    "symbol": getattr(r, "symbol", ""),
                }
                for r in results
            ],
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Kill switch failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kill switch failed: {exc}",
        )


@router.get(
    "/signals",
    summary="Get signal history",
    description="Get the history of processed signals (accepted and rejected).",
)
async def get_signals(limit: int = 100) -> Dict[str, Any]:
    """Get signal history."""
    try:
        engine = _get_engine()
        signals = engine.signal_history[-limit:] if engine.signal_history else []
        return {
            "signals": signals,
            "total_signals": len(engine.signal_history),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get signals: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get signals: {exc}",
        )


@router.get(
    "/orders",
    summary="Get order history",
    description="Get the history of executed orders and signals.",
)
async def get_orders(limit: int = 100) -> Dict[str, Any]:
    """Get order history."""
    try:
        engine = _get_engine()

        orders = engine.signal_history[-limit:] if engine.signal_history else []
        trades = engine.trade_history[-limit:] if engine.trade_history else []

        return {
            "signals": orders,
            "trades": trades,
            "total_signals": len(engine.signal_history),
            "total_trades": len(engine.trade_history),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get orders: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders: {exc}",
        )


@router.get(
    "/health",
    response_model=ExecutionHealthResponse,
    summary="Execution engine health check",
    description="Check the health of the execution pipeline.",
)
async def execution_health() -> ExecutionHealthResponse:
    """Get execution engine health status."""
    try:
        engine = _get_engine()

        health = await engine.health_check()

        return ExecutionHealthResponse(**health)

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Execution health check failed: {}", exc)
        return ExecutionHealthResponse(
            status="degraded",
            broker_connected=False,
            halted=True,
            mode="unknown",
            positions=0,
            pending_orders=0,
            daily_stats={},
        )


# ---------------------------------------------------------------------------
# Injection hooks (called from main.py lifespan)
# ---------------------------------------------------------------------------


def set_engine_instance(engine: ExecutionEngine) -> None:
    """Inject the global execution engine from main.py."""
    global _engine
    _engine = engine
    logger.debug("Execution engine injected into execute router")


def set_risk_instance(risk: RiskManager) -> None:
    """Inject the global risk manager from main.py."""
    global _risk
    _risk = risk
    logger.debug("Risk manager injected into execute router")
