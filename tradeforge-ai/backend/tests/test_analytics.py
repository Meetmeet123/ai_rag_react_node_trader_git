"""Tests for the analytics router."""

from __future__ import annotations

from datetime import datetime
from typing import Generator

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from config import settings


@pytest.fixture(autouse=True)
def _cleanup_analytics_trades() -> Generator[None, None, None]:
    """Remove trades and strategies created by analytics tests."""
    mongo_client = MongoClient(settings.MONGODB_URI)
    db = mongo_client[settings.MONGODB_DB_NAME]
    db["trades"].delete_many({"symbol": "ANALYTICSTEST"})
    db["strategies"].delete_many({"name": "Analytics Test Strategy"})
    yield
    db["trades"].delete_many({"symbol": "ANALYTICSTEST"})
    db["strategies"].delete_many({"name": "Analytics Test Strategy"})
    mongo_client.close()


def _mongo_db():
    """Return a synchronous MongoDB database object."""
    client = MongoClient(settings.MONGODB_URI)
    return client[settings.MONGODB_DB_NAME]


def _insert_test_strategy() -> str:
    """Insert a test strategy and return its ID."""
    db = _mongo_db()
    result = db["strategies"].insert_one(
        {
            "name": "Analytics Test Strategy",
            "instrument": "RELIANCE",
            "definition": {"name": "Analytics Test Strategy"},
            "segment": "equity",
            "timeframe": "15m",
            "status": "draft",
            "is_ai_generated": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    return str(result.inserted_id)


def _insert_test_trade(strategy_id: str, pnl: float) -> None:
    """Insert a closed test trade linked to the given strategy."""
    db = _mongo_db()
    now = datetime.utcnow()
    db["trades"].insert_one(
        {
            "strategy_id": ObjectId(strategy_id),
            "symbol": "ANALYTICSTEST",
            "direction": "buy",
            "entry_price": 100.0,
            "exit_price": 110.0 if pnl > 0 else 90.0,
            "quantity": 10,
            "entry_time": now,
            "exit_time": now,
            "pnl": pnl,
            "pnl_pct": 10.0 if pnl > 0 else -10.0,
            "is_paper": True,
            "created_at": now,
            "updated_at": now,
        }
    )


def test_dashboard_endpoint_returns_expected_keys(client: TestClient) -> None:
    """The dashboard endpoint should return the expected top-level keys."""
    response = client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {
        "kpis",
        "daily_pnl",
        "strategy_performance",
        "recent_trades",
    }

    kpis = data["kpis"]
    expected_kpi_keys = {
        "net_pnl",
        "total_trades",
        "win_rate",
        "max_drawdown",
        "avg_profit_per_trade",
        "avg_loss_per_trade",
        "profit_factor",
    }
    assert set(kpis.keys()) == expected_kpi_keys


def test_dashboard_reflects_closed_trades(client: TestClient) -> None:
    """Closed trades should be reflected in dashboard KPIs and strategy performance."""
    strategy_id = _insert_test_strategy()
    _insert_test_trade(strategy_id, 500.0)
    _insert_test_trade(strategy_id, -200.0)

    response = client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()

    assert data["kpis"]["total_trades"] >= 2
    assert data["kpis"]["net_pnl"] == pytest.approx(300.0, abs=0.01)

    strategy_perf = next(
        (s for s in data["strategy_performance"] if s["strategy_id"] == strategy_id),
        None,
    )
    assert strategy_perf is not None
    assert strategy_perf["name"] == "Analytics Test Strategy"
    assert strategy_perf["net_pnl"] == pytest.approx(300.0, abs=0.01)


def test_list_trades_with_pagination(client: TestClient) -> None:
    """The trades list endpoint should support pagination and filtering."""
    strategy_id = _insert_test_strategy()
    _insert_test_trade(strategy_id, 100.0)
    _insert_test_trade(strategy_id, 200.0)

    response = client.get(
        "/api/v1/analytics/trades?symbol=ANALYTICSTEST&limit=1&offset=0"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["trades"]) == 1

    second = client.get(
        "/api/v1/analytics/trades?symbol=ANALYTICSTEST&limit=1&offset=1"
    )
    assert second.status_code == 200
    assert len(second.json()["trades"]) == 1


def test_export_trades_csv(client: TestClient) -> None:
    """The export endpoint should return a CSV with trade data."""
    strategy_id = _insert_test_strategy()
    _insert_test_trade(strategy_id, 150.0)

    response = client.get("/api/v1/analytics/export?symbol=ANALYTICSTEST")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "trades.csv" in response.headers["content-disposition"]

    content = response.content.decode("utf-8")
    assert "id,symbol,strategy_id" in content
    assert "ANALYTICSTEST" in content


def test_metrics_endpoint_contains_request_counter(client: TestClient) -> None:
    """The /metrics endpoint should expose the HTTP request counter."""
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "http_requests_total" in content
