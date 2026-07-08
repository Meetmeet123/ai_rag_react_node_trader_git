"""
OHLC Candle Builder

Builds candles from raw tick data with support for multiple timeframes.
Uses bucket-based aggregation where ticks are grouped into time buckets
defined by the chosen timeframe (e.g., 5-minute buckets).

Example flow:
    builder = OHLCBuilder(timeframe_seconds=300)  # 5-min candles
    for tick in tick_stream:
        candle = builder.add_tick(tick)
        if candle:
            # A candle was completed (bucket closed)
            save_to_db(candle)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger


@dataclass
class Tick:
    """A single market tick (trade execution).

    Attributes:
        timestamp: Exact time of the trade.
        price: Execution price (must be > 0).
        quantity: Number of shares/contracts traded.
        side: Trade direction — 'buy' or 'sell'.
    """

    timestamp: datetime
    price: float
    quantity: int
    side: str  # buy or sell


@dataclass
class CandleBuilderState:
    """Internal state for the currently-open candle bucket.

    Tracks running open/high/low/close/volume so that we only
    need to update fields incrementally as ticks arrive.
    """

    bucket_start: datetime
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    volume: int = 0
    tick_count: int = 0
    buy_volume: int = 0
    sell_volume: int = 0


class OHLCBuilder:
    """Build OHLCV candles from a stream of Tick objects.

    The builder maintains a *current bucket*. Each incoming tick is
    assigned to a bucket based on its timestamp. When a tick falls
    into a *new* bucket the previous bucket is closed and emitted as
    a completed candle.

    This class is NOT thread-safe; external synchronization is required
    if ticks are produced by multiple threads / async tasks.

    Attributes:
        timeframe_seconds: Width of each candle bucket in seconds.
            Common values: 60 (1m), 300 (5m), 900 (15m), 3600 (1h).

    Example:
        >>> builder = OHLCBuilder(timeframe_seconds=300)
        >>> tick1 = Tick(datetime(2024,1,1,9,15,0), 2450.0, 100, "buy")
        >>> tick2 = Tick(datetime(2024,1,1,9,15,30), 2452.0, 50, "buy")
        >>> print(builder.add_tick(tick1))  # None — bucket still open
        >>> print(builder.add_tick(tick2))  # None — bucket still open
    """

    def __init__(self, timeframe_seconds: int = 300) -> None:
        """Initialise the builder.

        Args:
            timeframe_seconds: Candle width in seconds. Default = 300 (5 min).
        """
        if timeframe_seconds <= 0:
            raise ValueError("timeframe_seconds must be positive")
        self.timeframe: int = timeframe_seconds
        self.current_bucket: Optional[datetime] = None
        self.state: Optional[CandleBuilderState] = None
        self.completed_candles: List[Dict] = []  # buffer for closed candles
        self.total_ticks_processed: int = 0
        self.total_candles_completed: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_tick(self, tick: Tick) -> Optional[Dict]:
        """Add a single tick to the builder.

        If the tick falls into a new time bucket the previous bucket is
        closed and the completed candle dict is returned. Otherwise the
        running candle is updated in-place and ``None`` is returned.

        Args:
            tick: A market tick with timestamp, price, quantity, side.

        Returns:
            A completed candle dict (with keys ``timestamp``, ``open``,
            ``high``, ``low``, ``close``, ``volume``, ``tick_count``,
            ``buy_volume``, ``sell_volume``) or ``None`` if the bucket
            is still open.

        Raises:
            ValueError: If tick price is <= 0 or quantity < 1.
        """
        # --- validation ---
        if tick.price <= 0:
            raise ValueError(f"Tick price must be > 0, got {tick.price}")
        if tick.quantity < 1:
            raise ValueError(f"Tick quantity must be >= 1, got {tick.quantity}")

        self.total_ticks_processed += 1
        tick_bucket = self._get_bucket(tick.timestamp)

        # --- first tick ever ---
        if self.current_bucket is None:
            self.current_bucket = tick_bucket
            self.state = CandleBuilderState(
                bucket_start=tick_bucket,
                open_price=tick.price,
                high_price=tick.price,
                low_price=tick.price,
                close_price=tick.price,
                volume=tick.quantity,
                tick_count=1,
                buy_volume=tick.quantity if tick.side == "buy" else 0,
                sell_volume=tick.quantity if tick.side == "sell" else 0,
            )
            return None

        # --- same bucket → update running candle ---
        if tick_bucket == self.current_bucket:
            self._update_state(tick)
            return None

        # --- new bucket → close previous, start new ---
        completed = self._close_current_candle()
        self.completed_candles.append(completed)
        self.total_candles_completed += 1

        # Start new bucket
        self.current_bucket = tick_bucket
        self.state = CandleBuilderState(
            bucket_start=tick_bucket,
            open_price=tick.price,
            high_price=tick.price,
            low_price=tick.price,
            close_price=tick.price,
            volume=tick.quantity,
            tick_count=1,
            buy_volume=tick.quantity if tick.side == "buy" else 0,
            sell_volume=tick.quantity if tick.side == "sell" else 0,
        )
        return completed

    def build_candles(self, ticks: List[Tick]) -> pd.DataFrame:
        """Build a complete DataFrame of candles from a list of ticks.

        All ticks are processed in order; any buffered running candle is
        **not** included (only closed buckets are emitted). If you need
        the in-progress candle call :meth:`flush` afterwards.

        Args:
            ticks: List of Tick objects (must be sorted by timestamp).

        Returns:
            DataFrame with columns: timestamp, open, high, low, close,
            volume, tick_count, buy_volume, sell_volume.
        """
        if not ticks:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "tick_count",
                    "buy_volume",
                    "sell_volume",
                ]
            )

        # Ensure sorted — defensive, O(n log n)
        sorted_ticks = sorted(ticks, key=lambda t: t.timestamp)

        for tick in sorted_ticks:
            self.add_tick(tick)

        return self.get_candle_df()

    def flush(self) -> Optional[Dict]:
        """Force-close the current open bucket and return it as a candle.

        This is useful at the end of a trading session or when you want
        to capture the partially-built candle (e.g., for real-time
        display of the *current* candle).

        Returns:
            The current in-progress candle dict, or ``None`` if no
            ticks have been processed yet.
        """
        if self.current_bucket is None or self.state is None:
            return None
        completed = self._close_current_candle()
        self.completed_candles.append(completed)
        self.total_candles_completed += 1
        # Reset state so builder can be reused
        self.current_bucket = None
        self.state = None
        return completed

    def get_candle_df(self) -> pd.DataFrame:
        """Return all completed candles as a DataFrame.

        The in-progress candle (if any) is **not** included.
        """
        if not self.completed_candles:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "tick_count",
                    "buy_volume",
                    "sell_volume",
                ]
            )
        return pd.DataFrame(self.completed_candles)

    def reset(self) -> None:
        """Clear all state — completed candles, current bucket, counters."""
        self.current_bucket = None
        self.state = None
        self.completed_candles.clear()
        self.total_ticks_processed = 0
        self.total_candles_completed = 0
        logger.debug("OHLCBuilder state reset")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_bucket(self, timestamp: datetime) -> datetime:
        """Calculate the bucket start time for a given timestamp.

        Buckets are aligned to Unix epoch. For 5-min (300s) candles:
        09:15:00 → bucket 09:15:00, 09:17:23 → bucket 09:15:00,
        09:20:00 → bucket 09:20:00.

        Args:
            timestamp: The tick timestamp.

        Returns:
            A timezone-naive datetime representing the bucket start.
        """
        # Work with UTC to avoid DST issues, then convert back
        ts = (
            timestamp.replace(tzinfo=timezone.utc)
            if timestamp.tzinfo is None
            else timestamp.astimezone(timezone.utc)
        )
        epoch_sec = int(ts.timestamp())
        bucket_start_sec = (epoch_sec // self.timeframe) * self.timeframe
        bucket_dt = datetime.utcfromtimestamp(bucket_start_sec)
        return bucket_dt.replace(tzinfo=None)

    def _update_state(self, tick: Tick) -> None:
        """Update the running candle state with a new tick."""
        assert self.state is not None
        s = self.state
        s.high_price = max(s.high_price, tick.price)
        s.low_price = min(s.low_price, tick.price)
        s.close_price = tick.price
        s.volume += tick.quantity
        s.tick_count += 1
        if tick.side == "buy":
            s.buy_volume += tick.quantity
        else:
            s.sell_volume += tick.quantity

    def _close_current_candle(self) -> Dict:
        """Close the current bucket and return a candle dict.

        Preconditions:
            - ``self.state`` is not ``None``
            - ``self.current_bucket`` is not ``None``
        """
        assert self.state is not None
        assert self.current_bucket is not None
        s = self.state
        return {
            "timestamp": self.current_bucket,
            "open": s.open_price,
            "high": s.high_price,
            "low": s.low_price,
            "close": s.close_price,
            "volume": s.volume,
            "tick_count": s.tick_count,
            "buy_volume": s.buy_volume,
            "sell_volume": s.sell_volume,
        }

    def __repr__(self) -> str:
        return (
            f"<OHLCBuilder tf={self.timeframe}s "
            f"ticks={self.total_ticks_processed} "
            f"candles={self.total_candles_completed}>"
        )
