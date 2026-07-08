"""Pytest fixtures and configuration."""

from __future__ import annotations

import os
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Use a dedicated local test database so tests do not pollute the Atlas cluster.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/tradeforge_test")
os.environ.setdefault("MONGODB_DB_NAME", "tradeforge_test")

# Run Celery tasks eagerly in tests so no Redis worker is required.
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")


class _FakeRAGEngine:
    """Lightweight fake RAG engine used to avoid heavy model downloads in tests."""

    def __init__(self) -> None:
        self._queries_served = 0
        self._total_query_time_ms = 0.0
        self.ingestion = self
        self._ingested: Dict[str, List[Dict[str, Any]]] = {
            "strategies": [],
            "backtests": [],
            "trades": [],
        }

    def start_ingestion(self, **_: Any) -> None:
        pass

    def close(self) -> None:
        pass

    def get_stats(self) -> Dict[str, Any]:
        return {
            "status": "initialized",
            "performance": {
                "queries_served": self._queries_served,
                "total_query_time_ms": self._total_query_time_ms,
            },
            "ingestion": {
                "is_running": True,
                "ingestion_counts": {
                    "strategies": len(self._ingested["strategies"]),
                    "backtests": len(self._ingested["backtests"]),
                    "trades": len(self._ingested["trades"]),
                },
            },
        }

    def get_ingestion_stats(self) -> Dict[str, Any]:
        return self.get_stats()["ingestion"]

    async def ingest_strategy(self, strategy: Dict[str, Any]) -> bool:
        self._ingested["strategies"].append(strategy)
        return True

    async def ingest_backtest_result(self, backtest: Dict[str, Any]) -> bool:
        self._ingested["backtests"].append(backtest)
        return True

    async def ingest_trade(self, trade: Dict[str, Any]) -> bool:
        self._ingested["trades"].append(trade)
        return True

    async def get_strategy_context(
        self, user_prompt: str, instrument: str, segment: str = "equity"
    ) -> Dict[str, Any]:
        self._queries_served += 1
        return {
            "query": user_prompt,
            "instrument": instrument,
            "segment": segment,
            "similar_strategies": [],
            "market_context": [],
            "recent_news": [],
            "indicator_explanations": [],
            "backtest_insights": [],
            "market_regime": None,
        }

    def build_rag_prompt(
        self,
        template_type: str,
        query: str,
        retrieved_context: Dict[str, Any],
        **_: Any,
    ) -> str:
        return f"[{template_type}] {query}\nContext: {retrieved_context}"

    async def analyze_backtest(
        self, backtest_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        self._queries_served += 1
        return {
            "prompt": "RAG backtest analysis prompt",
            "similar_backtests": [],
            "market_conditions": [],
        }

    async def analyze_market(self, symbol: str) -> Dict[str, Any]:
        self._queries_served += 1
        return {
            "prompt": f"Market analysis for {symbol}",
            "market_context": [],
            "news": [],
            "regime": None,
        }

    async def find_similar_strategies(
        self, description: str, top_k: int = 5, **_: Any
    ) -> List[Dict[str, Any]]:
        self._queries_served += 1
        return []


@pytest.fixture(scope="session")
def fake_rag_engine() -> _FakeRAGEngine:
    """Return a shared fake RAG engine for the test session."""
    return _FakeRAGEngine()


@pytest.fixture(scope="session", autouse=True)
def mock_rag_service(fake_rag_engine: _FakeRAGEngine) -> None:
    """Patch the RAG service so tests never download transformer models."""
    with (
        patch("rag_service.get_rag", return_value=fake_rag_engine),
        patch("rag_service.get_rag_or_none", return_value=fake_rag_engine),
    ):
        yield


@pytest.fixture(scope="session")
def client(mock_rag_service: None) -> TestClient:
    """Return a TestClient for the FastAPI app with lifespan executed."""
    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def celery_eager_mode() -> None:
    """Force Celery tasks to run synchronously during tests."""
    from celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.result_backend = "cache+memory://"
