# TradeForge AI — Full E2E Production Build Plan

## 1. Commitment

Build a **complete, production-ready, end-to-end auto-trading platform**. No shortcuts, no mock data, no stubs. Every feature described in `plan.md`, `plan-v2.md`, and the README will be implemented with proper code structure, tests, security, DevOps, and MLOps practices. Timeline is flexible; quality and completeness are non-negotiable.

---

## 2. Current State Diagnosis

Phase 0 (Foundation Repair) and Phase 1 (Database & Auth) are functionally complete and the stack boots end-to-end. Remaining gaps are captured explicitly below so work can be sequenced from Phase 2 onward.

### What now works
- Backend boots cleanly with `uvicorn main:app` on `http://localhost:8000`.
- MongoDB/Beanie document models replaced the broken SQLAlchemy 1.4 → 2.0 layer.
- JWT/OAuth2 auth with bcrypt hashing is live: register, login, refresh, logout, `/me`.
- Strategies CRUD is wired to MongoDB with user scoping, deploy/stop/duplicate endpoints, and frontend adapter.
- Frontend API client (`src/lib/api.ts`), auth context, login/register pages, route guards, and typed hooks (`useApi`, `useWebSocket`) are in place.
- Frontend production build passes; backend and frontend smoke tests pass.
- Docker scaffolding (multi-stage frontend/backend Dockerfiles, `.dockerignore`, MongoDB `docker-compose.yml`) is created.

### Critical remaining gaps
- **Backtest router is still a stub** — accepts requests but never calls `BacktestEngine.run()`.
- **RAG (`TradeForgeRAG`) is built but not initialized** in lifespan and not wired into chat.
- **WebSocket/Socket.IO server is not mounted** in FastAPI.
- **CORS is still open** (`allow_origins=["*"]`) and must be locked before production.
- **No rate limiting, security headers, audit logs, or request correlation IDs**.
- **Auto-training runs in-process** (every 20 min); needs Celery + Redis decoupling.
- **Frontend strategy editor is partially wired**; condition builder/toolbar form state needs full API integration and validation.
- **Analytics, settings, live trading, and paper trading UIs still use mock data**.
- **Upstox broker connector missing**; broker credentials stored plaintext.
- **No CI/CD, staging configs, monitoring, or formal security scanning**.

---

## 3. Target End State

A single, coherent product where:

1. Users can register/login securely.
2. Users chat with an AI assistant to generate trading strategies in English/Hindi.
3. Users visually build, edit, duplicate, backtest, and deploy strategies.
4. Backtests run on real historical data with full metrics and equity curves.
5. Paper trading simulates execution with virtual capital in real time.
6. Live trading connects to Angel One / Zerodha / Fyers / Upstox with encrypted credentials.
7. Auto-training pipeline fine-tunes the LLM every 20 minutes (configurable) with full observability.
8. Model registry supports versioning, A/B testing, rollback, and drift detection.
9. RAG grounds AI responses in strategies, backtests, trades, and market regimes.
10. Risk manager enforces kill switch, daily loss limits, max positions, drawdown protection, and auto square-off.
11. Analytics dashboard shows real P&L, strategy performance, trade journal, and exportable reports.
12. Settings persist (account, broker APIs, risk, preferences, notifications).
13. Everything runs in Docker Compose locally and is deployable to staging/production.
14. Full test coverage, CI/CD, monitoring, and security hardening.

---

## 4. Tech Stack (Final)

### Backend
- Python 3.11, FastAPI, Uvicorn
- MongoDB + Motor + Beanie ODM (replaced SQLAlchemy/SQLite)
- Pydantic v2, python-dotenv
- Transformers + PEFT + Accelerate + bitsandbytes for LoRA fine-tuning
- ChromaDB + sentence-transformers for RAG
- python-socketio for WebSocket streaming
- Celery + Redis for background jobs (backtests, training, ingestion) *(pending)*
- httpx for broker/market APIs
- slowapi for rate limiting *(pending)*
- bcrypt + python-jose for auth
- loguru + structlog for structured logging
- Prometheus + Sentry for observability *(pending)*
- pytest + pytest-asyncio + pytest-cov

### Frontend
- React 19 + TypeScript 5.9 + Vite 7
- Tailwind CSS 3.4 + shadcn/ui
- React Router v7
- React Hook Form + Zod
- Recharts
- axios or native fetch API client
- Socket.IO client for WebSocket
- Vitest + React Testing Library + Playwright

