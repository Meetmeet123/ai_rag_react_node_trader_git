"""
Training Pipeline API Routes

- POST /trigger -- Manually trigger training (enqueues Celery worker if available)
- GET /status -- Get training pipeline status
- GET /jobs -- List training jobs
- GET /jobs/{id} -- Get job details
- POST /start-auto -- Start auto-training (Celery beat flag)
- POST /stop-auto -- Stop auto-training
- POST /rollback -- Rollback to previous model version
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from loguru import logger

from core.auto_trainer import AutoTrainingPipeline, TrainingJob, TriggerReason
from core.model_registry import ModelRegistry
from database.models import TrainingLog

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


def _training_log_to_dict(doc: TrainingLog) -> Dict[str, Any]:
    """Convert a TrainingLog document to the TrainingJob dict shape."""
    data = doc.model_dump()

    def _iso(val: Any) -> Any:
        from datetime import datetime

        return val.isoformat() if isinstance(val, datetime) else val

    return {
        "job_id": data.get("job_id"),
        "trigger_reason": data.get("trigger_reason"),
        "started_at": _iso(data.get("started_at")),
        "completed_at": _iso(data.get("completed_at")),
        "status": data.get("status"),
        "data_samples": data.get("data_samples") or 0,
        "epochs_trained": data.get("epochs") or 0,
        "final_loss": data.get("final_loss") or 0.0,
        "validation_loss": data.get("validation_loss") or 0.0,
        "model_version_id": data.get("version_id"),
        "checkpoint_path": data.get("checkpoint_path") or "",
        "error_message": data.get("error_message") or "",
        "backtest_metrics": data.get("backtest_metrics") or {},
        "deployed": data.get("deployed") or False,
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/trigger",
    response_model=TrainingTriggerResponse,
    summary="Manually trigger training",
    description="Manually trigger a training run. Enqueues a Celery worker when available.",
)
async def trigger_training() -> TrainingTriggerResponse:
    """Manually trigger a training run."""
    try:
        pipeline = _get_pipeline()

        # Prefer Celery so the heavy work happens in a worker process.
        try:
            from tasks.training import run_training_cycle

            job_id = await pipeline.reserve_job_id(
                trigger_reason=TriggerReason.MANUAL.value
            )
            run_training_cycle.apply_async(kwargs={"job_id": job_id})

            logger.info("Manual training enqueued — job {}", job_id)
            return TrainingTriggerResponse(
                success=True,
                job_id=job_id,
                message="Training enqueued",
            )
        except Exception as celery_exc:
            logger.warning(
                "Celery enqueue failed, falling back to inline training: {}",
                celery_exc,
            )
            job_id = await pipeline.trigger_manual_training()
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
        pipeline_status = await pipeline.get_status()

        return TrainingStatusResponse(**pipeline_status)

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
        jobs = await pipeline.get_jobs_history(limit=limit)

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
        log_doc = await TrainingLog.find_one(TrainingLog.job_id == job_id)
        if log_doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Training job {job_id} not found",
            )

        return TrainingJobResponse(**_training_log_to_dict(log_doc))

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
    description="Enable the automatic training scheduler (Celery beat runs every 20 minutes).",
)
async def start_auto_training() -> Dict[str, str]:
    """Enable the 20-minute auto-training flag."""
    try:
        pipeline = _get_pipeline()
        await pipeline.start()

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
    """Disable auto-training flag."""
    try:
        pipeline = _get_pipeline()
        await pipeline.stop()

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
