"""
Celery tasks for model training and fine-tuning.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from loguru import logger

from celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    name="tasks.training.run_training_job",
)
def run_training_job(
    self,
    job_id: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run a model training/fine-tuning job in a Celery worker.

    Args:
        job_id: The TrainingLog document ID.
        params: Training parameters (dataset filters, hyperparameters, etc.).

    Returns:
        A dictionary with the job result/status.
    """
    logger.info("Training job task started id={}", job_id)

    # NOTE: The concrete training pipeline is intentionally isolated here.
    # It will be wired once `LLMEngine.fine_tune()` / `TradingLLMTrainer`
    # alignment is completed (Phase 7).
    async def _placeholder() -> Dict[str, Any]:
        return {
            "job_id": job_id,
            "status": "pending_implementation",
            "message": "Training task scaffold is wired; implement LoRA/PEFT run in Phase 7.",
        }

    try:
        result = asyncio.run(_placeholder())
    except Exception as exc:
        logger.exception("Training job task failed id={}", job_id)
        self.retry(exc=exc)
        raise

    logger.info("Training job task completed id={}", job_id)
    return result
