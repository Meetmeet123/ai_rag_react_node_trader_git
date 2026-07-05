"""
TradeForge AI - MongoDB Engine & Beanie ODM Setup.

Provides Motor client configuration, Beanie initialization, and a helper
for retrieving the database object.
"""

from __future__ import annotations

from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie

from config import settings
from database.models import (
    Account,
    BacktestRun,
    BrokerConfig,
    MarketData,
    ModelVersion,
    RiskConfig,
    Signal,
    Strategy,
    Trade,
    TrainingLog,
    User,
)

# ---------------------------------------------------------------------------
# Global client / db references
# ---------------------------------------------------------------------------

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

DOCUMENT_MODELS: List[type] = [
    User,
    Account,
    Strategy,
    Trade,
    Signal,
    BacktestRun,
    ModelVersion,
    TrainingLog,
    BrokerConfig,
    RiskConfig,
    MarketData,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_client() -> AsyncIOMotorClient:
    """Return the global Motor client, creating it if necessary."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the global Motor database object."""
    global _db
    if _db is None:
        client = get_client()
        # Use the database name from settings, falling back to the one in the URI.
        db_name = settings.MONGODB_DB_NAME or client.get_default_database().name
        _db = client[db_name]
    return _db


async def init_db() -> None:
    """Initialize Beanie with all document models.

    Safe to call multiple times — Beanie handles repeated initialization.
    Invoke this once at application startup (e.g., in lifespan handler).
    """
    client = get_client()
    db_name = settings.MONGODB_DB_NAME
    if db_name:
        db = client[db_name]
    else:
        db = client.get_default_database()

    await init_beanie(database=db, document_models=DOCUMENT_MODELS)


async def close_db() -> None:
    """Close the Motor client connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
