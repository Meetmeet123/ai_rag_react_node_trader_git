"""
Authentication & User Management API Routes

- POST /register -- Create a new user account
- POST /login -- Authenticate and receive JWT tokens
- POST /refresh -- Refresh access token
- POST /logout -- Revoke refresh token (client-side delete)
- GET /me -- Get current user profile
"""

from __future__ import annotations

import bcrypt
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from loguru import logger

from config import settings
from database.models import Account, User, UserRole

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Request body for user registration."""

    email: str = Field(..., description="User email address")
    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )
    password: str = Field(..., min_length=6, description="User password")
    full_name: Optional[str] = Field(default=None, description="Full name")


class UserResponse(BaseModel):
    """Public user response."""

    id: str
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_approved_for_live: bool
    live_approved_at: Optional[str]
    created_at: Optional[str]


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str
    exp: Optional[datetime] = None
    type: Optional[str] = None


# Type alias used by other routers.
UserDocument = User


# ---------------------------------------------------------------------------
# Password & token helpers
# ---------------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a plain password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_token(subject: str, token_type: str, expires_minutes: int) -> str:
    """Create a JWT access or refresh token."""
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode = {"sub": subject, "exp": expire, "type": token_type}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            return None
        return TokenPayload(
            sub=subject,
            exp=datetime.utcfromtimestamp(payload.get("exp")),
            type=payload.get("type"),
        )
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------


def _user_to_response(user: User) -> Dict[str, Any]:
    """Convert a User document to a response dict."""
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "is_approved_for_live": user.is_approved_for_live,
        "live_approved_at": (
            user.live_approved_at.isoformat() if user.live_approved_at else None
        ),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def get_user_by_email(email: str) -> Optional[User]:
    """Fetch a user by email address."""
    return await User.find_one(User.email == email)


async def get_user_by_username(username: str) -> Optional[User]:
    """Fetch a user by username."""
    return await User.find_one(User.username == username)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[User]:
    """Dependency that returns the current authenticated user or None."""
    if not token:
        return None

    payload = decode_token(token)
    if payload is None or payload.type != "access":
        return None

    user = await User.get(payload.sub)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[User]:
    """Optional dependency that does not raise on missing/invalid tokens."""
    return await get_current_user(token)


async def get_current_active_user(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Dependency that requires a valid, active user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_admin(user: User = Depends(get_current_active_user)) -> User:
    """Dependency that requires an admin user."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email, username, and password.",
)
async def register(user_in: UserCreate) -> UserResponse:
    """Register a new user account."""
    # Normalize inputs
    email = user_in.email.lower().strip()
    username = user_in.username.lower().strip()

    # Check for existing email or username
    existing_email = await get_user_by_email(email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    existing_username = await get_user_by_username(username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    # Create user
    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=UserRole.USER,
        is_active=True,
        is_approved_for_live=False,
    )
    await user.insert()

    # Create empty account profile
    account = Account(user_id=user.id)
    await account.insert()

    logger.info("Registered new user id={} email={}", user.id, user.email)

    return UserResponse(**_user_to_response(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with username/email and password to receive JWT tokens.",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Authenticate a user and issue JWT tokens."""
    identifier = form_data.username.lower().strip()

    # Try email first, then username
    user = await get_user_by_email(identifier)
    if user is None:
        user = await get_user_by_username(identifier)

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await user.save()

    access_token = create_token(
        subject=str(user.id),
        token_type="access",
        expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    refresh_token = create_token(
        subject=str(user.id),
        token_type="refresh",
        expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 7,
    )

    logger.info("User logged in id={}", user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Issue a new access token using a valid refresh token.",
)
async def refresh_token(refresh_token: str) -> TokenResponse:
    """Refresh access token."""
    payload = decode_token(refresh_token)
    if payload is None or payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await User.get(payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_token(
        subject=str(user.id),
        token_type="access",
        expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    summary="Logout",
    description="Logout the current user. Tokens should be deleted client-side.",
)
async def logout(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Logout endpoint."""
    logger.info("User logged out id={}", current_user.id)
    return {"success": True, "message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the profile of the currently authenticated user.",
)
async def me(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    """Return current authenticated user profile."""
    return UserResponse(**_user_to_response(current_user))


@router.post(
    "/request-live-approval",
    summary="Request live trading approval",
    description="Current user requests admin approval to trade with real brokers.",
)
async def request_live_approval(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Flag the current user as requesting live-trading approval."""
    account = await Account.find_one(Account.user_id == current_user.id)
    if account is None:
        account = Account(user_id=current_user.id)
    account.live_approval_requested = True
    await account.save()
    logger.info("User {} requested live trading approval", current_user.id)
    return {
        "success": True,
        "message": "Live trading approval request submitted. An admin will review it.",
    }


@router.get(
    "/pending-live-approvals",
    summary="List pending live approvals",
    description="Admin-only: list users who have requested live trading approval.",
)
async def pending_live_approvals(
    admin: User = Depends(get_current_admin),
) -> List[Dict[str, Any]]:
    """Return users/accounts pending live-trading approval."""
    pending_accounts = await Account.find({"live_approval_requested": True}).to_list()
    if not pending_accounts:
        return []

    user_ids = [acc.user_id for acc in pending_accounts]
    users = await User.find(User.id.in_(user_ids)).to_list()
    user_map = {u.id: u for u in users}

    result = []
    for acc in pending_accounts:
        user = user_map.get(acc.user_id)
        if user is None:
            continue
        result.append(
            {
                "user": _user_to_response(user),
                "requested_at": acc.updated_at.isoformat() if acc.updated_at else None,
            }
        )
    return result


@router.post(
    "/users/{user_id}/approve-live",
    summary="Approve user for live trading",
    description="Admin-only: approve a user to connect real brokers and trade live.",
)
async def approve_user_for_live(
    user_id: str,
    admin: User = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Approve a user for live trading."""
    from beanie import PydanticObjectId
    from bson.errors import InvalidId

    try:
        uid = PydanticObjectId(user_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID",
        )

    user = await User.get(uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_approved_for_live = True
    user.live_approved_at = datetime.utcnow()
    user.live_approved_by = admin.id
    await user.save()

    account = await Account.find_one(Account.user_id == uid)
    if account is not None:
        account.live_approval_requested = False
        await account.save()

    logger.info("Admin {} approved user {} for live trading", admin.id, uid)
    return {
        "success": True,
        "message": f"User {user.username} approved for live trading",
        "user": _user_to_response(user),
    }
