"""
Celery tasks for backtest execution.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from loguru import logger

from celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="tasks.backtest.run_backtest",
)
def run_backtest_task(
    self,
    backtest_id: str,
    strategy_id: str,
    request_dict: Dict[str, Any],
) -> None:
    """
    Run a backtest asynchronously in a Celery worker.

    Args:
        backtest_id: The BacktestRun document ID.
        strategy_id: The Strategy document ID.
        request_dict: Serialized BacktestRequest.
    """
    # Lazy import to avoid circular imports between routers and tasks.
    from routers.backtest import BacktestRequest, _execute_backtest

    request = BacktestRequest(**request_dict)
    logger.info(
        "Celery backtest task started id={} strategy_id={}",
        backtest_id,
        strategy_id,
    )

    try:
        asyncio.run(_execute_backtest(backtest_id, strategy_id, request))
    except Exception as exc:
        logger.exception("Backtest task failed id={}", backtest_id)
        try:
            self.retry(exc=exc)
        except Exception as retry_exc:
            logger.error(
                "Backtest task retry/max retries exceeded id={}: {}",
                backtest_id,
                retry_exc,
            )
        raise

    logger.info("Celery backtest task completed id={}", backtest_id)
