"""
Abstract Base Class for Broker Connectors

All broker implementations (Angel One, Zerodha, Fyers, Upstox, Paper)
must implement this interface.

Defines standard dataclasses, enums, and abstract methods that every
broker connector must provide for order placement, position tracking,
portfolio queries, and market data retrieval.

Typical usage::

    broker = AngelOneBroker(api_key="...", client_id="...")
    await broker.connect()
    result = await broker.place_order(order_params)
    positions = await broker.get_positions()
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OrderSide(str, Enum):
    """Direction of an order."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Execution type for an order."""

    MARKET = "market"
    LIMIT = "limit"
    SL = "sl"  # Stop-loss (triggers as limit)
    SL_M = "sl_m"  # Stop-loss market
    CO = "co"  # Cover order
    BO = "bo"  # Bracket order
    AMO = "amo"  # After-market order


class ProductType(str, Enum):
    """Product / margin type used in Indian brokers."""

    MIS = "mis"  # Intraday (margin)
    CNC = "cnc"  # Cash-n-carry (delivery)
    NRML = "nrml"  # Normal (overnight F&O)


class Exchange(str, Enum):
    """Supported Indian exchanges."""

    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"  # NSE Futures & Options
    BFO = "BFO"  # BSE Futures & Options
    CDS = "CDS"  # Currency Derivatives
    MCX = "MCX"  # Commodities


class OrderStatus(str, Enum):
    """Lifecycle status of an order."""

    PENDING = "pending"
    OPEN = "open"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"
    TRIGGER_PENDING = "trigger_pending"
    AMO_REQ_RECEIVED = "amo_req_received"
    VALIDATION_PENDING = "validation_pending"
    EXECUTED = "executed"
    MODIFIED = "modified"
    MOD_PENDING = "mod_pending"
    MOD_REJECTED = "mod_rejected"
    CAN_PENDING = "can_pending"
    CAN_REJECTED = "can_rejected"
    AFTER_MARKET = "after_market"
    TRANSIT = "transit"


class Variety(str, Enum):
    """Order variety (used by Zerodha / Angel One)."""

    REGULAR = "regular"
    CO = "co"
    BO = "bo"
    AMO = "amo"
    ICEBERG = "iceberg"


# ---------------------------------------------------------------------------
# Pydantic models for request / response validation
# ---------------------------------------------------------------------------


