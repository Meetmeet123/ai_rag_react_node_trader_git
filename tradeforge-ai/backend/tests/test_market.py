"""Tests for the market data router."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import routers.market as market_router
from core.market_data.ingestor import MarketDataIngestor


class _FakeIngestor(MarketDataIngestor):
    """In-memory ingestor that never hits the network."""

    def __init__(self) -> None:
        # Skip parent __init__ to avoid creating an httpx client.
        self.data_dir = ""
        self._nse_session_ready = False
        self._session_lock = None  # type: ignore[assignment]

    async def fetch_historical(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        dates = pd.date_range(from_date, to_date, freq="D")
        base = 2500.0 + hash(symbol) % 100
        data = {
            "timestamp": dates,
            "open": [base + i * 0.1 for i in range(len(dates))],
            "high": [base + i * 0.1 + 1.0 for i in range(len(dates))],
            "low": [base + i * 0.1 - 1.0 for i in range(len(dates))],
            "close": [base + i * 0.1 + 0.5 for i in range(len(dates))],
            "volume": [1000 + i for i in range(len(dates))],
        }
        return pd.DataFrame(data)

    async def update_realtime(self, symbol: str) -> Optional[pd.DataFrame]:
        return await self.fetch_historical(
            symbol,
            datetime.now() - timedelta(days=5),
            datetime.now(),
            timeframe="1d",
        )

    def get_nifty50_constituents(self) -> list[str]:
        return ["RELIANCE", "TCS", "INFY"]

    async def close(self) -> None:
        pass


@pytest.fixture(scope="function")
def fake_market_ingestor(client: TestClient) -> None:
    """Replace the real market ingestor with a fake one for tests."""
    original = market_router._ingestor
    market_router._ingestor = _FakeIngestor()
    yield
    market_router._ingestor = original


def test_get_historical(client: TestClient, fake_market_ingestor: None) -> None:
    from_date = (datetime.now() - timedelta(days=30)).isoformat()
    to_date = datetime.now().isoformat()
    response = client.get(
        "/api/v1/market/historical/RELIANCE",
        params={"from_date": from_date, "to_date": to_date, "timeframe": "1d"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "RELIANCE"
    assert data["timeframe"] == "1d"
    assert data["records"] > 0
    assert "open" in data["data"][0]


def test_get_ltp(client: TestClient, fake_market_ingestor: None) -> None:
    response = client.get("/api/v1/market/ltp/RELIANCE")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "RELIANCE"
    assert data["price"] > 0


def test_get_nifty50(client: TestClient, fake_market_ingestor: None) -> None:
    response = client.get("/api/v1/market/nifty50")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert "RELIANCE" in data["constituents"]


def test_get_indicators_for_symbol(
    client: TestClient, fake_market_ingestor: None
) -> None:
    response = client.get("/api/v1/market/indicators/RELIANCE?period=30d")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "RELIANCE"
    assert "price_data" in data
    assert "indicators" in data
    assert "sma_20" in data["indicators"]


def test_post_indicators(client: TestClient) -> None:
    payload = {
        "open_prices": [100.0] * 60,
        "high_prices": [101.0] * 60,
        "low_prices": [99.0] * 60,
        "close_prices": [100.0 + i * 0.1 for i in range(60)],
        "volumes": [1000] * 60,
    }
    response = client.post("/api/v1/market/indicators", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "indicators" in data
    assert "sma_20" in data["indicators"]
    assert data["record_count"] == 60


def test_list_symbols(client: TestClient, fake_market_ingestor: None) -> None:
    response = client.get("/api/v1/market/symbols")
    assert response.status_code == 200
    data = response.json()
    assert "nifty50" in data
    assert "popular" in data
