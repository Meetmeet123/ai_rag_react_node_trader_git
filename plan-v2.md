# TradeForge AI v2 — Custom LLM + Auto-Training + Live Execution

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + TypeScript)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ AI Chat  │ │ Strategy │ │ Training │ │ Model    │ │ Auto-Execution   │  │
│  │ Assistant│ │ Builder  │ │ Dashboard│ │ Manager  │ │ Control Panel    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ WebSocket + REST
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKEND (Python FastAPI + WebSocket)                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  API Gateway (FastAPI Routers)                                      │    │
│  │  ├── /api/v1/llm          → Strategy generation, chat               │    │
│  │  ├── /api/v1/strategies   → CRUD for strategies                     │    │
│  │  ├── /api/v1/backtest     → Backtesting engine                      │    │
│  │  ├── /api/v1/train        → Model training pipeline                 │    │
│  │  ├── /api/v1/models       → Model management (versions, switch)     │    │
│  │  ├── /api/v1/execute      → Live trade execution                    │    │
│  │  ├── /api/v1/market       → Real-time market data                   │    │
│  │  └── /ws/v1/stream        → WebSocket for live signals              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  CORE ENGINE MODULES                                                │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │ LLM Engine   │  │ Strategy     │  │ Simulation / Backtest    │  │    │
│  │  │              │  │ Parser       │  │ Engine                   │  │    │
│  │  │ • Strategy   │  │              │  │                          │  │    │
│  │  │   Generator  │  │ • NL → JSON  │  │ • Historical data        │  │    │
│  │  │ • Formula    │  │ • Validate   │  │ • Indicator calc         │  │    │
│  │  │   Interpreter│  │ • Compile    │  │ • P&L tracking           │  │    │
│  │  │ • Market     │  │ • Generate   │  │ • Metrics (Sharpe, etc)  │  │    │
│  │  │   Analyzer   │  │   Python code│  │ • Equity curve           │  │    │
│  │  │ • Risk       │  │              │  │                          │  │    │
│  │  │   Advisor    │  │              │  │                          │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │ Auto-Training│  │ Model        │  │ Live Execution           │  │    │
│  │  │ Pipeline     │  │ Registry     │  │ Engine                   │  │    │
│  │  │              │  │              │  │                          │  │    │
│  │  │ • 20-min cron│  │ • Versions   │  │ • Signal generator       │  │    │
│  │  │ • Retrain on │  │ • A/B test   │  │ • Order router           │  │    │
│  │  │   new data   │  │ • Rollback   │  │ • Position manager       │  │    │
│  │  │ • Formula    │  │ • Performance│  │ • Risk guard             │  │    │
│  │  │   changes    │  │   tracking   │  │ • Broker API integration │  │    │
│  │  │ • Checkpoint │  │ • Active flag│  │ • P&L tracker            │  │    │
│  │  │   save       │  │              │  │                          │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  │                                                                     │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │ Market Data  │  │ Broker       │  │ Risk Manager             │  │    │
│  │  │ Ingestion    │  │ Connectors   │  │                          │  │    │
│  │  │              │  │              │  │ • Daily loss limit       │  │    │
│  │  │ • NSE/BSE    │  │ • Angel One  │  │ • Max drawdown           │  │    │
│  │  │   scraper    │  │ • Zerodha    │  │ • Position sizing        │  │    │
│  │  │ • WebSocket  │  │ • Fyers      │  │ • Kill switch            │  │    │
│  │  │   feeds      │  │ • Upstox     │  │ • Exposure limits        │  │    │
│  │  │ • OHLC build │  │ • Paper mode │  │ • Auto square-off        │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  DATA LAYER                                                         │    │
│  │  ├── SQLite (strategies, trades, configs, model metadata)           │    │
│  │  ├── Parquet (historical OHLC data — fast columnar reads)           │    │
│  │  ├── Pickle/Joblib (trained model checkpoints)                      │    │
│  │  └── JSON (strategy definitions, broker configs)                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Backend
- **Python 3.11+**, **FastAPI** (async web framework)
- **Uvicorn** (ASGI server with WebSocket support)
- **APScheduler** (20-min auto-training cron)
- **Transformers** (HuggingFace — LLM fine-tuning)
- **PyTorch** (ML model training)
- **Pandas + NumPy + TA-Lib** (indicator calculations)
- **Backtrader/Zipline-style custom engine** (backtesting)
- **SQLite + SQLAlchemy** (ORM database)
- **PyArrow + Parquet** (fast historical data storage)
- **python-socketio** (WebSocket streaming)
- **httpx** (async HTTP for broker APIs)
- **pydantic** (data validation)
- **loguru** (structured logging)
- **pytest** (testing)

