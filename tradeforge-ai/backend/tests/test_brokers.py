"""Tests for broker security, factory, and broker configuration API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.broker.factory import create_broker_from_config
from core.broker.paper_broker import PaperBroker
from core.broker.upstox import UpstoxBroker
from core.security import decrypt_value, encrypt_value, mask_value
from database.models import BrokerConfig, BrokerName


def test_encrypt_decrypt_roundtrip() -> None:
    """Encrypting and decrypting a value should return the original."""
    original = "super-secret-access-token"
    encrypted = encrypt_value(original)
    assert encrypted is not None
    assert encrypted != original
    decrypted = decrypt_value(encrypted)
    assert decrypted == original


def test_encrypt_decrypt_none_or_empty() -> None:
    """None and empty strings pass through unchanged."""
    assert encrypt_value(None) is None
    assert encrypt_value("") == ""
    assert decrypt_value(None) is None
    assert decrypt_value("") == ""


def test_mask_value() -> None:
    """mask_value hides all but the last four characters."""
    assert mask_value("abcdef1234") == "****1234"
    assert mask_value("1234") == "****1234"
    assert mask_value("") == "Not set"
    assert mask_value(None) == "Not set"


def test_upstox_get_login_url() -> None:
    """get_login_url builds the expected Upstox OAuth URL."""
    url = UpstoxBroker.get_login_url("my_api_key", "http://localhost/callback")
    assert url.startswith("https://api.upstox.com/v2/login/authorization/dialog")
    assert "client_id=my_api_key" in url
    assert "redirect_uri=http://localhost/callback" in url
    assert "response_type=code" in url


def test_create_broker_from_config_upstox(client: TestClient) -> None:
    """Factory returns an UpstoxBroker for an Upstox config."""
    config = BrokerConfig(
        broker=BrokerName.UPSTOX,
        api_key="api_key",
        api_secret=encrypt_value("api_secret"),
        access_token=encrypt_value("access_token"),
        client_id="client_id",
        is_active=True,
    )
    broker = create_broker_from_config(config)
    assert isinstance(broker, UpstoxBroker)
    assert broker.name == "upstox"
    assert broker.api_key == "api_key"
    assert broker.client_id == "client_id"
    # decrypted
    assert broker.access_token == "access_token"


def test_create_broker_from_config_paper(client: TestClient) -> None:
    """Factory returns a PaperBroker for a paper config."""
    config = BrokerConfig(
        broker=BrokerName.PAPER,
        is_active=True,
        is_paper=True,
    )
    broker = create_broker_from_config(config)
    assert isinstance(broker, PaperBroker)
    assert broker.name == "paper"


def test_broker_config_save_and_list(client: TestClient) -> None:
    """Saving a broker config and listing brokers returns the masked config."""
    payload = {
        "broker": "upstox",
        "api_key": "test_api_key",
        "api_secret": "test_api_secret",
        "client_id": "test_client_id",
        "access_token": "test_access_token",
        "redirect_uri": "http://localhost/callback",
        "is_active": True,
        "is_paper": False,
    }
    response = client.post("/api/v1/brokers/config", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["broker"] == "upstox"
    assert data["api_key"].startswith("****")
    assert data["api_key"] != payload["api_key"]
    assert data["api_secret"].startswith("****")
    assert data["api_secret"] != payload["api_secret"]
    assert data["access_token"].startswith("****")
    assert data["access_token"] != payload["access_token"]
    assert data["is_active"] is True

    response = client.get("/api/v1/brokers/")
    assert response.status_code == 200, response.text
    list_data = response.json()
    assert "upstox" in list_data["brokers"]
    assert list_data["active"] is not None
    assert list_data["active"]["id"] == data["id"]
