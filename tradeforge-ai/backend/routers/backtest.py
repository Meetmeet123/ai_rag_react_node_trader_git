"""
Backtest API Routes

- POST /run -- Run backtest for a strategy
- GET / -- List backtest runs
- GET /{id} -- Get backtest results
- GET /{id}/equity-curve -- Get equity curve data for charting
- GET /{id}/trade-log -- Get detailed trade log
- DELETE /{id} -- Delete a backtest run
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session

from database.connection import get_db_session
from database.models import BacktestRun, Strategy

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """Request body for running a backtest."""

    strategy_id: int = Field(..., description="ID of the strategy to backtest")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_capital: float = Field(default=1_000_000.0, gt=0, description="Starting capital in INR")
    brokerage_per_order: float = Field(default=20.0, ge=0, description="Brokerage per order side")
    slippage_pct: float = Field(default=0.05, ge=0, description="Slippage as percentage of price")
    position_sizing_type: str = Field(default="fixed_qty", description="fixed_qty | pct_capital | risk_based")
    position_sizing_value: float = Field(default=1.0, gt=0, description="Position sizing value")
    stop_loss_type: str = Field(default="fixed_pct", description="fixed_pct | atr | none")
    stop_loss_value: float = Field(default=1.0, ge=0, description="Stop loss value")
    target_type: str = Field(default="fixed_pct", description="fixed_pct | atr | rr_based | none")
    target_value: float = Field(default=2.0, ge=0, description="Target value")
    allow_short: bool = Field(default=True, description="Allow short selling")


class BacktestSummaryResponse(BaseModel):
    """Summary of a backtest run (for list view)."""

    id: int
    strategy_id: Optional[int]
    strategy_name: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    initial_capital: float
    status: str
    total_trades: Optional[int]
    win_rate: Optional[float]
    net_pnl: Optional[float]
    net_pnl_pct: Optional[float]
    sharpe_ratio: Optional[float]
    max_drawdown_pct: Optional[float]
    profit_factor: Optional[float]
    created_at: Optional[str]
    completed_at: Optional[str]

    class Config:
        from_attributes = True


class BacktestDetailResponse(BaseModel):
    """Detailed backtest results."""

    id: int
    strategy_id: Optional[int]
    strategy_name: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    initial_capital: float
    status: str
    error_message: Optional[str]

    # Summary metrics
    total_trades: Optional[int]
    winning_trades: Optional[int]
    losing_trades: Optional[int]
    win_rate: Optional[float]
    net_pnl: Optional[float]
    net_pnl_pct: Optional[float]
    gross_profit: Optional[float]
    gross_loss: Optional[float]
    profit_factor: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_pct: Optional[float]
    sharpe_ratio: Optional[float]
    avg_profit_per_trade: Optional[float]
    avg_loss_per_trade: Optional[float]
    avg_holding_period: Optional[float]

    # Curves & logs
    equity_curve: Optional[List[dict]]
    drawdown_curve: Optional[List[dict]]
    monthly_returns: Optional[dict]
    trade_log: Optional[list]

    created_at: Optional[str]
    completed_at: Optional[str]

    class Config:
        from_attributes = True


class BacktestListResponse(BaseModel):
    """Paginated backtest list response."""

    backtests: List[BacktestSummaryResponse]
    total: int
    strategy_id_filter: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _backtest_summary_to_dict(bt: BacktestRun, strategy_name: Optional[str] = None) -> Dict[str, Any]:
    """Convert BacktestRun to summary dict."""
    return {
        "id": bt.id,
        "strategy_id": bt.strategy_id,
        "strategy_name": strategy_name,
        "start_date": bt.start_date.isoformat() if bt.start_date else None,
        "end_date": bt.end_date.isoformat() if bt.end_date else None,
        "initial_capital": bt.initial_capital,
        "status": bt.status,
        "total_trades": bt.total_trades,
        "win_rate": bt.win_rate,
        "net_pnl": bt.net_pnl,
        "net_pnl_pct": bt.net_pnl_pct,
        "sharpe_ratio": bt.sharpe_ratio,
        "max_drawdown_pct": bt.max_drawdown_pct,
        "profit_factor": bt.profit_factor,
        "created_at": bt.created_at.isoformat() if bt.created_at else None,
        "completed_at": bt.completed_at.isoformat() if bt.completed_at else None,
    }


def _backtest_detail_to_dict(bt: BacktestRun, strategy_name: Optional[str] = None) -> Dict[str, Any]:
    """Convert BacktestRun to full detail dict."""
    return {
        "id": bt.id,
        "strategy_id": bt.strategy_id,
        "strategy_name": strategy_name,
        "start_date": bt.start_date.isoformat() if bt.start_date else None,
        "end_date": bt.end_date.isoformat() if bt.end_date else None,
        "initial_capital": bt.initial_capital,
        "status": bt.status,
        "error_message": bt.error_message,
        # Metrics
        "total_trades": bt.total_trades,
        "winning_trades": bt.winning_trades,
        "losing_trades": bt.losing_trades,
        "win_rate": bt.win_rate,
        "net_pnl": bt.net_pnl,
        "net_pnl_pct": bt.net_pnl_pct,
        "gross_profit": bt.gross_profit,
        "gross_loss": bt.gross_loss,
        "profit_factor": bt.profit_factor,
        "max_drawdown": bt.max_drawdown,
        "max_drawdown_pct": bt.max_drawdown_pct,
        "sharpe_ratio": bt.sharpe_ratio,
        "avg_profit_per_trade": bt.avg_profit_per_trade,
        "avg_loss_per_trade": bt.avg_loss_per_trade,
        "avg_holding_period": bt.avg_holding_period,
        # Curves & logs
        "equity_curve": bt.equity_curve,
        "drawdown_curve": bt.drawdown_curve,
        "monthly_returns": bt.monthly_returns,
        "trade_log": bt.trade_log,
        # Timestamps
        "created_at": bt.created_at.isoformat() if bt.created_at else None,
        "completed_at": bt.completed_at.isoformat() if bt.completed_at else None,
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=BacktestDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run backtest",
    description="Run a backtest for a strategy. Returns immediately with a 'running' status; results are populated asynchronously.",
)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
) -> BacktestDetailResponse:
    """
    Run backtest for a strategy.

    The backtest is executed asynchronously. The endpoint returns immediately
    with a 'running' status. Poll GET /{id} to check completion.
    """
    # Validate strategy exists
    strategy = db.query(Strategy).filter(Strategy.id == request.strategy_id).first()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {request.strategy_id} not found",
        )

    # Create backtest record
    backtest_run = BacktestRun(
        strategy_id=request.strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        status="running",
    )
    db.add(backtest_run)
    db.commit()
    db.refresh(backtest_run)

    logger.info(
        "Backtest started id={} strategy_id={} capital={}",
        backtest_run.id,
        request.strategy_id,
        request.initial_capital,
    )

    # NOTE: The actual backtest execution would be done in a background task
    # using the BacktestEngine. For now, we create the record and return it.
    # The background task would update the record with results.

    return BacktestDetailResponse(**_backtest_detail_to_dict(backtest_run, strategy.name))


@router.get(
    "/",
    response_model=BacktestListResponse,
    summary="List backtest runs",
    description="List all backtest runs with optional strategy filter.",
)
async def list_backtests(
    strategy_id: Optional[int] = None,
    db: Session = Depends(get_db_session),
) -> BacktestListResponse:
    """List backtest runs, optionally filtered by strategy ID."""
    query = db.query(BacktestRun)

    if strategy_id:
        query = query.filter(BacktestRun.strategy_id == strategy_id)

    backtests = query.order_by(BacktestRun.created_at.desc()).all()

    # Fetch strategy names in one query
    strategy_ids = {bt.strategy_id for bt in backtests if bt.strategy_id}
    strategies = (
        db.query(Strategy.id, Strategy.name).filter(Strategy.id.in_(strategy_ids)).all()
        if strategy_ids else []
    )
    strategy_names = {s.id: s.name for s in strategies}

    backtest_dicts = [
        BacktestSummaryResponse(**_backtest_summary_to_dict(bt, strategy_names.get(bt.strategy_id)))
        for bt in backtests
    ]

    return BacktestListResponse(
        backtests=backtest_dicts,
        total=len(backtest_dicts),
        strategy_id_filter=strategy_id,
    )


@router.get(
    "/{backtest_id}",
    response_model=BacktestDetailResponse,
    summary="Get backtest results",
    description="Get detailed results of a specific backtest run.",
)
async def get_backtest(
    backtest_id: int,
    db: Session = Depends(get_db_session),
) -> BacktestDetailResponse:
    """Get backtest results by ID."""
    backtest = db.query(BacktestRun).filter(BacktestRun.id == backtest_id).first()
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    strategy_name = None
    if backtest.strategy_id:
        strategy = db.query(Strategy).filter(Strategy.id == backtest.strategy_id).first()
        if strategy:
            strategy_name = strategy.name

    return BacktestDetailResponse(**_backtest_detail_to_dict(backtest, strategy_name))


@router.get(
    "/{backtest_id}/equity-curve",
    summary="Get equity curve",
    description="Get equity curve data points for charting.",
)
async def get_equity_curve(
    backtest_id: int,
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Get equity curve data points for chart rendering."""
    backtest = db.query(BacktestRun).filter(BacktestRun.id == backtest_id).first()
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    return {
        "backtest_id": backtest_id,
        "equity_curve": backtest.equity_curve or [],
        "drawdown_curve": backtest.drawdown_curve or [],
        "initial_capital": backtest.initial_capital,
        "data_points": len(backtest.equity_curve) if backtest.equity_curve else 0,
    }


@router.get(
    "/{backtest_id}/trade-log",
    summary="Get trade log",
    description="Get detailed trade log from a backtest run.",
)
async def get_trade_log(
    backtest_id: int,
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Get detailed trade log from a backtest run."""
    backtest = db.query(BacktestRun).filter(BacktestRun.id == backtest_id).first()
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    return {
        "backtest_id": backtest_id,
        "trades": backtest.trade_log or [],
        "total_trades": len(backtest.trade_log) if backtest.trade_log else 0,
        "winning_trades": backtest.winning_trades,
        "losing_trades": backtest.losing_trades,
    }


@router.delete(
    "/{backtest_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete backtest run",
    description="Delete a backtest run by ID.",
)
async def delete_backtest(
    backtest_id: int,
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Delete a backtest run."""
    backtest = db.query(BacktestRun).filter(BacktestRun.id == backtest_id).first()
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    db.delete(backtest)
    db.commit()

    logger.info("Deleted backtest id={}", backtest_id)

    return {"success": True, "message": f"Backtest {backtest_id} deleted"}
