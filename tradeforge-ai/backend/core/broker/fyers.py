"""
Fyers API Connector

Implements the :class:`BaseBroker` interface for Fyers trading platform.
Handles app ID + secret-based authentication, order placement, portfolio
queries, and market data retrieval via the Fyers API v2/v3.

Environment variables::

    FYERS_APP_ID       – Fyers App ID (format: <app_id>-<integer>)
    FYERS_APP_SECRET   – Fyers App Secret
    FYERS_ACCESS_TOKEN – Pre-generated access token (optional)
    FYERS_REDIRECT_URI – Redirect URI registered with Fyers

Typical usage (login flow)::

    # 1. Generate auth URL
    broker = FyersBroker(app_id="xxx", app_secret="yyy")
    auth_url = broker.get_auth_url()
    # ... user visits auth_url and authorises ...
    # ... auth_code is returned ...

    # 2. Generate access token
    token = await broker.generate_access_token(auth_code="auth_code_from_redirect")

    # 3. Trade
    await broker.connect()
    result = await broker.place_order(order_params)

Typical usage (with pre-existing token)::

    broker = FyersBroker(
        app_id="xxx", app_secret="yyy",
        access_token="existing_token",
    )
    await broker.connect()
    result = await broker.place_order(order_params)
"""

from __future__ import annotations

import os
from datetime import datetime
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
# Fyers API constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api-t1.fyers.in/api/v3"
AUTH_URL = "https://api-t1.fyers.in/api/v3/token"
DATA_URL = "https://api-t1.fyers.in/data/v3"

# Endpoints (relative to base)
PROFILE_ENDPOINT = "/profile"
FUNDS_ENDPOINT = "/funds"
HOLDINGS_ENDPOINT = "/holdings"
POSITIONS_ENDPOINT = "/positions"
ORDERS_ENDPOINT = "/orders"
ORDER_ENDPOINT = "/orders/{order_id}"
LTP_ENDPOINT = "/quotes"
HISTORY_ENDPOINT = "/history"

# Product type mapping
_PRODUCT_MAP = {
    ProductType.MIS: "INTRADAY",
    ProductType.CNC: "CNC",
    ProductType.NRML: "MARGIN",
}

_ORDER_TYPE_MAP = {
    OrderType.MARKET: "2",   # Fyers: 2 = Market
    OrderType.LIMIT: "1",    # Fyers: 1 = Limit
    OrderType.SL: "4",       # Fyers: 4 = Stop-Loss (SL-L)
    OrderType.SL_M: "3",     # Fyers: 3 = SL-M
}

_SIDE_MAP = {
    OrderSide.BUY: "1",   # Fyers: 1 = Buy
    OrderSide.SELL: "-1",  # Fyers: -1 = Sell
}

_EXCHANGE_MAP = {
    Exchange.NSE: "NSE",
    Exchange.BSE: "BSE",
    Exchange.NFO: "NFO",
    Exchange.BFO: "BFO",
    Exchange.CDS: "CDS",
    Exchange.MCX: "MCX",
}

# Status mapping
_STATUS_MAP = {
    "1": OrderStatus.EXECUTED,       # Completely executed
    "2": OrderStatus.PENDING,        # Pending
    "3": OrderStatus.REJECTED,       # Rejected
    "4": OrderStatus.CANCELLED,      # Cancelled
    "5": OrderStatus.TRANSIT,        # Transit
    "6": OrderStatus.TRIGGER_PENDING, # Trigger pending
}


# ---------------------------------------------------------------------------
# Broker implementation
# ---------------------------------------------------------------------------

