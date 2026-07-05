# TradeForge AI v2 — Custom LLM Auto-Trading Platform

A production-grade auto-trading software with **custom LLM**, **auto-training pipeline**, and **live trade execution**. The system generates trading strategies from natural language, backtests them, auto-trains every 20 minutes on new data, and executes trades automatically.

---

## Architecture Overview

```
Frontend (React + TypeScript)          Backend (Python FastAPI)
+ AI Chat Assistant     <──REST──>     + LLM Engine (Strategy Generation)
+ Training Dashboard    <──REST──>     + Strategy Parser (NL → Code)
+ Model Manager         <──REST──>     + Backtest Engine
+ Auto-Execution Panel  <──REST──>     + Auto-Training (20-min cron)
+ Trading Terminal      <──WebSocket──> + Live Execution Engine
                                        + Risk Manager
                                        + Model Registry
                                        + Broker Connectors
                                        + Market Data Ingestion
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
3. Build updated training dataset
4. Fine-tune LLM incrementally (LoRA/PEFT)
5. Validate via backtest
6. If improved → deploy as active model
7. If worse → keep old model, archive new one

### Live Trade Execution
- Auto-signal generation from trained model
- Paper trading mode (virtual ₹10L capital)
- Live mode via broker APIs (Angel One, Zerodha, Fyers, Upstox)
- Real-time WebSocket streaming

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
| Frontend | React 19 + TypeScript + Tailwind CSS + shadcn/ui + Recharts |
| Backend API | FastAPI + Uvicorn (ASGI) |
| WebSocket | python-socketio |
| Database | SQLite + SQLAlchemy 2.0 |
| LLM | Transformers + PEFT (LoRA) + DialoGPT-medium |
| ML Training | PyTorch + Datasets + Accelerate |
| Reinforcement Learning | Custom Q-Learning + DQN |
| Indicators | Pandas + NumPy + 21 custom indicators |
| Market Data | NSE India API + Yahoo Finance |
| Broker APIs | httpx (async HTTP) |
| Scheduling | APScheduler |
| Logging | Loguru |

---

## Project Structure

```
tradeforge-ai/
├── backend/
│   ├── main.py                    # FastAPI entry point (394 lines)
│   ├── config.py                  # Pydantic settings (154 lines)
│   ├── requirements.txt           # All dependencies
│   ├── Dockerfile                 # Container config
│   ├── database/
│   │   ├── models.py              # 10 ORM models + 7 enums (623 lines)
│   │   └── connection.py          # Engine + sessions (97 lines)
│   ├── core/
│   │   ├── llm_engine.py          # Custom LLM (1,694 lines)
│   │   ├── strategy_parser.py     # NL → Code (1,173 lines)
│   │   ├── indicators.py          # 21 indicators (721 lines)
│   │   ├── backtest_engine.py     # Backtesting (1,014 lines)
│   │   ├── execution_engine.py    # Live execution (701 lines)
│   │   ├── risk_manager.py        # Risk guards (655 lines)
│   │   ├── auto_trainer.py        # 20-min pipeline (1,047 lines)
│   │   ├── model_registry.py      # Version mgmt (545 lines)
│   │   ├── broker/
│   │   │   ├── base.py            # Abstract interface (438 lines)
│   │   │   ├── paper_broker.py    # Paper trading (507 lines)
│   │   │   ├── angel_one.py       # Angel One (527 lines)
│   │   │   ├── zerodha.py         # Zerodha (614 lines)
│   │   │   └── fyers.py           # Fyers (749 lines)
│   │   └── market_data/
│   │       ├── ingestor.py        # Data ingestion (479 lines)
│   │       └── ohlc_builder.py    # Candle builder (307 lines)
│   ├── routers/
│   │   ├── llm.py                 # LLM API (367 lines)
│   │   ├── strategies.py          # Strategy CRUD (456 lines)
│   │   ├── backtest.py            # Backtest API (387 lines)
│   │   ├── train.py               # Training API (366 lines)
│   │   ├── models.py              # Model mgmt API (391 lines)
│   │   ├── execute.py             # Execution API (416 lines)
│   │   └── market.py              # Market data API (443 lines)
│   ├── training/
│   │   ├── dataset_builder.py     # Dataset builder (1,623 lines)
│   │   ├── fine_tuner.py          # LoRA fine-tuning (976 lines)
│   │   └── reinforcement.py       # RL agent (1,446 lines)
│   ├── websocket/
│   │   └── server.py              # WebSocket server (392 lines)
│   └── shared/
│       └── schemas.py             # Pydantic schemas (425 lines)
├── frontend/                      # React app (existing)
├── docker-compose.yml
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

### 3. Run Backend
```bash
cd backend
python -c "from database.connection import init_db; init_db()"  # Create tables
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs at: http://localhost:8000/docs

### 4. Run Frontend
```bash
cd frontend
npm run dev
```

App at: http://localhost:5173

### 5. Run with Docker
```bash
docker-compose up --build
```

---

## API Endpoints (70+ Routes)

| Tag | Prefix | Endpoints |
|-----|--------|-----------|
| **LLM** | `/api/v1/llm` | Generate strategy, Chat, Explain, Analyze |
| **Strategies** | `/api/v1/strategies` | CRUD + Deploy + Stop + Duplicate |
| **Backtest** | `/api/v1/backtest` | Run + Results + Equity Curve + Trade Log |
| **Training** | `/api/v1/train` | Trigger + Status + Start/Stop Auto + Jobs |
| **Models** | `/api/v1/models` | List + Activate + Rollback + Compare |
| **Execution** | `/api/v1/execute` | Signal + Positions + Portfolio + Kill Switch |
| **Market Data** | `/api/v1/market` | Historical + LTP + Nifty 50 + Indicators |

---

## How the Auto-Training Works

```
Every 20 minutes:
    ┌─────────────────┐
    │  Check Changes  │ ← New data? Formula changed?
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
    │ Compare & Deploy│ ← Better? → Activate. Worse? → Archive.
    └─────────────────┘
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
- **Manual Approval**: Live deployment requires explicit user approval

---

## License

MIT License — Built for Indian traders.
