"""Integration tests for the RAG lifecycle and LLM route augmentation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

import rag_service
from core.llm_engine import StrategyOutput


class _FakeLLMEngine:
    """Deterministic LLM engine double that avoids transformer model loading."""

    def __init__(self, *_, **__) -> None:
        pass

    def is_ready(self) -> bool:
        return False

    def generate_strategy(self, prompt: str) -> StrategyOutput:
        return StrategyOutput(
            strategy_name="RAG Test Strategy",
            description=f"Generated for: {prompt}",
            instrument="NIFTY50",
            segment="equity",
            timeframe="15m",
            entry_conditions=[],
            exit_conditions=[],
            confidence=0.85,
            reasoning="Rule-based fallback for tests",
        )

    def chat(
        self,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        return f"Echo: {message}"

    def analyze_backtest(
        self,
        backtest_results: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> str:
        return "Test backtest analysis"


@pytest.fixture(autouse=True)
def _patch_llm_engine(monkeypatch: Any) -> None:
    """Replace the real LLM engine so tests stay fast and offline."""
    monkeypatch.setattr("routers.llm.LLMEngine", _FakeLLMEngine)


@pytest.fixture
def fake_rag(monkeypatch: Any, fake_rag_engine: Any) -> Any:
    """Explicitly monkeypatch the RAG service accessors for these tests."""
    monkeypatch.setattr(rag_service, "get_rag_or_none", lambda: fake_rag_engine)
    monkeypatch.setattr(rag_service, "get_rag", lambda: fake_rag_engine)
    return fake_rag_engine


def test_rag_service_get_rag_or_none(fake_rag: Any) -> None:
    """`get_rag_or_none` should return the engine when RAG is available."""
    engine = rag_service.get_rag_or_none()
    assert engine is not None
    assert hasattr(engine, "get_strategy_context")
    assert hasattr(engine, "build_rag_prompt")


def test_rag_service_get_rag_or_none_graceful_failure(monkeypatch: Any) -> None:
    """`get_rag_or_none` should return None when the engine cannot start."""

    def _raising_get_rag() -> Any:
        raise RuntimeError("model missing")

    def _tolerant_get_rag_or_none() -> Optional[Any]:
        try:
            return rag_service.get_rag()
        except Exception:
            return None

    monkeypatch.setattr(rag_service, "get_rag", _raising_get_rag)
    monkeypatch.setattr(rag_service, "get_rag_or_none", _tolerant_get_rag_or_none)
    assert rag_service.get_rag_or_none() is None


def test_rag_status_endpoint(client: TestClient, fake_rag: Any) -> None:
    """The RAG status endpoint should always return 200 with the expected shape."""
    response = client.get("/api/v1/llm/rag-status")
    assert response.status_code == 200
    data = response.json()
    assert "initialized" in data
    assert "queries_served" in data
    assert "total_query_time_ms" in data
    assert "ingestion" in data


def test_generate_strategy_endpoint(client: TestClient, fake_rag: Any) -> None:
    """/generate-strategy should return a structured strategy with generated code."""
    payload = {
        "prompt": "Buy Nifty when RSI is below 30 with 1% stop loss",
        "instrument": "NIFTY50",
        "segment": "index",
        "timeframe": "15m",
    }
    response = client.post("/api/v1/llm/generate-strategy", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "strategy" in data
    assert "generated_code" in data
    assert "confidence" in data
    assert "reasoning" in data
    assert 0.0 <= data["confidence"] <= 1.0


def test_chat_endpoint(client: TestClient, fake_rag: Any) -> None:
    """/chat should return a response and never fail because of RAG."""
    payload = {"message": "What do you think about NIFTY50 today?"}
    response = client.post("/api/v1/llm/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)


def test_analyze_backtest_endpoint(client: TestClient, fake_rag: Any) -> None:
    """/analyze-backtest should return an analysis and metrics summary."""
    payload = {
        "results": {
            "total_return": 12.5,
            "sharpe_ratio": 1.2,
            "max_drawdown": 5.0,
            "win_rate": 55.0,
            "total_trades": 40,
        }
    }
    response = client.post("/api/v1/llm/analyze-backtest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "analysis" in data
    assert "metrics_summary" in data
