"""
Angel One SmartAPI Connector

Implements the :class:`BaseBroker` interface for Angel One trading.
Handles JWT authentication via TOTP, order placement, portfolio queries,
and market data retrieval using the SmartAPI v1 endpoints.

Environment variables::

    ANGEL_ONE_API_KEY      – SmartAPI app key
    ANGEL_ONE_CLIENT_ID    – Client code (user id)
    ANGEL_ONE_PASSWORD     – Login password
    ANGEL_ONE_TOTP_SECRET  – TOTP secret for 2FA

Typical usage::

    broker = AngelOneBroker(
        api_key="...", client_id="...", password="...", totp_secret="..."
    )
    await broker.connect()
    result = await broker.place_order(order_params)
"""

from __future__ import annotations

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
# Angel One SmartAPI constants
# ---------------------------------------------------------------------------

BASE_URL = "https://apiconnect.angelone.in"
LOGIN_URL = f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
ORDER_URL = f"{BASE_URL}/rest/secure/angelbroking/order/v1/placeOrder"
MODIFY_ORDER_URL = f"{BASE_URL}/rest/secure/angelbroking/order/v1/modifyOrder"
CANCEL_ORDER_URL = f"{BASE_URL}/rest/secure/angelbroking/order/v1/cancelOrder"
ORDER_BOOK_URL = f"{BASE_URL}/rest/secure/angelbroking/order/v1/getOrderBook"
POSITIONS_URL = f"{BASE_URL}/rest/secure/angelbroking/order/v1/getPosition"
HOLDINGS_URL = f"{BASE_URL}/rest/secure/angelbroking/portfolio/v1/getHolding"
FUNDS_URL = f"{BASE_URL}/rest/secure/angelbroking/user/v1/getRMS"
LTP_URL = f"{BASE_URL}/rest/secure/angelbroking/order/v1/getLtpData"

# Exchange token mappings for LTP
_EXCHANGE_MAP = {
    Exchange.NSE: "NSE",
    Exchange.BSE: "BSE",
    Exchange.NFO: "NFO",
    Exchange.BFO: "BFO",
    Exchange.MCX: "MCX",
    Exchange.CDS: "CDS",
}

_PRODUCT_MAP = {
    ProductType.MIS: "INTRADAY",
    ProductType.CNC: "DELIVERY",
    ProductType.NRML: "CARRYFORWARD",
}

_ORDER_TYPE_MAP = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "STOPLOSS_LIMIT",
    OrderType.SL_M: "STOPLOSS_MARKET",
}

_SIDE_MAP = {
    OrderSide.BUY: "BUY",
    OrderSide.SELL: "SELL",
}

# Reverse status mapping
_STATUS_MAP = {
    "complete": OrderStatus.COMPLETE,
    "rejected": OrderStatus.REJECTED,
    "cancelled": OrderStatus.CANCELLED,
    "open": OrderStatus.OPEN,
    "pending": OrderStatus.PENDING,
    "after market": OrderStatus.AFTER_MARKET,
    "amo req received": OrderStatus.AMO_REQ_RECEIVED,
    "modification": OrderStatus.MODIFIED,
}


# ---------------------------------------------------------------------------
# Broker implementation
# ---------------------------------------------------------------------------


