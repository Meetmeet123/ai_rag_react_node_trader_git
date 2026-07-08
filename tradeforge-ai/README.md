# TradeForge AI v2 — Custom LLM Auto-Trading Platform

A production-grade auto-trading software with **custom LLM**, **auto-training pipeline**, and **live trade execution**. The system generates trading strategies from natural language, backtests them, auto-trains every 20 minutes on new data, and executes trades automatically.

---

## Architecture Overview

```
Frontend (React 19 + TypeScript + Vite)
+ AI Chat Assistant      <──REST──>     Backend (Python 3.11 + FastAPI)
+ Training Dashboard     <──REST──>     + LLM Engine (Strategy Generation)
+ Model Manager          <──REST──>     + RAG Engine (Retrieval Augmentation)
+ Auto-Execution Panel   <──REST──>     + Strategy Parser (NL → Code)
+ Trading Terminal       <──WebSocket──>+ Live Execution Engine
                                         + Risk Manager
+ Live/Paper Trading     <──REST──>     + Model Registry (versions + shadow mode)
                                         + Auto-Training (Celery beat / 20 min)
                                         + Broker Connectors (Paper, Angel, Zerodha, Fyers, Upstox)
                                         + Market Data Ingestion

Data & Infrastructure
+ MongoDB (Beanie ODM)   + Redis (Celery broker/cache)
+ Prometheus metrics     + Sentry error reporting
+ MLflow tracking        + S3/MinIO artifact store
```

---

## Key Features

### Custom LLM for Trading
- **Natural language strategy generation**: Type "Buy Nifty when RSI < 30" → AI generates complete strategy
- **Strategy explanation**: AI explains any strategy in plain English/Hindi
- **Backtest analysis**: AI reads backtest results and suggests improvements
- **70+ training pairs**: RSI, MACD, Bollinger, SMA crossover, multi-condition strategies
- **Hindi language support**: Accepts prompts in Hindi

### Auto-Training Pipeline (Every 20 Minutes)
1. Detect new market data since last training
2. Detect strategy formula changes
3. Detect distribution drift against the active model
4. Build updated training dataset
5. Fine-tune LLM incrementally (LoRA/PEFT)
6. Validate via backtest
7. Upload checkpoint artifact to S3/MinIO
8. If improved → deploy as active model (or shadow first)
9. If worse → keep old model, archive new one

### Live Trade Execution
- Auto-signal generation from trained model
- Paper trading mode (virtual ₹10L capital)
- Live mode via broker APIs (Angel One, Zerodha, Fyers, Upstox)
- Live-trading approval gate (admin approval required)
- Broker circuit breaker on consecutive failures
- Real-time WebSocket streaming

### Security & Guardrails
- Prompt-injection guard (`core.prompt_guard`)
- Input sanitization (`core.sanitization`)
- JWT authentication + admin approval for live trading
- Fernet encryption for broker credentials

### Observability
- Prometheus metrics for training, inference, execution, risk, and drift
- Sentry error reporting with release/environment/user context
- Structured JSON logging via Loguru

### MLOps
- MLflow experiment tracking
- S3/MinIO model artifact storage
- Kolmogorov-Smirnov drift detection on strategy feature distributions
- Model registry with active + shadow/challenger versions
- Shadow inference endpoint to compare active vs challenger

### Risk Management (11 Guards)
- Kill switch (emergency halt)
- Daily loss limit
- Max positions/exposure
- Consecutive loss protection
- Auto square-off (3:15 PM)
- Market hours validation

### Backtesting Engine
- Slippage simulation (configurable %)
- Flat brokerage (₹20/order)
- Sharpe, Sortino, Calmar ratios
- Equity curve & drawdown analysis
- Monthly returns heatmap

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS + shadcn/ui + Recharts |
| Backend API | FastAPI + Uvicorn (ASGI) |
| WebSocket | python-socketio |
| Database | MongoDB + Beanie ODM |
| Cache / Task Queue | Redis + Celery |
| LLM | Transformers + PEFT (LoRA) + DialoGPT-medium |
| ML Training | PyTorch + Datasets + Accelerate |
| Reinforcement Learning | Custom Q-Learning + DQN |
| Indicators | Pandas + NumPy + 21 custom indicators |
| Market Data | NSE India API + Yahoo Finance |
| Broker APIs | httpx (async HTTP) |
| Scheduling | Celery Beat |
| Logging | Loguru |
| Metrics | Prometheus |
| Error Tracking | Sentry |
| Experiment Tracking | MLflow |
| Artifact Storage | S3 / MinIO |
| CI/CD | GitHub Actions + Docker |
| Lint/Format | Ruff, Black, ESLint, TypeScript |

