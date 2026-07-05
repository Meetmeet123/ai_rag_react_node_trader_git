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

import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from config import settings
from database.connection import init_db, close_db

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

    train_router.set_pipeline_instance(pipeline)
    train_router.set_registry_instance(services["registry"])
    models_router.set_registry_instance(services["registry"])
    execute_router.set_engine_instance(engine)
    execute_router.set_risk_instance(services["risk"])
    market_router.set_ingestor_instance(services["ingestor"])

    logger.info("Router singletons injected")

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
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

from routers import auth, llm, strategies, backtest, train, models, execute, market

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["Strategies"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtest"])
app.include_router(train.router, prefix="/api/v1/train", tags=["Training"])
app.include_router(models.router, prefix="/api/v1/models", tags=["Models"])
app.include_router(execute.router, prefix="/api/v1/execute", tags=["Execution"])
app.include_router(market.router, prefix="/api/v1/market", tags=["Market Data"])

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