### DevOps / MLOps
- Docker + Docker Compose (multi-stage, non-root)
- GitHub Actions CI/CD
- nginx reverse proxy + SSL
- PostgreSQL, Redis
- MLflow or Weights & Biases
- DVC for data/model versioning
- S3-compatible object storage for artifacts
- Grafana dashboards + alerting

---

## 5. Phase-by-Phase Execution

### Phase 0 — Foundation Repair (Boot the Stack)
**Goal:** Backend starts, frontend builds, Docker Compose works, API client is wired.

**Backend Tasks**
- [x] Audit and complete `requirements.txt` with every missing package.
- [x] ~~Upgrade SQLAlchemy to 2.0~~ (replaced with MongoDB/Beanie stack).
- [x] Fix `core/__init__.py` stale imports.
- [x] Create `.env` from `.env.example` and validate `SECRET_KEY`.
- [x] Verify `uvicorn main:app` boots cleanly.
- [x] Add `python-dotenv`, `pyarrow`, `loguru`, `apscheduler`, `motor`, `beanie` verification.

**Frontend Tasks**
- [x] Create `tradeforge-ai/frontend/.env.example` and `.env`.
- [x] Create `src/lib/api.ts` typed API client with request/response interceptors.
- [x] Create `src/types/api.ts` mirroring backend schemas.
- [x] Render `Toaster` in `main.tsx`.
- [x] Add global error boundary and suspense fallback.
- [x] Create `src/hooks/useApi.ts` and `src/hooks/useWebSocket.ts`.

**DevOps Tasks**
- [x] Create `tradeforge-ai/frontend/Dockerfile` (multi-stage nginx).
- [x] Add `.dockerignore` for frontend and backend.
- [x] Harden `backend/Dockerfile` (non-root user, multi-stage, dev deps separation).
- [x] Update `docker-compose.yml` to use MongoDB instead of SQLite/PostgreSQL.
- [x] Add health checks for all services.
- [x] Create Docker scaffolding (frontend/backend Dockerfiles, `.dockerignore`, MongoDB compose). Verification pending — Docker/Docker Compose not available in this environment.

**Tests**
- [x] Backend smoke test: `/health` returns 200.
- [x] Frontend smoke test: build succeeds and calls `/health`.

**Deliverable:** `docker-compose up` produces a working, talking stack.

---

### Phase 1 — Database, Migrations, Auth & Users
**Goal:** Persistent document model (MongoDB) with secure authentication.

**Backend Tasks**
- [x] Add `User` and `Account` models to `database/models.py`.
- [x] Add password hashing (bcrypt) and JWT/OAuth2 login.
- [x] Add `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`.
- [x] Protect write endpoints with optional auth and user scoping.
- [x] Add multi-tenancy: strategies/backtests scoped to `user_id`.
- [x] ~~Set up Alembic and create initial migration~~ (not needed with MongoDB).
- [ ] Add seed script for demo user and sample strategies.

**Frontend Tasks**
- [x] Create `/login` and `/register` pages.
- [x] Add auth context/provider with token refresh.
- [x] Add route guards for `/app/*`.
- [x] Add logout in top bar.

**DevOps Tasks**
- [x] Switch docker-compose database to MongoDB.
- [ ] Add migration step to startup/CI (MongoDB init/seed).

**Tests**
- [ ] Unit tests for password hashing and JWT.
- [ ] API tests for auth lifecycle.
- [ ] E2E: register → login → access dashboard.

**Deliverable:** Secure, multi-user system. Migrations not required with MongoDB/Beanie.

---

### Phase 2 — Strategies CRUD (First Full E2E Feature)
**Goal:** Users create, list, edit, duplicate, deploy, stop, and delete strategies; changes persist.

**Backend Tasks**
- [x] Verify and harden `routers/strategies.py` CRUD with user scoping.
- [x] Add status filter to `GET /api/v1/strategies` (pagination/search TBD).
- [ ] Add audit logging for strategy mutations.
- [x] Add `POST /api/v1/strategies/{id}/deploy` and `/stop` with mode validation.

**Frontend Tasks**
- [x] Delete `strategies/mockData.ts`; replace with API client (`src/lib/api.ts`) and backend adapter (`src/pages/strategies/adapter.ts`).
- [x] Wire `StrategyListPanel` and strategy list/status flows to backend API.
- [ ] Fully wire `StrategyEditor`, `StrategyToolbar`, `ConditionBuilder`, `IndicatorPalette` form state to API payloads.
- [ ] Add loading skeletons, empty states, error states.
- [ ] Implement `react-hook-form` + Zod validation for strategy forms.
- [ ] Add toast feedback for all mutations.

