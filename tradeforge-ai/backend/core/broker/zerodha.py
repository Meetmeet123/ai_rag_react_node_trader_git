"""
Zerodha Kite Connect API Connector

Implements the :class:`BaseBroker` interface for Zerodha trading.
Handles API key + request-token based authentication, order placement,
portfolio queries, and market data via the Kite Connect REST API.

Environment variables::

    ZERODHA_API_KEY       – Kite Connect API key
    ZERODHA_API_SECRET    – Kite Connect API secret
    ZERODHA_ACCESS_TOKEN  – Pre-generated access token (optional)

Typical usage (login flow)::

    # 1. Generate login URL and redirect user
    broker = ZerodhaBroker(api_key="xxx", api_secret="yyy")
    login_url = broker.get_login_url()
    # ... user visits login_url and authorises ...
    # ... request_token is returned in callback URL ...

    # 2. Generate session
    await broker.generate_session(request_token="request_token_from_callback")

    # 3. Trade
    result = await broker.place_order(order_params)

Typical usage (with pre-existing token)::

    broker = ZerodhaBroker(
        api_key="xxx",
        api_secret="yyy",
        access_token="existing_token",
    )
    await broker.connect()  # Validates token
    result = await broker.place_order(order_params)
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

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
)

# ---------------------------------------------------------------------------
# Zerodha Kite Connect constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.kite.trade"
LOGIN_URL = "https://kite.zerodha.com/connect/login"

# Endpoints
SESSION_URL = f"{BASE_URL}/session/token"
PROFILE_URL = f"{BASE_URL}/user/profile"
ORDERS_URL = f"{BASE_URL}/orders"
ORDER_INFO_URL = f"{BASE_URL}/orders/{{order_id}}"
MODIFY_ORDER_URL = f"{BASE_URL}/orders/{{order_id}}"
CANCEL_ORDER_URL = f"{BASE_URL}/orders/{{order_id}}"
TRADES_URL = f"{BASE_URL}/orders/{{order_id}}/trades"
POSITIONS_URL = f"{BASE_URL}/portfolio/positions"
HOLDINGS_URL = f"{BASE_URL}/portfolio/holdings"
MARGINS_URL = f"{BASE_URL}/user/margins"
LTP_URL = f"{BASE_URL}/quote/ltp"
OHLC_URL = f"{BASE_URL}/quote/ohlc"

# Product type mapping
_PRODUCT_MAP = {
    ProductType.MIS: "MIS",
    ProductType.CNC: "CNC",
    ProductType.NRML: "NRML",
}

_ORDER_TYPE_MAP = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "SL",
    OrderType.SL_M: "SL-M",
    OrderType.CO: "CO",
    OrderType.BO: "BO",
    OrderType.AMO: "AMO",
}

_SIDE_MAP = {
    OrderSide.BUY: "BUY",
    OrderSide.SELL: "SELL",
}

_EXCHANGE_MAP = {
    Exchange.NSE: "NSE",
    Exchange.BSE: "BSE",
    Exchange.NFO: "NFO",
    Exchange.BFO: "BFO",
    Exchange.CDS: "CDS",
    Exchange.MCX: "MCX",
}

# Status mapping from Kite to our enum
_STATUS_MAP = {
    "COMPLETE": OrderStatus.COMPLETE,
    "REJECTED": OrderStatus.REJECTED,
    "CANCELLED": OrderStatus.CANCELLED,
    "OPEN": OrderStatus.OPEN,
    "PENDING": OrderStatus.PENDING,
    "AMO REQ RECEIVED": OrderStatus.AMO_REQ_RECEIVED,
    "UPDATE": OrderStatus.MODIFIED,
    "VALIDATION PENDING": OrderStatus.VALIDATION_PENDING,
    "MODIFY PENDING": OrderStatus.MOD_PENDING,
    "MODIFY REJECTED": OrderStatus.MOD_REJECTED,
    "CANCEL PENDING": OrderStatus.CAN_PENDING,
    "CANCEL REJECTED": OrderStatus.CAN_REJECTED,
    "TRIGGER PENDING": OrderStatus.TRIGGER_PENDING,
    "AFTER MARKET": OrderStatus.AFTER_MARKET,
}


# ---------------------------------------------------------------------------
# Broker implementation
# ---------------------------------------------------------------------------


class ZerodhaBroker(BaseBroker):
    """Zerodha Kite Connect broker connector.

    Args:
        api_key: Kite Connect API key.
        api_secret: Kite Connect API secret.
        access_token: Optional pre-existing access token.
    """

    name: str = "zerodha"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ZERODHA_API_KEY", "")
        self.api_secret = api_secret or os.getenv("ZERODHA_API_SECRET", "")
        self.access_token = access_token or os.getenv("ZERODHA_ACCESS_TOKEN")

        self.user_id: Optional[str] = None
        self._connected = False
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers = {
                "X-Kite-Version": "3",
            }
            if self.api_key:
                headers["X-Kite-ApiKey"] = self.api_key
            if self.access_token:
                headers["Authorization"] = f"token {self.api_key}:{self.access_token}"

            self._http = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=headers,
                timeout=httpx.Timeout(30.0),
            )
        return self._http

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Parse Kite Connect API response."""
        try:
            data = response.json()
        except Exception as exc:
            raise ZerodhaAPIError(f"Invalid JSON: {exc}") from exc

        if data.get("status") == "error":
            error_type = data.get("error_type", "")
            message = data.get("message", "Unknown error")
            raise ZerodhaAPIError(f"{error_type}: {message}")

        return data.get("data", data)

    # ------------------------------------------------------------------
    # Login flow helpers
    # ------------------------------------------------------------------

    def get_login_url(self) -> str:
        """Generate the Kite login URL for the user to visit.

        Returns:
            Full URL string that the user must open in a browser.
        """
        return f"{LOGIN_URL}?api_key={self.api_key}&v=3"

    async def generate_session(self, request_token: str) -> Dict[str, Any]:
        """Exchange request token for access token.

        This is the second step of the OAuth flow after the user has
        authorised the app and a ``request_token`` is received in the
        callback URL.

        Args:
            request_token: Token from the post-login callback.

        Returns:
            Dict with ``access_token``, ``refresh_token``, ``user_id``.
        """
        # Generate checksum: sha256(api_key + request_token + api_secret)
        checksum = hashlib.sha256(
            f"{self.api_key}{request_token}{self.api_secret}".encode()
        ).hexdigest()

        payload = {
            "api_key": self.api_key,
            "request_token": request_token,
            "checksum": checksum,
        }

        try:
            response = await self._client().post(SESSION_URL, data=payload)
            response.raise_for_status()
            data = self._handle_response(response)

            self.access_token = data.get("access_token")
            self.user_id = data.get("user_id")

            # Update client headers with new token
            client = self._client()
            client.headers["Authorization"] = (
                f"token {self.api_key}:{self.access_token}"
            )

            self._connected = True
            logger.info("Zerodha session generated | user={}", self.user_id)
            return data

        except Exception as exc:
            logger.exception("Zerodha session generation failed: {}", exc)
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Validate the existing access token by fetching user profile."""
        if not self.access_token:
            logger.error("No access token available. Call generate_session() first.")
            return False

        try:
            response = await self._client().get(PROFILE_URL)
            data = self._handle_response(response)

            self.user_id = data.get("user_id")
            self._connected = True
            logger.info("Zerodha connected | user={}", self.user_id)
            return True

        except Exception as exc:
            logger.exception("Zerodha connect failed: {}", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close the HTTP session."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None
        self._connected = False
        logger.info("Zerodha disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected and self.access_token is not None

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place order via Kite Connect.

        Args:
            params: Normalised :class:`OrderParams`.

        Returns:
            :class:`OrderResult` with Kite ``order_id``.
        """
        payload = {
            "exchange": _EXCHANGE_MAP.get(params.exchange, "NSE"),
            "tradingsymbol": params.symbol,
            "transaction_type": _SIDE_MAP.get(params.side, "BUY"),
            "quantity": str(params.quantity),
            "product": _PRODUCT_MAP.get(params.product_type, "MIS"),
            "order_type": _ORDER_TYPE_MAP.get(params.order_type, "MARKET"),
            "validity": "DAY",
            "tag": (params.tag or "TF")[:8],  # Kite max 8 chars
        }

        if params.price > 0:
            payload["price"] = str(params.price)
        if params.trigger_price > 0:
            payload["trigger_price"] = str(params.trigger_price)

        try:
            response = await self._client().post(ORDERS_URL, data=payload)
            data = self._handle_response(response)

            order_id = data.get("order_id", "")
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.PENDING,
                symbol=params.symbol,
                quantity=params.quantity,
                message="Order placed",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Zerodha place_order failed: {}", exc)
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                symbol=params.symbol,
                quantity=params.quantity,
                message=str(exc),
            )

    async def modify_order(
        self,
        order_id: str,
        params: Dict[str, Any],
    ) -> OrderResult:
        """Modify an existing order."""
        payload: Dict[str, Any] = {}
        if "price" in params:
            payload["price"] = str(params["price"])
        if "quantity" in params:
            payload["quantity"] = str(params["quantity"])
        if "trigger_price" in params:
            payload["trigger_price"] = str(params["trigger_price"])
        if "order_type" in params:
            payload["order_type"] = params["order_type"]

        try:
            url = MODIFY_ORDER_URL.format(order_id=order_id)
            response = await self._client().put(url, data=payload)
            data = self._handle_response(response)

            return OrderResult(
                order_id=data.get("order_id", order_id),
                status=OrderStatus.MODIFIED,
                message="Order modified",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Zerodha modify_order failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an open order."""
        try:
            url = CANCEL_ORDER_URL.format(order_id=order_id)
            response = await self._client().delete(url)
            data = self._handle_response(response)

            return OrderResult(
                order_id=data.get("order_id", order_id),
                status=OrderStatus.CANCELLED,
                message="Order cancelled",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Zerodha cancel_order failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get status of a single order."""
        try:
            url = ORDER_INFO_URL.format(order_id=order_id)
            response = await self._client().get(url)
            data = self._handle_response(response)

            # Kite returns a list of order updates
            if isinstance(data, list) and data:
                latest = data[0]
            elif isinstance(data, dict):
                latest = data
            else:
                return OrderResult(
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Order not found",
                )

            status_str = latest.get("status", "PENDING")
            return OrderResult(
                order_id=order_id,
                status=_STATUS_MAP.get(status_str, OrderStatus.PENDING),
                symbol=latest.get("tradingsymbol", ""),
                quantity=int(latest.get("quantity", 0)),
                filled_qty=int(latest.get("filled_quantity", 0)),
                avg_price=float(latest.get("average_price", 0) or 0),
                message=latest.get("status_message", ""),
                broker_raw=latest,
            )

        except Exception as exc:
            logger.exception("Zerodha get_order_status failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def get_order_book(self) -> List[OrderResult]:
        """Fetch all orders for the day."""
        try:
            response = await self._client().get(ORDERS_URL)
            data = self._handle_response(response)

            if not isinstance(data, list):
                return []

            results = []
            for item in data:
                status_str = item.get("status", "PENDING")
                results.append(
                    OrderResult(
                        order_id=item.get("order_id", ""),
                        status=_STATUS_MAP.get(status_str, OrderStatus.PENDING),
                        symbol=item.get("tradingsymbol", ""),
                        quantity=int(item.get("quantity", 0)),
                        filled_qty=int(item.get("filled_quantity", 0)),
                        avg_price=float(item.get("average_price", 0) or 0),
                        message=item.get("status_message", ""),
                        broker_raw=item,
                    )
                )
            return results

        except Exception as exc:
            logger.exception("Zerodha get_order_book failed: {}", exc)
            return []

    # ------------------------------------------------------------------
    # Portfolio queries
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch day and net positions."""
        try:
            response = await self._client().get(POSITIONS_URL)
            data = self._handle_response(response)

            positions = []
            day_pos = data.get("day", []) if isinstance(data, dict) else []
            net_pos = data.get("net", []) if isinstance(data, dict) else []

            for pos_list in [day_pos, net_pos]:
                for item in pos_list:
                    qty = int(item.get("quantity", 0))
                    positions.append(
                        PositionData(
                            symbol=item.get("tradingsymbol", ""),
                            exchange=Exchange(item.get("exchange", "NSE")),
                            product=ProductType(item.get("product", "MIS").lower()),
                            quantity=qty,
                            avg_price=float(
                                item.get("average_price", 0)
                                or item.get("buy_price", 0)
                                or 0
                            ),
                            last_price=float(item.get("last_price", 0) or 0),
                            pnl=float(item.get("pnl", 0) or 0),
                            day_pnl=float(item.get("day_buy_value", 0) or 0),
                            overnight_quantity=int(item.get("overnight_quantity", 0)),
                            buy_quantity=int(item.get("buy_quantity", 0)),
                            sell_quantity=int(item.get("sell_quantity", 0)),
                            buy_price=float(item.get("buy_price", 0) or 0),
                            sell_price=float(item.get("sell_price", 0) or 0),
                            broker_raw=item,
                        )
                    )
            return positions

        except Exception as exc:
            logger.exception("Zerodha get_positions failed: {}", exc)
            return []

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch Demat holdings."""
        try:
            response = await self._client().get(HOLDINGS_URL)
            data = self._handle_response(response)

            if not isinstance(data, list):
                return []

            holdings = []
            for item in data:
                holdings.append(
                    HoldingData(
                        symbol=item.get("tradingsymbol", ""),
                        exchange=Exchange(item.get("exchange", "NSE")),
                        quantity=int(item.get("quantity", 0)),
                        avg_price=float(item.get("average_price", 0) or 0),
                        last_price=float(item.get("last_price", 0) or 0),
                        pnl=float(item.get("pnl", 0) or 0),
                        day_change_pct=float(item.get("day_change_percentage", 0) or 0),
                        broker_raw=item,
                    )
                )
            return holdings

        except Exception as exc:
            logger.exception("Zerodha get_holdings failed: {}", exc)
            return []

    async def get_funds(self) -> FundsData:
        """Fetch available margins."""
        try:
            response = await self._client().get(MARGINS_URL)
            data = self._handle_response(response)

            equity = data.get("equity", {}) if isinstance(data, dict) else {}

            return FundsData(
                available_cash=float(equity.get("available", {}).get("cash", 0) or 0),
                used_margin=float(equity.get("used", {}).get("debits", 0) or 0),
                opening_balance=float(
                    equity.get("available", {}).get("opening_balance", 0) or 0
                ),
                payin=float(equity.get("available", {}).get("collateral", 0) or 0),
                span_margin=float(equity.get("used", {}).get("span", 0) or 0),
                exposure_margin=float(equity.get("used", {}).get("exposure", 0) or 0),
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Zerodha get_funds failed: {}", exc)
            return FundsData()

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbol: str, exchange: Exchange = Exchange.NSE) -> float:
        """Get Last Traded Price for an instrument.

        Uses the ``/quote/ltp`` endpoint which accepts an exchange:symbol
        identifier.
        """
        inst = f"{_EXCHANGE_MAP.get(exchange, 'NSE')}:{symbol}"
        params = {"i": inst}

        try:
            response = await self._client().get(LTP_URL, params=params)
            data = self._handle_response(response)

            quote = data.get(inst, {})
            return float(quote.get("last_price", 0))

        except Exception as exc:
            logger.exception("Zerodha get_ltp failed for {}: {}", symbol, exc)
            return 0.0

    async def get_ltps(
        self,
        symbols: List[str],
        exchange: Exchange = Exchange.NSE,
    ) -> Dict[str, float]:
        """Batch LTP fetch using a single API call."""
        ex = _EXCHANGE_MAP.get(exchange, "NSE")
        insts = [f"{ex}:{s}" for s in symbols]
        params = [("i", i) for i in insts]

        try:
            response = await self._client().get(LTP_URL, params=params)
            data = self._handle_response(response)

            result: Dict[str, float] = {}
            for sym in symbols:
                inst = f"{ex}:{sym}"
                quote = data.get(inst, {})
                result[sym] = float(quote.get("last_price", 0))
            return result

        except Exception as exc:
            logger.exception("Zerodha get_ltps failed: {}", exc)
            return {sym: 0.0 for sym in symbols}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ZerodhaAPIError(Exception):
    """Raised when the Zerodha API returns an error response."""

    pass