class AngelOneBroker(BaseBroker):
    """Angel One SmartAPI broker connector.

    Args:
        api_key: SmartAPI application key.
        client_id: Angel One client code (user ID).
        password: Account password.
        totp_secret: TOTP secret for two-factor authentication.
    """

    name: str = "angel_one"

    def __init__(
        self,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        password: Optional[str] = None,
        totp_secret: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ANGEL_ONE_API_KEY", "")
        self.client_id = client_id or os.getenv("ANGEL_ONE_CLIENT_ID", "")
        self.password = password or os.getenv("ANGEL_ONE_PASSWORD", "")
        self.totp_secret = totp_secret or os.getenv("ANGEL_ONE_TOTP_SECRET", "")

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self._connected = False

        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "",
                "X-ClientPublicIP": "",
                "X-MACAddress": "",
            }
            if self.api_key:
                headers["X-PrivateKey"] = self.api_key
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            self._http = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=headers,
                timeout=httpx.Timeout(30.0),
            )
        return self._http

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Parse and validate SmartAPI response envelope."""
        try:
            data = response.json()
        except Exception as exc:
            raise BrokerAPIError(f"Invalid JSON response: {exc}") from exc

        if not data.get("status"):
            error_msg = data.get("message", "Unknown error")
            error_code = data.get("errorcode", "")
            raise BrokerAPIError(f"SmartAPI error: {error_msg} (code={error_code})")

        return data.get("data", {})

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Authenticate with SmartAPI and obtain access token.

        Uses TOTP-based two-factor authentication.
        """
        try:
            import pyotp
        except ImportError:
            logger.error("pyotp not installed. Run: pip install pyotp")
            return False

        totp = pyotp.TOTP(self.totp_secret)
        totp_code = totp.now()

        payload = {
            "clientcode": self.client_id,
            "password": self.password,
            "totp": totp_code,
        }

        client = self._client()
        # Remove auth header for login
        original_auth = client.headers.pop("Authorization", None)

        try:
            response = await client.post(LOGIN_URL, json=payload)
            response.raise_for_status()
            data = self._handle_response(response)

            self.access_token = data.get("jwtToken")
            self.refresh_token = data.get("refreshToken")
            self.feed_token = data.get("feedToken")

            # Update headers with new token
            if self.access_token:
                client.headers["Authorization"] = f"Bearer {self.access_token}"

            self._connected = True
            logger.info(
                "AngelOne connected | client={}",
                self.client_id,
            )
            return True

        except Exception as exc:
            logger.exception("AngelOne login failed: {}", exc)
            self._connected = False
            return False

        finally:
            if original_auth:
                client.headers["Authorization"] = original_auth

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None
        self._connected = False
        self.access_token = None
        logger.info("AngelOne disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected and self.access_token is not None

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place order via SmartAPI.

        Args:
            params: Normalised :class:`OrderParams`.

        Returns:
            :class:`OrderResult` with Angel One ``order_id``.
        """
        payload = {
            "variety": "NORMAL",
            "tradingsymbol": params.symbol,
            "symboltoken": params.metadata.get("token", ""),
            "transactiontype": _SIDE_MAP.get(params.side, "BUY"),
            "exchange": _EXCHANGE_MAP.get(params.exchange, "NSE"),
            "ordertype": _ORDER_TYPE_MAP.get(params.order_type, "MARKET"),
            "producttype": _PRODUCT_MAP.get(params.product_type, "INTRADAY"),
            "duration": "DAY",
            "price": str(params.price),
            "squareoff": "0",
            "stoploss": str(params.trigger_price),
            "quantity": str(params.quantity),
        }

        try:
            response = await self._client().post(ORDER_URL, json=payload)
            data = self._handle_response(response)

            order_id = data.get("orderid", "")
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.OPEN,
                symbol=params.symbol,
                quantity=params.quantity,
                message="Order placed",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("AngelOne place_order failed: {}", exc)
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
        payload = {
            "variety": "NORMAL",
            "orderid": order_id,
            "ordertype": params.get("order_type", "MARKET"),
            "producttype": params.get("product_type", "INTRADAY"),
            "duration": "DAY",
            "price": str(params.get("price", 0)),
            "quantity": str(params.get("quantity", 0)),
            "tradingsymbol": params.get("symbol", ""),
            "symboltoken": params.get("token", ""),
            "exchange": params.get("exchange", "NSE"),
        }

        try:
            response = await self._client().post(MODIFY_ORDER_URL, json=payload)
            data = self._handle_response(response)

            return OrderResult(
                order_id=order_id,
                status=OrderStatus.MODIFIED,
                symbol=params.get("symbol", ""),
                message="Order modified",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("AngelOne modify_order failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an open order."""
        payload = {
            "variety": "NORMAL",
            "orderid": order_id,
        }

        try:
            response = await self._client().post(CANCEL_ORDER_URL, json=payload)
            data = self._handle_response(response)

            return OrderResult(
                order_id=order_id,
                status=OrderStatus.CANCELLED,
                message="Order cancelled",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("AngelOne cancel_order failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get status of a single order from the order book."""
        try:
            orders = await self.get_order_book()
            for order in orders:
                if order.order_id == order_id:
                    return order
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found in order book",
            )
        except Exception as exc:
            logger.exception("AngelOne get_order_status failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def get_order_book(self) -> List[OrderResult]:
        """Fetch the full order book."""
        try:
            response = await self._client().post(ORDER_BOOK_URL)
            data = self._handle_response(response)

            if not isinstance(data, list):
                data = [data] if data else []

            results = []
            for item in data:
                status_str = str(item.get("status", "")).lower()
                results.append(
                    OrderResult(
                        order_id=item.get("orderid", ""),
                        status=_STATUS_MAP.get(status_str, OrderStatus.PENDING),
                        symbol=item.get("tradingsymbol", ""),
                        quantity=int(item.get("quantity", 0)),
                        filled_qty=int(item.get("filledshares", 0)),
                        avg_price=float(item.get("averageprice", 0) or 0),
                        message=item.get("text", ""),
                        broker_raw=item,
                    )
                )
            return results

        except Exception as exc:
            logger.exception("AngelOne get_order_book failed: {}", exc)
            return []

    # ------------------------------------------------------------------
    # Portfolio queries
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch day and net positions."""
        try:
            response = await self._client().post(POSITIONS_URL)
            data = self._handle_response(response)

            positions = []
            day_positions = (
                data.get("dayWisePosition", []) if isinstance(data, dict) else []
            )
            net_positions = (
                data.get("netWisePosition", []) if isinstance(data, dict) else []
            )

            for pos_list in [day_positions, net_positions]:
                for item in pos_list:
                    qty = int(
                        item.get("netqty", 0)
                        or item.get("buyqty", 0) - item.get("sellqty", 0)
                    )
                    positions.append(
                        PositionData(
                            symbol=item.get("tradingsymbol", ""),
                            exchange=Exchange(item.get("exchange", "NSE")),
                            product=ProductType.MIS,
                            quantity=qty,
                            avg_price=float(
                                item.get("netavg", item.get("buyavgprice", 0)) or 0
                            ),
                            last_price=float(item.get("ltp", 0) or 0),
                            pnl=float(item.get("pnl", 0) or 0),
                            day_pnl=float(item.get("daybuyamt", 0) or 0),
                            broker_raw=item,
                        )
                    )
            return positions

        except Exception as exc:
            logger.exception("AngelOne get_positions failed: {}", exc)
            return []

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch Demat holdings."""
        try:
            response = await self._client().post(HOLDINGS_URL)
            data = self._handle_response(response)

            if not isinstance(data, list):
                data = data if isinstance(data, list) else []

            holdings = []
            for item in data:
                holdings.append(
                    HoldingData(
                        symbol=item.get("tradingsymbol", ""),
                        exchange=Exchange(item.get("exchange", "NSE")),
                        quantity=int(item.get("quantity", 0)),
                        avg_price=float(item.get("averageprice", 0) or 0),
                        last_price=float(item.get("ltp", 0) or 0),
                        pnl=float(item.get("profitandloss", 0) or 0),
                        day_change_pct=float(item.get("daychangepercentage", 0) or 0),
                        broker_raw=item,
                    )
                )
            return holdings

        except Exception as exc:
            logger.exception("AngelOne get_holdings failed: {}", exc)
            return []

    async def get_funds(self) -> FundsData:
        """Fetch RMS / fund limits."""
        try:
            response = await self._client().post(FUNDS_URL)
            data = self._handle_response(response)

            return FundsData(
                available_cash=float(data.get("net", 0) or 0),
                used_margin=float(data.get("m2mrealized", 0) or 0),
                opening_balance=float(data.get("availablecash", 0) or 0),
                payin=float(data.get("collateral", 0) or 0),
                span_margin=float(data.get("spanmargin", 0) or 0),
                adhoc_margin=float(data.get("adhocmargin", 0) or 0),
                exposure_margin=float(data.get("exposuremargin", 0) or 0),
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("AngelOne get_funds failed: {}", exc)
            return FundsData()

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbol: str, exchange: Exchange = Exchange.NSE) -> float:
        """Get Last Traded Price for an instrument."""
        # Token resolution would normally require an instrument master lookup
        # For now, we use the symbol directly with a default token
        payload = {
            "exchange": _EXCHANGE_MAP.get(exchange, "NSE"),
            "tradingsymbol": symbol,
            "symboltoken": "",  # Will be resolved
        }

        try:
            response = await self._client().post(LTP_URL, json=payload)
            data = self._handle_response(response)
            return float(data.get("ltp", 0) or data.get("data", {}).get("ltp", 0))

        except Exception as exc:
            logger.exception("AngelOne get_ltp failed for {}: {}", symbol, exc)
            return 0.0


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class BrokerAPIError(Exception):
    """Raised when the broker API returns an error response."""

    pass
