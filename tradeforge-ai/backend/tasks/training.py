"""
Celery tasks for the auto-training pipeline.

The actual training cycle is delegated to ``core.auto_trainer.AutoTrainingPipeline``
so that the API process and Celery workers share the same implementation and
state (stored in MongoDB via ``TrainingPipelineState`` / ``TrainingLog``).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    name="tasks.training.run_training_cycle",
)
def run_training_cycle(self, job_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Run one scheduled auto-training cycle in a Celery worker.

    The pipeline flag in ``TrainingPipelineState`` is checked first; if
    auto-training is disabled the task returns immediately.  All
    dependencies are built from ``config.settings`` (mirroring ``main.py``).

    Args:
        job_id: Optional pre-reserved job ID returned by the API trigger
            endpoint.  If omitted, the worker allocates the next available
            ID from the shared state.

    Returns:
        A dictionary describing the outcome:
        ``{"status": "skipped", "reason": "..."}`` or
        ``{"job_id": int, "status": str, "deployed": bool}`` or
        ``{"status": "failed", "error": str}``.
    """

    async def _run() -> Dict[str, Any]:
        from config import settings
        from database.connection import init_db
        from database.models import TrainingPipelineState

        await init_db()

        state = await TrainingPipelineState.find_one()
        if state is None or not state.is_running:
            logger.info("Auto-training cycle skipped: pipeline not running")
            return {"status": "skipped", "reason": "not running"}

        from core.artifact_store import ArtifactStore
        from core.auto_trainer import AutoTrainingPipeline
        from core.backtest_engine import BacktestEngine
        from core.drift_detector import DriftDetector
        from core.llm_engine import LLMEngine
        from core.market_data.ingestor import MarketDataIngestor
        from core.model_registry import ModelRegistry
        from core.validation_backtest_adapter import ValidationBacktestAdapter
        from training.dataset_builder import StrategyDatasetBuilder

        llm = LLMEngine()
        backtest = BacktestEngine()
        registry = ModelRegistry(models_dir=settings.MODELS_DIR)
        ingestor = MarketDataIngestor(data_dir=settings.HISTORICAL_DATA_DIR)
        dataset_builder = StrategyDatasetBuilder()
        validation_adapter = ValidationBacktestAdapter(
            ingestor=ingestor,
            backtest_engine=backtest,
        )
        artifact_store = ArtifactStore()
        drift_detector = DriftDetector(threshold=settings.DRIFT_THRESHOLD)

        pipeline = AutoTrainingPipeline(
            llm_engine=llm,
            backtest_engine=validation_adapter,
            model_registry=registry,
            dataset_builder=dataset_builder,
            training_interval_minutes=settings.TRAINING_INTERVAL_MINUTES,
            models_dir=settings.MODELS_DIR,
            artifact_store=artifact_store,
            drift_detector=drift_detector,
            shadow_mode=getattr(settings, "MODEL_SHADOW_MODE", False),
        )
        await pipeline.initialize()

        job = await pipeline.run_single_cycle(job_id=job_id)
        if job is None:
            return {"status": "skipped", "reason": "no changes"}

        return {
            "job_id": job.job_id,
            "status": job.status,
            "deployed": job.deployed,
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("Auto-training cycle failed: {}", exc)
        return {"status": "failed", "error": str(exc)}
