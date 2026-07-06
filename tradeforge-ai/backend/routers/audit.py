"""
Audit log administration API.

Provides read-only access to the audit log collection. All endpoints require
an authenticated user with the ``admin`` role.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from beanie.operators import Eq
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from database.models import AuditLog, User
from routers.auth import get_current_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    """Single audit log entry response."""

    id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status_code: int
    timestamp: str
    details: Optional[Dict[str, Any]] = None


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""

    logs: List[AuditLogResponse]
    total: int = Field(..., description="Total number of matching audit log entries")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit_to_response(log: AuditLog) -> AuditLogResponse:
    """Convert an AuditLog document to a serialisable response model."""
    return AuditLogResponse(
        id=str(log.id),
        user_id=str(log.user_id) if log.user_id else None,
        username=log.username,
        role=log.role,
        action=log.action,
        resource=log.resource,
        resource_id=log.resource_id,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        status_code=log.status_code,
        timestamp=log.timestamp.isoformat() if log.timestamp else "",
        details=log.details,
    )


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=AuditLogListResponse,
    summary="List audit logs",
    description="Return a paginated list of audit log entries. Admin only.",
)
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=500, description="Number of logs to return"),
    offset: int = Query(default=0, ge=0, description="Number of logs to skip"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    action: Optional[str] = Query(default=None, description="Filter by HTTP method"),
    resource: Optional[str] = Query(default=None, description="Filter by resource path"),
    current_user: User = Depends(get_current_admin),
) -> AuditLogListResponse:
    """List audit logs with optional filters. Restricted to admin users."""
    try:
        query = AuditLog.find()

        if user_id is not None:
            try:
                query = query.find(Eq(AuditLog.user_id, PydanticObjectId(user_id)))
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user_id format: {user_id}",
                ) from None

        if action is not None:
            query = query.find(AuditLog.action == action.upper())

        if resource is not None:
            query = query.find(AuditLog.resource == resource)

        total = await query.count()
        logs = (
            await query.sort(-AuditLog.timestamp)
            .skip(offset)
            .limit(limit)
            .to_list()
        )

        logger.debug(
            "Admin {} listed audit logs | total={} returned={}",
            current_user.id,
            total,
            len(logs),
        )

        return AuditLogListResponse(
            logs=[_audit_to_response(log) for log in logs],
            total=total,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list audit logs: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list audit logs: {exc}",
        ) from exc
