"""
Upstox API v2 Connector

Implements the :class:`BaseBroker` interface for Upstox trading.  All HTTP
calls use the synchronous ``requests`` library wrapped in an executor so the
connector remains async-compatible inside the execution engine.

For the OAuth flow::

    login_url = UpstoxBroker.get_login_url(api_key, redirect_uri)
    # redirect user to login_url...
    # receive ``code`` in callback...
    token_response = UpstoxBroker.exchange_code_for_token(
        code, api_key, api_secret, redirect_uri
    )
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
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

BASE_URL = "https://api.upstox.com/v2"
LOGIN_URL = "https://api.upstox.com/v2/login/authorization/dialog"

# Upstox product / order type / side / exchange mapping
_PRODUCT_MAP = {
    ProductType.MIS: "I",
    ProductType.CNC: "D",
    ProductType.NRML: "M",
}

_ORDER_TYPE_MAP = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "SL",
    OrderType.SL_M: "SL-M",
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

# Upstox status strings to normalised enum (best-effort mapping)
_STATUS_MAP = {
    "complete": OrderStatus.COMPLETE,
    "rejected": OrderStatus.REJECTED,
    "cancelled": OrderStatus.CANCELLED,
    "open": OrderStatus.OPEN,
    "pending": OrderStatus.PENDING,
    "trigger pending": OrderStatus.TRIGGER_PENDING,
    "after market": OrderStatus.AFTER_MARKET,
    "amo req received": OrderStatus.AMO_REQ_RECEIVED,
    "validation pending": OrderStatus.VALIDATION_PENDING,
    "modify pending": OrderStatus.MOD_PENDING,
    "modify rejected": OrderStatus.MOD_REJECTED,
    "cancel pending": OrderStatus.CAN_PENDING,
    "cancel rejected": OrderStatus.CAN_REJECTED,
}


def _now() -> datetime:
    """Return current UTC datetime."""
    return datetime.utcnow()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _map_status(status: Any) -> OrderStatus:
    if status is None:
        return OrderStatus.PENDING
    return _STATUS_MAP.get(str(status).strip().lower(), OrderStatus.PENDING)


def _headers(access_token: Optional[str]) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


class UpstoxBroker(BaseBroker):
    """Upstox API v2 broker connector.

    Args:
        api_key: Upstox app API key.
        api_secret: Upstox app API secret.
        redirect_uri: OAuth redirect URI registered with the app.
        access_token: OAuth access token for the user.
        client_id: Upstox client/user id (optional).
    """

    name: str = "upstox"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
    ):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.redirect_uri = redirect_uri or ""
        self.access_token = access_token or ""
        self.client_id = client_id or ""

        self._connected = False

    # ------------------------------------------------------------------
    # Static / class helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_login_url(api_key: str, redirect_uri: str) -> str:
        """Build the Upstox OAuth login URL."""
        return (
            f"{LOGIN_URL}?client_id={api_key}"
            f"&redirect_uri={redirect_uri}&response_type=code"
        )

    @classmethod
    def exchange_code_for_token(
        cls,
        code: str,
        api_key: str,
        api_secret: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """Exchange an OAuth authorisation code for tokens.

        Returns the parsed JSON response from Upstox.  Callers should handle
        ``access_token`` extraction and persistence.
        """
        url = f"{BASE_URL}/login/authorization/token"
        data = {
            "code": code,
            "client_id": api_key,
            "client_secret": api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.exception("Upstox token exchange failed: {}", exc)
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Validate the access token by fetching the user profile."""
        if not self.access_token:
            logger.error("Upstox connect failed: no access token")
            self._connected = False
            return False

        url = f"{BASE_URL}/user/profile"
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    url, headers=_headers(self.access_token), timeout=30
                ),
            )
            if response.status_code == 200:
                self._connected = True
                logger.info("Upstox connected | client_id={}", self.client_id)
                return True
            logger.warning(
                "Upstox connect failed | status={} body={}",
                response.status_code,
                response.text[:200],
            )
            self._connected = False
            return False
        except Exception as exc:
            logger.exception("Upstox connect error: {}", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Clear the session state."""
        self._connected = False
        logger.info("Upstox disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected and bool(self.access_token)

    # ------------------------------------------------------------------
    # Request helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute a synchronous ``requests`` call inside the async loop.

        Returns the ``data`` payload from the Upstox response envelope, or the
        raw JSON on unexpected shape.  Returns ``None`` on failure.
        """
        if not self.is_connected:
            logger.warning("Upstox request without connection: {} {}", method, endpoint)
            return None

        url = (
            f"{BASE_URL}{endpoint}"
            if endpoint.startswith("/")
            else f"{BASE_URL}/{endpoint}"
        )
        headers = _headers(self.access_token)

        # For form-encoded calls
        if data:
            headers.pop("Content-Type", None)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    data=data,
                    headers=headers,
                    timeout=30,
                ),
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and "data" in payload:
                return payload["data"]
            return payload
        except Exception as exc:
            logger.exception("Upstox request failed {} {}: {}", method, endpoint, exc)
            return None

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    def _build_order_payload(self, params: OrderParams) -> Dict[str, Any]:
        """Convert normalised OrderParams to Upstox v2 payload."""
        payload: Dict[str, Any] = {
            "symbol": f"{_EXCHANGE_MAP.get(params.exchange, 'NSE')}:{params.symbol}",
            "quantity": params.quantity,
            "side": _SIDE_MAP.get(params.side, "BUY"),
            "order_type": _ORDER_TYPE_MAP.get(params.order_type, "MARKET"),
            "product": _PRODUCT_MAP.get(params.product_type, "I"),
            "validity": "DAY",
        }
        if params.price > 0 and params.order_type in (OrderType.LIMIT, OrderType.SL):
            payload["price"] = params.price
        if params.trigger_price > 0 and params.order_type in (
            OrderType.SL,
            OrderType.SL_M,
        ):
            payload["trigger_price"] = params.trigger_price
        if params.tag:
            payload["tag"] = params.tag[:8]
        return payload

    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place a new order via Upstox."""
        payload = self._build_order_payload(params)
        data = await self._request("POST", "/order/place", json=payload)

        if data is None:
            return OrderResult(
                status=OrderStatus.REJECTED,
                symbol=params.symbol,
                quantity=params.quantity,
                message="Upstox order placement failed",
                timestamp=_now(),
            )

        order_id = str(data.get("order_id", "")) if isinstance(data, dict) else ""
        return OrderResult(
            order_id=order_id,
            status=OrderStatus.PENDING,
            symbol=params.symbol,
            quantity=params.quantity,
            message="Order placed on Upstox",
            timestamp=_now(),
            broker_raw=data,
        )

    async def modify_order(
        self,
        order_id: str,
        params: Dict[str, Any],
    ) -> OrderResult:
        """Modify an existing Upstox order."""
        payload: Dict[str, Any] = {"order_id": order_id}
        if "quantity" in params:
            payload["quantity"] = params["quantity"]
        if "price" in params:
            payload["price"] = params["price"]
        if "trigger_price" in params:
            payload["trigger_price"] = params["trigger_price"]
        if "order_type" in params:
            payload["order_type"] = params["order_type"]

        data = await self._request("PUT", "/order/modify", json=payload)
        if data is None:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Upstox modify order failed",
                timestamp=_now(),
            )

        new_id = (
            str(data.get("order_id", order_id)) if isinstance(data, dict) else order_id
        )
        return OrderResult(
            order_id=new_id,
            status=OrderStatus.MODIFIED,
            message="Order modified on Upstox",
            timestamp=_now(),
            broker_raw=data,
        )

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an existing Upstox order."""
        data = await self._request(
            "DELETE", "/order/cancel", json={"order_id": order_id}
        )
        if data is None:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Upstox cancel order failed",
                timestamp=_now(),
            )

        return OrderResult(
            order_id=order_id,
            status=OrderStatus.CANCELLED,
            message="Order cancelled on Upstox",
            timestamp=_now(),
            broker_raw=data,
        )

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Fetch status for a single order."""
        data = await self._request(
            "GET", "/order/details", params={"order_id": order_id}
        )
        if not isinstance(data, dict):
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found",
                timestamp=_now(),
            )

        return OrderResult(
            order_id=str(data.get("order_id", order_id)),
            status=_map_status(data.get("status")),
            symbol=str(data.get("symbol", "")).split(":")[-1],
            quantity=_safe_int(data.get("quantity")),
            filled_qty=_safe_int(data.get("filled_quantity")),
            avg_price=_safe_float(data.get("average_price")),
            message=str(data.get("status_message", "")),
            timestamp=_now(),
            broker_raw=data,
        )

    async def get_order_book(self) -> List[OrderResult]:
        """Fetch the full day's order book."""
        data = await self._request("GET", "/order/book")
        if not isinstance(data, list):
            return []

        results: List[OrderResult] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append(
                OrderResult(
                    order_id=str(item.get("order_id", "")),
                    status=_map_status(item.get("status")),
                    symbol=str(item.get("symbol", "")).split(":")[-1],
                    quantity=_safe_int(item.get("quantity")),
                    filled_qty=_safe_int(item.get("filled_quantity")),
                    avg_price=_safe_float(item.get("average_price")),
                    message=str(item.get("status_message", "")),
                    timestamp=_now(),
                    broker_raw=item,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Portfolio queries
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch short-term / day positions."""
        data = await self._request("GET", "/portfolio/short-term-positions")
        if not isinstance(data, list):
            return []

        positions: List[PositionData] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            exchange_str = str(item.get("exchange", "NSE")).upper()
            product_str = str(item.get("product", "I")).upper()
            product = {
                "I": ProductType.MIS,
                "D": ProductType.CNC,
                "M": ProductType.NRML,
            }.get(product_str, ProductType.MIS)

            qty = _safe_int(item.get("quantity"))
            positions.append(
                PositionData(
                    symbol=str(item.get("tradingsymbol", "")),
                    exchange=(
                        Exchange(exchange_str)
                        if exchange_str in Exchange._value2member_map_
                        else Exchange.NSE
                    ),
                    product=product,
                    quantity=qty,
                    avg_price=_safe_float(item.get("average_price")),
                    last_price=_safe_float(item.get("last_price")),
                    pnl=_safe_float(item.get("pnl")),
                    day_pnl=_safe_float(item.get("day_pnl")),
                    overnight_quantity=_safe_int(item.get("overnight_quantity")),
                    buy_quantity=_safe_int(item.get("buy_quantity")),
                    sell_quantity=_safe_int(item.get("sell_quantity")),
                    buy_price=_safe_float(item.get("buy_price")),
                    sell_price=_safe_float(item.get("sell_price")),
                    broker_raw=item,
                )
            )
        return positions

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch long-term Demat holdings."""
        data = await self._request("GET", "/portfolio/long-term-holdings")
        if not isinstance(data, list):
            return []

        holdings: List[HoldingData] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            exchange_str = str(item.get("exchange", "NSE")).upper()
            holdings.append(
                HoldingData(
                    symbol=str(item.get("tradingsymbol", "")),
                    exchange=(
                        Exchange(exchange_str)
                        if exchange_str in Exchange._value2member_map_
                        else Exchange.NSE
                    ),
                    quantity=_safe_int(item.get("quantity")),
                    avg_price=_safe_float(item.get("average_price")),
                    last_price=_safe_float(item.get("last_price")),
                    pnl=_safe_float(item.get("pnl")),
                    day_change_pct=_safe_float(item.get("day_change_percentage")),
                    broker_raw=item,
                )
            )
        return holdings

    async def get_funds(self) -> FundsData:
        """Fetch funds and margin information."""
        data = await self._request("GET", "/user/get-funds-and-margin")
        if not isinstance(data, dict):
            return FundsData()

        equity = data.get("equity", {}) if isinstance(data.get("equity"), dict) else {}
        available = (
            equity.get("available", {})
            if isinstance(equity.get("available"), dict)
            else {}
        )
        used = equity.get("used", {}) if isinstance(equity.get("used"), dict) else {}

        return FundsData(
            available_cash=_safe_float(available.get("cash")),
            used_margin=_safe_float(used.get("debits")),
            opening_balance=_safe_float(available.get("opening_balance")),
            payin=_safe_float(available.get("payin")),
            payout=_safe_float(available.get("payout")),
            span_margin=_safe_float(used.get("span")),
            adhoc_margin=_safe_float(used.get("adhoc")),
            exposure_margin=_safe_float(used.get("exposure")),
            available_intraday_payin=_safe_float(available.get("intraday_payin")),
            broker_raw=data,
        )

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbol: str, exchange: Exchange = Exchange.NSE) -> float:
        """Fetch the last traded price for a symbol."""
        exchange_str = _EXCHANGE_MAP.get(exchange, "NSE")
        inst = f"{exchange_str}:{symbol.upper().strip()}"
        data = await self._request("GET", "/market-quote/ltp", params={"symbol": inst})

        if not isinstance(data, dict):
            return 0.0

        quote = data.get(inst, {}) if isinstance(data.get(inst), dict) else {}
        if not quote and symbol.upper().strip() in data:
            quote = data[symbol.upper().strip()]
        return _safe_float(quote.get("last_price"))