class OrderParams(BaseModel):
    """Standardised order parameters accepted by every broker connector.

    Attributes:
        symbol: Trading symbol (e.g. ``RELIANCE-EQ``, ``NIFTY24MAYFUT``).
        quantity: Number of shares / lots.
        side: ``buy`` or ``sell``.
        order_type: ``market``, ``limit``, ``sl``, ``sl_m``, etc.
        product_type: ``mis``, ``cnc``, ``nrml``.
        exchange: Exchange on which the instrument is listed.
        price: Limit price (required for ``limit`` / ``sl`` orders).
        trigger_price: Trigger price for SL orders.
        tag: Optional user-defined identifier (max 8 chars on some brokers).
    """

    symbol: str = Field(..., min_length=1, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Order quantity")
    side: OrderSide = Field(..., description="Order direction")
    order_type: OrderType = Field(default=OrderType.MARKET)
    product_type: ProductType = Field(default=ProductType.MIS)
    exchange: Exchange = Field(default=Exchange.NSE)
    price: float = Field(default=0.0, ge=0.0)
    trigger_price: float = Field(default=0.0, ge=0.0)
    tag: Optional[str] = Field(default=None, max_length=20)

    @field_validator("price", "trigger_price")
    @classmethod
    def _round_to_two(cls, v: float) -> float:
        return round(v, 2)

    def to_broker_payload(self, broker_name: str = "generic") -> Dict[str, Any]:
        """Convert to a broker-specific payload dict.

        Sub-classes may override to add broker-specific fields.
        """
        return {
            "symbol": self.symbol,
            "qty": self.quantity,
            "side": self.side.value,
            "type": self.order_type.value,
            "product": self.product_type.value,
            "exchange": self.exchange.value,
            "price": self.price,
            "trigger_price": self.trigger_price,
            "tag": self.tag,
        }


class OrderResult(BaseModel):
    """Normalised result returned after an order operation.

    Attributes:
        order_id: Broker-generated unique order identifier.
        status: Current order status.
        symbol: Trading symbol.
        quantity: Requested quantity.
        filled_qty: Actually filled quantity.
        avg_price: Average fill price (0.0 if not filled yet).
        message: Human-readable status or error message.
        timestamp: UTC timestamp when the result was created.
        broker_raw: Raw broker response (useful for debugging).
    """

    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    symbol: str = ""
    quantity: int = 0
    filled_qty: int = 0
    avg_price: float = 0.0
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    broker_raw: Optional[Dict[str, Any]] = None

    @property
    def is_complete(self) -> bool:
        return self.status == OrderStatus.COMPLETE

    @property
    def is_rejected(self) -> bool:
        return self.status == OrderStatus.REJECTED


class PositionData(BaseModel):
    """Normalised position representation."""

    symbol: str
    exchange: Exchange
    product: ProductType
    quantity: int = 0  # Positive = long, Negative = short
    avg_price: float = 0.0
    last_price: float = 0.0
    pnl: float = 0.0
    day_pnl: float = 0.0
    overnight_quantity: int = 0
    buy_quantity: int = 0
    sell_quantity: int = 0
    buy_price: float = 0.0
    sell_price: float = 0.0
    broker_raw: Optional[Dict[str, Any]] = None


class HoldingData(BaseModel):
    """Normalised holding representation."""

    symbol: str
    exchange: Exchange
    quantity: int = 0
    avg_price: float = 0.0
    last_price: float = 0.0
    pnl: float = 0.0
    day_change_pct: float = 0.0
    broker_raw: Optional[Dict[str, Any]] = None


class FundsData(BaseModel):
    """Normalised funds / margin information."""

    available_cash: float = 0.0
    used_margin: float = 0.0
    opening_balance: float = 0.0
    payin: float = 0.0
    payout: float = 0.0
    span_margin: float = 0.0
    adhoc_margin: float = 0.0
    exposure_margin: float = 0.0
    available_intraday_payin: float = 0.0
    broker_raw: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Abstract broker interface
# ---------------------------------------------------------------------------


class BaseBroker(ABC):
    """Abstract broker interface that every concrete connector must implement.

    The design follows an async-first pattern suitable for high-frequency
    signal processing.  All I/O bound methods are ``async`` so they can be
    awaited inside the :class:`ExecutionEngine` event loop.
    """

    name: str = "abstract"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def connect(self) -> bool:
        """Authenticate and establish a session with the broker.

        Returns:
            ``True`` if the connection + login succeeded.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the session and release resources."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the broker session is currently active."""
        ...

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place a new order.

        Args:
            params: Normalised :class:`OrderParams` instance.

        Returns:
            :class:`OrderResult` with broker-generated ``order_id``.
        """
        ...

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        params: Dict[str, Any],
    ) -> OrderResult:
        """Modify an open / pending order.

        Args:
            order_id: Existing broker order id.
            params: Dict of fields to update (e.g. ``price``, ``trigger_price``).

        Returns:
            Updated :class:`OrderResult`.
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel a pending or open order.

        Args:
            order_id: Broker order id to cancel.

        Returns:
            :class:`OrderResult` with status ``CANCELLED`` on success.
        """
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResult:
        """Query the current status of a single order.

        Args:
            order_id: Broker order id.

        Returns:
            :class:`OrderResult` reflecting latest status.
        """
        ...

    @abstractmethod
    async def get_order_book(self) -> List[OrderResult]:
        """Fetch the full day's order book.

        Returns:
            List of :class:`OrderResult` objects.
        """
        ...

    # ------------------------------------------------------------------
    # Portfolio queries
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_positions(self) -> List[PositionData]:
        """Fetch currently open positions (day + overnight).

        Returns:
            List of :class:`PositionData`.
        """
        ...

    @abstractmethod
    async def get_holdings(self) -> List[HoldingData]:
        """Fetch Demat holdings.

        Returns:
            List of :class:`HoldingData`.
        """
        ...

    @abstractmethod
    async def get_funds(self) -> FundsData:
        """Fetch available funds and margin utilisation.

        Returns:
            :class:`FundsData`.
        """
        ...

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_ltp(self, symbol: str, exchange: Exchange = Exchange.NSE) -> float:
        """Get the Last Traded Price for an instrument.

        Args:
            symbol: Trading symbol.
            exchange: Exchange enum.

        Returns:
            Last traded price as ``float``.
        """
        ...

    async def get_ltps(
        self,
        symbols: List[str],
        exchange: Exchange = Exchange.NSE,
    ) -> Dict[str, float]:
        """Batch LTP fetch (default implementation loops over :meth:`get_ltp`).

        Concrete brokers may override this with a single network call for
        better performance.
        """
        tasks = [self.get_ltp(sym, exchange) for sym in symbols]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        result: Dict[str, float] = {}
        for sym, price in zip(symbols, prices):
            if isinstance(price, Exception):
                result[sym] = 0.0
            else:
                result[sym] = price
        return result

    # ------------------------------------------------------------------
    # Square-off helpers
    # ------------------------------------------------------------------

    async def square_off_position(self, position: PositionData) -> OrderResult:
        """Convenience method to square off a single position.

        Derives the opposite-side order automatically and submits it as a
        **market** order in the same product type.
        """
        side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        params = OrderParams(
            symbol=position.symbol,
            quantity=abs(position.quantity),
            side=side,
            order_type=OrderType.MARKET,
            product_type=position.product,
            exchange=position.exchange,
            tag="sqoff",
        )
        return await self.place_order(params)

    async def square_off_all(self) -> List[OrderResult]:
        """Square off **all** open positions (emergency / EOD routine).

        Returns:
            List of :class:`OrderResult` objects—one per position.
        """
        positions = await self.get_positions()
        results: List[OrderResult] = []
        for pos in positions:
            if pos.quantity != 0:
                result = await self.square_off_position(pos)
                results.append(result)
        return results