**Tests**
- [ ] Backend pytest for strategy CRUD + deploy/stop.
- [ ] Frontend Vitest for form validation.
- [ ] Playwright E2E: create → edit → duplicate → deploy → stop → delete.

**Deliverable:** Fully functional strategy builder and manager.

---

### Phase 3 — Backtest Engine (Remove Stub)
**Goal:** Real backtest execution with metrics, equity curve, trade log, and monthly heatmap.

**Backend Tasks**
- [ ] Replace stub in `routers/backtest.py` with real `BacktestEngine.run()` call.
- [ ] Move backtest execution to Celery worker; update status/progress in DB.
- [ ] Add `GET /api/v1/backtest/{id}/status`, `/results`, `/equity-curve`, `/trade-log`.
- [ ] Persist results as JSON/Parquet; generate monthly returns heatmap.
- [ ] Add backtest queue with concurrency limits.

**Frontend Tasks**
- [ ] Wire `BacktestWizard` to real endpoints.
- [ ] `Step3_Running.tsx` polls real status/progress.
- [ ] `Step4_Results.tsx` renders real metrics and charts.
- [ ] Delete `backtest/mockData.ts`.

**Tests**
- [ ] Unit tests for `BacktestEngine` with fixture OHLC data.
- [ ] API tests for backtest lifecycle.
- [ ] E2E: select strategy → run backtest → view results.

**Deliverable:** Backtest page runs real simulations end-to-end.

---

### Phase 4 — Market Data & Indicators
**Goal:** Reliable historical and real-time market data feeding the engine.

**Backend Tasks**
- [ ] Fix `core/market_data/ingestor.py` NSE/Yahoo fallback; ensure intraday data strategy.
- [ ] Add Parquet caching and validation.
- [ ] Add `GET /api/v1/market/historical`, `/ltp`, `/nifty50`, `/indicators`.
- [ ] Add scheduled ingestion job (Celery beat) for daily data.
- [ ] Verify all 21 indicators in `core/indicators.py`.

**Frontend Tasks**
- [ ] Wire `MarketTickerBar` and `WatchlistPanel` to market API.
- [ ] Replace random-walk `CandlestickChart` with real OHLC data.
- [ ] Add indicator overlays from backend.

**Tests**
- [ ] Unit tests for indicators.
- [ ] API tests for market data endpoints.

**Deliverable:** Real market data flows through charts and backtests.

---

### Phase 5 — Paper Trading Simulation
**Goal:** Deploy strategies to paper mode; watch virtual capital, positions, signals update live.

**Backend Tasks**
- [ ] Finalize `ExecutionEngine` + `PaperBroker` integration.
- [ ] Add Celery tasks for signal generation and order simulation.
- [ ] Add `GET /api/v1/execute/portfolio`, `/signals`, `/orders`, `/positions`.
- [ ] Integrate risk manager before every order.
- [ ] Add WebSocket broadcast for signal/P&L updates.

**Frontend Tasks**
- [ ] Wire `PaperTrading` page to execution API and WebSocket.
- [ ] Replace `paper/data.ts` with live data.
- [ ] Add real-time virtual capital card, signal log, order book, positions.

**Tests**
- [ ] Unit tests for `PaperBroker`.
- [ ] API tests for deploy/signals/positions.
- [ ] E2E: deploy strategy → signal → position updates.

**Deliverable:** Working paper trading terminal.

---

### Phase 6 — AI Chat & Strategy Generation
**Goal:** Users describe strategies in natural language (English/Hindi) and the AI generates saveable strategies.

**Backend Tasks**
- [ ] Fix `LLMEngine.generate_strategy` to consistently output valid JSON strategy.
- [ ] Add `POST /api/v1/llm/chat`, `/generate-strategy`, `/explain`, `/analyze`.
- [ ] Add prompt guardrails and output validation/retry.
- [ ] Integrate with strategy CRUD so generated strategies can be saved directly.

**Frontend Tasks**
- [ ] Create `/app/ai` route with AI Chat Panel.
- [ ] Build chat UI with prompt suggestions, markdown rendering, strategy preview.
- [ ] Add "Save Strategy" and "Run Backtest" actions from chat.

**Tests**
- [ ] Unit tests for `NLParser` and `StrategyValidator`.
- [ ] API tests for LLM endpoints.
- [ ] E2E: type prompt → generated strategy → save → backtest.

**Deliverable:** AI-assisted strategy creation works end-to-end.

---

### Phase 7 — Training Dashboard & Model Registry
**Goal:** Full visibility and control over model training, versions, and rollout.

