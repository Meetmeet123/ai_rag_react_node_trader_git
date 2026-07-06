"""
Socket.IO WebSocket server for real-time trade/signal/P&L broadcasts.

Mounted at ``/socket.io`` by ``main.py``. Clients can join rooms such as
``paper``, ``live``, or ``global`` to receive targeted events.
"""

from __future__ import annotations

from typing import Any, Dict

import socketio
from loguru import logger

from config import settings

# ---------------------------------------------------------------------------
# Socket.IO server
# ---------------------------------------------------------------------------

sio: socketio.AsyncServer = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[origin.strip() for origin in settings.FRONTEND_URL.split(",") if origin.strip()],
    logger=False,
    engineio_logger=False,
)

socket_app: socketio.ASGIApp = socketio.ASGIApp(sio, socketio_path="")


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


@sio.event
async def connect(sid: str, environ: Dict[str, Any], auth: Any = None) -> None:
    """Handle new client connections."""
    logger.info("WebSocket client connected: {}", sid)
    await sio.enter_room(sid, "global")


@sio.event
async def disconnect(sid: str) -> None:
    """Handle client disconnections."""
    logger.info("WebSocket client disconnected: {}", sid)


@sio.on("subscribe")
async def on_subscribe(sid: str, data: Any) -> None:
    """Subscribe the client to a room (e.g., ``paper`` or ``live``)."""
    room = (data.get("room") if isinstance(data, dict) else str(data)) or "global"
    await sio.enter_room(sid, room)
    logger.debug("Client {} subscribed to room {}", sid, room)


@sio.on("unsubscribe")
async def on_unsubscribe(sid: str, data: Any) -> None:
    """Unsubscribe the client from a room."""
    room = (data.get("room") if isinstance(data, dict) else str(data)) or "global"
    await sio.leave_room(sid, room)
    logger.debug("Client {} unsubscribed from room {}", sid, room)


# ---------------------------------------------------------------------------
# Broadcast helpers
# ---------------------------------------------------------------------------


async def emit_event(event: str, data: Any, room: str = "global") -> None:
    """Emit an event to all clients in a room."""
    try:
        await sio.emit(event, data, room=room)
    except Exception as exc:
        logger.warning("Failed to emit WebSocket event {}: {}", event, exc)
