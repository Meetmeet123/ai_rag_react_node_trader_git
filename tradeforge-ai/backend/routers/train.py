"""
Training Pipeline API Routes

- POST /trigger -- Manually trigger training
- GET /status -- Get training pipeline status
- GET /jobs -- List training jobs
- GET /jobs/{id} -- Get job details
- POST /start-auto -- Start auto-training (20-min cron)
- POST /stop-auto -- Stop auto-training
- POST /rollback -- Rollback to previous model version
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from core.auto_trainer import AutoTrainingPipeline, TrainingJob, TrainingStatus
from core.model_registry import ModelRegistry

router = APIRouter()

# Module-level singletons (populated at app startup)
_pipeline: Optional[AutoTrainingPipeline] = None
_registry: Optional[ModelRegistry] = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TrainingTriggerResponse(BaseModel):
    """Response for training trigger."""

    success: bool
    job_id: Optional[int] = None
    message: str


class TrainingStatusResponse(BaseModel):
    """Auto-training pipeline status."""

    is_running: bool
    current_job_id: Optional[int]
    last_training_time: Optional[str]
    next_scheduled_run: Optional[str]
    interval_minutes: int
    total_jobs_completed: int
    total_jobs_failed: int
    consecutive_failures: int
    active_model_version_id: Optional[int]
    active_model_name: Optional[str]
    last_formula_hash: str
    circuit_breaker_open: bool


class TrainingJobResponse(BaseModel):
    """Single training job details."""

    job_id: int
    trigger_reason: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    data_samples: int
    epochs_trained: int
    final_loss: float
    validation_loss: float
    model_version_id: Optional[int]
    checkpoint_path: str
    error_message: str
    backtest_metrics: Dict[str, Any]
    deployed: bool


class TrainingJobListResponse(BaseModel):
    """List of training jobs."""

    jobs: List[Dict[str, Any]]
    total: int
    limit: int


class RollbackResponse(BaseModel):
    """Model rollback response."""

    success: bool
    message: str
    new_active_version: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pipeline() -> AutoTrainingPipeline:
    """Get the global pipeline instance (injected from main.py)."""
    global _pipeline
    if _pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Training pipeline not initialized",
        )
    return _pipeline


def _get_registry() -> ModelRegistry:
    """Get the global registry instance (injected from main.py)."""
    global _registry
    if _registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model registry not initialized",
        )
    return _registry


def _job_to_dict(job: TrainingJob) -> Dict[str, Any]:
    """Convert TrainingJob to JSON-friendly dict."""
    return {
        "job_id": job.job_id,
        "trigger_reason": job.trigger_reason,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "data_samples": job.data_samples,
        "epochs_trained": job.epochs_trained,
        "final_loss": job.final_loss,
        "validation_loss": job.validation_loss,
        "model_version_id": job.model_version_id,
        "checkpoint_path": job.checkpoint_path,
        "error_message": job.error_message,
        "backtest_metrics": job.backtest_metrics,
        "deployed": job.deployed,
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/trigger",
    response_model=TrainingTriggerResponse,
    summary="Manually trigger training",
    description="Manually trigger a training run. The job runs in the background.",
)
async def trigger_training() -> TrainingTriggerResponse:
    """Manually trigger a training run."""
    try:
        pipeline = _get_pipeline()
        job_id = await pipeline.trigger_manual_training()

        logger.info("Manual training triggered — job {}", job_id)

        return TrainingTriggerResponse(
            success=True,
            job_id=job_id,
            message=f"Training job {job_id} started",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to trigger training: {}", exc)
        return TrainingTriggerResponse(
            success=False,
            message=f"Failed to trigger training: {exc}",
        )


@router.get(
    "/status",
    response_model=TrainingStatusResponse,
    summary="Get training pipeline status",
    description="Get the current status of the auto-training pipeline.",
)
async def get_training_status() -> TrainingStatusResponse:
    """Get auto-training pipeline status."""
    try:
        pipeline = _get_pipeline()
        status = pipeline.get_status()

        return TrainingStatusResponse(**status)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get training status: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get training status: {exc}",
        )


@router.get(
    "/jobs",
    response_model=TrainingJobListResponse,
    summary="List training jobs",
    description="List recent training jobs (newest first).",
)
async def list_training_jobs(limit: int = 50) -> TrainingJobListResponse:
    """List recent training jobs."""
    try:
        pipeline = _get_pipeline()
        jobs = pipeline.get_jobs_history(limit=limit)

        return TrainingJobListResponse(
            jobs=jobs,
            total=len(jobs),
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list training jobs: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list training jobs: {exc}",
        )


@router.get(
    "/jobs/{job_id}",
    response_model=TrainingJobResponse,
    summary="Get training job details",
    description="Get detailed information about a specific training job.",
)
async def get_training_job(job_id: int) -> TrainingJobResponse:
    """Get training job details by ID."""
    try:
        pipeline = _get_pipeline()
        jobs = pipeline.jobs_history

        job = next((j for j in jobs if j.job_id == job_id), None)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Training job {job_id} not found",
            )

        return TrainingJobResponse(**_job_to_dict(job))

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get training job {}: {}", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get training job: {exc}",
        )


@router.post(
    "/start-auto",
    summary="Start auto-training",
    description="Start the automatic training scheduler (runs every 20 minutes).",
)
async def start_auto_training() -> Dict[str, str]:
    """Start 20-minute auto-training cron."""
    try:
        pipeline = _get_pipeline()
        pipeline.start()

        logger.info("Auto-training scheduler started")

        return {
            "success": "true",
            "message": f"Auto-training started (interval: {pipeline.interval} min)",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to start auto-training: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start auto-training: {exc}",
        )


@router.post(
    "/stop-auto",
    summary="Stop auto-training",
    description="Stop the automatic training scheduler.",
)
async def stop_auto_training() -> Dict[str, str]:
    """Stop auto-training cron."""
    try:
        pipeline = _get_pipeline()
        pipeline.stop()

        logger.info("Auto-training scheduler stopped")

        return {"success": "true", "message": "Auto-training stopped"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to stop auto-training: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop auto-training: {exc}",
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
        pipeline = _get_pipeline()
        result = await pipeline.force_rollback()

        registry = _get_registry()
        active = registry.get_active_version()

        if result:
            return RollbackResponse(
                success=True,
                message="Model rollback successful",
                new_active_version=active.version_id if active else None,
            )
        else:
            return RollbackResponse(
                success=False,
                message="Rollback failed — no previous version available",
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Rollback failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Injection hook (called from main.py lifespan)
# ---------------------------------------------------------------------------

def set_pipeline_instance(pipeline: AutoTrainingPipeline) -> None:
    """Inject the global pipeline instance from main.py."""
    global _pipeline
    _pipeline = pipeline
    logger.debug("Training pipeline injected into train router")


def set_registry_instance(registry: ModelRegistry) -> None:
    """Inject the global registry instance from main.py."""
    global _registry
    _registry = registry
    logger.debug("Model registry injected into train router")