**Backend Tasks**
- [ ] Move auto-training to Celery worker (decoupled from API process).
- [ ] Fix or replace `llm_engine.fine_tune()` with working LoRA/PEFT run.
- [ ] Add `POST /api/v1/train/trigger`, `/start-auto`, `/stop-auto`, `GET /status`, `/jobs`.
- [ ] Add `GET /api/v1/models`, `/compare`, `/activate`, `/rollback`, `/archive`.
- [ ] Integrate experiment tracking (MLflow/W&B).

**Frontend Tasks**
- [ ] Create `/app/training` Training Dashboard with loss curves, metrics, job list.
- [ ] Create `/app/models` Model Manager with versions, active model, rollback.

**Tests**
- [ ] Unit tests for `AutoTrainingPipeline` and `ModelRegistry`.
- [ ] API tests for training/model endpoints.
- [ ] E2E: trigger training → view job → activate model.

**Deliverable:** Training and model management fully functional.

---

### Phase 8 — RAG Activation
**Goal:** AI responses are grounded in retrieved strategies, backtests, trades, and market context.

**Backend Tasks**
- [ ] Initialize `TradeForgeRAG` in `main.py` lifespan.
- [ ] Auto-ingest strategies, backtests, trades on create/update.
- [ ] Add real news/commentary ingestion source or documented placeholder.
- [ ] Wire RAG context into `/api/v1/llm/chat` and `/analyze`.

**Frontend Tasks**
- [ ] Show source citations in AI chat.
- [ ] Add market regime context card.

**Tests**
- [ ] Unit tests for retriever/reranker/prompt builder.
- [ ] API tests for RAG-augmented chat.

**Deliverable:** RAG-powered AI assistant.

---

### Phase 9 — Live Trading & Broker Connectors
**Goal:** Users connect real brokers and deploy strategies to live mode with full safety.

**Backend Tasks**
- [ ] Implement missing Upstox broker connector.
- [ ] Add dynamic broker selection from `BrokerConfig`.
- [ ] Encrypt broker credentials at rest (AES-256-GCM).
- [ ] Add live-mode approval workflow and audit logging.
- [ ] Harden kill switch, daily loss limit, auto square-off, market hours.
- [ ] Add circuit breaker for broker API failures.

**Frontend Tasks**
- [ ] Wire `BrokerAPISettings` to real connect/disconnect APIs.
- [ ] Add live trading toggle with confirmation and risk warnings.
- [ ] Wire `LiveTrading` page to real execution signals and broker order book.

**Tests**
- [ ] Unit tests for all broker connectors with mocked HTTP.
- [ ] API tests for live deploy/kill-switch.
- [ ] E2E: connect paper broker → deploy → kill switch works.

**Deliverable:** Live trading ready for supervised pilot.

---

### Phase 10 — Analytics, Settings & Reporting
**Goal:** Complete remaining UI surfaces with real data and polish.

**Backend Tasks**
- [ ] Add `/api/v1/analytics/*` endpoints (P&L, performance, trade journal, drawdown, monthly report).
- [ ] Add report export (CSV/PDF).
- [ ] Add settings endpoints for account, broker, risk, preferences, notifications.

**Frontend Tasks**
- [ ] Wire `Analytics` page and all sub-components to real API.
- [ ] Wire all `Settings` forms to backend.
- [ ] Add mobile-responsive layouts for app pages.
- [ ] Add onboarding flow and in-app help.

**Tests**
- [ ] E2E for analytics and settings.

**Deliverable:** Complete, polished product surface.

---

### Phase 11 — Security, Compliance & Rate Limiting
**Goal:** Platform is safe to expose to users.

**Backend Tasks**
- [ ] Lock CORS to exact origins.
- [ ] Add rate limiting (`slowapi`) on all endpoints; stricter on execution/kill-switch.
- [ ] Add security headers middleware (HSTS, CSP, X-Frame-Options, etc.).
- [ ] Add structured audit log table for all trading actions.
- [ ] Add input sanitization and output encoding.
- [ ] Add request/response logging with correlation IDs.

**Frontend Tasks**
- [ ] Add permission-aware UI (hide live trading until approved).
- [ ] Add security disclaimers and kill-switch visibility.

**Tests**
- [ ] Security tests: CORS, rate limits, auth bypass attempts.
- [ ] Audit log verification.

**Deliverable:** Security-hardened platform.

---

### Phase 12 — DevOps, MLOps & Observability
**Goal:** Production-ready deployment and operations.

