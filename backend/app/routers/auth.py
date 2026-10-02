"""
routers/auth.py
Authentication endpoints:
  POST /api/v1/auth/login   — returns access + refresh tokens
  POST /api/v1/auth/refresh — exchange refresh token for new access token
  GET  /api/v1/auth/me      — returns the caller's own profile
"""
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserMeResponse,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_username,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, summary="Login and receive JWT tokens")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username + password.
    Returns a short-lived access token (30 min) and a long-lived refresh token (7 days).
    Include the access token in subsequent requests as:
        Authorization: Bearer <access_token>
    """
    user = authenticate_user(db, body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
    )


@router.post("/refresh", response_model=TokenResponse, summary="Exchange refresh token for new access token")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Provide a valid refresh token to get a new access token without re-entering credentials.
    The refresh token itself is also renewed.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exc
        username: str | None = payload.get("sub")
        if not username:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_exc

    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
    )


@router.get("/me", response_model=UserMeResponse, summary="Get current user's profile")
def me(current_user: User = Depends(get_current_user)):
    """
    Returns the authenticated user's profile, role, and linked ID.
    The frontend uses this after login to know which dashboard to show.
    """
    return current_user
