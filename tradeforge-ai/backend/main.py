"""
TradeForge AI -- Main FastAPI Application

Custom LLM-powered auto-trading platform with:
- Strategy generation from natural language
- Backtesting engine
- Auto-training pipeline (every 20 minutes)
- Live trade execution
- Real-time WebSocket streaming
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Deque, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_client import make_asgi_app, Counter
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database.connection import init_db, close_db
from websocket_server import socket_app

# ---------------------------------------------------------------------------
# Configure structured logging
# ---------------------------------------------------------------------------

logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG" if settings.DEBUG else "INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)
logger.add(
    "logs/tradeforge.log",
    level="INFO",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

# ---------------------------------------------------------------------------
# Global service instances (initialized on startup)
# ---------------------------------------------------------------------------

services: Dict[str, Any] = {}

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events -- startup and shutdown."""
    # =====================================================================
    # Startup
    # =====================================================================
    logger.info("=" * 60)
    logger.info(f"  Starting {settings.APP_NAME} v2.0.0")
    logger.info("=" * 60)

    # -- Initialize Sentry (optional) ---------------------------------------
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)
        logger.info("Sentry error reporting initialized")

    # -- Initialize database ------------------------------------------------
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as exc:
        logger.error("Database initialization failed: {}", exc)
        raise

    # -- Initialize core services -------------------------------------------
    from core.llm_engine import LLMEngine
    from core.backtest_engine import BacktestEngine
    from core.broker.paper_broker import PaperBroker
    from core.risk_manager import RiskManager
    from core.model_registry import ModelRegistry
    from core.market_data.ingestor import MarketDataIngestor
    from core.execution_engine import ExecutionEngine, ExecutionMode
    from core.auto_trainer import AutoTrainingPipeline
    from training.dataset_builder import StrategyDatasetBuilder

    services["llm"] = LLMEngine()
    logger.info("LLM Engine initialized")

    services["backtest"] = BacktestEngine()
    logger.info("Backtest Engine initialized")

    services["broker"] = PaperBroker()
    logger.info("Paper Broker initialized")

    services["risk"] = RiskManager({
        "daily_loss_limit": settings.MAX_DAILY_LOSS_PCT / 100 * settings.DEFAULT_CAPITAL,
        "max_positions": settings.MAX_POSITIONS,
    })
    logger.info("Risk Manager initialized")

    services["registry"] = ModelRegistry(models_dir=settings.MODELS_DIR)
    logger.info("Model Registry initialized")

    services["ingestor"] = MarketDataIngestor(data_dir=settings.HISTORICAL_DATA_DIR)
    logger.info("Market Data Ingestor initialized")

    services["dataset_builder"] = StrategyDatasetBuilder()
    logger.info("Dataset Builder initialized")

    # -- Initialize execution engine ----------------------------------------
    engine = ExecutionEngine(
        broker=services["broker"],
        risk_manager=services["risk"],
        mode=ExecutionMode.PAPER,
    )
    services["execution"] = engine
    logger.info("Execution Engine initialized (paper mode)")

    # -- Try to load an active live broker configuration ----------------------
    async def _load_active_broker() -> None:
        """Replace the paper broker with a live broker if a config exists."""
        from core.broker.factory import create_broker_from_config
        from database.models import BrokerConfig, BrokerName

        try:
            active_config = await BrokerConfig.find_one(
                BrokerConfig.is_active == True,
                BrokerConfig.is_paper == False,
                BrokerConfig.broker != BrokerName.PAPER,
            )
            if active_config is None:
                logger.info("No active live broker config found; staying in paper mode")
                return

            logger.info(
                "Active live broker config found | broker={}",
                active_config.broker.value,
            )
            live_broker = create_broker_from_config(active_config)
            connected = await live_broker.connect()
            if connected:
                services["broker"] = live_broker
                new_engine = ExecutionEngine(
                    broker=live_broker,
                    risk_manager=services["risk"],
                    mode=ExecutionMode.LIVE,
                )
                # Carry over callbacks
                new_engine.callbacks["on_trade"] = engine.callbacks.get("on_trade")
                services["execution"] = new_engine
                execute_router.set_engine_instance(new_engine)
                brokers_router.set_broker_instance(live_broker)
                brokers_router.set_execution_engine(new_engine)
                active_config.is_connected = True
                active_config.last_connected_at = datetime.utcnow()
                await active_config.save()
                logger.info(
                    "Switched to live broker | broker={}",
                    live_broker.name,
                )
            else:
                active_config.is_connected = False
                await active_config.save()
                logger.warning(
                    "Failed to connect to live broker | broker={}; staying in paper mode",
                    active_config.broker.value,
                )
        except Exception as exc:
            logger.warning("Could not load active live broker: {}", exc)

    # -- Wire real-time WebSocket broadcasts --------------------------------
    from websocket_server import emit_event

    async def _emit_trade_update(signal: Any, result: Any) -> None:
        await emit_event(
            "trade",
            {
                "signal": signal.model_dump() if hasattr(signal, "model_dump") else signal,
                "result": result.model_dump() if hasattr(result, "model_dump") else result,
            },
            room="paper",
        )
        current_engine = services.get("execution")
        if current_engine is not None:
            await emit_event("portfolio_update", current_engine.get_portfolio_summary(), room="paper")

    engine.callbacks["on_trade"] = _emit_trade_update
    logger.info("WebSocket broadcast callbacks wired")

    # -- Initialize RAG engine ----------------------------------------------
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.DATA_DIR, "chromadb"), exist_ok=True)

        import rag_service

        services["rag"] = rag_service.get_rag()
        services["rag"].start_ingestion(tracked_symbols=["NIFTY50"])
        logger.info("RAG engine initialized")
    except Exception as exc:
        logger.warning("RAG engine failed to initialize: {}", exc)

    # -- Initialize auto-training pipeline ----------------------------------
    pipeline = AutoTrainingPipeline(
        llm_engine=services["llm"],
        backtest_engine=services["backtest"],
        model_registry=services["registry"],
        dataset_builder=services["dataset_builder"],
        training_interval_minutes=settings.TRAINING_INTERVAL_MINUTES,
        models_dir=settings.MODELS_DIR,
    )
    services["pipeline"] = pipeline
    logger.info(
        "Auto-Training Pipeline initialized ({}-min interval)",
        settings.TRAINING_INTERVAL_MINUTES,
    )

    # -- Inject singletons into routers -------------------------------------
    from routers import train as train_router
    from routers import models as models_router
    from routers import execute as execute_router
    from routers import market as market_router
    from routers import brokers as brokers_router

    train_router.set_pipeline_instance(pipeline)
    train_router.set_registry_instance(services["registry"])
    models_router.set_registry_instance(services["registry"])
    execute_router.set_engine_instance(services["execution"])
    execute_router.set_risk_instance(services["risk"])
    market_router.set_ingestor_instance(services["ingestor"])
    brokers_router.set_broker_instance(services["broker"])
    brokers_router.set_execution_engine(services["execution"])

    logger.info("Router singletons injected")

    # -- Try to load an active live broker configuration ----------------------
    await _load_active_broker()

    # -- Start auto-training (if configured) --------------------------------
    try:
        pipeline.start()
        logger.info("Auto-training scheduler started")
    except Exception as exc:
        logger.warning("Auto-training scheduler failed to start: {}", exc)

    logger.info("All services initialized successfully")
    logger.info("TradeForge AI is ready")

    yield

    # =====================================================================
    # Shutdown
    # =====================================================================
    logger.info("Shutting down {}...", settings.APP_NAME)

    # Stop auto-training
    try:
        if "pipeline" in services:
            services["pipeline"].stop()
            logger.info("Auto-training scheduler stopped")
    except Exception as exc:
        logger.warning("Error stopping auto-training: {}", exc)

    # Disconnect broker
    try:
        if "broker" in services:
            await services["broker"].disconnect()
            logger.info("Broker disconnected")
    except Exception as exc:
        logger.warning("Error disconnecting broker: {}", exc)

    # Close market data ingestor
    try:
        if "ingestor" in services:
            await services["ingestor"].close()
            logger.info("Market data ingestor closed")
    except Exception as exc:
        logger.warning("Error closing ingestor: {}", exc)

    # Close RAG engine
    try:
        if "rag" in services:
            services["rag"].close()
            logger.info("RAG engine closed")
    except Exception as exc:
        logger.warning("Error closing RAG engine: {}", exc)

    # Close MongoDB connection
    try:
        await close_db()
        logger.info("Database connection closed")
    except Exception as exc:
        logger.warning("Error closing database connection: {}", exc)

    logger.info("{} shutdown complete", settings.APP_NAME)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Custom LLM-powered auto-trading platform with auto-training pipeline.\n\n"
        "## Features\n"
        "- **LLM Strategy Generation**: Convert natural language to trading strategies\n"
        "- **Backtesting**: Full-featured backtest engine with realistic execution\n"
        "- **Auto-Training**: Model retraining every 20 minutes\n"
        "- **Live Execution**: Paper and live trading with risk management\n"
        "- **WebSocket**: Real-time market data, signals, and training progress\n"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Security & CORS configuration