---

## Project Structure

```
tradeforge-ai/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Pydantic settings
│   ├── requirements.txt           # All dependencies
│   ├── Dockerfile                 # Container config
│   ├── celery_app.py              # Celery app + beat schedule
│   ├── database/
│   │   ├── models.py              # Beanie/MongoDB document models
│   │   └── connection.py          # MongoDB init
│   ├── core/
│   │   ├── llm_engine.py          # Custom LLM + shadow inference
│   │   ├── strategy_parser.py     # NL → Code
│   │   ├── indicators.py          # 21 indicators
│   │   ├── backtest_engine.py     # Backtesting
│   │   ├── execution_engine.py    # Live execution
│   │   ├── risk_manager.py        # Risk guards
│   │   ├── auto_trainer.py        # Auto-training pipeline
│   │   ├── model_registry.py      # Version mgmt + shadow mode
│   │   ├── artifact_store.py      # S3/MinIO checkpoint uploads
│   │   ├── drift_detector.py      # KS-test drift detection
│   │   ├── metrics.py             # Prometheus metrics
│   │   ├── prompt_guard.py        # Prompt-injection detection
│   │   ├── sanitization.py        # Input sanitization
│   │   ├── validation_backtest_adapter.py  # Train/validate bridge
│   │   ├── broker/
│   │   │   ├── base.py            # Abstract interface
│   │   │   ├── paper_broker.py    # Paper trading
│   │   │   ├── angel_one.py       # Angel One
│   │   │   ├── zerodha.py         # Zerodha
│   │   │   ├── fyers.py           # Fyers
│   │   │   └── upstox.py          # Upstox
│   │   └── market_data/
│   │       ├── ingestor.py        # Data ingestion
│   │       └── ohlc_builder.py    # Candle builder
│   ├── routers/
│   │   ├── llm.py                 # LLM API (incl. shadow generation)
│   │   ├── strategies.py          # Strategy CRUD
│   │   ├── backtest.py            # Backtest API
│   │   ├── train.py               # Training API
│   │   ├── models.py              # Model mgmt API (shadow + promote)
│   │   ├── execute.py             # Execution API
│   │   ├── market.py              # Market data API
│   │   ├── auth.py                # Auth + live approval
│   │   ├── audit.py               # Audit log
│   │   ├── analytics.py           # Dashboard analytics
│   │   ├── brokers.py             # Broker config
│   │   └── settings.py            # Settings
│   ├── tasks/                     # Celery tasks
│   │   ├── training.py            # Auto-training worker
│   │   ├── backtest.py            # Backtest worker
│   │   ├── market_data.py         # Market ingest worker
│   │   └── execution.py           # Signal worker
│   ├── training/
│   │   ├── dataset_builder.py     # Dataset builder
│   │   ├── fine_tuner.py          # LoRA fine-tuning
│   │   └── reinforcement.py       # RL agent
│   ├── websocket/
│   │   └── server.py              # WebSocket server
│   └── tests/                     # pytest suite
├── frontend/                      # React app + Vitest + Playwright
├── docker-compose.yml
├── .github/workflows/ci.yml       # GitHub Actions CI/CD
├── .pre-commit-config.yaml        # Pre-commit hooks
├── scripts/                       # Backup/restore helpers
├── monitoring/                    # Prometheus config
├── .env.example
└── README.md
```

**Total: 20,299 lines of Python backend + 8,000+ lines of React frontend**

---

## Quick Start

### 1. Clone & Setup
```bash
cd tradeforge-ai

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your broker API keys
```

### 3. Start Dependencies
Make sure MongoDB and Redis are running locally (or use Docker Compose):
```bash
# macOS with Homebrew
brew services start mongodb-community@7.0
brew services start redis
```

