"""
Market Data API Routes

- GET /historical/{symbol} -- Get historical OHLCV data
- GET /ltp/{symbol} -- Get last traded price
- GET /nifty50 -- Get Nifty 50 constituents with data
- GET /quote/{symbol} -- Full quote with indicators
- POST /indicators -- Calculate technical indicators
- GET /symbols -- List available symbols
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from core.indicators import (
    calculate_all_indicators,
)
from core.market_data.ingestor import MarketDataIngestor

router = APIRouter()

# Module-level singleton (injected from main.py)
_ingestor: Optional[MarketDataIngestor] = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class HistoricalDataResponse(BaseModel):
    """Response model for historical OHLCV data."""

    symbol: str
    timeframe: str
    from_date: str
    to_date: str
    records: int
    data: List[Dict[str, Any]]


class LTPResponse(BaseModel):
    """Last traded price response."""

    symbol: str
    price: float
    timestamp: str
    source: str


class Nifty50Response(BaseModel):
    """Nifty 50 constituents response."""

    constituents: List[str]
    count: int
    source: str


class QuoteResponse(BaseModel):
    """Full quote with indicators."""

    symbol: str
    timestamp: str
    price_data: Dict[str, Any]
    indicators: Dict[str, Any]


class IndicatorsRequest(BaseModel):
    """Request body for calculating technical indicators."""

    open_prices: List[float] = Field(..., description="List of open prices")
    high_prices: List[float] = Field(..., description="List of high prices")
    low_prices: List[float] = Field(..., description="List of low prices")
    close_prices: List[float] = Field(..., description="List of close prices")
    volumes: List[float] = Field(default_factory=list, description="List of volumes")


class IndicatorsResponse(BaseModel):
    """Technical indicators response."""

    indicators: Dict[str, Any]
    record_count: int
    calculated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_ingestor() -> MarketDataIngestor:
    """Get the global market data ingestor instance (injected from main.py)."""
    global _ingestor
    if _ingestor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data ingestor not initialized",
        )
    return _ingestor


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get(
    "/historical/{symbol}",
    response_model=HistoricalDataResponse,
    summary="Get historical OHLCV data",
    description="Fetch historical OHLCV data for a given symbol and date range.",
)
async def get_historical(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
    timeframe: str = "1d",
) -> HistoricalDataResponse:
    """Get historical OHLCV data for a symbol."""
    try:
        ingestor = _get_ingestor()

        df = await ingestor.fetch_historical(
            symbol=symbol.upper(),
            from_date=from_date,
            to_date=to_date,
            timeframe=timeframe,
        )

        if df.empty:
            return HistoricalDataResponse(
                symbol=symbol.upper(),
                timeframe=timeframe,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                records=0,
                data=[],
            )

        # Convert DataFrame to list of dicts
        records = df.to_dict(orient="records")

        # Convert timestamps to ISO strings
        for record in records:
            if "timestamp" in record and hasattr(record["timestamp"], "isoformat"):
                record["timestamp"] = record["timestamp"].isoformat()

        return HistoricalDataResponse(
            symbol=symbol.upper(),
            timeframe=timeframe,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            records=len(records),
            data=records,
        )

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Failed to fetch historical data: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch historical data: {exc}",
        )


@router.get(
    "/ltp/{symbol}",
    response_model=LTPResponse,
    summary="Get last traded price",
    description="Get the last traded price for a symbol.",
)
async def get_ltp(symbol: str) -> LTPResponse:
    """Get last traded price for a symbol."""
    try:
        ingestor = _get_ingestor()

        df = await ingestor.update_realtime(symbol=symbol.upper())

        if df is not None and not df.empty:
            latest = df.iloc[-1]
            return LTPResponse(
                symbol=symbol.upper(),
                price=float(latest["close"]),
                timestamp=(
                    latest["timestamp"].isoformat()
                    if hasattr(latest["timestamp"], "isoformat")
                    else str(latest["timestamp"])
                ),
                source="cache",
            )

        # Fallback: return 0 with a note
        return LTPResponse(
            symbol=symbol.upper(),
            price=0.0,
            timestamp=datetime.utcnow().isoformat(),
            source="unavailable",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get LTP for {}: {}", symbol, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get LTP: {exc}",
        )


@router.get(
    "/nifty50",
    response_model=Nifty50Response,
    summary="Get Nifty 50 constituents",
    description="Get the list of Nifty 50 index constituents.",
)
async def get_nifty50() -> Nifty50Response:
    """Get Nifty 50 constituent list."""
    try:
        ingestor = _get_ingestor()
        constituents = ingestor.get_nifty50_constituents()

        return Nifty50Response(
            constituents=constituents,
            count=len(constituents),
            source="NSE India",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get Nifty 50: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Nifty 50: {exc}",
        )


@router.get(
    "/quote/{symbol}",
    response_model=QuoteResponse,
    summary="Get full quote with indicators",
    description="Get a full quote including OHLCV data and technical indicators for a symbol.",
)
async def get_quote(
    symbol: str,
    period: str = "30d",
) -> QuoteResponse:
    """Get full quote with indicators."""
    try:
        ingestor = _get_ingestor()

        days_map = {
            "1d": 1,
            "5d": 5,
            "7d": 7,
            "15d": 15,
            "30d": 30,
            "90d": 90,
            "180d": 180,
            "365d": 365,
        }
        days = days_map.get(period, 30)

        to_date = datetime.now()
        from_date = to_date - __import__("datetime").timedelta(days=days)

        df = await ingestor.fetch_historical(
            symbol=symbol.upper(),
            from_date=from_date,
            to_date=to_date,
            timeframe="1d",
        )

        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data available for {symbol}",
            )

        latest = df.iloc[-1]

        # Calculate indicators on close prices
        close_prices = df["close"].tolist()
        high_prices = df["high"].tolist()
        low_prices = df["low"].tolist()
        open_prices = df["open"].tolist()
        volumes = df["volume"].tolist() if "volume" in df.columns else []

        try:
            import pandas as pd

            ind_df = pd.DataFrame(
                {
                    "open": open_prices,
                    "high": high_prices,
                    "low": low_prices,
                    "close": close_prices,
                    "volume": volumes if volumes else [0] * len(close_prices),
                }
            )
            ind_df = calculate_all_indicators(ind_df)

            # Get latest indicator values
            latest_indicators = {
                name: (
                    float(ind_df[name].iloc[-1])
                    if name in ind_df.columns and not ind_df[name].empty
                    else None
                )
                for name in ind_df.columns
                if name not in ("open", "high", "low", "close", "volume")
            }
        except Exception as ind_exc:
            logger.warning("Indicator calculation failed for {}: {}", symbol, ind_exc)
            latest_indicators = {}

        # Convert timestamps
        ts = latest["timestamp"]
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

        return QuoteResponse(
            symbol=symbol.upper(),
            timestamp=ts_str,
            price_data={
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "close": float(latest["close"]),
                "volume": int(latest.get("volume", 0)),
                "change": (
                    round(float(latest["close"]) - float(df.iloc[-2]["close"]), 2)
                    if len(df) > 1
                    else 0.0
                ),
                "change_pct": (
                    round(
                        (float(latest["close"]) - float(df.iloc[-2]["close"]))
                        / float(df.iloc[-2]["close"])
                        * 100,
                        2,
                    )
                    if len(df) > 1
                    else 0.0
                ),
            },
            indicators=latest_indicators,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get quote for {}: {}", symbol, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quote: {exc}",
        )


@router.get(
    "/indicators/{symbol}",
    response_model=QuoteResponse,
    summary="Get technical indicators for a symbol",
    description="Fetch historical data and calculate all technical indicators for a symbol.",
)
async def get_indicators_for_symbol(
    symbol: str,
    period: str = "30d",
) -> QuoteResponse:
    """Get OHLCV plus technical indicators for a symbol."""
    # Reuse the quote endpoint logic.
    return await get_quote(symbol=symbol, period=period)


@router.post(
    "/indicators",
    response_model=IndicatorsResponse,
    summary="Calculate technical indicators from raw prices",
    description="Calculate all technical indicators from raw OHLCV arrays.",
)
async def calculate_indicators(request: IndicatorsRequest) -> IndicatorsResponse:
    """Calculate technical indicators from price data."""
    try:
        if len(request.close_prices) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 close prices are required",
            )

        import pandas as pd

        df = pd.DataFrame(
            {
                "open": request.open_prices,
                "high": request.high_prices,
                "low": request.low_prices,
                "close": request.close_prices,
                "volume": (
                    request.volumes
                    if request.volumes
                    else [0.0] * len(request.close_prices)
                ),
            }
        )
        ind_df = calculate_all_indicators(df)

        # Convert indicator columns to serialisable lists
        indicator_cols = [
            c
            for c in ind_df.columns
            if c not in ("open", "high", "low", "close", "volume")
        ]
        serializable_indicators = {
            name: (
                [
                    None if pd.isna(v) else round(float(v), 4)
                    for v in ind_df[name].tolist()
                ]
                if name in ind_df.columns
                else []
            )
            for name in indicator_cols
        }

        return IndicatorsResponse(
            indicators=serializable_indicators,
            record_count=len(request.close_prices),
            calculated_at=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Indicator calculation failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indicator calculation failed: {exc}",
        )


@router.get(
    "/symbols",
    summary="List available symbols",
    description="Get a list of available trading symbols.",
)
async def list_symbols() -> Dict[str, Any]:
    """List available symbols."""
    try:
        ingestor = _get_ingestor()
        nifty50 = ingestor.get_nifty50_constituents()

        return {
            "nifty50": nifty50,
            "total_count": len(nifty50),
            "popular": [
                "RELIANCE",
                "TCS",
                "HDFCBANK",
                "INFY",
                "ICICIBANK",
                "SBIN",
                "ITC",
                "LT",
                "BHARTIARTL",
                "ADANIENT",
            ],
            "indices": ["NIFTY50", "BANKNIFTY", "FINNIFTY", "SENSEX"],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list symbols: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list symbols: {exc}",
        )


# ---------------------------------------------------------------------------
# Injection hook (called from main.py lifespan)
# ---------------------------------------------------------------------------


def set_ingestor_instance(ingestor: MarketDataIngestor) -> None:
    """Inject the global market data ingestor from main.py."""
    global _ingestor
    _ingestor = ingestor
    logger.debug("Market data ingestor injected into market router")
