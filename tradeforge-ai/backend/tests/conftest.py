"""Pytest fixtures and configuration."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Return a TestClient for the FastAPI app."""
    from main import app

    return TestClient(app)
