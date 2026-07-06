"""Tests for the execution signal-generation Celery task."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from beanie import PydanticObjectId

from database.models import Signal, StrategyStatus, Trade
from tasks.execution import generate_signals


def _make_ohlcv(rows: int = 110) -> pd.DataFrame:
    """Return a deterministic OHLCV DataFrame for condition evaluation."""
    base = 100.0
    timestamps = [
        datetime.utcnow() - timedelta(days=rows - i)
        for i in range(rows)
    ]
    data = []
    for idx, ts in enumerate(timestamps):
        close = base + idx * 0.5
        data.append({
            "timestamp": ts,
            "open": close - 1.0,
            "high": close + 1.0,
            "low": close - 1.5,
            "close": close,
            "volume": 1000 + idx,
        })
    return pd.DataFrame(data)


class FakeMarketDataIngestor:
    """In-process fake ingestor that returns canned OHLCV data."""

    def __init__(self, data_dir: str = "") -> None:
        self.data_dir = data_dir

    async def fetch_historical(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        return _make_ohlcv()

    async def close(self) -> None:
        pass


class FakeFindMany:
    """Supports the chained Beanie query API: .sort().limit().to_list()."""

    def __init__(self, documents: List[Any]) -> None:
        self._documents = documents

    def sort(self, *_args, **_kwargs) -> "FakeFindMany":
        return self

    def limit(self, *_args, **_kwargs) -> "FakeFindMany":
        return self

    async def to_list(self) -> List[Any]:
        return self._documents


def _make_strategy(
    entry_conditions: List[dict],
    exit_conditions: List[dict] | None = None,
) -> MagicMock:
    strategy = MagicMock()
    strategy.id = PydanticObjectId()
    strategy.name = "Test Strategy"
    strategy.instrument = "TESTSYM"
    strategy.segment = "equity"
    strategy.timeframe = "1d"
    strategy.definition = {}
    strategy.entry_conditions = entry_conditions
    strategy.exit_conditions = exit_conditions or []
    strategy.position_sizing_value = 5
    strategy.stop_loss_value = 1.0
    strategy.target_value = 2.0
    strategy.status = StrategyStatus.PAPER
    strategy.user_id = None
    return strategy


@pytest.fixture
def bypass_market_hours():
    """Patch RiskManager so market-hour/weekend checks never reject paper trades."""
    from core.risk_manager import RiskCheckResult, RiskManager

    original = RiskManager._check_market_hours
    RiskManager._check_market_hours = lambda self, now: RiskCheckResult(
        allowed=True
    )
    yield
    RiskManager._check_market_hours = original


def test_generate_signals_creates_buy_signal(
    client,
    bypass_market_hours,
) -> None:
    """A deployed strategy with a true entry condition should produce a Signal."""
    strategy = _make_strategy(
        entry_conditions=[
            {
                "indicator": "price",
                "operator": ">",
                "value": "0",
                "valueType": "number",
            }
        ],
    )
    strategies_find = FakeFindMany([strategy])
    signals_find = FakeFindMany([])

    captured_signals: List[Signal] = []
    captured_trades: List[Trade] = []

    async def capture_signal_insert(self: Signal) -> None:
        captured_signals.append(self)

    async def capture_trade_insert(self: Trade) -> None:
        captured_trades.append(self)

    with (
        patch("tasks.execution.Strategy.find", return_value=strategies_find),
        patch("tasks.execution.Signal.find", return_value=signals_find),
        patch.object(Signal, "insert", new=capture_signal_insert),
        patch.object(Trade, "insert", new=capture_trade_insert),
        patch("tasks.execution.MarketDataIngestor", FakeMarketDataIngestor),
    ):
        result = generate_signals.apply().get()

    assert result["strategies_evaluated"] == 1
    assert result["signals_generated"] == 1
    assert result["trades_executed"] == 1

    strategy_result = result["results"][0]
    assert strategy_result["strategy_id"] == str(strategy.id)
    assert strategy_result["signal_created"] == 1
    assert strategy_result["direction"] == "buy"
    assert strategy_result["executed"] is True
    assert strategy_result["trade_created"] == 1

    assert len(captured_signals) == 1
    signal_doc = captured_signals[0]
    assert signal_doc.symbol == "TESTSYM"
    assert signal_doc.direction.value == "buy"
    assert signal_doc.quantity == 5
    assert signal_doc.status.value == "executed"

    assert len(captured_trades) == 1
    trade_doc = captured_trades[0]
    assert trade_doc.symbol == "TESTSYM"
    assert trade_doc.direction.value == "buy"
    assert trade_doc.quantity == 5
    assert trade_doc.entry_price is not None


def test_generate_signals_no_signal_when_conditions_not_met(
    client,
    bypass_market_hours,
) -> None:
    """No signal should be created when neither entry nor exit conditions fire."""
    strategy = _make_strategy(
        entry_conditions=[
            {
                "indicator": "price",
                "operator": "<",
                "value": "0",
                "valueType": "number",
            }
        ],
    )
    strategies_find = FakeFindMany([strategy])
    signals_find = FakeFindMany([])

    captured_signals: List[Signal] = []
    captured_trades: List[Trade] = []

    async def capture_signal_insert(self: Signal) -> None:
        captured_signals.append(self)

    async def capture_trade_insert(self: Trade) -> None:
        captured_trades.append(self)

    with (
        patch("tasks.execution.Strategy.find", return_value=strategies_find),
        patch("tasks.execution.Signal.find", return_value=signals_find),
        patch.object(Signal, "insert", new=capture_signal_insert),
        patch.object(Trade, "insert", new=capture_trade_insert),
        patch("tasks.execution.MarketDataIngestor", FakeMarketDataIngestor),
    ):
        result = generate_signals.apply().get()

    strategy_result = result["results"][0]
    assert strategy_result["signal_created"] == 0
    assert strategy_result["reason"] == "no_signal"

    assert len(captured_signals) == 0
    assert len(captured_trades) == 0
