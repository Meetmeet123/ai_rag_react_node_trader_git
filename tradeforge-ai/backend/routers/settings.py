"""
User Settings API Routes

- GET /  -- Retrieve the current user's risk configuration
- PUT /  -- Update the current user's risk configuration
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from core.sanitization import sanitize_string
from database.models import RiskConfig
from routers.auth import get_current_user_optional, UserDocument

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RiskSettingsUpdate(BaseModel):
    """Subset of RiskConfig fields that may be updated by the user."""

    daily_loss_limit: Optional[float] = Field(
        default=None, ge=0, description="Maximum daily loss in absolute terms"
    )
    daily_loss_limit_enabled: Optional[bool] = Field(
        default=None, description="Whether the daily loss guard is active"
    )
    max_positions: Optional[int] = Field(
        default=None, ge=1, description="Maximum number of concurrent open positions"
    )
    max_exposure_per_trade_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum percentage of capital allocated to a single trade",
    )
    max_exposure_overall_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum percentage of capital allocated across all positions",
    )
    kill_switch_enabled: Optional[bool] = Field(
        default=None, description="Whether the kill switch is active"
    )
    auto_square_off_time: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=5,
        description="Auto square-off time in HH:MM format",
    )

    @field_validator("auto_square_off_time")
    @classmethod
    def _validate_time_format(cls, value: Optional[str]) -> Optional[str]:
        """Validate that the square-off time is HH:MM when provided."""
        if value is None:
            return value
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("auto_square_off_time must be in HH:MM format")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise ValueError("auto_square_off_time must be in HH:MM format") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("auto_square_off_time contains invalid hour/minute")
        return value


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def _default_risk_settings() -> Dict[str, Any]:
    """Return the default/global risk configuration as a plain dict."""
    return {
        "daily_loss_limit": RiskConfig.model_fields["daily_loss_limit"].default,
        "daily_loss_limit_enabled": RiskConfig.model_fields[
            "daily_loss_limit_enabled"
        ].default,
        "max_positions": RiskConfig.model_fields["max_positions"].default,
        "max_exposure_per_trade_pct": RiskConfig.model_fields[
            "max_exposure_per_trade_pct"
        ].default,
        "max_exposure_overall_pct": RiskConfig.model_fields[
            "max_exposure_overall_pct"
        ].default,
        "kill_switch_enabled": RiskConfig.model_fields["kill_switch_enabled"].default,
        "auto_square_off_time": RiskConfig.model_fields["auto_square_off_time"].default,
    }


async def _get_or_create_risk_config(
    current_user: Optional[UserDocument],
) -> RiskConfig:
    """Fetch the user's RiskConfig document, creating it with defaults if missing."""
    user_id = current_user.id if current_user else None

    if user_id is not None:
        config = await RiskConfig.find_one(RiskConfig.user_id == user_id)
    else:
        config = await RiskConfig.find_one({"user_id": None})

    if config is None:
        config = RiskConfig(user_id=user_id)
        await config.insert()

    return config


def _risk_config_to_dict(config: RiskConfig) -> Dict[str, Any]:
    """Return only the user-editable risk settings as a dict."""
    return {
        "daily_loss_limit": config.daily_loss_limit,
        "daily_loss_limit_enabled": config.daily_loss_limit_enabled,
        "max_positions": config.max_positions,
        "max_exposure_per_trade_pct": config.max_exposure_per_trade_pct,
        "max_exposure_overall_pct": config.max_exposure_overall_pct,
        "kill_switch_enabled": config.kill_switch_enabled,
        "auto_square_off_time": config.auto_square_off_time,
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get(
    "/",
    summary="Get risk settings",
    description="Return the current user's risk configuration, or the default configuration.",
)
async def get_settings(
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Get the current user's risk settings."""
    user_id = current_user.id if current_user else None

    if user_id is not None:
        config = await RiskConfig.find_one(RiskConfig.user_id == user_id)
    else:
        config = await RiskConfig.find_one({"user_id": None})

    if config is None:
        return _default_risk_settings()

    return _risk_config_to_dict(config)


@router.put(
    "/",
    summary="Update risk settings",
    description="Update the current user's risk configuration (created if missing).",
)
async def update_settings(
    update: RiskSettingsUpdate,
    current_user: Optional[UserDocument] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Update the current user's risk settings."""
    try:
        config = await _get_or_create_risk_config(current_user)

        data = update.model_dump(exclude_unset=True)
        for field, value in data.items():
            if isinstance(value, str):
                value = sanitize_string(value)
            setattr(config, field, value)

        config.touch()
        await config.save()

        logger.info(
            "Risk settings updated user={}",
            current_user.id if current_user else "anonymous",
        )

        return _risk_config_to_dict(config)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to update risk settings: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update risk settings: {exc}",
        )
