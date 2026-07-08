"""
TradeForge AI - API Router Package.

All routers are imported here for clean inclusion in the main FastAPI app.
"""

from routers import (
    analytics,
    llm,
    strategies,
    backtest,
    train,
    models,
    execute,
    market,
    brokers,
    settings,
    audit,
)

__all__ = [
    "analytics",
    "llm",
    "strategies",
    "backtest",
    "train",
    "models",
    "execute",
    "market",
    "brokers",
    "settings",
    "audit",
]
