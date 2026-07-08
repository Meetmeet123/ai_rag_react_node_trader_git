"""
Celery tasks for paper/live execution signal generation and order simulation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

import rag_service
from celery_app import celery_app
from config import settings
from core.broker.paper_broker import PaperBroker
from core.condition_evaluator import evaluate_conditions
from core.execution_engine import (
    ExecutionEngine,
    ExecutionMode,
    SignalDirection,
    TradeSignal,
)
from core.market_data.ingestor import MarketDataIngestor
from core.risk_manager import RiskManager
from database.models import (
    BrokerName,
    Signal,
    SignalStatus,
    Strategy,
    StrategyStatus,
    Trade,
    TradeDirection,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lookback_days_for_timeframe(timeframe: str, bars: int = 100) -> int:
    """Return a day count that should yield at least ``bars`` candles."""
    multipliers = {
        "1m": 7,
        "5m": 7,
        "15m": 7,
        "1h": 30,
        "1d": 200,
    }
    return multipliers.get(timeframe, 30)


def _latest_condition_value(series: Optional[pd.Series]) -> bool:
    """Safely return the latest boolean value from a condition series."""
    if series is None or series.empty:
        return False
    value = series.iloc[-1]
    if pd.isna(value):
        return False
    return bool(value)


async def _has_open_long_position(strategy: Strategy) -> bool:
    """Return True if the latest signal for the strategy is an open BUY."""
    latest_signals = (
        await Signal.find({"strategy_id": strategy.id})
        .sort([("created_at", -1)])
        .limit(1)
        .to_list()
    )

    if not latest_signals:
        return False

    latest = latest_signals[0]
    return latest.direction == TradeDirection.BUY and latest.status in (
        SignalStatus.PENDING,
        SignalStatus.EXECUTED,
    )


async def _process_strategy(strategy: Strategy) -> Dict[str, Any]:
    """Evaluate a single strategy and execute a signal if conditions fire."""
    strategy_id_str = str(strategy.id)
    symbol = strategy.instrument.upper()
    log_ctx = {"strategy_id": strategy_id_str, "symbol": symbol}
    logger.info("Evaluating strategy {}", log_ctx)

    ingestor = MarketDataIngestor(data_dir=settings.HISTORICAL_DATA_DIR)
    try:
        timeframe = strategy.timeframe or "1d"
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=_lookback_days_for_timeframe(timeframe))

        df = await ingestor.fetch_historical(
            symbol,
            from_date,
            to_date,
            timeframe=timeframe,
        )

        if df.empty or len(df) < 2:
            logger.warning(
                "Insufficient market data for strategy {} rows={}",
                log_ctx,
                len(df),
            )
            return {
                "strategy_id": strategy_id_str,
                "signal_created": 0,
                "trade_created": 0,
                "reason": "insufficient_data",
            }

        # Normalise columns to the lowercase format expected by the evaluator.
        df.columns = [str(c).lower() for c in df.columns]

        entry_series = evaluate_conditions(df, strategy.entry_conditions or [])
        exit_series = evaluate_conditions(df, strategy.exit_conditions or [])

        entry_triggered = _latest_condition_value(entry_series)
        exit_triggered = _latest_condition_value(exit_series)

        logger.info(
            "Strategy {} conditions entry={} exit={}",
            log_ctx,
            entry_triggered,
            exit_triggered,
        )

        has_open_long = await _has_open_long_position(strategy)

        signal_direction: Optional[SignalDirection] = None
        if entry_triggered and not has_open_long:
            signal_direction = SignalDirection.BUY
        elif exit_triggered and has_open_long:
            signal_direction = SignalDirection.SELL
        else:
            logger.info("No signal generated for strategy {}", log_ctx)
            return {
                "strategy_id": strategy_id_str,
                "signal_created": 0,
                "trade_created": 0,
                "reason": "no_signal",
            }

        quantity = max(int(strategy.position_sizing_value or 1), 1)
        signal_price = float(df["close"].iloc[-1])

        trade_signal = TradeSignal(
            symbol=symbol,
            direction=signal_direction,
            quantity=quantity,
            price=signal_price,
            confidence=1.0,
            strategy_id=strategy_id_str,
            model_version="paper",
            metadata={
                "timeframe": timeframe,
                "entry_conditions_met": entry_triggered,
                "exit_conditions_met": exit_triggered,
            },
        )

        broker = PaperBroker(initial_balance=settings.DEFAULT_CAPITAL)
        await broker.connect()
        # Use permissive paper-mode risk settings so signal generation is not
        # blocked by conservative defaults during automated evaluation.
        risk = RiskManager(
            config={
                "daily_loss_limit": 1_000_000,
                "max_positions": 100,
                "max_exposure_per_trade_pct": 100,
                "max_exposure_overall_pct": 100,
            }
        )
        engine = ExecutionEngine(broker, risk, mode=ExecutionMode.PAPER)

        try:
            exec_result = await engine.on_signal(trade_signal)
            executed = bool(exec_result.get("success"))
            # The execution engine returns summary metadata; retrieve the
            # actual fill price from the paper broker's trade history.
            if executed and broker.trade_history:
                executed_price = float(broker.trade_history[-1]["price"])
            else:
                executed_price = None
        finally:
            await broker.disconnect()

        logger.info(
            "Execution result for strategy {}: success={} executed_price={}",
            log_ctx,
            executed,
            executed_price,
        )

        signal_doc = Signal(
            user_id=strategy.user_id,
            strategy_id=strategy.id,
            symbol=symbol,
            direction=TradeDirection(signal_direction.value),
            signal_price=signal_price,
            executed_price=executed_price,
            quantity=quantity,
            status=SignalStatus.EXECUTED if executed else SignalStatus.FAILED,
            confidence=trade_signal.confidence,
            indicators_snapshot={
                "entry_triggered": entry_triggered,
                "exit_triggered": exit_triggered,
                "has_open_long": has_open_long,
            },
            executed_at=datetime.utcnow() if executed else None,
        )
        await signal_doc.insert()
        logger.info(
            "Signal document created id={} strategy={} direction={} status={}",
            signal_doc.id,
            strategy_id_str,
            signal_doc.direction.value,
            signal_doc.status.value,
        )

        trade_doc: Optional[Trade] = None
        if executed:
            avg_price = float(executed_price or signal_price)

            if signal_direction == SignalDirection.BUY:
                entry_price = avg_price
                exit_price = None
                pnl = None
            else:
                # Find the preceding BUY signal that opened the long.
                buy_signals = (
                    await Signal.find(
                        {
                            "strategy_id": strategy.id,
                            "direction": TradeDirection.BUY.value,
                        }
                    )
                    .sort([("created_at", -1)])
                    .limit(1)
                    .to_list()
                )
                entry_price = (
                    float(buy_signals[0].executed_price)
                    if buy_signals and buy_signals[0].executed_price
                    else avg_price
                )
                exit_price = avg_price
                pnl = (exit_price - entry_price) * quantity

            trade_doc = Trade(
                user_id=strategy.user_id,
                strategy_id=strategy.id,
                signal_id=signal_doc.id,
                symbol=symbol,
                direction=TradeDirection(signal_direction.value),
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                entry_time=datetime.utcnow(),
                broker=BrokerName.PAPER,
                broker_order_id=str(exec_result.get("order_id", "")),
                is_paper=True,
                pnl=pnl,
            )
            await trade_doc.insert()
            logger.info(
                "Trade document created id={} strategy={} direction={}",
                trade_doc.id,
                strategy_id_str,
                trade_doc.direction.value,
            )

            # Ingest the executed trade into the RAG vector store.
            try:
                rag = rag_service.get_rag_or_none()
                if rag is not None:
                    trade_dict = {
                        "trade_id": str(trade_doc.id),
                        "symbol": trade_doc.symbol,
                        "strategy_name": strategy.name,
                        "strategy_id": str(strategy.id),
                        "side": trade_doc.direction.value,
                        "entry_price": trade_doc.entry_price,
                        "exit_price": trade_doc.exit_price,
                        "quantity": trade_doc.quantity,
                        "entry_time": (
                            trade_doc.entry_time.isoformat()
                            if trade_doc.entry_time
                            else None
                        ),
                        "exit_time": (
                            trade_doc.exit_time.isoformat()
                            if trade_doc.exit_time
                            else None
                        ),
                        "pnl": trade_doc.pnl,
                        "status": (
                            "closed"
                            if signal_direction == SignalDirection.SELL
                            else "open"
                        ),
                    }
                    await rag.ingestion.ingest_trade(trade_dict)
            except Exception as exc:
                logger.warning(
                    "RAG trade ingestion failed for strategy {}: {}",
                    log_ctx,
                    exc,
                )

        return {
            "strategy_id": strategy_id_str,
            "signal_created": 1,
            "trade_created": 1 if trade_doc else 0,
            "direction": signal_direction.value,
            "executed": executed,
            "message": exec_result.get("message", ""),
        }
    except Exception as exc:
        logger.exception("Error processing strategy {}: {}", log_ctx, exc)
        return {
            "strategy_id": strategy_id_str,
            "signal_created": 0,
            "trade_created": 0,
            "error": str(exc),
        }
    finally:
        await ingestor.close()


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    name="tasks.execution.generate_signals",
)
def generate_signals(
    self,
    strategy_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate and execute trading signals for all deployed strategies.

    Queries strategies with status ``PAPER`` or ``ACTIVE``, fetches recent
    market data, evaluates entry/exit conditions, and routes any generated
    signal through the paper execution engine. Persists ``Signal`` and
    ``Trade`` documents when appropriate.

    Args:
        strategy_id: Deprecated single-strategy argument; ignored. Kept for
            backward compatibility with existing callers.
        payload: Deprecated payload argument; ignored.
    """
    logger.info("Signal generation task started strategy_id={}", strategy_id)

    async def _run() -> Dict[str, Any]:
        strategies = await Strategy.find(
            {
                "status": {
                    "$in": [
                        StrategyStatus.PAPER.value,
                        StrategyStatus.ACTIVE.value,
                    ]
                }
            }
        ).to_list()
        logger.info("Found {} deployed strategies", len(strategies))

        if not strategies:
            logger.info("No deployed strategies; nothing to evaluate")
            return {
                "strategies_evaluated": 0,
                "signals_generated": 0,
                "trades_executed": 0,
            }

        results: List[Dict[str, Any]] = []
        total_signals = 0
        total_trades = 0

        for strategy in strategies:
            result = await _process_strategy(strategy)
            results.append(result)
            total_signals += result.get("signal_created", 0)
            total_trades += result.get("trade_created", 0)

        summary = {
            "strategies_evaluated": len(strategies),
            "signals_generated": total_signals,
            "trades_executed": total_trades,
            "results": results,
        }
        logger.info("Signal generation task completed {}", summary)
        return summary

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("Signal generation task failed: {}", exc)
        try:
            self.retry(exc=exc)
        except Exception as retry_exc:
            logger.error(
                "Signal generation retry/max retries exceeded: {}",
                retry_exc,
            )
        raise


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    name="tasks.execution.simulate_order",
)
def simulate_order(
    self,
    order_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Simulate an order in paper mode.

    Placeholder for Celery-based paper order simulation. Full implementation
    can delegate to :class:`PaperBroker` if needed in the future.
    """
    logger.info("Simulate order task started payload={}", order_payload)
    result = {
        "status": "pending_implementation",
        "message": "Order simulation task scaffold is wired; integrate PaperBroker when required.",
    }
    logger.info("Simulate order task completed")
    return result
