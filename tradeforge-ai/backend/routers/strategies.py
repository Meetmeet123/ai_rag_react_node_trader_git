"""
Strategy Management API Routes

- GET / -- List all strategies
- POST / -- Create new strategy
- GET /{id} -- Get strategy details
- PUT /{id} -- Update strategy
- DELETE /{id} -- Delete strategy
- POST /{id}/deploy -- Deploy strategy (paper/live)
- POST /{id}/stop -- Stop strategy
- POST /{id}/duplicate -- Duplicate strategy
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session

from database.connection import get_db_session
from database.models import Strategy, StrategyStatus

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StrategyCreate(BaseModel):
    """Request body for creating a new strategy."""

    name: str = Field(..., min_length=1, max_length=200, description="Strategy name")
    description: str = Field(default="", description="Strategy description")
    instrument: str = Field(..., min_length=1, max_length=50, description="Trading instrument")
    segment: str = Field(default="equity", description="Market segment")
    timeframe: str = Field(default="15m", description="Candle timeframe")
    entry_conditions: List[dict] = Field(default_factory=list, description="Entry conditions")
    exit_conditions: List[dict] = Field(default_factory=list, description="Exit conditions")
    stop_loss: dict = Field(default_factory=dict, description="Stop loss config")
    target: dict = Field(default_factory=dict, description="Target config")
    position_sizing: dict = Field(default_factory=dict, description="Position sizing config")
    definition: Optional[dict] = Field(default=None, description="Full strategy definition JSON")
    nl_prompt: Optional[str] = Field(default=None, description="Original NL prompt (if AI-generated)")


class StrategyResponse(BaseModel):
    """Strategy response model."""

    id: int
    name: str
    description: Optional[str]
    instrument: str
    segment: str
    timeframe: str
    definition: Optional[dict]
    generated_code: Optional[str]
    nl_prompt: Optional[str]
    status: str
    is_ai_generated: bool
    backtest_results: Optional[dict]
    entry_conditions: Optional[dict]
    exit_conditions: Optional[dict]
    stop_loss_type: Optional[str]
    stop_loss_value: Optional[float]
    target_type: Optional[str]
    target_value: Optional[float]
    position_sizing_type: Optional[str]
    position_sizing_value: Optional[float]
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class StrategyListResponse(BaseModel):
    """Paginated strategy list response."""

    strategies: List[StrategyResponse]
    total: int
    status_filter: Optional[str] = None


class DeployRequest(BaseModel):
    """Request body for deploying a strategy."""

    mode: str = Field(default="paper", description="Deployment mode: paper or live")


class StrategyActionResponse(BaseModel):
    """Response for strategy actions (deploy, stop, duplicate)."""

    success: bool
    message: str
    strategy_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strategy_to_dict(strategy: Strategy) -> Dict[str, Any]:
    """Convert a Strategy ORM object to a serialisable dict."""
    return {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description,
        "instrument": strategy.instrument,
        "segment": strategy.segment.value if strategy.segment else "equity",
        "timeframe": strategy.timeframe,
        "definition": strategy.definition,
        "generated_code": strategy.generated_code,
        "nl_prompt": strategy.nl_prompt,
        "status": strategy.status.value if strategy.status else "draft",
        "is_ai_generated": strategy.is_ai_generated,
        "backtest_results": strategy.backtest_results,
        "entry_conditions": strategy.entry_conditions,
        "exit_conditions": strategy.exit_conditions,
        "stop_loss_type": strategy.stop_loss_type,
        "stop_loss_value": strategy.stop_loss_value,
        "target_type": strategy.target_type,
        "target_value": strategy.target_value,
        "position_sizing_type": strategy.position_sizing_type,
        "position_sizing_value": strategy.position_sizing_value,
        "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
        "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=StrategyListResponse,
    summary="List all strategies",
    description="List all strategies with optional status filter.",
)
async def list_strategies(
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
) -> StrategyListResponse:
    """List all strategies with optional filter by status."""
    query = db.query(Strategy)

    if status:
        try:
            status_enum = StrategyStatus(status.lower())
            query = query.filter(Strategy.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{status}'. Valid: {[s.value for s in StrategyStatus]}",
            )

    strategies = query.order_by(Strategy.created_at.desc()).all()
    strategy_dicts = [_strategy_to_dict(s) for s in strategies]

    logger.debug("Listed {} strategies (filter={})", len(strategy_dicts), status)

    return StrategyListResponse(
        strategies=strategy_dicts,
        total=len(strategy_dicts),
        status_filter=status,
    )


@router.post(
    "/",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new strategy",
    description="Create a new trading strategy with the given parameters.",
)
async def create_strategy(
    strategy: StrategyCreate,
    db: Session = Depends(get_db_session),
) -> StrategyResponse:
    """Create a new strategy."""
    try:
        db_strategy = Strategy(
            name=strategy.name,
            description=strategy.description,
            instrument=strategy.instrument.upper(),
            segment=strategy.segment,
            timeframe=strategy.timeframe,
            definition=strategy.definition or {
                "name": strategy.name,
                "instrument": strategy.instrument,
                "segment": strategy.segment,
                "timeframe": strategy.timeframe,
                "entry_conditions": strategy.entry_conditions,
                "exit_conditions": strategy.exit_conditions,
                "stop_loss": strategy.stop_loss,
                "target": strategy.target,
                "position_sizing": strategy.position_sizing,
            },
            entry_conditions=strategy.entry_conditions,
            exit_conditions=strategy.exit_conditions,
            stop_loss_type=strategy.stop_loss.get("type", "fixed_pct"),
            stop_loss_value=float(strategy.stop_loss.get("value", 1.0)),
            target_type=strategy.target.get("type", "fixed_pct"),
            target_value=float(strategy.target.get("value", 2.0)),
            position_sizing_type=strategy.position_sizing.get("type", "fixed_qty"),
            position_sizing_value=float(strategy.position_sizing.get("value", 1.0)),
            status=StrategyStatus.DRAFT,
            is_ai_generated=strategy.nl_prompt is not None,
            nl_prompt=strategy.nl_prompt,
        )

        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)

        logger.info("Created strategy id={} name='{}'", db_strategy.id, db_strategy.name)

        return StrategyResponse(**_strategy_to_dict(db_strategy))

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create strategy: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create strategy: {exc}",
        )


@router.get(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Get strategy details",
    description="Get detailed information about a specific strategy.",
)
async def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db_session),
) -> StrategyResponse:
    """Get strategy details by ID."""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {strategy_id} not found",
        )

    return StrategyResponse(**_strategy_to_dict(strategy))


@router.put(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Update strategy",
    description="Update an existing strategy's parameters.",
)
async def update_strategy(
    strategy_id: int,
    strategy: StrategyCreate,
    db: Session = Depends(get_db_session),
) -> StrategyResponse:
    """Update an existing strategy."""
    db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not db_strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {strategy_id} not found",
        )

    db_strategy.name = strategy.name
    db_strategy.description = strategy.description
    db_strategy.instrument = strategy.instrument.upper()
    db_strategy.segment = strategy.segment
    db_strategy.timeframe = strategy.timeframe
    db_strategy.definition = strategy.definition or db_strategy.definition
    db_strategy.entry_conditions = strategy.entry_conditions
    db_strategy.exit_conditions = strategy.exit_conditions
    db_strategy.stop_loss_type = strategy.stop_loss.get("type", db_strategy.stop_loss_type)
    db_strategy.stop_loss_value = float(strategy.stop_loss.get("value", db_strategy.stop_loss_value or 1.0))
    db_strategy.target_type = strategy.target.get("type", db_strategy.target_type)
    db_strategy.target_value = float(strategy.target.get("value", db_strategy.target_value or 2.0))
    db_strategy.position_sizing_type = strategy.position_sizing.get("type", db_strategy.position_sizing_type)
    db_strategy.position_sizing_value = float(strategy.position_sizing.get("value", db_strategy.position_sizing_value or 1.0))

    db.commit()
    db.refresh(db_strategy)

    logger.info("Updated strategy id={}", strategy_id)

    return StrategyResponse(**_strategy_to_dict(db_strategy))


@router.delete(
    "/{strategy_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete strategy",
    description="Delete a strategy by ID. Associated trades, signals, and backtests are preserved.",
)
async def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    """Delete a strategy by ID."""
    db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not db_strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {strategy_id} not found",
        )

    name = db_strategy.name
    db.delete(db_strategy)
    db.commit()

    logger.info("Deleted strategy id={} name='{}'", strategy_id, name)

    return {"success": True, "message": f"Strategy '{name}' (ID {strategy_id}) deleted"}


@router.post(
    "/{strategy_id}/deploy",
    response_model=StrategyActionResponse,
    summary="Deploy strategy",
    description="Deploy a strategy to paper trading or live trading.",
)
async def deploy_strategy(
    strategy_id: int,
    request: DeployRequest,
    db: Session = Depends(get_db_session),
) -> StrategyActionResponse:
    """Deploy strategy to paper or live trading."""
    db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not db_strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {strategy_id} not found",
        )

    mode = request.mode.lower()
    if mode not in ("paper", "live"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode '{mode}'. Must be 'paper' or 'live'.",
        )

    new_status = StrategyStatus.PAPER if mode == "paper" else StrategyStatus.ACTIVE
    db_strategy.status = new_status
    db.commit()

    logger.info(
        "Deployed strategy id={} to {} mode (status={})",
        strategy_id,
        mode,
        new_status.value,
    )

    return StrategyActionResponse(
        success=True,
        message=f"Strategy '{db_strategy.name}' deployed to {mode} trading",
        strategy_id=strategy_id,
    )


@router.post(
    "/{strategy_id}/stop",
    response_model=StrategyActionResponse,
    summary="Stop strategy",
    description="Stop a deployed strategy and set status back to draft.",
)
async def stop_strategy(
    strategy_id: int,
    db: Session = Depends(get_db_session),
) -> StrategyActionResponse:
    """Stop a deployed strategy."""
    db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not db_strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {strategy_id} not found",
        )

    previous_status = db_strategy.status.value if db_strategy.status else "unknown"
    db_strategy.status = StrategyStatus.DRAFT
    db.commit()

    logger.info(
        "Stopped strategy id={} (previous status={})",
        strategy_id,
        previous_status,
    )

    return StrategyActionResponse(
        success=True,
        message=f"Strategy '{db_strategy.name}' stopped (was {previous_status})",
        strategy_id=strategy_id,
    )


@router.post(
    "/{strategy_id}/duplicate",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate strategy",
    description="Create a copy of an existing strategy with '- Copy' appended to the name.",
)
async def duplicate_strategy(
    strategy_id: int,
    db: Session = Depends(get_db_session),
) -> StrategyResponse:
    """Duplicate a strategy."""
    db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not db_strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy with ID {strategy_id} not found",
        )

    new_strategy = Strategy(
        name=f"{db_strategy.name} - Copy",
        description=db_strategy.description,
        instrument=db_strategy.instrument,
        segment=db_strategy.segment,
        timeframe=db_strategy.timeframe,
        definition=db_strategy.definition,
        generated_code=db_strategy.generated_code,
        nl_prompt=db_strategy.nl_prompt,
        entry_conditions=db_strategy.entry_conditions,
        exit_conditions=db_strategy.exit_conditions,
        stop_loss_type=db_strategy.stop_loss_type,
        stop_loss_value=db_strategy.stop_loss_value,
        target_type=db_strategy.target_type,
        target_value=db_strategy.target_value,
        position_sizing_type=db_strategy.position_sizing_type,
        position_sizing_value=db_strategy.position_sizing_value,
        status=StrategyStatus.DRAFT,
        is_ai_generated=db_strategy.is_ai_generated,
    )

    db.add(new_strategy)
    db.commit()
    db.refresh(new_strategy)

    logger.info(
        "Duplicated strategy id={} -> new id={}",
        strategy_id,
        new_strategy.id,
    )

    return StrategyResponse(**_strategy_to_dict(new_strategy))