class FyersBroker(BaseBroker):
    """Fyers API v3 broker connector.

    Args:
        app_id: Fyers App ID (e.g. ``ABC123-100``).
        app_secret: Fyers App Secret.
        redirect_uri: Redirect URI registered with Fyers.
        access_token: Optional pre-existing access token.
    """

    name: str = "fyers"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("FYERS_APP_ID", "")
        self.app_secret = app_secret or os.getenv("FYERS_APP_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv("FYERS_REDIRECT_URI", "https://localhost")
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN")

        self.user_id: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self._connected = False
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers = {
                "Content-Type": "application/json",
            }
            if self.access_token:
                headers["Authorization"] = f"{self.app_id}:{self.access_token}"

            self._http = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=headers,
                timeout=httpx.Timeout(30.0),
            )
        return self._http

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Parse Fyers API response envelope."""
        try:
            data = response.json()
        except Exception as exc:
            raise FyersAPIError(f"Invalid JSON response: {exc}") from exc

        # Fyers uses 's' for status: 'ok' or 'error'
        if data.get("s") == "error" or data.get("code") not in (200, None):
            msg = data.get("message", data.get("msg", "Unknown error"))
            raise FyersAPIError(f"Fyers API error: {msg}")

        return data

    # ------------------------------------------------------------------
    # Auth flow helpers
    # ------------------------------------------------------------------

    def get_auth_url(self, state: str = "tradeforge") -> str:
        """Generate the Fyers authorisation URL.

        Args:
            state: Optional state parameter for CSRF protection.

        Returns:
            Full URL to redirect the user to.
        """
        return (
            f"https://api-t1.fyers.in/api/v3/generate-authcode?"
            f"client_id={self.app_id}&redirect_uri={self.redirect_uri}&"
            f"response_type=code&state={state}"
        )

    async def generate_access_token(self, auth_code: str) -> str:
        """Exchange authorisation code for an access token.

        Args:
            auth_code: The code received in the redirect URI after user
                authorisation.

        Returns:
            Access token string.
        """
        import hashlib

        # Create SHA-256 hash of app_id + app_secret
        hash_input = f"{self.app_id}:{self.app_secret}"
        app_id_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        payload = {
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": auth_code,
        }

        try:
            response = await self._client().post(AUTH_URL, json=payload)
            data = self._handle_response(response)

            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")

            # Update client headers
            client = self._client()
            client.headers["Authorization"] = f"{self.app_id}:{self.access_token}"

            logger.info("Fyers access token generated")
            return self.access_token

        except Exception as exc:
            logger.exception("Fyers token generation failed: {}", exc)
            raise

    async def refresh_access_token(self) -> str:
        """Refresh the access token using the stored refresh token."""
        if not self.refresh_token:
            raise FyersAPIError("No refresh token available")

        payload = {
            "grant_type": "refresh_token",
            "appIdHash": self._generate_app_hash(),
            "refresh_token": self.refresh_token,
        }

        try:
            response = await self._client().post(AUTH_URL, json=payload)
            data = self._handle_response(response)

            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")

            client = self._client()
            client.headers["Authorization"] = f"{self.app_id}:{self.access_token}"

            logger.info("Fyers access token refreshed")
            return self.access_token

        except Exception as exc:
            logger.exception("Fyers token refresh failed: {}", exc)
            raise

    def _generate_app_hash(self) -> str:
        """Generate SHA-256 hash of app_id:app_secret."""
        import hashlib
        return hashlib.sha256(
            f"{self.app_id}:{self.app_secret}".encode()
        ).hexdigest()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Validate the access token by fetching user profile."""
        if not self.access_token:
            logger.error("No access token. Call generate_access_token() first.")
            return False

        try:
            response = await self._client().get(PROFILE_ENDPOINT)
            data = self._handle_response(response)

            profile = data.get("data", {})
            self.user_id = profile.get("fy_id", "")
            self._connected = True

            logger.info("Fyers connected | user={}", self.user_id)
            return True

        except Exception as exc:
            logger.exception("Fyers connect failed: {}", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close the HTTP session."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None
        self._connected = False
        logger.info("Fyers disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected and self.access_token is not None

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place order via Fyers API.

        Args:
            params: Normalised :class:`OrderParams`.

        Returns:
            :class:`OrderResult` with Fyers ``order_id``.
        """
        # Build Fyers symbol format: NSE:SBIN-EQ
        fyers_symbol = self._to_fyers_symbol(params.symbol, params.exchange)

        payload = {
            "symbol": fyers_symbol,
            "qty": params.quantity,
            "type": int(_ORDER_TYPE_MAP.get(params.order_type, "2")),
            "side": int(_SIDE_MAP.get(params.side, "1")),
            "productType": _PRODUCT_MAP.get(params.product_type, "INTRADAY"),
            "limitPrice": params.price if params.order_type == OrderType.LIMIT else 0,
            "stopPrice": params.trigger_price if params.order_type in (OrderType.SL, OrderType.SL_M) else 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
            "stopLoss": 0,
            "takeProfit": 0,
        }

        try:
            response = await self._client().post(ORDERS_ENDPOINT, json=payload)
            data = self._handle_response(response)

            order_data = data.get("data", {})
            order_id = order_data.get("id", "")

            return OrderResult(
                order_id=order_id,
                status=OrderStatus.PENDING,
                symbol=params.symbol,
                quantity=params.quantity,
                message="Order placed",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Fyers place_order failed: {}", exc)
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
        payload: Dict[str, Any] = {
            "id": order_id,
        }
        if "price" in params:
            payload["limitPrice"] = float(params["price"])
        if "quantity" in params:
            payload["qty"] = int(params["quantity"])
        if "trigger_price" in params:
            payload["stopPrice"] = float(params["trigger_price"])
        if "order_type" in params:
            payload["type"] = int(_ORDER_TYPE_MAP.get(
                OrderType(params["order_type"]), "2"
            ))

        try:
            response = await self._client().patch(ORDERS_ENDPOINT, json=payload)
            data = self._handle_response(response)

            return OrderResult(
                order_id=order_id,
                status=OrderStatus.MODIFIED,
                message="Order modified",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Fyers modify_order failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an open order."""
        payload = {"id": order_id}

        try:
            response = await self._client().delete(ORDERS_ENDPOINT, json=payload)
            data = self._handle_response(response)

            return OrderResult(
                order_id=order_id,
                status=OrderStatus.CANCELLED,
                message="Order cancelled",
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Fyers cancel_order failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get status of a single order."""
        try:
            url = ORDER_ENDPOINT.format(order_id=order_id)
            response = await self._client().get(url)
            data = self._handle_response(response)

            order_data = data.get("data", {})
            if not order_data:
                return OrderResult(
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Order not found",
                )

            status_code = str(order_data.get("status", "2"))
            return OrderResult(
                order_id=order_id,
                status=_STATUS_MAP.get(status_code, OrderStatus.PENDING),
                symbol=order_data.get("symbol", ""),
                quantity=int(order_data.get("qty", 0)),
                filled_qty=int(order_data.get("filledQty", 0)),
                avg_price=float(order_data.get("filledAvgPrice", 0) or 0),
                message=order_data.get("message", ""),
                broker_raw=order_data,
            )

        except Exception as exc:
            logger.exception("Fyers get_order_status failed: {}", exc)
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=str(exc),
            )

    async def get_order_book(self) -> List[OrderResult]:
        """Fetch all orders for the day."""
        try:
            response = await self._client().get(ORDERS_ENDPOINT)
            data = self._handle_response(response)

            order_list = data.get("orderBook", []) if isinstance(data, dict) else []
            if not order_list:
                order_list = data if isinstance(data, list) else []

            results = []
            for item in order_list:
                status_code = str(item.get("status", "2"))
                # Parse symbol from Fyers format: NSE:SBIN-EQ -> SBIN-EQ
                symbol = item.get("symbol", "").split(":")[-1]
                results.append(OrderResult(
                    order_id=item.get("id", ""),
                    status=_STATUS_MAP.get(status_code, OrderStatus.PENDING),
                    symbol=symbol,
                    quantity=int(item.get("qty", 0)),
                    filled_qty=int(item.get("filledQty", 0)),
                    avg_price=float(item.get("filledAvgPrice", 0) or 0),
                    message=item.get("message", ""),
                    broker_raw=item,
                ))
            return results

        except Exception as exc:
            logger.exception("Fyers get_order_book failed: {}", exc)
            return []

    # ------------------------------------------------------------------
    # Portfolio queries
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Fetch day and net positions."""
        try:
            response = await self._client().get(POSITIONS_ENDPOINT)
            data = self._handle_response(response)

            net_pos = data.get("netPositions", []) if isinstance(data, dict) else []
            day_pos = data.get("overall", {}) if isinstance(data, dict) else {}

            positions = []
            for item in net_pos:
                symbol = item.get("symbol", "").split(":")[-1]
                qty = int(item.get("netQty", 0))
                positions.append(PositionData(
                    symbol=symbol,
                    exchange=Exchange(item.get("exchange", "NSE")),
                    product=ProductType.MIS,
                    quantity=qty,
                    avg_price=float(item.get("buyAvg", item.get("sellAvg", 0)) or 0),
                    last_price=float(item.get("ltp", 0) or 0),
                    pnl=float(item.get("pl", 0) or 0),
                    day_pnl=float(item.get("dayPl", 0) or 0),
                    buy_quantity=int(item.get("buyQty", 0)),
                    sell_quantity=int(item.get("sellQty", 0)),
                    broker_raw=item,
                ))
            return positions

        except Exception as exc:
            logger.exception("Fyers get_positions failed: {}", exc)
            return []

    async def get_holdings(self) -> List[HoldingData]:
        """Fetch Demat holdings."""
        try:
            response = await self._client().get(HOLDINGS_ENDPOINT)
            data = self._handle_response(response)

            holdings_list = data.get("holdings", []) if isinstance(data, dict) else []
            if not holdings_list:
                holdings_list = data if isinstance(data, list) else []

            holdings = []
            for item in holdings_list:
                symbol = item.get("symbol", "").split(":")[-1]
                holdings.append(HoldingData(
                    symbol=symbol,
                    exchange=Exchange(item.get("exchange", "NSE")),
                    quantity=int(item.get("quantity", 0)),
                    avg_price=float(item.get("costPrice", 0) or 0),
                    last_price=float(item.get("ltp", 0) or 0),
                    pnl=float(item.get("pnl", 0) or 0),
                    day_change_pct=float(item.get("fyToken", 0) or 0),
                    broker_raw=item,
                ))
            return holdings

        except Exception as exc:
            logger.exception("Fyers get_holdings failed: {}", exc)
            return []

    async def get_funds(self) -> FundsData:
        """Fetch available funds and margin utilisation."""
        try:
            response = await self._client().get(FUNDS_ENDPOINT)
            data = self._handle_response(response)

            fund_limit = data.get("fund_limit", []) if isinstance(data, dict) else []

            # Parse fund_limit array
            avail = 0.0
            used = 0.0
            opening = 0.0

            for item in fund_limit:
                title = item.get("title", "").lower()
                amount = float(item.get("amount", 0) or 0)
                if "available" in title or "equity amount" in title:
                    avail = amount
                elif "used" in title or "collateral" in title:
                    used = amount
                elif "opening" in title:
                    opening = amount

            return FundsData(
                available_cash=avail,
                used_margin=used,
                opening_balance=opening,
                broker_raw=data,
            )

        except Exception as exc:
            logger.exception("Fyers get_funds failed: {}", exc)
            return FundsData()

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbol: str, exchange: Exchange = Exchange.NSE) -> float:
        """Get Last Traded Price for an instrument."""
        fyers_symbol = self._to_fyers_symbol(symbol, exchange)
        payload = {"symbols": fyers_symbol}

        try:
            response = await self._client().post(LTP_ENDPOINT, json=payload)
            data = self._handle_response(response)

            quotes = data.get("d", {})
            if isinstance(quotes, dict):
                # Single quote
                return float(quotes.get("v", {}).get("lp", 0))
            elif isinstance(quotes, list) and quotes:
                return float(quotes[0].get("v", {}).get("lp", 0))

            return 0.0

        except Exception as exc:
            logger.exception("Fyers get_ltp failed for {}: {}", symbol, exc)
            return 0.0

    async def get_ltps(
        self,
        symbols: List[str],
        exchange: Exchange = Exchange.NSE,
    ) -> Dict[str, float]:
        """Batch LTP fetch."""
        fyers_symbols = [self._to_fyers_symbol(s, exchange) for s in symbols]
        payload = {"symbols": ",".join(fyers_symbols)}

        try:
            response = await self._client().post(LTP_ENDPOINT, json=payload)
            data = self._handle_response(response)

            quotes = data.get("d", [])
            result: Dict[str, float] = {}
            for q in quotes:
                sym = q.get("n", "").split(":")[-1]
                price = float(q.get("v", {}).get("lp", 0))
                result[sym] = price

            # Fill missing with 0
            for sym in symbols:
                if sym not in result:
                    result[sym] = 0.0
            return result

        except Exception as exc:
            logger.exception("Fyers get_ltps failed: {}", exc)
            return {sym: 0.0 for sym in symbols}

    # ------------------------------------------------------------------
    # Symbol formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _to_fyers_symbol(symbol: str, exchange: Exchange) -> str:
        """Convert to Fyers symbol format: ``NSE:SBIN-EQ``."""
        ex = _EXCHANGE_MAP.get(exchange, "NSE")
        sym = symbol.upper().strip()
        # Append -EQ for equities if not already present
        if ex in ("NSE", "BSE") and "-EQ" not in sym and "-CE" not in sym and "-PE" not in sym and "FUT" not in sym:
            sym = f"{sym}-EQ"
        return f"{ex}:{sym}"

    @staticmethod
    def _from_fyers_symbol(fyers_symbol: str) -> str:
        """Convert from Fyers format to plain symbol."""
        return fyers_symbol.split(":")[-1]

    # ------------------------------------------------------------------
    # Historical data
    # ------------------------------------------------------------------

    async def get_historical_data(
        self,
        symbol: str,
        exchange: Exchange = Exchange.NSE,
        resolution: str = "1D",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical candlestick data from Fyers.

        Args:
            symbol: Trading symbol.
            exchange: Exchange enum.
            resolution: Candle resolution (``1``, ``5``, ``15``, ``60``, ``1D``).
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).

        Returns:
            List of OHLCV dicts.
        """
        fyers_symbol = self._to_fyers_symbol(symbol, exchange)

        if not from_date:
            from datetime import timedelta
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        params = {
            "symbol": fyers_symbol,
            "resolution": resolution,
            "date_format": "1",  # YYYY-MM-DD
            "range_from": from_date,
            "range_to": to_date,
            "cont_flag": "1",
        }

        try:
            response = await self._client().get(HISTORY_ENDPOINT, params=params)
            data = self._handle_response(response)

            candles = data.get("candles", [])
            results = []
            for c in candles:
                # Format: [timestamp, open, high, low, close, volume]
                if len(c) >= 6:
                    results.append({
                        "timestamp": datetime.fromtimestamp(c[0]),
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": c[5],
                    })
            return results

        except Exception as exc:
            logger.exception("Fyers get_historical_data failed: {}", exc)
            return []


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class FyersAPIError(Exception):
    """Raised when the Fyers API returns an error response."""
    pass
