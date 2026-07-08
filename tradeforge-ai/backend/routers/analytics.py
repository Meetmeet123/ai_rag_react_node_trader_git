"""
Analytics API Routes

- GET /dashboard -- Aggregated trading KPIs, daily P&L, strategy performance, and recent trades
- GET /trades   -- Paginated trade list with filters
- GET /export   -- Export trades as a CSV download
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from loguru import logger

from database.models import Strategy, Trade
from routers.auth import get_current_user_optional, UserDocument

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class KpiResponse(BaseModel):
    """High-level key performance indicators."""

    net_pnl: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    avg_profit_per_trade: float
    avg_loss_per_trade: float
    profit_factor: float


class DailyPnlItem(BaseModel):
    """P&L aggregated by calendar date."""

    date: str
    pnl: float
    cumulative: float


class StrategyPerformanceItem(BaseModel):
    """Per-strategy performance summary."""

    strategy_id: str
    name: str
    trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    net_pnl: float
    avg_profit: float
    avg_loss: float
    profit_factor: float


class RecentTradeItem(BaseModel):
    """Recent trade summary for the dashboard."""

    id: str
    symbol: str
    strategy_name: str
    side: str
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    pnl: Optional[float]
    pnl_pct: Optional[float]
    entry_time: str
    exit_time: Optional[str]
    status: str


class DashboardResponse(BaseModel):
    """Combined analytics dashboard payload."""

    kpis: KpiResponse
    daily_pnl: List[DailyPnlItem]
    strategy_performance: List[StrategyPerformanceItem]
    recent_trades: List[RecentTradeItem]


class TradeListItem(BaseModel):
    """Single trade in the paginated trade list."""

    id: str
    symbol: str
    strategy_id: Optional[str]
    strategy_name: Optional[str]
    direction: str
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    pnl: Optional[float]
    pnl_pct: Optional[float]
    entry_time: str
    exit_time: Optional[str]
    broker: Optional[str]
    is_paper: bool
    status: str


class TradeListResponse(BaseModel):
    """Paginated trade list response."""

    trades: List[TradeListItem]
    total: int


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


def _trade_status(trade: Trade) -> str:
    """Derive a textual status for a trade."""
    return "closed" if trade.pnl is not None else "open"


def _trade_date(trade: Trade) -> date:
    """Best-effort calendar date for a trade."""
    ts = trade.exit_time or trade.entry_time
    return ts.date() if ts else trade.created_at.date()


def _closed_trades(trades: List[Trade]) -> List[Trade]:
    """Return only trades that have an associated P&L."""
    return [t for t in trades if t.pnl is not None]


def _compute_kpis(closed: List[Trade]) -> KpiResponse:
    """Compute aggregate KPIs from a list of closed trades."""
    total = len(closed)
    if total == 0:
        return KpiResponse(
            net_pnl=0.0,
            total_trades=0,
            win_rate=0.0,
            max_drawdown=0.0,
            avg_profit_per_trade=0.0,
            avg_loss_per_trade=0.0,
            profit_factor=0.0,
        )

    wins = [t for t in closed if t.pnl and t.pnl > 0]
    losses = [t for t in closed if t.pnl and t.pnl < 0]

    gross_profit = sum(t.pnl for t in wins) if wins else 0.0
    gross_loss = sum(t.pnl for t in losses) if losses else 0.0
    net_pnl = gross_profit + gross_loss

    win_rate = len(wins) / total

    # Max drawdown from cumulative P&L series sorted by trade date.
    sorted_trades = sorted(
        closed, key=lambda t: t.exit_time or t.entry_time or datetime.min
    )
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted_trades:
        cumulative += t.pnl or 0.0
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_dd:
            max_dd = drawdown

    avg_profit = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else 0.0

    return KpiResponse(
        net_pnl=round(net_pnl, 4),
        total_trades=total,
        win_rate=round(win_rate, 4),
        max_drawdown=round(max_dd, 4),
        avg_profit_per_trade=round(avg_profit, 4),
        avg_loss_per_trade=round(avg_loss, 4),
        profit_factor=round(profit_factor, 4),
    )


def _compute_daily_pnl(closed: List[Trade]) -> List[DailyPnlItem]:
    """Aggregate closed P&L by calendar date and compute cumulative values."""
    daily: Dict[date, float] = defaultdict(float)
    for t in closed:
        daily[_trade_date(t)] += t.pnl or 0.0

    items: List[DailyPnlItem] = []
    cumulative = 0.0
    for d in sorted(daily):
        cumulative += daily[d]
        items.append(
            DailyPnlItem(
                date=d.isoformat(),
                pnl=round(daily[d], 4),
                cumulative=round(cumulative, 4),
            )
        )
    return items


def _compute_strategy_performance(
    closed: List[Trade], strategy_names: Dict[str, str]
) -> List[StrategyPerformanceItem]:
    """Group closed trades by strategy and compute per-strategy metrics."""
    groups: Dict[str, List[Trade]] = defaultdict(list)
    for t in closed:
        sid = str(t.strategy_id) if t.strategy_id else "unassigned"
        groups[sid].append(t)

    items: List[StrategyPerformanceItem] = []
    for sid in sorted(groups):
        trades = groups[sid]
        wins = [t for t in trades if t.pnl and t.pnl > 0]
        losses = [t for t in trades if t.pnl and t.pnl < 0]

        gross_profit = sum(t.pnl for t in wins) if wins else 0.0
        gross_loss = sum(t.pnl for t in losses) if losses else 0.0
        net_pnl = gross_profit + gross_loss

        avg_profit = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0
        profit_factor = gross_profit / abs(gross_loss) if gross_loss != 0 else 0.0

        items.append(
            StrategyPerformanceItem(
                strategy_id=sid,
                name=strategy_names.get(sid, "Unknown"),
                trades=len(trades),
                winning_trades=len(wins),
                losing_trades=len(losses),
                win_rate=round(len(wins) / len(trades), 4) if trades else 0.0,
                net_pnl=round(net_pnl, 4),
                avg_profit=round(avg_profit, 4),
                avg_loss=round(avg_loss, 4),
                profit_factor=round(profit_factor, 4),
            )
        )
    return items


def _trade_to_recent_item(
    trade: Trade, strategy_names: Dict[str, str]
) -> RecentTradeItem:
    """Convert a Trade document to a dashboard recent-trade item."""
    sid = str(trade.strategy_id) if trade.strategy_id else "unassigned"
    return RecentTradeItem(
        id=str(trade.id),
        symbol=trade.symbol,
        strategy_name=strategy_names.get(sid, "Unknown"),
        side=trade.direction.value if trade.direction else "",
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        pnl=trade.pnl,
        pnl_pct=trade.pnl_pct,
        entry_time=trade.entry_time.isoformat() if trade.entry_time else "",
        exit_time=trade.exit_time.isoformat() if trade.exit_time else None,
        status=_trade_status(trade),
    )


def _trade_to_list_item(trade: Trade, strategy_names: Dict[str, str]) -> TradeListItem:
    """Convert a Trade document to a paginated list item."""
    sid = str(trade.strategy_id) if trade.strategy_id else None
    return TradeListItem(
        id=str(trade.id),
        symbol=trade.symbol,
        strategy_id=sid,
        strategy_name=strategy_names.get(sid, "Unknown") if sid else "Unassigned",
        direction=trade.direction.value if trade.direction else "",
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        pnl=trade.pnl,
        pnl_pct=trade.pnl_pct,
        entry_time=trade.entry_time.isoformat() if trade.entry_time else "",
        exit_time=trade.exit_time.isoformat() if trade.exit_time else None,
        broker=trade.broker.value if trade.broker else None,
        is_paper=trade.is_paper,
        status=_trade_status(trade),
    )


def _build_trade_query(
    current_user: Optional[UserDocument],
    symbol: Optional[str] = None,
    strategy_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
):
    """Build a Beanie query for trades with the standard filters."""
    query = Trade.find()

    if current_user is not None:
        query = query.find(Trade.user_id == current_user.id)

    if symbol:
        query = query.find(Trade.symbol == symbol.upper())

    if strategy_id:
        query = query.find(Trade.strategy_id == _object_id(strategy_id))

    if from_date:
        query = query.find(Trade.entry_time >= from_date)

    if to_date:
        query = query.find(Trade.entry_time <= to_date)

    return query


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Trading dashboard analytics",
    description="Aggregate KPIs, daily P&L, strategy performance, and recent trades.",
)
async def get_dashboard(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> DashboardResponse:
    """Return the full analytics dashboard for the current user (or all trades when unauthenticated)."""
    try:
        trades = (
            await _build_trade_query(current_user).sort(-Trade.entry_time).to_list()
        )
        closed = _closed_trades(trades)

        # Strategy name lookup for the groups we need.
        strategy_ids = {str(t.strategy_id) for t in trades if t.strategy_id} | {
            str(t.strategy_id) for t in closed if t.strategy_id
        }
        strategies = (
            await Strategy.find(
                {"_id": {"$in": [PydanticObjectId(sid) for sid in strategy_ids]}}
            ).to_list()
            if strategy_ids
            else []
        )
        strategy_names = {str(s.id): s.name for s in strategies}

        kpis = _compute_kpis(closed)
        daily_pnl = _compute_daily_pnl(closed)
        strategy_performance = _compute_strategy_performance(closed, strategy_names)
        recent_trades = [_trade_to_recent_item(t, strategy_names) for t in trades[:10]]

        logger.info(
            "Analytics dashboard served user={} trades={} closed={}",
            current_user.id if current_user else "anonymous",
            len(trades),
            len(closed),
        )

        return DashboardResponse(
            kpis=kpis,
            daily_pnl=daily_pnl,
            strategy_performance=strategy_performance,
            recent_trades=recent_trades,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to build analytics dashboard: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build analytics dashboard: {exc}",
        )


@router.get(
    "/trades",
    response_model=TradeListResponse,
    summary="List trades",
    description="List trades with optional filters and pagination.",
)
async def list_trades(
    symbol: Optional[str] = None,
    strategy_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> TradeListResponse:
    """Return a paginated list of trades matching the supplied filters."""
    try:
        query = _build_trade_query(
            current_user, symbol, strategy_id, from_date, to_date
        )
        total = await query.count()
        trades = await query.sort(-Trade.entry_time).skip(offset).limit(limit).to_list()

        strategy_ids = {str(t.strategy_id) for t in trades if t.strategy_id}
        strategies = (
            await Strategy.find(
                {"_id": {"$in": [PydanticObjectId(sid) for sid in strategy_ids]}}
            ).to_list()
            if strategy_ids
            else []
        )
        strategy_names = {str(s.id): s.name for s in strategies}

        return TradeListResponse(
            trades=[_trade_to_list_item(t, strategy_names) for t in trades],
            total=total,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list trades: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list trades: {exc}",
        )


@router.get(
    "/export",
    summary="Export trades as CSV",
    description="Download all trades matching the supplied filters as a CSV file.",
)
async def export_trades(
    request: Request,
    symbol: Optional[str] = None,
    strategy_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Response:
    """Export trades as a CSV download."""
    try:
        query = _build_trade_query(
            current_user, symbol, strategy_id, from_date, to_date
        )
        trades = await query.sort(-Trade.entry_time).to_list()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "symbol",
                "strategy_id",
                "direction",
                "entry_price",
                "exit_price",
                "quantity",
                "entry_time",
                "exit_time",
                "pnl",
                "pnl_pct",
                "broker",
                "is_paper",
                "status",
            ]
        )
        for t in trades:
            writer.writerow(
                [
                    str(t.id),
                    t.symbol,
                    str(t.strategy_id) if t.strategy_id else "",
                    t.direction.value if t.direction else "",
                    t.entry_price,
                    t.exit_price if t.exit_price is not None else "",
                    t.quantity,
                    t.entry_time.isoformat() if t.entry_time else "",
                    t.exit_time.isoformat() if t.exit_time else "",
                    t.pnl if t.pnl is not None else "",
                    t.pnl_pct if t.pnl_pct is not None else "",
                    t.broker.value if t.broker else "",
                    t.is_paper,
                    _trade_status(t),
                ]
            )

        csv_bytes = output.getvalue().encode("utf-8")
        filename = "trades.csv"
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to export trades: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export trades: {exc}",
        )
