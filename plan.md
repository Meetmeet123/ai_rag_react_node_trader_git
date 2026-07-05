# Auto-Trading Platform — Build Plan

## Overview
Build a complete auto-trading software where users can input custom formulas/strategies, and the system auto-generates buy/sell signals, stop-loss, position sizing, and executes trades via broker APIs.

## Key Features
1. **Strategy Builder** — Visual formula editor for custom trading strategies (indicators, conditions, entry/exit rules)
2. **Backtesting Engine** — Historical data backtesting with P&L, win rate, Sharpe ratio
3. **Paper Trading** — Simulated trading with virtual money
4. **Live Trading** — Broker API integration (Angel One, Zerodha Kite, Fyers, Upstox)
5. **Risk Management** — Stop-loss, trailing stop, position sizing, max drawdown protection
6. **Dashboard** — Real-time P&L, open positions, order book, strategy performance
7. **Multi-Asset Support** — Stocks, Nifty/BankNifty F&O, Options strategies

## Tech Stack
- **Frontend**: React + TypeScript + Tailwind CSS + shadcn/ui
- **Charts**: Lightweight Charts (TradingView) + Recharts
- **State**: Zustand
- **Backend Simulation**: Mock server with localStorage persistence
- **Broker APIs**: Angel One SmartAPI, Zerodha Kite Connect (simulated)

## Architecture
- `/app` — Strategy builder, dashboard, backtesting
- `/components` — Reusable UI components
- `/hooks` — Custom React hooks for trading logic
- `/lib` — Utilities, formula parser, backtest engine
- `/services` — Broker API services, data feeds

## Build Stages

### Stage 1 — Project Scaffolding & Core UI
- Initialize project with React + Vite + TypeScript + Tailwind
- Set up routing, theme, layout
- Build sidebar navigation, header, main layout

### Stage 2 — Strategy Builder
- Formula input UI with autocomplete
- Technical indicator library (SMA, EMA, RSI, MACD, Bollinger Bands, etc.)
- Entry/exit condition builder
- Stop-loss and target configuration

### Stage 3 — Market Data & Charts
- Historical data management
- Candlestick charts with indicators overlay
- Real-time price simulation

### Stage 4 — Backtesting Engine
- Historical data backtesting
- Performance metrics (P&L, win rate, max drawdown, Sharpe ratio)
- Trade log visualization
- Equity curve chart

### Stage 5 — Trading Dashboard
- Live market watch
- Order placement panel
- Position tracker
- P&L summary

### Stage 6 — Paper Trading & Auto-Execution
- Paper trading simulation
- Signal generation from strategies
- Virtual order execution
- Performance tracking

### Stage 7 — Polish & Deploy
- Animations, responsive design
- Final testing
- Deploy to production

## Skill: vibecoding-webapp-swarm
