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

from datetime import datetime

import pandas as pd
from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from config import settings
from core.backtest_engine import BacktestConfig, BacktestEngine
from core.condition_evaluator import evaluate_conditions
from core.market_data.ingestor import MarketDataIngestor
from core.synthetic_data import generate_ohlcv
from database.models import BacktestRun, Strategy
from routers.auth import get_current_user_optional, UserDocument

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """Request body for running a backtest."""

    strategy_id: str = Field(..., description="ID of the strategy to backtest")
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

    id: str
    strategy_id: Optional[str]
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


class BacktestDetailResponse(BaseModel):
    """Detailed backtest results."""

    id: str
    strategy_id: Optional[str]
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


class BacktestListResponse(BaseModel):
    """Paginated backtest list response."""

    backtests: List[BacktestSummaryResponse]
    total: int
    strategy_id_filter: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _object_id(id_str: str) -> PydanticObjectId:
    """Convert a string to a PydanticObjectId or raise a 400 error."""
    try:
        return PydanticObjectId(id_str)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID format: {id_str}",
        ) from exc


def _backtest_summary_to_dict(bt: BacktestRun, strategy_name: Optional[str] = None) -> Dict[str, Any]:
    """Convert BacktestRun to summary dict."""
    return {
        "id": str(bt.id),
        "strategy_id": str(bt.strategy_id) if bt.strategy_id else None,
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
        "id": str(bt.id),
        "strategy_id": str(bt.strategy_id) if bt.strategy_id else None,
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


async def _execute_backtest(
    backtest_id: str,
    strategy_id: str,
    request: BacktestRequest,
) -> None:
    """Run the backtest engine and persist results to the BacktestRun document."""
    bt = await BacktestRun.get(_object_id(backtest_id))
    strategy = await Strategy.get(_object_id(strategy_id))
    if not bt or not strategy:
        logger.warning("Backtest or strategy missing for execution id={}", backtest_id)
        return

    try:
        ingestor = MarketDataIngestor(data_dir=settings.HISTORICAL_DATA_DIR)
        df = await ingestor.fetch_historical(
            strategy.instrument,
            request.start_date,
            request.end_date,
            timeframe=strategy.timeframe or "1d",
        )
        await ingestor.close()

        if df.empty:
            logger.warning(
                "No market data for {} ({}); falling back to synthetic data",
                strategy.instrument,
                strategy.timeframe,
            )
            df = generate_ohlcv(
                strategy.instrument,
                request.start_date,
                request.end_date,
                timeframe=strategy.timeframe or "1d",
            )

        df = df.set_index("timestamp")
        df.columns = [c.lower() for c in df.columns]

        entry_signals = evaluate_conditions(df, strategy.entry_conditions or [])
        exit_signals = evaluate_conditions(df, strategy.exit_conditions or [])
        if entry_signals is None:
            entry_signals = pd.Series(False, index=df.index)
        if exit_signals is None:
            exit_signals = pd.Series(False, index=df.index)

        atr_series = None
        if strategy.stop_loss_type == "atr" or strategy.target_type == "atr":
            from core.indicators import atr

            atr_series = atr(df["high"], df["low"], df["close"], 14)

        config = BacktestConfig(
            initial_capital=request.initial_capital,
            brokerage_per_order=request.brokerage_per_order,
            slippage_pct=request.slippage_pct,
            position_sizing_type=request.position_sizing_type,
            position_sizing_value=request.position_sizing_value,
            stop_loss_type=request.stop_loss_type,
            stop_loss_value=request.stop_loss_value,
            target_type=request.target_type,
            target_value=request.target_value,
            allow_short=request.allow_short,
            max_positions=1,
        )
        engine = BacktestEngine(config)
        result = engine.run(
            df,
            entry_signals,
            exit_signals,
            symbol=strategy.instrument,
            atr_series=atr_series,
        )

        bt.status = "completed"
        bt.total_trades = result.total_trades
        bt.winning_trades = result.winning_trades
        bt.losing_trades = result.losing_trades
        bt.win_rate = result.win_rate
        bt.net_pnl = result.net_pnl
        bt.net_pnl_pct = result.net_pnl_pct
        bt.gross_profit = result.gross_profit
        bt.gross_loss = result.gross_loss
        bt.profit_factor = result.profit_factor
        bt.max_drawdown = result.max_drawdown
        bt.max_drawdown_pct = result.max_drawdown_pct
        bt.sharpe_ratio = result.sharpe_ratio
        bt.avg_profit_per_trade = result.avg_profit_per_trade
        bt.avg_loss_per_trade = result.avg_loss_per_trade
        bt.avg_holding_period = result.avg_holding_period_hours
        bt.equity_curve = result.equity_curve
        bt.drawdown_curve = result.drawdown_curve
        bt.monthly_returns = {"monthly": result.monthly_returns} if result.monthly_returns else None
        bt.trade_log = [t.to_dict() for t in result.trade_log]
        bt.completed_at = datetime.utcnow()
        await bt.save()

        logger.info(
            "Backtest completed id={} trades={} pnl={:.2f} win_rate={:.1f}%",
            backtest_id,
            result.total_trades,
            result.net_pnl,
            result.win_rate,
        )
    except Exception as exc:
        logger.exception("Backtest execution failed id={}", backtest_id)
        bt.status = "failed"
        bt.error_message = str(exc)
        bt.completed_at = datetime.utcnow()
        await bt.save()


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
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BacktestDetailResponse:
    """
    Run backtest for a strategy.

    The backtest is executed asynchronously. The endpoint returns immediately
    with a 'running' status. Poll GET /{id} to check completion.
    """
    # Validate strategy exists
    strategy = await Strategy.get(_object_id(request.strategy_id))
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {request.strategy_id} not found",
        )

    if current_user is not None and strategy.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Create backtest record
    backtest_run = BacktestRun(
        user_id=current_user.id if current_user else None,
        strategy_id=_object_id(request.strategy_id),
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        status="running",
    )
    await backtest_run.insert()

    logger.info(
        "Backtest started id={} strategy_id={} capital={}",
        backtest_run.id,
        request.strategy_id,
        request.initial_capital,
    )

    background_tasks.add_task(_execute_backtest, str(backtest_run.id), request.strategy_id, request)

    return BacktestDetailResponse(**_backtest_detail_to_dict(backtest_run, strategy.name))


