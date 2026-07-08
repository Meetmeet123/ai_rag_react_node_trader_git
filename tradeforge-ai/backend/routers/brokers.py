"""
Broker configuration & connection management API.

All endpoints are scoped under ``/api/v1/brokers``.  Sensitive values are
encrypted at rest and masked in responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger

from config import settings
from core.broker.base import BaseBroker
from core.broker.factory import create_broker_from_config
from core.broker.paper_broker import PaperBroker
from core.broker.upstox import UpstoxBroker
from core.execution_engine import ExecutionEngine
from core.sanitization import sanitize_string
from core.security import decrypt_value, encrypt_value, mask_value
from database.models import BrokerConfig, BrokerName
from routers.auth import UserDocument, get_current_user_optional

router = APIRouter()

# Module-level singletons injected from main.py
_broker_instance: Optional[BaseBroker] = None
_execution_engine: Optional[ExecutionEngine] = None
_default_redirect_uri: str = "http://localhost:8000/api/v1/brokers/upstox/callback"


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class BrokerConfigPayload(BaseModel):
    """Request body for saving broker configuration."""

    broker: BrokerName
    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    access_token: Optional[str] = Field(default=None)
    redirect_uri: Optional[str] = Field(default=None)
    is_active: bool = Field(default=False)
    is_paper: bool = Field(default=False)


class BrokerConfigResponse(BaseModel):
    """Masked broker configuration response."""

    id: str
    broker: str
    api_key: str
    api_secret: str
    client_id: str
    access_token: str
    redirect_uri: Optional[str]
    is_active: bool
    is_paper: bool
    is_connected: bool
    last_connected_at: Optional[str]


class BrokerStatusResponse(BaseModel):
    """Broker connection status response."""

    broker: str
    is_connected: bool
    is_paper: bool
    is_active: bool
    last_connected_at: Optional[str]


class BrokerListResponse(BaseModel):
    """List supported brokers and active config."""

    brokers: List[str]
    active: Optional[BrokerConfigResponse]


class LoginUrlResponse(BaseModel):
    """Upstox OAuth login URL response."""

    login_url: str


class ExchangeTokenRequest(BaseModel):
    """Request body to exchange an Upstox OAuth code."""

    code: str = Field(..., min_length=1)


class ExchangeTokenResponse(BaseModel):
    """Response after exchanging an Upstox OAuth code."""

    success: bool
    message: str
    access_token: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_to_response(config: BrokerConfig) -> BrokerConfigResponse:
    """Convert a BrokerConfig document to a masked response."""
    return BrokerConfigResponse(
        id=str(config.id),
        broker=config.broker.value,
        api_key=mask_value(config.api_key),
        api_secret=mask_value(config.api_secret),
        client_id=mask_value(config.client_id),
        access_token=mask_value(config.access_token),
        redirect_uri=getattr(config, "redirect_uri", None),
        is_active=config.is_active,
        is_paper=config.is_paper,
        is_connected=config.is_connected,
        last_connected_at=(
            config.last_connected_at.isoformat() if config.last_connected_at else None
        ),
    )


async def _get_active_config(user: Optional[UserDocument]) -> Optional[BrokerConfig]:
    """Return the active broker config for the user, if any."""
    query = BrokerConfig.find({"is_active": True})
    if user is not None:
        query = query.find(BrokerConfig.user_id == user.id)
    else:
        query = query.find({"user_id": None})
    return await query.first_or_none()


def _set_broker_instance(broker: BaseBroker) -> None:
    """Update the module-level broker singleton (used by main.py)."""
    global _broker_instance
    _broker_instance = broker


def _set_execution_engine(engine: ExecutionEngine) -> None:
    """Update the module-level execution engine singleton (used by main.py)."""
    global _execution_engine
    _execution_engine = engine


def _default_upstox_redirect_uri(config: Optional[BrokerConfig]) -> str:
    """Return the redirect URI to use for Upstox OAuth."""
    if config is not None:
        redirect = getattr(config, "redirect_uri", None)
        if redirect:
            return redirect
    return _default_redirect_uri


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/", response_model=BrokerListResponse, summary="List supported brokers")
async def list_brokers(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BrokerListResponse:
    """Return all supported broker names and the active masked config."""
    active = await _get_active_config(current_user)
    return BrokerListResponse(
        brokers=[b.value for b in BrokerName],
        active=_config_to_response(active) if active else None,
    )


@router.get(
    "/config", response_model=BrokerConfigResponse, summary="Get active broker config"
)
async def get_broker_config(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BrokerConfigResponse:
    """Return the current active broker config with credentials masked."""
    config = await _get_active_config(current_user)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active broker configuration found",
        )
    return _config_to_response(config)


@router.post(
    "/config",
    response_model=BrokerConfigResponse,
    summary="Save or update broker config",
)
async def save_broker_config(
    payload: BrokerConfigPayload,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BrokerConfigResponse:
    """Save or update broker configuration.  Secrets are encrypted at rest."""
    # Build the config document
    config_data: Dict[str, Any] = {
        "broker": payload.broker,
        "api_key": payload.api_key,
        "api_secret": encrypt_value(payload.api_secret),
        "client_id": sanitize_string(payload.client_id),
        "access_token": encrypt_value(payload.access_token),
        "is_active": payload.is_active,
        "is_paper": payload.is_paper,
    }
    if payload.redirect_uri is not None:
        config_data["redirect_uri"] = sanitize_string(payload.redirect_uri)

    if current_user is not None:
        config_data["user_id"] = current_user.id

    if payload.is_active:
        # Deactivate any existing active config for this user
        existing_query = BrokerConfig.find(
            {"is_active": True},
            BrokerConfig.broker != payload.broker,
        )
        if current_user is not None:
            existing_query = existing_query.find(
                BrokerConfig.user_id == current_user.id
            )
        else:
            existing_query = existing_query.find({"user_id": None})
        existing = await existing_query.to_list()
        for cfg in existing:
            cfg.is_active = False
            cfg.is_connected = False
            await cfg.save()

    # Look for an existing config for the same broker + user to update
    existing_query = BrokerConfig.find(BrokerConfig.broker == payload.broker)
    if current_user is not None:
        existing_query = existing_query.find(BrokerConfig.user_id == current_user.id)
    else:
        existing_query = existing_query.find({"user_id": None})
    existing_config = await existing_query.first_or_none()

    if existing_config is not None:
        for key, value in config_data.items():
            setattr(existing_config, key, value)
        existing_config.touch()
        await existing_config.save()
        config = existing_config
    else:
        config = BrokerConfig(**config_data)
        await config.insert()

    logger.info(
        "Broker config saved | broker={} user={} active={}",
        payload.broker.value,
        current_user.id if current_user else None,
        payload.is_active,
    )
    return _config_to_response(config)


@router.delete(
    "/config/{config_id}",
    summary="Delete a broker config",
)
async def delete_broker_config(
    config_id: str,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Delete a broker configuration by ID."""
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid config id",
        )

    config = await BrokerConfig.get(obj_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker config not found",
        )

    if current_user is not None and config.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to delete this config",
        )

    await config.delete()
    logger.info(
        "Broker config deleted | id={} broker={}", config_id, config.broker.value
    )
    return {"success": True, "message": "Broker config deleted"}


