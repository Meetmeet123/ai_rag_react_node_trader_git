"""
WebSocket Server for Real-Time Communication

Broadcasts live trading data across five namespaces:

    - ``/market``    — Live market ticks, OHLC candles, order-book snapshots
    - ``/signals``   — Trading signals emitted by the active model
    - ``/training``  — Training progress updates (epoch-level granularity)
    - ``/portfolio`` — Portfolio equity, open positions, P&L changes
    - ``/alerts``    — System alerts (severity-tiered)

Built on ``python-socketio`` with async ASGI support.  Clients subscribe
to namespaces they're interested in; messages are only sent to subscribed
clients, keeping bandwidth usage low.

Message flow:
    1. Producer (market ingestor / trainer / executor) calls one of the
       ``broadcast_*`` methods.
    2. Server looks up which clients are subscribed to that namespace.
    3. Messages are emitted only to those clients (Socket.IO rooms).

Example (client-side JavaScript):
    const socket = io("ws://localhost:8001");
    socket.emit("subscribe", { namespace: "signals" });
    socket.on("signal", (data) => console.log("New signal:", data));

Example (server-side broadcast):
    >>> ws = TradeForgeWebSocket()
    >>> await ws.broadcast_signal({
    ...     "symbol": "RELIANCE", "action": "buy",
    ...     "confidence": 0.85, "price": 2450.50
    ... })
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import socketio
from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Namespaces offered by the server
NAMESPACES = ["market", "signals", "training", "portfolio", "alerts"]

# Default Socket.IO configuration
DEFAULT_PING_TIMEOUT = 60
DEFAULT_PING_INTERVAL = 25


# ---------------------------------------------------------------------------
# Server class
# ---------------------------------------------------------------------------


class TradeForgeWebSocket:
    """WebSocket server for real-time trading data distribution.

    Wraps ``socketio.AsyncServer`` and provides typed broadcast helpers
    for each namespace.  Subscription tracking is done in-memory.

    Attributes:
        sio: The underlying ``AsyncServer`` instance.
        app: ASGI app that can be mounted in FastAPI/Starlette.
        clients: Map of namespace -> set of subscribed socket IDs.
    """

    def __init__(
        self,
        cors_origins: Optional[List[str]] = None,
        ping_timeout: int = DEFAULT_PING_TIMEOUT,
        ping_interval: int = DEFAULT_PING_INTERVAL,
    ) -> None:
        """Initialise the WebSocket server.

        Args:
            cors_origins: List of allowed origins for CORS.  Defaults to
                ``["*"]`` (allow all) — tighten in production.
            ping_timeout: Seconds before a client is considered disconnected.
            ping_interval: Seconds between ping packets.
        """
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=cors_origins or ["*"],
            ping_timeout=ping_timeout,
            ping_interval=ping_interval,
            logger=False,  # we use loguru
            engineio_logger=False,
        )
        self.app = socketio.ASGIApp(self.sio)

        # Per-namespace client tracking: namespace -> set(sid)
        self.clients: Dict[str, Set[str]] = {ns: set() for ns in NAMESPACES}

        # Metrics
        self.messages_broadcast: int = 0
        self.messages_dropped: int = 0
        self.client_connections_total: int = 0

        self._setup_handlers()
        logger.info("TradeForgeWebSocket initialised")

    # ------------------------------------------------------------------
    # Handler setup
    # ------------------------------------------------------------------

    def _setup_handlers(self) -> None:
        """Register all Socket.IO event handlers."""

        @self.sio.event
        async def connect(sid: str, environ: Dict[str, Any]) -> None:
            """Handle new client connection."""
            self.client_connections_total += 1
            logger.info(
                f"Client connected: {sid} (total={self.client_connections_total})"
            )
            # Auto-subscribe to 'alerts' so clients always get critical alerts
            self.clients["alerts"].add(sid)
            await self.sio.emit(
                "connected",
                {
                    "sid": sid,
                    "server_time": datetime.utcnow().isoformat(),
                    "namespaces_available": NAMESPACES,
                    "auto_subscribed": ["alerts"],
                },
                room=sid,
            )

        @self.sio.event
        async def disconnect(sid: str) -> None:
            """Handle client disconnection — clean up all subscriptions."""
            logger.info(f"Client disconnected: {sid}")
            for ns, subscribers in self.clients.items():
                if sid in subscribers:
                    subscribers.discard(sid)

        @self.sio.on("subscribe")
        async def handle_subscribe(sid: str, data: Dict[str, Any]) -> None:
            """Subscribe a client to a namespace.

            Expected data: ``{"namespace": "signals", "symbols": ["RELIANCE"]}``
            (symbols is optional and only meaningful for ``market``).
            """
            namespace = data.get("namespace", "market")
            if namespace not in NAMESPACES:
                await self.sio.emit(
                    "error",
                    {
                        "message": f"Unknown namespace '{namespace}'. Available: {NAMESPACES}"
                    },
                    room=sid,
                )
                return

            self.clients[namespace].add(sid)

            # Store per-client symbol filter (only for market namespace)
            if namespace == "market" and "symbols" in data:
                await self.sio.save_session(
                    sid, {"subscribed_symbols": set(data["symbols"])}
                )

            await self.sio.emit(
                "subscribed",
                {
                    "namespace": namespace,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=sid,
            )
            logger.debug(f"Client {sid} subscribed to {namespace}")

        @self.sio.on("unsubscribe")
        async def handle_unsubscribe(sid: str, data: Dict[str, Any]) -> None:
            """Unsubscribe a client from a namespace."""
            namespace = data.get("namespace", "market")
            if namespace in self.clients:
                self.clients[namespace].discard(sid)
            await self.sio.emit(
                "unsubscribed",
                {"namespace": namespace, "timestamp": datetime.utcnow().isoformat()},
                room=sid,
            )
            logger.debug(f"Client {sid} unsubscribed from {namespace}")

        @self.sio.on("ping_keepalive")
        async def handle_ping(sid: str, data: Dict[str, Any]) -> None:
            """Client keepalive ping — respond with pong."""
            await self.sio.emit(
                "pong_keepalive", {"server_time": time.time()}, room=sid
            )

        @self.sio.on("get_status")
        async def handle_get_status(sid: str, data: Dict[str, Any]) -> None:
            """Return server status to requesting client."""
            status = {
                "server_time": datetime.utcnow().isoformat(),
                "namespaces": {ns: len(subs) for ns, subs in self.clients.items()},
                "total_connections": self.client_connections_total,
                "messages_broadcast": self.messages_broadcast,
                "messages_dropped": self.messages_dropped,
            }
            await self.sio.emit("server_status", status, room=sid)

    # ------------------------------------------------------------------
    # Broadcast helpers — one per namespace
    # ------------------------------------------------------------------

    async def broadcast_market_tick(self, tick: Dict[str, Any]) -> int:
        """Broadcast a market tick to all ``/market`` subscribers.

        Args:
            tick: Dict with at minimum ``symbol``, ``price``, ``timestamp``.

        Returns:
            Number of clients the message was sent to.
        """
        return await self._broadcast_to_namespace("market", "tick", tick)

    async def broadcast_ohlcv(self, candle: Dict[str, Any]) -> int:
        """Broadcast a completed OHLCV candle.

        Args:
            candle: Dict with ``timestamp``, ``open``, ``high``, ``low``,
                ``close``, ``volume``, ``symbol``.
        """
        return await self._broadcast_to_namespace("market", "ohlcv", candle)

    async def broadcast_signal(self, signal: Dict[str, Any]) -> int:
        """Broadcast a trading signal.

        Args:
            signal: Dict with ``signal_id``, ``symbol``, ``action``,
                ``confidence``, ``timestamp``, ``price_at_signal``.
        """
        return await self._broadcast_to_namespace("signals", "signal", signal)

    async def broadcast_training_progress(self, progress: Dict[str, Any]) -> int:
        """Broadcast a training-progress update.

        Args:
            progress: Dict with ``job_id``, ``event``, ``epoch``,
                ``total_epochs``, ``loss``, ``val_loss``, etc.
        """
        return await self._broadcast_to_namespace("training", "progress", progress)

    async def broadcast_portfolio_update(self, update: Dict[str, Any]) -> int:
        """Broadcast a portfolio / position update.

        Args:
            update: Dict with ``timestamp``, ``total_equity``,
                ``open_positions``, ``daily_pnl``, etc.
        """
        return await self._broadcast_to_namespace("portfolio", "update", update)

    async def broadcast_alert(self, alert: Dict[str, Any]) -> int:
        """Broadcast a system alert to all connected clients.

        Alerts bypass the normal subscription filter and go to everyone
        (since alerts are auto-subscribed).

        Args:
            alert: Dict with ``severity``, ``category``, ``title``,
                ``message``, ``timestamp``, optional ``metadata``.
        """
        # Enrich with timestamp if missing
        if "timestamp" not in alert:
            alert["timestamp"] = datetime.utcnow().isoformat()

        # Add alert_id if missing
        if "alert_id" not in alert:
            alert["alert_id"] = f"alert-{int(time.time() * 1000)}"

        return await self._broadcast_to_namespace("alerts", "alert", alert)

    # ------------------------------------------------------------------
    # Targeted messaging
    # ------------------------------------------------------------------

    async def send_to_client(self, sid: str, event: str, data: Dict[str, Any]) -> bool:
        """Send a message to a specific client.

        Args:
            sid: Socket.IO session ID.
            event: Event name.
            data: Payload dict.

        Returns:
            ``True`` if the client exists and message was sent.
        """
        try:
            await self.sio.emit(event, data, room=sid)
            return True
        except Exception as exc:
            logger.warning(f"Failed to send to client {sid}: {exc}")
            return False

    async def broadcast_to_all(self, event: str, data: Dict[str, Any]) -> int:
        """Broadcast a message to **all** connected clients regardless
        of namespace subscriptions.

        Use sparingly — prefer namespace-scoped broadcasts.

        Returns:
            Number of recipients.
        """
        try:
            await self.sio.emit(event, data)
            self.messages_broadcast += 1
            # Approximate count
            all_sids = set()
            for sids in self.clients.values():
                all_sids.update(sids)
            return len(all_sids)
        except Exception as exc:
            logger.error(f"Broadcast to all failed: {exc}")
            return 0

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _broadcast_to_namespace(
        self,
        namespace: str,
        event: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit an event to all clients subscribed to a namespace.

        Args:
            namespace: One of the registered namespace names.
            event: Socket.IO event name.
            data: Payload dictionary.

        Returns:
            Number of clients the message was delivered to.
        """
        subscribers = self.clients.get(namespace, set())
        if not subscribers:
            self.messages_dropped += 1
            return 0

        # Enrich data with server timestamp
        enriched = {
            **data,
            "_server_ts": datetime.utcnow().isoformat(),
            "_ns": namespace,
        }

        count = 0
        for sid in list(subscribers):
            try:
                await self.sio.emit(event, enriched, room=sid)
                count += 1
            except Exception as exc:
                logger.debug(f"Emit to {sid} failed: {exc}")
                subscribers.discard(sid)

        self.messages_broadcast += count
        return count

    # ------------------------------------------------------------------
    # Admin / introspection
    # ------------------------------------------------------------------

    def get_subscriber_counts(self) -> Dict[str, int]:
        """Return number of subscribers per namespace."""
        return {ns: len(subs) for ns, subs in self.clients.items()}

    def get_total_unique_clients(self) -> int:
        """Count unique connected clients across all namespaces."""
        all_sids: Set[str] = set()
        for sids in self.clients.values():
            all_sids.update(sids)
        return len(all_sids)

    def reset_metrics(self) -> None:
        """Reset broadcast/drop counters."""
        self.messages_broadcast = 0
        self.messages_dropped = 0

    def __repr__(self) -> str:
        counts = self.get_subscriber_counts()
        return (
            f"<TradeForgeWebSocket clients={self.get_total_unique_clients()} "
            f"subscribers={counts} broadcast={self.messages_broadcast}>"
        )
