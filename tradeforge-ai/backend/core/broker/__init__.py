"""
TradeForge AI — Broker Connectors

Abstract base and concrete implementations for Indian broker APIs:
- Angel One (SmartAPI)
- Zerodha (Kite Connect)
- Fyers (API v3)
- Paper Trading (simulation)
"""

from core.broker.base import (
    BaseBroker,
    Exchange,
    FundsData,
    HoldingData,
    OrderParams,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionData,
    ProductType,
    Variety,
)

from core.broker.paper_broker import PaperBroker

__all__ = [
    # Base
    "BaseBroker",
    "Exchange",
    "FundsData",
    "HoldingData",
    "OrderParams",
    "OrderResult",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionData",
    "ProductType",
    "Variety",
    # Paper
    "PaperBroker",
    # Real brokers (imported on demand to avoid hard dependencies)
]