@router.post(
    "/{broker}/connect",
    response_model=BrokerStatusResponse,
    summary="Connect a configured broker",
)
async def connect_broker(
    broker: BrokerName,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BrokerStatusResponse:
    """Load the active config for the broker and connect."""
    query = BrokerConfig.find(BrokerConfig.broker == broker, {"is_active": True})
    if current_user is not None:
        query = query.find(BrokerConfig.user_id == current_user.id)
    else:
        query = query.find({"user_id": None})
    config = await query.first_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active configuration found for broker '{broker.value}'",
        )

    try:
        live_broker = create_broker_from_config(config)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        )

    connected = await live_broker.connect()
    config.is_connected = connected
    if connected:
        config.last_connected_at = datetime.utcnow()
    await config.save()

    if connected:
        _set_broker_instance(live_broker)
        logger.info("Broker connected | broker={}", broker.value)
    else:
        logger.warning("Broker connect failed | broker={}", broker.value)

    return BrokerStatusResponse(
        broker=broker.value,
        is_connected=connected,
        is_paper=config.is_paper,
        is_active=config.is_active,
        last_connected_at=(
            config.last_connected_at.isoformat() if config.last_connected_at else None
        ),
    )


@router.post(
    "/disconnect",
    response_model=BrokerStatusResponse,
    summary="Disconnect the active broker",
)
async def disconnect_broker(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BrokerStatusResponse:
    """Disconnect the currently active broker."""
    config = await _get_active_config(current_user)
    broker_name = config.broker.value if config else "unknown"

    try:
        if _broker_instance is not None:
            await _broker_instance.disconnect()
    except Exception as exc:
        logger.warning("Error disconnecting broker: {}", exc)

    if config is not None:
        config.is_connected = False
        await config.save()

    # Revert to paper broker for safety
    paper = PaperBroker()
    await paper.connect()
    _set_broker_instance(paper)

    return BrokerStatusResponse(
        broker=broker_name,
        is_connected=False,
        is_paper=True,
        is_active=config.is_active if config else False,
        last_connected_at=(
            config.last_connected_at.isoformat()
            if config and config.last_connected_at
            else None
        ),
    )


@router.get(
    "/status",
    response_model=BrokerStatusResponse,
    summary="Broker connection status",
)
async def broker_status(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> BrokerStatusResponse:
    """Return the active broker connection status."""
    config = await _get_active_config(current_user)
    if config is None:
        return BrokerStatusResponse(
            broker="paper",
            is_connected=_broker_instance.is_connected if _broker_instance else False,
            is_paper=True,
            is_active=False,
            last_connected_at=None,
        )

    is_connected = (
        _broker_instance.is_connected if _broker_instance else config.is_connected
    )
    return BrokerStatusResponse(
        broker=config.broker.value,
        is_connected=is_connected,
        is_paper=config.is_paper,
        is_active=config.is_active,
        last_connected_at=(
            config.last_connected_at.isoformat() if config.last_connected_at else None
        ),
    )


@router.get(
    "/upstox/login-url",
    response_model=LoginUrlResponse,
    summary="Get Upstox OAuth login URL",
)
async def upstox_login_url(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> LoginUrlResponse:
    """Return the Upstox OAuth login URL for the configured app."""
    query = BrokerConfig.find(BrokerConfig.broker == BrokerName.UPSTOX)
    if current_user is not None:
        query = query.find(BrokerConfig.user_id == current_user.id)
    else:
        query = query.find({"user_id": None})
    config = await query.first_or_none()

    api_key = config.api_key if config and config.api_key else settings.UPSTOX_API_KEY
    redirect_uri = _default_upstox_redirect_uri(config)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upstox API key not configured",
        )

    return LoginUrlResponse(login_url=UpstoxBroker.get_login_url(api_key, redirect_uri))


@router.post(
    "/upstox/exchange-token",
    response_model=ExchangeTokenResponse,
    summary="Exchange Upstox OAuth code for access token",
)
async def upstox_exchange_token(
    body: ExchangeTokenRequest,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> ExchangeTokenResponse:
    """Exchange an Upstox authorisation code and save the access token."""
    query = BrokerConfig.find(BrokerConfig.broker == BrokerName.UPSTOX)
    if current_user is not None:
        query = query.find(BrokerConfig.user_id == current_user.id)
    else:
        query = query.find({"user_id": None})
    config = await query.first_or_none()

    api_key = config.api_key if config and config.api_key else settings.UPSTOX_API_KEY
    api_secret = (
        decrypt_value(config.api_secret) if config and config.api_secret else None
    )
    redirect_uri = _default_upstox_redirect_uri(config)

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upstox API key and secret must be configured first",
        )

    try:
        token_response = UpstoxBroker.exchange_code_for_token(
            code=body.code,
            api_key=api_key,
            api_secret=api_secret,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        logger.exception("Upstox token exchange failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {exc}",
        )

    access_token = (
        token_response.get("access_token") if isinstance(token_response, dict) else None
    )
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access_token returned by Upstox",
        )

    if config is None:
        config = BrokerConfig(
            user_id=current_user.id if current_user else None,
            broker=BrokerName.UPSTOX,
            api_key=api_key,
            api_secret=encrypt_value(api_secret),
            redirect_uri=redirect_uri,
            access_token=encrypt_value(access_token),
            is_active=True,
            is_paper=False,
        )
        await config.insert()
    else:
        config.access_token = encrypt_value(access_token)
        config.is_active = True
        config.touch()
        await config.save()

    # Try to connect immediately
    broker = create_broker_from_config(config)
    connected = await broker.connect()
    config.is_connected = connected
    if connected:
        config.last_connected_at = datetime.utcnow()
        _set_broker_instance(broker)
    await config.save()

    return ExchangeTokenResponse(
        success=connected,
        message="Connected" if connected else "Token saved but connect failed",
        access_token=mask_value(access_token),
    )


# ---------------------------------------------------------------------------
# Injection hooks (called from main.py lifespan)
# ---------------------------------------------------------------------------


def set_broker_instance(broker: BaseBroker) -> None:
    """Inject the global broker instance from main.py."""
    _set_broker_instance(broker)
    logger.debug("Broker instance injected into brokers router")


def set_execution_engine(engine: ExecutionEngine) -> None:
    """Inject the global execution engine instance from main.py."""
    _set_execution_engine(engine)
    logger.debug("Execution engine injected into brokers router")