@router.get(
    "/",
    response_model=BacktestListResponse,
    summary="List backtest runs",
    description="List all backtest runs with optional strategy filter.",
)
async def list_backtests(
    strategy_id: Optional[str] = None,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BacktestListResponse:
    """List backtest runs, optionally filtered by strategy ID."""
    query = BacktestRun.find()

    if current_user is not None:
        query = query.find(BacktestRun.user_id == current_user.id)

    if strategy_id:
        query = query.find(BacktestRun.strategy_id == _object_id(strategy_id))

    backtests = await query.sort(-BacktestRun.created_at).to_list()

    # Fetch strategy names
    strategy_ids = {bt.strategy_id for bt in backtests if bt.strategy_id}
    strategies = (
        await Strategy.find({"_id": {"$in": list(strategy_ids)}}).to_list()
        if strategy_ids else []
    )
    strategy_names = {str(s.id): s.name for s in strategies}

    backtest_dicts = [
        BacktestSummaryResponse(**_backtest_summary_to_dict(bt, strategy_names.get(str(bt.strategy_id))))
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
    backtest_id: str,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BacktestDetailResponse:
    """Get backtest results by ID."""
    backtest = await BacktestRun.get(_object_id(backtest_id))
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    if current_user is not None and backtest.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    strategy_name = None
    if backtest.strategy_id:
        strategy = await Strategy.get(backtest.strategy_id)
        if strategy:
            strategy_name = strategy.name

    return BacktestDetailResponse(**_backtest_detail_to_dict(backtest, strategy_name))


@router.get(
    "/{backtest_id}/equity-curve",
    summary="Get equity curve",
    description="Get equity curve data points for charting.",
)
async def get_equity_curve(
    backtest_id: str,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Get equity curve data points for chart rendering."""
    backtest = await BacktestRun.get(_object_id(backtest_id))
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    if current_user is not None and backtest.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

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
    backtest_id: str,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Get detailed trade log from a backtest run."""
    backtest = await BacktestRun.get(_object_id(backtest_id))
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    if current_user is not None and backtest.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

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
    backtest_id: str,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Delete a backtest run."""
    backtest = await BacktestRun.get(_object_id(backtest_id))
    if not backtest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with ID {backtest_id} not found",
        )

    if current_user is not None and backtest.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await backtest.delete()

    logger.info("Deleted backtest id={}", backtest_id)

    return {"success": True, "message": f"Backtest {backtest_id} deleted"}
