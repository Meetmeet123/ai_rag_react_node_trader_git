"""
Model Management API Routes

- GET / -- List all model versions
- GET /active -- Get active model
- POST /{id}/activate -- Activate a model version
- POST /rollback -- Rollback to previous version
- GET /compare -- Compare two versions
- DELETE /{id} -- Delete a version
- GET /{id} -- Get version details
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from core.model_registry import ModelRegistry, ModelVersionInfo

router = APIRouter()

# Module-level singleton (injected from main.py)
_registry: Optional[ModelRegistry] = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ModelVersionResponse(BaseModel):
    """Response model for a model version."""

    version_id: int
    version_name: str
    description: Optional[str]
    checkpoint_path: str
    training_data_size: Optional[int]
    training_duration_sec: float
    epochs: int
    final_loss: float
    validation_loss: float
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    backtest_pnl: float
    status: str
    is_active: bool
    is_shadow: bool
    triggered_by: str
    artifact_uri: Optional[str]
    created_at: Optional[str]
    completed_at: Optional[str]


class ShadowResponse(BaseModel):
    """Response for setting or promoting a shadow model."""

    success: bool
    message: str
    shadow_version: Optional[int] = None
    active_version: Optional[int] = None


class ModelListResponse(BaseModel):
    """Response model for listing model versions."""

    versions: List[ModelVersionResponse]
    total: int
    active_version_id: Optional[int]
    shadow_version_id: Optional[int]


class ActivateResponse(BaseModel):
    """Response for activating a model version."""

    success: bool
    message: str
    activated_version: Optional[int] = None


class CompareRequest(BaseModel):
    """Request body for comparing two model versions."""

    version_a: int = Field(..., description="Baseline version ID")
    version_b: int = Field(..., description="Challenger version ID")


class CompareResponse(BaseModel):
    """Response for version comparison."""

    version_a_id: int
    version_a_name: str
    version_b_id: int
    version_b_name: str
    v1_metrics: Dict[str, float]
    v2_metrics: Dict[str, float]
    deltas: Dict[str, float]
    composite_score: float
    winner_id: int
    summary: str


class RollbackResponse(BaseModel):
    """Response for model rollback."""

    success: bool
    message: str
    new_active_version: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_registry() -> ModelRegistry:
    """Get the global registry instance (injected from main.py)."""
    global _registry
    if _registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model registry not initialized",
        )
    return _registry


def _version_to_response(v: ModelVersionInfo) -> ModelVersionResponse:
    """Convert ModelVersionInfo to response model."""
    return ModelVersionResponse(
        version_id=v.version_id,
        version_name=v.version_name,
        description=v.description,
        checkpoint_path=v.checkpoint_path,
        training_data_size=v.training_data_size,
        training_duration_sec=v.training_duration_sec,
        epochs=v.epochs,
        final_loss=v.final_loss,
        validation_loss=v.validation_loss,
        accuracy=v.accuracy,
        precision=v.precision,
        recall=v.recall,
        f1_score=v.f1_score,
        backtest_pnl=v.backtest_pnl,
        status=v.status,
        is_active=v.is_active,
        is_shadow=v.is_shadow,
        triggered_by=v.triggered_by,
        artifact_uri=v.artifact_uri,
        created_at=v.created_at.isoformat() if v.created_at else None,
        completed_at=v.completed_at.isoformat() if v.completed_at else None,
    )


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=ModelListResponse,
    summary="List all model versions",
    description="List all model versions sorted by creation date (newest first).",
)
async def list_models(
    status_filter: Optional[str] = None,
) -> ModelListResponse:
    """List all model versions."""
    try:
        registry = _get_registry()
        versions = registry.list_versions(status_filter=status_filter)

        return ModelListResponse(
            versions=[_version_to_response(v) for v in versions],
            total=len(versions),
            active_version_id=registry.active_version_id,
            shadow_version_id=registry.shadow_version_id,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list models: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {exc}",
        )


@router.get(
    "/active",
    response_model=Optional[ModelVersionResponse],
    summary="Get active model",
    description="Get the currently active model version.",
)
async def get_active_model() -> Optional[ModelVersionResponse]:
    """Get currently active model version."""
    try:
        registry = _get_registry()
        active = registry.get_active_version()

        if active is None:
            return None

        return _version_to_response(active)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get active model: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active model: {exc}",
        )


@router.get(
    "/{version_id}",
    response_model=ModelVersionResponse,
    summary="Get version details",
    description="Get detailed information about a specific model version.",
)
async def get_version(version_id: int) -> ModelVersionResponse:
    """Get model version details."""
    try:
        registry = _get_registry()
        version = registry.get_version(version_id)

        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version {version_id} not found",
            )

        return _version_to_response(version)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get version {}: {}", version_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get version: {exc}",
        )


@router.post(
    "/{version_id}/activate",
    response_model=ActivateResponse,
    summary="Activate a model version",
    description="Activate a specific model version for live inference.",
)
async def activate_model(version_id: int) -> ActivateResponse:
    """Activate a model version."""
    try:
        registry = _get_registry()
        version = registry.get_version(version_id)

        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version {version_id} not found",
            )

        result = registry.activate_version(version_id)

        if result:
            logger.info("Activated model version {}", version_id)
            return ActivateResponse(
                success=True,
                message=f"Model version {version_id} ({version.version_name}) activated",
                activated_version=version_id,
            )
        else:
            return ActivateResponse(
                success=False,
                message=f"Failed to activate version {version_id} — status may be archived or failed",
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to activate version {}: {}", version_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate model: {exc}",
        )


@router.post(
    "/rollback",
    response_model=RollbackResponse,
    summary="Rollback model version",
    description="Rollback to the previously active model version.",
)
async def rollback_model() -> RollbackResponse:
    """Rollback to previous active version."""
    try:
        registry = _get_registry()
        result = registry.rollback()

        active = registry.get_active_version()

        if result:
            return RollbackResponse(
                success=True,
                message="Rollback successful",
                new_active_version=active.version_id if active else None,
            )
        else:
            return RollbackResponse(
                success=False,
                message="Rollback failed — no eligible previous version",
            )

    except Exception as exc:
        logger.exception("Rollback failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {exc}",
        )


@router.get(
    "/compare",
    response_model=CompareResponse,
    summary="Compare two model versions",
    description="Compare two model versions across all metrics and determine a winner.",
)
async def compare_models(
    version_a: int,
    version_b: int,
) -> CompareResponse:
    """Compare two model versions."""
    try:
        registry = _get_registry()
        result = registry.compare_versions(version_a, version_b)

        return CompareResponse(**result)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Failed to compare versions: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare versions: {exc}",
        )


@router.get(
    "/shadow",
    response_model=Optional[ModelVersionResponse],
    summary="Get shadow model",
    description="Get the current shadow/challenger model version.",
)
async def get_shadow_model() -> Optional[ModelVersionResponse]:
    """Get currently shadow model version."""
    try:
        registry = _get_registry()
        shadow = registry.get_shadow_version()
        if shadow is None:
            return None
        return _version_to_response(shadow)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get shadow model: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get shadow model: {exc}",
        )


@router.post(
    "/{version_id}/shadow",
    response_model=ShadowResponse,
    summary="Set shadow model",
    description="Mark a model version as the shadow/challenger model.",
)
async def set_shadow_model(version_id: int) -> ShadowResponse:
    """Set a model version as shadow."""
    try:
        registry = _get_registry()
        version = registry.get_version(version_id)
        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version {version_id} not found",
            )

        result = registry.set_shadow_version(version_id)
        if result:
            return ShadowResponse(
                success=True,
                message=f"Version {version_id} set as shadow model",
                shadow_version=version_id,
            )
        return ShadowResponse(
            success=False,
            message=f"Failed to set version {version_id} as shadow",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to set shadow version {}: {}", version_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set shadow model: {exc}",
        )


@router.post(
    "/shadow/promote",
    response_model=ActivateResponse,
    summary="Promote shadow to active",
    description="Promote the current shadow/challenger model to active.",
)
async def promote_shadow_model() -> ActivateResponse:
    """Promote shadow model to active."""
    try:
        registry = _get_registry()
        shadow = registry.get_shadow_version()
        if shadow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No shadow model is set",
            )

        result = registry.promote_shadow_to_active()
        active = registry.get_active_version()
        if result:
            return ActivateResponse(
                success=True,
                message=f"Shadow version {shadow.version_id} promoted to active",
                activated_version=active.version_id if active else None,
            )
        return ActivateResponse(
            success=False,
            message="Failed to promote shadow model",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to promote shadow model: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote shadow model: {exc}",
        )


@router.delete(
    "/{version_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a model version",
    description="Permanently delete a model version and its checkpoint files.",
)
async def delete_model(version_id: int) -> Dict[str, Any]:
    """Delete a model version."""
    try:
        registry = _get_registry()
        version = registry.get_version(version_id)

        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version {version_id} not found",
            )

        name = version.version_name
        registry.delete_version(version_id)

        logger.info("Deleted model version {} ({})", version_id, name)

        return {
            "success": True,
            "message": f"Model version {version_id} ({name}) deleted",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete version {}: {}", version_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete model: {exc}",
        )


# ---------------------------------------------------------------------------
# Injection hook (called from main.py lifespan)
# ---------------------------------------------------------------------------


def set_registry_instance(registry: ModelRegistry) -> None:
    """Inject the global registry instance from main.py."""
    global _registry
    _registry = registry
    logger.debug("Model registry injected into models router")
