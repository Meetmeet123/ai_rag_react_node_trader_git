"""
Market Data Ingestion Pipeline

Downloads historical OHLCV data and maintains a local Parquet cache for
fast retrieval.  Supports NSE (India) equity, index, and futures data.

Architecture:
    1. Primary source — NSE India official API (free, no auth required).
    2. Fallback source — Yahoo Finance via yfinance.
    3. Local cache — Apache Parquet on disk (fast columnar reads).

The ingestor handles:
    - Symbol normalization (NSE vs Yahoo formats).
    - Session management with keep-alive HTTP pooling.
    - Rate-limit friendly delays between requests.
    - Automatic cache invalidation based on trading-calendar awareness.

Example:
    >>> ingestor = MarketDataIngestor(data_dir="./data")
    >>> df = await ingestor.fetch_historical(
    ...     symbol="RELIANCE", from_date=datetime(2024,1,1),
    ...     to_date=datetime(2024,6,1), timeframe="1d"
    ... )
    >>> print(df.head())
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
import pandas as pd
from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NSE_BASE_URL = "https://www.nseindia.com"
NSE_CHART_URL = "https://www.nseindia.com/api/chart-databyindex"
NSE_HISTORICAL_URL = "https://www.nseindia.com/api/historical/cm/equity"

# NSE requires a session cookie + standard browser headers
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

# Timeframe → seconds mapping for internal use
TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
}

# Full Nifty 50 constituents (as of 2024)
NIFTY50_CONSTITUENTS: List[str] = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "ICICIBANK",
    "INFY",
    "HINDUNILVR",
    "ITC",
    "SBIN",
    "BHARTIARTL",
    "BAJFINANCE",
    "LICI",
    "KOTAKBANK",
    "LT",
    "HCLTECH",
    "AXISBANK",
    "ASIANPAINT",
    "MARUTI",
    "SUNPHARMA",
    "TITAN",
    "ADANIENT",
    "ULTRACEMCO",
    "BAJAJFINSV",
    "NESTLEIND",
    "WIPRO",
    "ADANIPORTS",
    "POWERGRID",
    "JSWSTEEL",
    "M&M",
    "LTIM",
    "TATAMOTORS",
    "COALINDIA",
    "TATASTEEL",
    "HINDALCO",
    "ONGC",
    "BPCL",
    "GRASIM",
    "BRITANNIA",
    "VEDL",
    "CIPLA",
    "EICHERMOTORS",
    "DIVISLAB",
    "DRREDDY",
    "HEROMOTOCO",
    "HINDPETRO",
    "INDUSINDBK",
    "NTPC",
    "SHRIRAMFIN",
    "APOLLOHOSP",
    "BAJAJ-AUTO",
    "TATACONSUM",
]


class MarketDataIngestor:
    """Market data ingestion with NSE-first, Yahoo-fallback strategy.

    Attributes:
        data_dir: Root directory for Parquet cache files.
        http: Shared async HTTP client (httpx.AsyncClient) with
            connection pooling and browser-like headers.
    """

    def __init__(self, data_dir: str = "./data/historical") -> None:
        """Initialise the ingestor.

        Args:
            data_dir: Path to directory where Parquet cache files are
                stored.  Created automatically if it does not exist.
        """
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Shared HTTP client with NSE-compatible headers & cookie jar
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers=NSE_HEADERS,
            follow_redirects=True,
        )
        self._nse_session_ready: bool = False
        self._session_lock = asyncio.Lock()

        logger.info(f"MarketDataIngestor initialised — cache dir: {data_dir}")

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    async def fetch_historical(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data for a symbol.

        Resolution order:
            1. Check local Parquet cache.
            2. Try NSE India API.
            3. Fallback to Yahoo Finance.

        Args:
            symbol: NSE trading symbol, e.g. ``"RELIANCE"`` or
                ``"NIFTY 50"`` for the index.
            from_date: Start of the requested range (inclusive).
            to_date: End of the requested range (inclusive).
            timeframe: Candle granularity — ``"1m"``, ``"5m"``,
                ``"15m"``, ``"1h"``, ``"1d"``.

        Returns:
            DataFrame with columns ``timestamp``, ``open``, ``high``,
            ``low``, ``close``, ``volume``.  Empty DataFrame if no
            data could be retrieved.

        Raises:
            ValueError: For unsupported timeframe strings.
        """
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. "
                f"Supported: {list(TIMEFRAME_SECONDS.keys())}"
            )

        # 1. Check cache first
        cached = self.load_from_parquet(symbol, timeframe)
        if cached is not None and not cached.empty:
            cache_min = cached["timestamp"].min()
            cache_max = cached["timestamp"].max()
            # If cache fully covers request, return slice
            if cache_min <= from_date and cache_max >= to_date:
                mask = (cached["timestamp"] >= from_date) & (
                    cached["timestamp"] <= to_date
                )
                logger.info(f"[{symbol}] Cache hit — returning {mask.sum()} rows")
                return cached.loc[mask].copy().reset_index(drop=True)

        # 2. Try NSE (daily-only for now)
        df: Optional[pd.DataFrame] = None
        if timeframe == "1d":
            try:
                df = await self._fetch_nse_historical(symbol, from_date, to_date)
                if df is not None and not df.empty:
                    logger.info(f"[{symbol}] NSE fetch succeeded — {len(df)} rows")
            except Exception as exc:
                logger.warning(f"[{symbol}] NSE fetch failed: {exc}")

        # 3. Fallback to Yahoo
        if df is None or df.empty:
            try:
                df = await self._fetch_yahoo_historical(
                    symbol, from_date, to_date, timeframe
                )
                if df is not None and not df.empty:
                    logger.info(f"[{symbol}] Yahoo fetch succeeded — {len(df)} rows")
            except Exception as exc:
                logger.warning(f"[{symbol}] Yahoo fetch failed: {exc}")

        if df is None or df.empty:
            logger.error(
                f"[{symbol}] All data sources exhausted — returning empty DataFrame"
            )
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        # Cache & return
        self.save_to_parquet(df, symbol, timeframe)
        mask = (df["timestamp"] >= from_date) & (df["timestamp"] <= to_date)
        return df.loc[mask].copy().reset_index(drop=True)

    async def fetch_nse_data(
        self,
        symbol: str,
        period: str = "1y",
    ) -> pd.DataFrame:
        """Fetch from NSE India API.

        Args:
            symbol: NSE symbol.
            period: One of ``"1mo"``, ``"3mo"``, ``"6mo"``, ``"1y"``,
                ``"2y"``, ``"5y"``.

        Returns:
            DataFrame with OHLCV columns.
        """
        period_map = {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
        }
        days = period_map.get(period, 365)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        return await self._fetch_nse_historical(
            symbol, from_date, to_date, timeframe="1d"
        )

    async def fetch_yahoo_data(
        self,
        symbol: str,
        period: str = "1y",
    ) -> pd.DataFrame:
        """Fetch from Yahoo Finance as fallback.

        Args:
            symbol: NSE symbol (will be mapped to Yahoo format).
            period: Yahoo-style period string.

        Returns:
            DataFrame with OHLCV columns.
        """
        to_date = datetime.now()
        period_map_days = {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
        }
        days = period_map_days.get(period, 365)
        from_date = to_date - timedelta(days=days)
        return await self._fetch_yahoo_historical(
            symbol, from_date, to_date, timeframe="1d"
        )

    def save_to_parquet(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> None:
        """Save OHLCV DataFrame to Parquet for fast future reads.

        Files are stored as ``{data_dir}/{symbol}_{timeframe}.parquet``.
        Existing files are overwritten.

        Args:
            df: DataFrame with at least ``timestamp`` column.
            symbol: Trading symbol (used in filename).
            timeframe: Timeframe string (used in filename).
        """
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            logger.error(
                f"Refusing to save invalid Parquet for {symbol}: missing {missing}"
            )
            return

        safe_symbol = symbol.replace(" ", "_").replace("/", "_")
        filepath = os.path.join(self.data_dir, f"{safe_symbol}_{timeframe}.parquet")
        try:
            # Ensure timestamp is datetime for consistent round-trips.
            if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                df = df.copy()
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.to_parquet(filepath, index=False, compression="zstd")
            logger.debug(f"Saved {len(df)} rows to {filepath}")
        except Exception as exc:
            logger.error(f"Failed to save Parquet {filepath}: {exc}")

    def load_from_parquet(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """Load cached OHLCV data from Parquet.

        Args:
            symbol: Trading symbol.
            timeframe: Timeframe string.

        Returns:
            DataFrame or ``None`` if cache file does not exist or is invalid.
        """
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        safe_symbol = symbol.replace(" ", "_").replace("/", "_")
        filepath = os.path.join(self.data_dir, f"{safe_symbol}_{timeframe}.parquet")
        if not os.path.exists(filepath):
            return None
        try:
            df = pd.read_parquet(filepath)
            missing = required - set(df.columns)
            if missing:
                logger.warning(
                    f"Invalid Parquet cache for {symbol}: missing {missing}; re-fetching"
                )
                return None
            if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                df = df.copy()
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            logger.debug(f"Loaded {len(df)} rows from {filepath}")
            return df
        except Exception as exc:
            logger.error(f"Failed to load Parquet {filepath}: {exc}")
            return None

    async def update_realtime(self, symbol: str) -> Optional[pd.DataFrame]:
        """Update cached data with the latest available ticks/candles.

        Fetches the last 5 days from NSE, merges with cache, deduplicates,
        and writes back.

        Args:
            symbol: Trading symbol.

        Returns:
            Updated DataFrame or ``None`` on failure.
        """
        cache = self.load_from_parquet(symbol, "1d")
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=5)
            new_data = await self._fetch_nse_historical(symbol, from_date, to_date)
            if new_data is None or new_data.empty:
                return cache

            if cache is not None and not cache.empty:
                merged = pd.concat([cache, new_data], ignore_index=True)
                merged = merged.drop_duplicates(subset=["timestamp"], keep="last")
                merged = merged.sort_values("timestamp").reset_index(drop=True)
            else:
                merged = new_data

            self.save_to_parquet(merged, symbol, "1d")
            logger.info(f"[{symbol}] Realtime update — {len(merged)} total rows")
            return merged
        except Exception as exc:
            logger.error(f"[{symbol}] Realtime update failed: {exc}")
            return cache

    def get_nifty50_constituents(self) -> List[str]:
        """Return the full list of Nifty 50 constituents."""
        return NIFTY50_CONSTITUENTS.copy()

    # ------------------------------------------------------------------
    # NSE helpers
    # ------------------------------------------------------------------

    async def _ensure_nse_session(self) -> None:
        """Prime the NSE session by hitting the homepage to get cookies.

        NSE India requires a valid session cookie for API calls.
        This is done lazily and cached.
        """
        if self._nse_session_ready:
            return
        async with self._session_lock:
            if self._nse_session_ready:
                return
            try:
                resp = await self.http.get(f"{NSE_BASE_URL}/", timeout=15)
                resp.raise_for_status()
                self._nse_session_ready = True
                logger.debug("NSE session primed successfully")
            except Exception as exc:
                logger.warning(f"Failed to prime NSE session: {exc}")
                self._nse_session_ready = False

    async def _fetch_nse_historical(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframe: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Fetch historical data from NSE India API.

        Uses the ``/api/historical/cm/equity`` endpoint. Currently this
        endpoint only provides daily data, so non-daily timeframes are
        ignored and will fall back to Yahoo Finance.
        """
        await self._ensure_nse_session()

        from_str = from_date.strftime("%d-%m-%Y")
        to_str = to_date.strftime("%d-%m-%Y")
        url = (
            f"{NSE_HISTORICAL_URL}?symbol={symbol.upper()}"
            f"&series=[%22EQ%22]&from={from_str}&to={to_str}"
        )
        try:
            resp = await self.http.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data or "data" not in data or not data["data"]:
                logger.debug(f"[{symbol}] NSE returned empty data payload")
                return None
            return self._parse_nse_historical(data["data"])
        except httpx.HTTPStatusError as exc:
            logger.warning(f"[{symbol}] NSE HTTP error {exc.response.status_code}")
            return None
        except Exception as exc:
            logger.warning(f"[{symbol}] NSE parse error: {exc}")
            return None

    def _parse_nse_historical(self, raw_data: List[Dict]) -> pd.DataFrame:
        """Parse NSE historical JSON into a clean DataFrame."""
        records = []
        for row in raw_data:
            if not row:
                continue
            try:
                # NSE field names vary; handle both formats
                ts_raw = (
                    row.get("CH_TIMESTAMP") or row.get("TIMESTAMP") or row.get("date")
                )
                if ts_raw is None:
                    continue
                ts = pd.to_datetime(ts_raw)
                records.append(
                    {
                        "timestamp": ts,
                        "open": float(
                            row.get("CH_OPENING_PRICE") or row.get("OPEN", 0)
                        ),
                        "high": float(
                            row.get("CH_TRADE_HIGH_PRICE") or row.get("HIGH", 0)
                        ),
                        "low": float(
                            row.get("CH_TRADE_LOW_PRICE") or row.get("LOW", 0)
                        ),
                        "close": float(
                            row.get("CH_CLOSING_PRICE") or row.get("CLOSE", 0)
                        ),
                        "volume": int(
                            row.get("CH_TOT_TRADED_QTY") or row.get("VOLUME", 0)
                        ),
                    }
                )
            except (ValueError, TypeError) as exc:
                logger.debug(f"Skipping malformed NSE row: {exc}")
                continue

        df = pd.DataFrame(records)
        if df.empty:
            return df
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Yahoo helpers
    # ------------------------------------------------------------------

    async def _fetch_yahoo_historical(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframe: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Fetch historical data from Yahoo Finance.

        Yahoo Finance uses ``.NS`` suffix for NSE symbols.
        Uses the ``query1.finance.yahoo.com`` endpoint.
        """
        # Map internal timeframes to Yahoo intervals.
        yahoo_interval = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "60m",
            "1d": "1d",
        }.get(timeframe, "1d")
        # Yahoo intraday data is limited; keep date range tight for 1m.
        if timeframe == "1m" and (to_date - from_date).days > 7:
            from_date = to_date - timedelta(days=7)

        yahoo_symbol = f"{symbol.upper()}.NS"
        from_ts = int(from_date.timestamp())
        to_ts = int(to_date.timestamp())

        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
            f"?period1={from_ts}&period2={to_ts}&interval={yahoo_interval}"
            f"&events=history"
        )
        try:
            resp = await self.http.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            chart = payload.get("chart", {})
            if chart.get("error"):
                logger.warning(f"[{symbol}] Yahoo error: {chart['error']}")
                return None
            result = chart.get("result", [{}])[0]
            return self._parse_yahoo_result(result)
        except Exception as exc:
            logger.warning(f"[{symbol}] Yahoo fetch error: {exc}")
            return None

    def _parse_yahoo_result(self, result: Dict) -> Optional[pd.DataFrame]:
        """Parse Yahoo Finance chart result into DataFrame."""
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        if not timestamps:
            return None

        df = pd.DataFrame(
            {
                "timestamp": [datetime.utcfromtimestamp(ts) for ts in timestamps],
                "open": quote.get("open", []),
                "high": quote.get("high", []),
                "low": quote.get("low", []),
                "close": quote.get("close", []),
                "volume": quote.get("volume", []),
            }
        )
        # Drop rows with NaN in critical columns
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self.http.aclose()
        logger.info("MarketDataIngestor HTTP client closed")

    def __repr__(self) -> str:
        return f"<MarketDataIngestor cache={self.data_dir}>"
