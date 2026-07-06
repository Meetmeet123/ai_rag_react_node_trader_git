"""
Celery tasks for market data ingestion.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List

from loguru import logger

from celery_app import celery_app
from config import settings
from core.market_data.ingestor import MarketDataIngestor


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.market_data.daily_ingest",
)
def daily_ingest(self) -> None:
    """
    Scheduled task to refresh daily OHLCV data for a default watchlist.

    Runs every 6 hours via Celery beat. In a full implementation this would
    iterate the user's watchlist; here it seeds a small default set.
    """
    symbols: List[str] = ["NIFTY50", "RELIANCE", "TCS", "INFY", "HDFCBANK"]
    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=365)

    async def _run() -> None:
        ingestor = MarketDataIngestor(data_dir=settings.HISTORICAL_DATA_DIR)
        try:
            for symbol in symbols:
                try:
                    df = await ingestor.fetch_historical(
                        symbol,
                        from_date,
                        to_date,
                        timeframe="1d",
                    )
                    logger.info(
                        "Daily ingest fetched {} rows for {}",
                        len(df),
                        symbol,
                    )
                except Exception as exc:
                    logger.warning("Daily ingest failed for {}: {}", symbol, exc)
        finally:
            await ingestor.close()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.exception("Daily ingest task failed: {}", exc)
        self.retry(exc=exc)