**DevOps Tasks**
- [ ] Add GitHub Actions CI/CD: lint, test, build, security scan, push images.
- [ ] Add staging and production environment configs.
- [ ] Add nginx reverse proxy with SSL.
- [ ] Add DB backup/restore scripts and scheduled backups.
- [ ] Add `.pre-commit-config.yaml`.
- [ ] Add dependency vulnerability scanning.

**MLOps Tasks**
- [ ] Integrate MLflow or Weights & Biases.
- [ ] Add DVC for dataset/model versioning.
- [ ] Add model drift detection.
- [ ] Add champion/challenger A/B rollout.
- [ ] Move artifacts to S3-compatible object storage.

**Observability Tasks**
- [ ] Add Prometheus `/metrics` endpoint.
- [ ] Add Grafana dashboards.
- [ ] Add Sentry error tracking.
- [ ] Add alerting (training failures, kill-switch, broker downtime).

**Tests**
- [ ] Load tests with `locust`/`k6`.
- [ ] Disaster-recovery drill.

**Deliverable:** Production-ready deployment with monitoring and MLOps.

---

## 6. Code Structure Standards

- **Backend:**
  - All routers under `/api/v1/`.
  - Services injected via FastAPI dependencies.
  - Pydantic schemas in `shared/schemas.py`.
  - Database models in `database/models.py`; migrations via Alembic.
  - Core business logic in `core/`; no HTTP logic in core.
  - Broker connectors implement `BaseBroker` interface.
  - Background work via Celery tasks in `tasks/`.
  - Tests mirror source structure under `tests/`.

- **Frontend:**
  - API client centralized in `src/lib/api.ts`.
  - All data fetched from backend; no local mock arrays for product data.
  - Forms use `react-hook-form` + Zod.
  - Components are typed; no `any` propagation.
  - Feature folders under `src/pages/` and `src/components/`.
  - Tests co-located or under `src/__tests__/`.

- **DevOps:**
  - Multi-stage Dockerfiles, non-root users.
  - Environment-specific configs in `config/` or `.env.{env}`.
  - Infrastructure as code where possible (Docker Compose for local, Terraform/CloudFormation optional for cloud).

---

## 7. Testing Requirements

Every phase must include:

- **Backend unit tests:** pytest for core logic, routers, and services.
- **Frontend unit tests:** Vitest + React Testing Library for hooks/components.
- **Integration tests:** API contract tests.
- **E2E tests:** Playwright covering the main user journey.
- **Target coverage:** 80%+ for backend, 70%+ for frontend.

Security:
- `bandit` for Python.
- `npm audit` for frontend.
- OWASP ZAP baseline scan in CI.

---

## 8. Definition of Done (Per Phase)

A phase is complete only when:

1. All tasks checked off.
2. Feature works end-to-end (frontend → API → DB → response → UI).
3. Unit, integration, and E2E tests pass.
4. Docker Compose builds and runs.
5. No new lint/security warnings.
6. Documentation updated (README, API docs, runbook if needed).
7. Code reviewed and merged.

---

## 9. Immediate First Actions (Phase 0/1 → Phase 2)

1. ~~Fix `requirements.txt` and install dependencies.~~
2. ~~Replace SQLAlchemy/SQLite with MongoDB/Beanie models.~~
3. ~~Fix `core/__init__.py` stale imports.~~
4. ~~Create `.env` with `SECRET_KEY`.~~
5. ~~Create `frontend/Dockerfile` and `.dockerignore`.~~
6. ~~Add API client, auth, Toaster, and typed hooks to frontend.~~
7. ~~Add first smoke tests.~~
8. **Next:** Complete strategies editor wiring (form state → backend payload, validation, toast feedback).
9. **Next:** Replace backtest stub with real `BacktestEngine.run()` execution and frontend polling.
10. **Next:** Lock CORS to exact origins and add rate limiting/security headers.

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Scope is large | Strict phase gates; no skipping phases; each phase delivers a working E2E increment. |
| Live trading danger | Live mode locked behind feature flag and admin approval until Phase 11. |
| Broker API costs | All connectors tested in paper/sandbox mode first. |
| Training costs | Use small LoRA adapters; auto-training opt-in; GPU-only tasks queued. |
| Data reliability | Validate against known reference prices; add data-quality checks. |
| Regulatory | Audit logs, disclaimers, kill-switch; legal review before public launch. |

---

## 11. Single Approach

There is only one approach: **complete the full product end-to-end, phase by phase, with no shortcuts.** Each phase builds on the previous, and every feature is wired, tested, and hardened before moving on.
