"""
TradeForge AI - Central Configuration Module.

Uses pydantic-settings with .env file support for all application configuration.
All sensitive values (API keys, secrets) are read from environment variables.
"""

from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All configuration values can be overridden via environment variables
    or a .env file in the project root. Sensitive values like API keys
    should never be committed to version control.
    """

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_NAME: str = Field(default="TradeForge AI", description="Application display name")
    DEBUG: bool = Field(default=False, description="Enable debug mode with verbose logging")
    SECRET_KEY: str = Field(description="Secret key for JWT signing and encryption")
    FRONTEND_URL: str = Field(
        default="http://localhost:5173",
        description="Allowed frontend origin(s); comma-separated for multiple",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24, description="JWT access token expiration in minutes"
    )

    # ------------------------------------------------------------------
    # Task Queue (Celery + Redis)
    # ------------------------------------------------------------------
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL (Redis)",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0",
        description="Celery result backend URL (Redis)",
    )

    # ------------------------------------------------------------------
    # Database (MongoDB)
    # ------------------------------------------------------------------
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017/tradeforge",
        description="MongoDB connection URI",
    )
    MONGODB_DB_NAME: str = Field(
        default="tradeforge",
        description="MongoDB database name (overrides URI db name if set)",
    )

    # ------------------------------------------------------------------
    # LLM (Large Language Model)
    # ------------------------------------------------------------------
    LLM_MODEL_NAME: str = Field(
        default="microsoft/DialoGPT-medium",
        description="Hugging Face model identifier for the trading LLM"
    )
    LLM_CHECKPOINT_DIR: str = Field(
        default="./training/checkpoints",
        description="Directory to store fine-tuned model checkpoints"
    )
    LLM_MAX_LENGTH: int = Field(
        default=512,
        ge=1,
        le=4096,
        description="Maximum token length for LLM generation"
    )
    LLM_TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for LLM generation"
    )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    TRAINING_INTERVAL_MINUTES: int = Field(
        default=20,
        ge=1,
        description="Auto-training interval in minutes"
    )
    BATCH_SIZE: int = Field(
        default=16,
        ge=1,
        description="Training batch size"
    )
    LEARNING_RATE: float = Field(
        default=2e-5,
        gt=0.0,
        description="Optimizer learning rate"
    )
    EPOCHS: int = Field(
        default=3,
        ge=1,
        description="Number of training epochs"
    )

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    DEFAULT_CAPITAL: float = Field(
        default=1_000_000.0,
        gt=0.0,
        description="Default initial capital for backtesting and paper trading"
    )
    DEFAULT_TIMEFRAME: str = Field(
        default="15m",
        description="Default candle timeframe (e.g., 1m, 5m, 15m, 1h, 1d)"
    )
    MAX_POSITIONS: int = Field(
        default=10,
        ge=1,
        description="Maximum number of concurrent open positions"
    )
    MAX_DAILY_LOSS_PCT: float = Field(
        default=2.0,
        ge=0.0,
        le=100.0,
        description="Maximum daily loss percentage before kill switch"
    )

    # ------------------------------------------------------------------
    # Market Data
    # ------------------------------------------------------------------
    MARKET_OPEN_TIME: str = Field(
        default="09:15",
        description="Market open time (IST)"
    )
    MARKET_CLOSE_TIME: str = Field(
        default="15:30",
        description="Market close time (IST)"
    )

    # ------------------------------------------------------------------
    # Broker API Credentials (from environment)
    # ------------------------------------------------------------------
    ANGEL_ONE_API_KEY: str = Field(default="", description="Angel One broker API key")
    ANGEL_ONE_CLIENT_ID: str = Field(default="", description="Angel One client ID")
    ZERODHA_API_KEY: str = Field(default="", description="Zerodha Kite API key")
    FYERS_APP_ID: str = Field(default="", description="Fyers application ID")
    UPSTOX_API_KEY: str = Field(default="", description="Upstox API key")

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Fernet encryption key (base64). Falls back to deriving from SECRET_KEY.",
    )

    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error reporting. Disabled when not set.",
    )

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    DATA_DIR: str = Field(default="./data", description="Base data directory")
    HISTORICAL_DATA_DIR: str = Field(
        default="./data/historical",
        description="Historical OHLCV data storage"
    )
    STRATEGIES_DIR: str = Field(
        default="./strategies",
        description="User-defined strategy storage"
    )
    MODELS_DIR: str = Field(
        default="./models",
        description="Serialized model artefacts"
    )

    model_config = ConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Global settings singleton — import this instance everywhere.
settings: Settings = Settings()
