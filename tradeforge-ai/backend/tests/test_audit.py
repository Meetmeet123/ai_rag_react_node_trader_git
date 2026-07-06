"""Tests for the audit log middleware and admin API."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from config import settings
from database.models import UserRole


def _mongo_client() -> MongoClient:
    """Return a synchronous MongoDB client for test assertions."""
    return MongoClient(settings.MONGODB_URI)


async def _register_user(
    client: TestClient, email: str, username: str, password: str = "testpass123"
) -> Dict[str, Any]:
    """Register a new test user via the API."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _login(
    client: TestClient, username: str, password: str = "testpass123"
) -> str:
    """Authenticate and return an access token."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _make_admin(username: str) -> None:
    """Promote a registered user to admin."""
    mongo = _mongo_client()
    db = mongo[settings.MONGODB_DB_NAME]
    result = db["users"].update_one(
        {"username": username},
        {"$set": {"role": UserRole.ADMIN.value}},
    )
    assert result.matched_count == 1
    mongo.close()


@pytest.fixture(autouse=True)
def _cleanup_audit_logs() -> None:
    """Remove all audit logs before each test."""
    mongo = _mongo_client()
    db = mongo[settings.MONGODB_DB_NAME]
    db["audit_logs"].delete_many({})
    yield
    db["audit_logs"].delete_many({})
    mongo.close()


async def test_mutating_request_creates_audit_log(client: TestClient) -> None:
    """POST /api/v1/strategies/ should create an audit log entry."""
    payload = {
        "name": "Audit Test Strategy",
        "instrument": "RELIANCE",
        "segment": "equity",
        "timeframe": "15m",
    }
    response = client.post("/api/v1/strategies/", json=payload)
    assert response.status_code == 201, response.text

    # Give the fire-and-forget audit task time to complete.
    db = _mongo_client()[settings.MONGODB_DB_NAME]
    logs: list[Dict[str, Any]] = []
    for _ in range(20):
        logs = list(db["audit_logs"].find())
        if logs:
            break
        await asyncio.sleep(0.05)

    assert len(logs) >= 1
    log = logs[0]
    assert log["action"] == "POST"
    assert log["resource"] == "/api/v1/strategies/"
    assert log["status_code"] == 201
    assert log["details"] is not None
    assert log["details"].get("name") == "Audit Test Strategy"


async def test_audit_log_contains_user_when_authenticated(client: TestClient) -> None:
    """Authenticated requests record the acting user in the audit log."""
    suffix = uuid.uuid4().hex[:8]
    username = f"audituser_{suffix}"
    await _register_user(client, f"{username}@test.com", username)
    token = await _login(client, username)

    payload = {"name": "User Audit Strategy", "instrument": "INFY"}
    response = client.post(
        "/api/v1/strategies/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text

    db = _mongo_client()[settings.MONGODB_DB_NAME]
    logs: list[Dict[str, Any]] = []
    for _ in range(20):
        logs = list(db["audit_logs"].find())
        if logs:
            break
        await asyncio.sleep(0.05)

    assert len(logs) >= 1
    log = logs[0]
    assert log["username"] == username
    assert log["role"] is not None


async def test_admin_can_list_audit_logs(client: TestClient) -> None:
    """Admins can retrieve audit logs through the admin-only endpoint."""
    suffix = uuid.uuid4().hex[:8]
    username = f"adminaudit_{suffix}"
    await _register_user(client, f"{username}@test.com", username)
    _make_admin(username)
    token = await _login(client, username)

    # Generate an auditable event.
    client.post("/api/v1/strategies/", json={"name": "Admin Log Strategy", "instrument": "TCS"})
    await asyncio.sleep(0.2)

    response = client.get(
        "/api/v1/audit-logs/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "logs" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(log["resource"] == "/api/v1/strategies/" for log in data["logs"])


async def test_non_admin_cannot_list_audit_logs(client: TestClient) -> None:
    """Non-admin users receive a 403 when accessing audit logs."""
    suffix = uuid.uuid4().hex[:8]
    await _register_user(client, f"normaluser_{suffix}@test.com", f"normaluser_{suffix}")
    token = await _login(client, f"normaluser_{suffix}")

    response = client.get(
        "/api/v1/audit-logs/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"
