"""
Paper Trading Broker — Simulates order execution for testing.

Maintains virtual positions, P&L, and balance.  Simulates realistic
execution with configurable slippage and (optional) random latency.
Implements the :class:`BaseBroker` interface so it can be used as a
drop-in replacement for any real broker inside the
:class:`~core.execution_engine.ExecutionEngine`.

Typical usage::

    broker = PaperBroker(initial_balance=1_000_000, slippage_pct=0.05)
    await broker.connect()
    result = await broker.place_order(order_params)
    positions = await broker.get_positions()
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from core.broker.base import (
    BaseBroker,
    Exchange,
    FundsData,
    HoldingData,
    OrderParams,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionData,
    ProductType,
)


# ---------------------------------------------------------------------------
# Internal position tracking for paper broker
# ---------------------------------------------------------------------------

@dataclass
class _PaperPosition:
    """Internal mutable position record."""
    symbol: str
    exchange: Exchange
    product: ProductType
    quantity: int
    avg_price: float
    last_price: float
    buy_qty: int = 0
    sell_qty: int = 0
    buy_price: float = 0.0
    sell_price: float = 0.0


# ---------------------------------------------------------------------------
# Paper Broker
# ---------------------------------------------------------------------------

class PaperBroker(BaseBroker):
    """Paper trading simulator.

    Attributes:
        name: Broker identifier (``"paper"``).
        balance: Available cash balance.
        used_margin: Margin currently blocked.
        positions: Map of ``symbol -> _PaperPosition``.
        orders: Map of ``order_id -> OrderResult``.
        trade_history: Chronological list of filled trade dicts.
    """

    name: str = "paper"

    def __init__(
        self,
        initial_balance: float = 1_000_000.0,
        slippage_pct: float = 0.05,
        brokerage_per_order: float = 20.0,
        simulate_latency: bool = False,
        latency_ms_range: tuple = (10, 100),
    ):
        self._initial_balance = initial_balance
        self.balance = initial_balance
        self.used_margin = 0.0
        self.positions: Dict[str, _PaperPosition] = {}
        self.orders: Dict[str, OrderResult] = {}
        self.trade_history: List[Dict[str, Any]] = []

        self.slippage_pct = slippage_pct
        self.brokerage = brokerage_per_order
        self.simulate_latency = simulate_latency
        self.latency_ms_range = latency_ms_range

        self._order_counter = 0
        self._connected = False
        self._price_cache: Dict[str, float] = {}  # symbol -> simulated LTP

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect the paper broker (always succeeds)."""
        self._connected = True
        self.balance = self._initial_balance
        logger.info(
            "PaperBroker connected | balance={:,.2f} slippage={}% brokerage={}",
            self.balance, self.slippage_pct, self.brokerage,
        )
        return True

    async def disconnect(self) -> None:
        """Disconnect and release resources."""
        self._connected = False
        logger.info("PaperBroker disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Latency simulation
    # ------------------------------------------------------------------

    async def _maybe_sleep(self) -> None:
        """Optionally add artificial latency to simulate network delay."""
        if self.simulate_latency:
            ms = random.randint(*self.latency_ms_range)
            await asyncio.sleep(ms / 1000)

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place a simulated order.

        For market orders the fill price is the ``close`` price (or a
        simulated LTP) with slippage applied.  For limit orders the fill
        only occurs if the limit price is reachable.

        Args:
            params: Normalised :class:`OrderParams`.

        Returns:
            :class:`OrderResult` with a generated ``order_id``.
        """
        await self._maybe_sleep()

        self._order_counter += 1
        order_id = f"PAPER-{self._order_counter:06d}"

        # Get fill price
        fill_price = self._get_fill_price(params)
        if fill_price <= 0:
            result = OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol=params.symbol,
                quantity=params.quantity,
                message="No price data available for symbol",
            )
            self.orders[order_id] = result
            return result

        # Apply slippage
        slipped_price = self._apply_slippage(fill_price, params.side)
        turnover = slipped_price * params.quantity
        brokerage = self.brokerage

        # Margin check
        required_margin = turnover * self._margin_pct(params.product_type)
        if params.side == OrderSide.BUY and self.balance < required_margin + brokerage:
            result = OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                symbol=params.symbol,
                quantity=params.quantity,
                message=f"Insufficient balance: {self.balance:,.2f} < {required_margin + brokerage:,.2f}",
            )
            self.orders[order_id] = result
            logger.warning("Order rejected (margin): {} {} qty={}", params.symbol, params.side.value, params.quantity)
            return result

        # Execute
        self._update_position(params, slipped_price)
        self.balance -= brokerage
        if params.side == OrderSide.BUY:
            self.used_margin += required_margin

        # Record
        self.trade_history.append({
            "order_id": order_id,
            "symbol": params.symbol,
            "side": params.side.value,
            "quantity": params.quantity,
            "price": slipped_price,
            "brokerage": brokerage,
            "timestamp": datetime.utcnow().isoformat(),
        })

        result = OrderResult(
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            symbol=params.symbol,
            quantity=params.quantity,
            filled_qty=params.quantity,
            avg_price=slipped_price,
            message="Order filled (paper)",
        )
        self.orders[order_id] = result

        logger.debug(
            "Paper fill | {} {} {} @ {:.2f} brokerage={}",
            params.side.value, params.symbol, params.quantity, slipped_price, brokerage,
        )
        return result

    async def modify_order(
        self,
        order_id: str,
        params: Dict[str, Any],
    ) -> OrderResult:
        """Modify an existing paper order.

        In paper mode modifications are instant and always succeed if the
        order exists and is still open.
        """
        await self._maybe_sleep()

        if order_id not in self.orders:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found",
            )

        existing = self.orders[order_id]
        if existing.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=f"Cannot modify order with status {existing.status.value}",
            )

        # Update fields
        if "price" in params:
            existing.avg_price = float(params["price"])
        if "quantity" in params:
            existing.quantity = int(params["quantity"])

        existing.status = OrderStatus.MODIFIED
        existing.message = "Order modified (paper)"
        self.orders[order_id] = existing

        logger.debug("Paper order modified | {}", order_id)
        return existing

    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel a pending paper order."""
        await self._maybe_sleep()

        if order_id not in self.orders:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order not found",
            )

        existing = self.orders[order_id]
        if existing.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message=f"Cannot cancel order with status {existing.status.value}",
            )

        existing.status = OrderStatus.CANCELLED
        existing.message = "Order cancelled (paper)"
        self.orders[order_id] = existing

        logger.debug("Paper order cancelled | {}", order_id)
        return existing

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Return the current status of a paper order."""
        if order_id in self.orders:
            return self.orders[order_id]
        return OrderResult(
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="Order not found",
        )

    async def get_order_book(self) -> List[OrderResult]:
        """Return all paper orders."""
        return list(self.orders.values())

    # ------------------------------------------------------------------
    # Portfolio queries
    # ------------------------------------------------------------------

    async def get_positions(self) -> List[PositionData]:
        """Return current virtual positions."""
        result = []
        for sym, pos in self.positions.items():
            pnl = (pos.last_price - pos.avg_price) * pos.quantity if pos.quantity > 0 else \
                  (pos.avg_price - pos.last_price) * abs(pos.quantity)
            result.append(PositionData(
                symbol=pos.symbol,
                exchange=pos.exchange,
                product=pos.product,
                quantity=pos.quantity,
                avg_price=pos.avg_price,
                last_price=pos.last_price,
                pnl=round(pnl, 2),
                buy_quantity=pos.buy_qty,
                sell_quantity=pos.sell_qty,
                buy_price=pos.buy_price,
                sell_price=pos.sell_price,
            ))
        return result

    async def get_holdings(self) -> List[HoldingData]:
        """Return delivery holdings (positions with product CNC)."""
        result = []
        for sym, pos in self.positions.items():
            if pos.product == ProductType.CNC:
                pnl = (pos.last_price - pos.avg_price) * pos.quantity
                result.append(HoldingData(
                    symbol=pos.symbol,
                    exchange=pos.exchange,
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                    last_price=pos.last_price,
                    pnl=round(pnl, 2),
                ))
        return result

    async def get_funds(self) -> FundsData:
        """Return virtual fund details."""
        return FundsData(
            available_cash=self.balance,
            used_margin=self.used_margin,
            opening_balance=self._initial_balance,
        )

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_ltp(self, symbol: str, exchange: Exchange = Exchange.NSE) -> float:
        """Get last traded price.

        In paper mode the price comes from an internal cache that can be
        seeded by the caller via :meth:`set_simulated_price`.
        """
        symbol = symbol.upper().strip()
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        # Return a deterministic pseudo-price based on symbol hash
        # so repeated calls are consistent within a session.
        h = hash(symbol) % 10000
        return float(100 + abs(h) % 4900)

    async def get_ltps(
        self,
        symbols: List[str],
        exchange: Exchange = Exchange.NSE,
    ) -> Dict[str, float]:
        """Batch LTP fetch (optimised single call)."""
        return {sym: await self.get_ltp(sym, exchange) for sym in symbols}

    def set_simulated_price(self, symbol: str, price: float) -> None:
        """Seed the LTP cache for a symbol.

        Call this from your data feed to update prices before order
        placement so the paper broker fills at realistic levels.
        """
        self._price_cache[symbol.upper().strip()] = price

    def set_simulated_prices(self, prices: Dict[str, float]) -> None:
        """Batch-update the LTP cache."""
        for sym, price in prices.items():
            self._price_cache[sym.upper().strip()] = price

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_fill_price(self, params: OrderParams) -> float:
        """Determine the fill price for an order."""
        symbol = params.symbol.upper().strip()

        # Use cached price if available
        if symbol in self._price_cache:
            base_price = self._price_cache[symbol]
        else:
            # Generate deterministic price
            h = hash(symbol) % 10000
            base_price = float(100 + abs(h) % 4900)

        # Limit order: only fill if price is favourable
        if params.order_type == OrderType.LIMIT and params.price > 0:
            if params.side == OrderSide.BUY and base_price > params.price:
                # Price moved above limit – partial / no fill simulation
                return params.price if random.random() > 0.3 else 0.0
            if params.side == OrderSide.SELL and base_price < params.price:
                return params.price if random.random() > 0.3 else 0.0
            return params.price

        # SL order
        if params.order_type in (OrderType.SL, OrderType.SL_M):
            if params.trigger_price > 0:
                # Simulate trigger hit
                return params.trigger_price
            return base_price

        return base_price

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        """Apply slippage to the fill price."""
        factor = self.slippage_pct / 100
        noise = random.uniform(-factor * 0.3, factor * 0.3)  # Small random component
        if side == OrderSide.BUY:
            return round(price * (1 + factor + noise), 2)
        return round(price * (1 - factor - noise), 2)

    def _margin_pct(self, product: ProductType) -> float:
        """Return margin requirement as a fraction."""
        return {
            ProductType.MIS: 0.20,   # 5x leverage = 20% margin
            ProductType.NRML: 1.00,  # Full margin
            ProductType.CNC: 1.00,   # Full cash
        }.get(product, 1.00)

    def _update_position(self, params: OrderParams, fill_price: float) -> None:
        """Update internal position state after a fill."""
        symbol = params.symbol.upper().strip()

        if symbol not in self.positions:
            self.positions[symbol] = _PaperPosition(
                symbol=symbol,
                exchange=params.exchange,
                product=params.product_type,
                quantity=0,
                avg_price=0.0,
                last_price=fill_price,
            )

        pos = self.positions[symbol]
        pos.last_price = fill_price

        if params.side == OrderSide.BUY:
            # Update average price
            total_value = pos.avg_price * pos.quantity + fill_price * params.quantity
            pos.quantity += params.quantity
            pos.avg_price = total_value / pos.quantity if pos.quantity > 0 else 0
            pos.buy_qty += params.quantity
            pos.buy_price = fill_price
        else:
            # Reduce or flip
            if pos.quantity > 0:
                # Closing long
                close_qty = min(params.quantity, pos.quantity)
                pnl = (fill_price - pos.avg_price) * close_qty
                self.balance += pnl
                pos.quantity -= close_qty
                pos.sell_qty += close_qty
                pos.sell_price = fill_price

                if pos.quantity == 0:
                    del self.positions[symbol]
            else:
                # Increasing short
                total_value = abs(pos.avg_price * pos.quantity) + fill_price * params.quantity
                pos.quantity -= params.quantity
                pos.avg_price = total_value / abs(pos.quantity) if pos.quantity != 0 else 0
                pos.sell_qty += params.quantity
                pos.sell_price = fill_price

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all state (useful between backtest runs)."""
        self.balance = self._initial_balance
        self.used_margin = 0.0
        self.positions.clear()
        self.orders.clear()
        self.trade_history.clear()
        self._price_cache.clear()
        self._order_counter = 0
        logger.info("PaperBroker state reset")

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Return chronological trade history."""
        return self.trade_history.copy()
