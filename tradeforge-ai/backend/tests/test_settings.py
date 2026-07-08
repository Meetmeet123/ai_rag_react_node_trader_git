"""Tests for the settings router."""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from config import settings


@pytest.fixture(autouse=True)
def _cleanup_settings() -> Generator[None, None, None]:
    """Reset the global RiskConfig document before and after each test."""
    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    db["risk_configs"].delete_many({"user_id": None})
    yield
    db["risk_configs"].delete_many({"user_id": None})
    client.close()


EXPECTED_KEYS = {
    "daily_loss_limit",
    "daily_loss_limit_enabled",
    "max_positions",
    "max_exposure_per_trade_pct",
    "max_exposure_overall_pct",
    "kill_switch_enabled",
    "auto_square_off_time",
}


def test_get_settings_returns_defaults(client: TestClient) -> None:
    """GET /api/v1/settings/ should return the default risk configuration."""
    response = client.get("/api/v1/settings/")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == EXPECTED_KEYS
    assert data["max_positions"] >= 1
    assert 0 <= data["max_exposure_per_trade_pct"] <= 100
    assert 0 <= data["max_exposure_overall_pct"] <= 100


def test_settings_put_roundtrip(client: TestClient) -> None:
    """PUT /api/v1/settings/ should persist updates that are returned by GET."""
    update_payload = {
        "daily_loss_limit": 5000.0,
        "max_positions": 5,
        "max_exposure_per_trade_pct": 15.0,
        "auto_square_off_time": "14:30",
    }
    put_response = client.put("/api/v1/settings/", json=update_payload)
    assert put_response.status_code == 200
    put_data = put_response.json()
    assert put_data["daily_loss_limit"] == 5000.0
    assert put_data["max_positions"] == 5
    assert put_data["max_exposure_per_trade_pct"] == 15.0
    assert put_data["auto_square_off_time"] == "14:30"

    get_response = client.get("/api/v1/settings/")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["daily_loss_limit"] == 5000.0
    assert get_data["max_positions"] == 5
    assert get_data["max_exposure_per_trade_pct"] == 15.0
    assert get_data["auto_square_off_time"] == "14:30"


def test_settings_validation_rejects_invalid_values(client: TestClient) -> None:
    """Invalid numeric values and malformed time strings should be rejected."""
    invalid_payloads = [
        {"max_exposure_per_trade_pct": 150.0},
        {"max_positions": 0},
        {"daily_loss_limit": -100.0},
        {"auto_square_off_time": "25:00"},
        {"auto_square_off_time": "not-a-time"},
    ]
    for payload in invalid_payloads:
        response = client.put("/api/v1/settings/", json=payload)
        assert response.status_code == 422, f"Payload {payload} should be rejected"