### 4. Run Backend
```bash
cd backend
source .venv/bin/activate
python -c "import asyncio; from database.connection import init_db; asyncio.run(init_db())"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs at: http://localhost:8000/docs

### 5. Run Celery Worker & Beat
```bash
cd backend
source .venv/bin/activate
celery -A celery_app worker --loglevel=info --concurrency=2
celery -A celery_app beat --loglevel=info
```

### 6. Run Frontend
```bash
cd frontend
npm run dev -- --port 3000
```

App at: http://localhost:3000

### 7. Run with Docker
```bash
docker-compose up --build
```

---

## API Endpoints (70+ Routes)

| Tag | Prefix | Endpoints |
|-----|--------|-----------|
| **LLM** | `/api/v1/llm` | Generate strategy, shadow generation, Chat, Explain, Analyze |
| **Strategies** | `/api/v1/strategies` | CRUD + Deploy + Stop + Duplicate |
| **Backtest** | `/api/v1/backtest` | Run + Results + Equity Curve + Trade Log |
| **Training** | `/api/v1/train` | Trigger + Status + Start/Stop Auto + Jobs |
| **Models** | `/api/v1/models` | List + Activate + Rollback + Compare + Shadow + Promote |
| **Execution** | `/api/v1/execute` | Signal + Positions + Portfolio + Kill Switch |
| **Market Data** | `/api/v1/market` | Historical + LTP + Nifty 50 + Indicators |
| **Auth / Users** | `/api/v1/auth` | Login, register, live-approval |
| **Audit** | `/api/v1/audit` | Audit log |
| **Analytics** | `/api/v1/analytics` | Dashboard metrics |

---

## How the Auto-Training Works

```
Every 20 minutes (Celery beat):
    ┌─────────────────┐
    │  Check Changes  │ ← New data? Formula changed? Drift detected?
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │  Build Dataset  │ ← From strategies + market data
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │  Fine-tune LLM  │ ← LoRA adapters, incremental
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │    Backtest     │ ← Validate on unseen data
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ Upload Artifact │ ← S3/MinIO checkpoint archive
    └────────┬────────┘
             ▼
    ┌─────────────────┐
    │ Compare & Deploy│ ← Better? → Activate (or shadow).
    └─────────────────┘     Worse? → Archive.
```

---

## Strategy Generation Examples

```python
# POST /api/v1/llm/generate-strategy
{
    "prompt": "Buy Nifty when RSI goes below 30 and sell when it crosses above 70",
    "instrument": "NIFTY50",
    "timeframe": "15m"
}

# Response:
{
    "strategy": {
        "name": "RSI Mean Reversion Nifty",
        "instrument": "NIFTY50",
        "timeframe": "15m",
        "entry_conditions": [
            {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
        ],
        "exit_conditions": [
            {"indicator": "rsi", "period": 14, "condition": ">", "value": 70}
        ],
        "stop_loss": {"type": "fixed_pct", "value": 1.0},
        "target": {"type": "fixed_pct", "value": 3.0}
    },
    "confidence": 0.92,
    "reasoning": "RSI below 30 indicates oversold conditions..."
}
```

---

## Safety & Risk Management

- **Kill Switch**: Instantly stops all trading and closes positions
- **Paper Mode Default**: All strategies start in paper trading
- **Daily Loss Limit**: Auto-stops trading if daily loss exceeded
- **Circuit Breaker**: 3 consecutive training failures pause auto-training
- **Model Validation**: Every trained model is backtested before deployment
- **Manual Approval**: Live deployment requires explicit admin approval

---

## Monitoring & Operations

- **Prometheus**: metrics exposed on `/metrics` (training, inference, execution, risk, drift)
- **Sentry**: set `SENTRY_DSN` for error tracking
- **MLflow**: set `MLFLOW_TRACKING_URI` for experiment tracking
- **Logs**: structured logs written to `backend/logs/tradeforge.log`
- **Backups**: use `scripts/backup-mongo.sh` and `scripts/restore-mongo.sh`
- **Pre-commit**: install with `pre-commit install` to run ruff, black, ESLint, and TypeScript checks

---

## License

MIT License — Built for Indian traders.
