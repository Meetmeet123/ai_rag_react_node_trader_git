"""
TradeForge AI - API Router Package.

All routers are imported here for clean inclusion in the main FastAPI app.
"""

from routers import llm, strategies, backtest, train, models, execute, market

__all__ = ["llm", "strategies", "backtest", "train", "models", "execute", "market"]
