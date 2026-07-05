"""Backend smoke tests."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    """The /health endpoint should return a healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "TradeForge AI"
    assert "services" in data


def test_root_endpoint(client: TestClient) -> None:
    """The root endpoint should expose app metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "TradeForge AI"
    assert data["api_prefix"] == "/api/v1"
