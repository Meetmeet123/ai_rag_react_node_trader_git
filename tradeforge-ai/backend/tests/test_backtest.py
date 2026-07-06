"""Tests for the backtest router and Celery task wiring."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def test_run_backtest_endpoint(client: TestClient) -> None:
    """End-to-end: create a strategy, enqueue a backtest, and verify completion."""
    strategy_payload = {
        "name": "Celery Backtest Test",
        "instrument": "NIFTY50",
        "segment": "index",
        "timeframe": "1d",
        "entry_conditions": [],
        "exit_conditions": [],
    }
    create_resp = client.post("/api/v1/strategies/", json=strategy_payload)
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["id"]

    start = datetime.utcnow() - timedelta(days=180)
    end = datetime.utcnow()
    backtest_payload = {
        "strategy_id": strategy_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "initial_capital": 100_000,
        "brokerage_per_order": 20,
        "slippage_pct": 0.05,
        "position_sizing_type": "fixed_qty",
        "position_sizing_value": 1,
        "stop_loss_type": "fixed_pct",
        "stop_loss_value": 1.0,
        "target_type": "fixed_pct",
        "target_value": 2.0,
        "allow_short": True,
    }

    response = client.post("/api/v1/backtest/run", json=backtest_payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "running"
    assert data["strategy_id"] == strategy_id

    # With eager Celery tasks the backtest should already be completed.
    result_response = client.get(f"/api/v1/backtest/{data['id']}")
    assert result_response.status_code == 200
    result = result_response.json()
    assert result["status"] == "completed"
    assert result["total_trades"] is not None
    assert result["equity_curve"] is not None

    client.delete(f"/api/v1/strategies/{strategy_id}")