# ---------------------------------------------------------------------------

_origins = [origin.strip() for origin in settings.FRONTEND_URL.split(",") if origin.strip()]
if settings.DEBUG:
    _origins.extend(["http://localhost:3000", "http://127.0.0.1:5173"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter (requests per IP per minute)."""

    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, Deque[float]] = defaultdict(lambda: Deque(maxlen=max_requests * 2))

    async def dispatch(self, request: Request, call_next):
        # Exclude the Prometheus metrics endpoint from rate limiting.
        if request.url.path.startswith("/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = self.requests[client_ip]
        while window and window[0] < now - self.window_seconds:
            window.popleft()
        if len(window) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": True, "status_code": 429, "detail": "Rate limit exceeded. Please slow down."},
            )
        window.append(now)
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log requests with a correlation ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or os.urandom(8).hex()
        request.state.request_id = request_id
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        REQUEST_COUNT.labels(
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        ).inc()
        logger.info(
            "{} {} {} - {} - {}ms - request_id={}",
            request.method,
            request.url.path,
            response.status_code,
            request.client.host if request.client else "-",
            f"{duration:.1f}",
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


# Paths that are excluded from auth-state lookup and audit logging.
_AUDIT_SKIP_PATHS = {
    "/metrics",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

_OBJECT_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


class AuthStateMiddleware(BaseHTTPMiddleware):
    """Resolve the current user from the JWT and attach it to request state."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _AUDIT_SKIP_PATHS or path.startswith("/socket.io"):
            request.state.current_user = None
            return await call_next(request)

        user: Optional[Any] = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            from routers.auth import get_current_user_optional

            token = auth_header[7:]
            try:
                user = await get_current_user_optional(token)
            except Exception as exc:
                logger.debug("Could not resolve current user for audit: {}", exc)

        request.state.current_user = user
        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Fire-and-forget audit logging for mutating HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Skip health, docs, metrics, and WebSocket endpoints.
        if path in _AUDIT_SKIP_PATHS or path.startswith("/socket.io"):
            return await call_next(request)

        # Skip authentication endpoints to avoid capturing credentials.
        if method == "POST" and path in {"/api/v1/auth/login", "/api/v1/auth/register"}:
            return await call_next(request)

        # Extract resource_id if the last path segment looks like an ObjectId.
        resource_id: Optional[str] = None
        last_segment = path.rstrip("/").rsplit("/", 1)[-1]
        if _OBJECT_ID_RE.match(last_segment):
            resource_id = last_segment

        # Build a sanitized details payload for JSON mutating requests (read
        # before the route handler consumes the body so it is cached for
        # downstream use).
        details: Optional[Dict[str, Any]] = None
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                content_length = request.headers.get("content-length")
                try:
                    too_large = content_length is not None and int(content_length) > 2048
                except ValueError:
                    too_large = False

                if not too_large:
                    try:
                        from core.sanitization import sanitize_dict

                        body = await request.body()
                        payload = json.loads(body) if body else {}
                        details = sanitize_dict(payload)
                        details_json = json.dumps(details, default=str)
                        if len(details_json) > 2048:
                            details = {"_summary": details_json[:2048]}
                    except Exception:
                        details = None

        response = await call_next(request)

        # Only log mutating methods.
        if method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return response

        user = getattr(request.state, "current_user", None)

        log_entry = {
            "user_id": str(user.id) if user is not None else None,
            "username": getattr(user, "username", None),
            "role": getattr(user, "role", None),
            "action": method,
            "resource": path,
            "resource_id": resource_id,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "status_code": response.status_code,
            "details": details,
        }

        asyncio.create_task(
            self._insert_audit_log(log_entry),
            name=f"audit-log-{method}-{path}",
        )
        return response

    @staticmethod
    async def _insert_audit_log(log_entry: Dict[str, Any]) -> None:
        try:
            from database.models import AuditLog

            await AuditLog(**log_entry).insert()
        except Exception as exc:
            logger.warning("Failed to insert audit log: {}", exc)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthStateMiddleware)
app.add_middleware(AuditLogMiddleware)

# Mount Socket.IO application at /socket.io
app.mount("/socket.io", socket_app)

# Mount Prometheus metrics endpoint at /metrics
app.mount("/metrics", make_asgi_app())

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

from routers import auth, analytics, settings as settings_router, llm, strategies, backtest, train, models, execute, market, brokers, audit as audit_router

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["Strategies"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtest"])
app.include_router(train.router, prefix="/api/v1/train", tags=["Training"])
app.include_router(models.router, prefix="/api/v1/models", tags=["Models"])
app.include_router(execute.router, prefix="/api/v1/execute", tags=["Execution"])
app.include_router(market.router, prefix="/api/v1/market", tags=["Market Data"])
app.include_router(brokers.router, prefix="/api/v1/brokers", tags=["Brokers"])
app.include_router(audit_router.router, prefix="/api/v1/audit-logs", tags=["Audit"])

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Format HTTP exceptions as consistent JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler."""
    logger.exception("Unhandled exception: {}", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "Internal server error",
        },
    )


# ---------------------------------------------------------------------------
# Root & health endpoints
# ---------------------------------------------------------------------------


@app.get("/", summary="Root endpoint", tags=["Status"])
async def root() -> Dict[str, Any]:
    """Get application info and available features."""
    return {
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "status": "running",
        "features": [
            "llm_strategy_generation",
            "strategy_crud",
            "backtesting",
            "auto_training_20min",
            "live_execution",
            "paper_trading",
            "risk_management",
            "model_registry",
            "market_data",
            "websocket_streaming",
        ],
        "api_prefix": "/api/v1",
        "docs": "/docs",
    }


@app.get("/health", summary="Health check", tags=["Status"])
async def health_check() -> Dict[str, Any]:
    """Get health status of all services."""
    service_status = {}
    for name, svc in services.items():
        try:
            if hasattr(svc, "is_ready"):
                service_status[name] = "up" if svc.is_ready() else "degraded"
            elif hasattr(svc, "is_halted"):
                service_status[name] = "up (halted)" if svc.is_halted else "up"
            elif hasattr(svc, "_is_running"):
                service_status[name] = "running" if svc._is_running else "idle"
            else:
                service_status[name] = "up"
        except Exception:
            service_status[name] = "error"

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "services": service_status,
    }


@app.get("/api/v1/status", summary="System status", tags=["Status"])
async def system_status() -> Dict[str, Any]:
    """Get complete system status including all services and configuration."""
    try:
        registry = services.get("registry")
        pipeline = services.get("pipeline")
        risk = services.get("risk")
        broker = services.get("broker")

        active_model = None
        if registry:
            av = registry.get_active_version()
            if av:
                active_model = {
                    "version_id": av.version_id,
                    "version_name": av.version_name,
                    "accuracy": av.accuracy,
                    "f1_score": av.f1_score,
                }

        pipeline_status = pipeline.get_status() if pipeline else {}

        return {
            "app": settings.APP_NAME,
            "version": "2.0.0",
            "status": "running",
            "config": {
                "default_capital": settings.DEFAULT_CAPITAL,
                "default_timeframe": settings.DEFAULT_TIMEFRAME,
                "max_positions": settings.MAX_POSITIONS,
                "max_daily_loss_pct": settings.MAX_DAILY_LOSS_PCT,
                "training_interval_min": settings.TRAINING_INTERVAL_MINUTES,
                "market_open": settings.MARKET_OPEN_TIME,
                "market_close": settings.MARKET_CLOSE_TIME,
            },
            "active_model": active_model,
            "pipeline": pipeline_status,
            "risk_summary": risk.get_risk_summary() if risk else {},
            "broker": {
                "name": broker.name if broker else "unknown",
                "connected": broker.is_connected if broker else False,
                "balance": broker.get_balance() if broker else 0,
            } if broker else {},
            "model_versions": registry.get_version_count() if registry else 0,
        }

    except Exception as exc:
        logger.exception("System status error: {}", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {exc}",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
