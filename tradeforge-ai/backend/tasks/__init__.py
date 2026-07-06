"""
Celery task package.

Handles per-worker-process database initialization and shutdown.
"""

from __future__ import annotations

import asyncio

from celery import signals
from loguru import logger

from database.connection import init_db, close_db

# ---------------------------------------------------------------------------
# Worker lifecycle hooks
# ---------------------------------------------------------------------------


@signals.worker_process_init.connect
def init_worker_process(**_kwargs) -> None:
    """Initialize MongoDB/Beanie for each Celery worker process."""
    try:
        asyncio.run(init_db())
        logger.info("Celery worker database initialized")
    except Exception as exc:  # pragma: no cover
        logger.exception("Celery worker database initialization failed: {}", exc)
        raise


@signals.worker_process_shutdown.connect
def shutdown_worker_process(**_kwargs) -> None:
    """Close MongoDB connection when a Celery worker process shuts down."""
    try:
        asyncio.run(close_db())
        logger.info("Celery worker database connection closed")
    except Exception as exc:  # pragma: no cover
        logger.warning("Error closing Celery worker database connection: {}", exc)