### Frontend (Additions to existing React app)
- **AI Chat Panel** — Real-time chat with strategy assistant
- **Training Dashboard** — Model training status, loss curves, metrics
- **Model Manager** — Switch between model versions
- **Auto-Execution Panel** — Control auto-trading parameters

## Project Structure

```
tradeforge-ai/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Central configuration
│   ├── requirements.txt
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py          # SQLAlchemy engine/session
│   │   ├── models.py              # All ORM models
│   │   └── migrations/            # Alembic migrations
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── llm.py                 # LLM strategy generation
│   │   ├── strategies.py          # Strategy CRUD
│   │   ├── backtest.py            # Backtesting API
│   │   ├── train.py               # Training pipeline API
│   │   ├── models.py              # Model management API
│   │   ├── execute.py             # Live execution API
│   │   └── market.py              # Market data API
│   ├── core/
│   │   ├── __init__.py
│   │   ├── llm_engine.py          # Custom LLM for trading
│   │   ├── strategy_parser.py     # NL → Strategy JSON → Python code
│   │   ├── backtest_engine.py     # Historical simulation engine
│   │   ├── indicators.py          # Technical indicator library
│   │   ├── auto_trainer.py        # 20-min auto-training pipeline
│   │   ├── model_registry.py      # Model versioning & A/B testing
│   │   ├── execution_engine.py    # Live trade signal generator
│   │   ├── risk_manager.py        # Risk controls & kill switch
│   │   ├── broker/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Abstract broker interface
│   │   │   ├── angel_one.py       # Angel One SmartAPI
│   │   │   ├── zerodha.py         # Zerodha Kite
│   │   │   ├── fyers.py           # Fyers API
│   │   │   ├── upstox.py          # Upstox API
│   │   │   └── paper_broker.py    # Paper trading simulator
│   │   └── market_data/
│   │       ├── __init__.py
│   │       ├── ingestor.py        # Data ingestion pipeline
│   │       ├── ohlc_builder.py    # Candle building from ticks
│   │       └── websocket_client.py# Real-time WebSocket feeds
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── server.py              # Socket.IO server for live data
│   ├── training/
│   │   ├── __init__.py
│   │   ├── dataset_builder.py     # Build training datasets
│   │   ├── fine_tuner.py          # Fine-tune LLM on trading data
│   │   ├── reinforcement.py       # RL for trade execution
│   │   └── checkpoints/           # Saved model weights
│   ├── models/                    # Serialized model files
│   ├── strategies/                # Generated strategy Python files
│   ├── data/
│   │   ├── historical/            # Parquet OHLC files
│   │   └── checkpoints/           # Training checkpoints
│   └── tests/
├── frontend/                      # Existing React app + new features
│   └── ...
└── docker-compose.yml             # Full stack orchestration
```

## Build Plan

### Stage 1: Backend Foundation
- Database models (strategies, trades, models, configs)
- Core indicators library
- Market data ingestion
- Strategy parser

### Stage 2: LLM Engine + Strategy Generation
- Custom LLM fine-tuning pipeline
- NL → Strategy JSON → Python code converter
- AI Chat endpoint

### Stage 3: Backtest Engine
- Historical simulation engine
- Performance metrics calculation
- Equity curve generation

### Stage 4: Auto-Training Pipeline
- 20-minute cron scheduler
- Dataset builder from new data + formula changes
- Model fine-tuning loop
- Checkpoint saving & model registry

### Stage 5: Live Execution Engine
- Signal generator from trained model
- Broker connectors (Angel One, Zerodha, etc.)
- Risk manager integration
- Paper + Live mode

### Stage 6: WebSocket Server
- Real-time market data streaming
- Live signal broadcasting
- Training progress updates

### Stage 7: Frontend AI Features
- AI Chat panel
- Training dashboard
- Model manager
- Auto-execution controls

### Stage 8: Integration + Deploy
- Full system integration
- Docker Compose setup
- Deploy both frontend + backend
