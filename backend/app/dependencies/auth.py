"""
dependencies/auth.py
FastAPI dependency functions for authentication and role-based access control.

Usage in a route:
    from app.dependencies.auth import get_current_user, require_role, block_patient_role

    @router.get("/admin-only")
    def admin_route(current_user = Depends(require_role("admin"))):
        ...

    @router.get("/staff-only")
    def staff_route(current_user = Depends(block_patient_role)):
        ...

    @router.get("/my-data")
    def patient_route(current_user = Depends(require_own_patient_or_staff)):
        ...
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_token, get_user_by_username

# OAuth2PasswordBearer reads the token from the Authorization: Bearer <token> header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# ─────────────────────────────────────────────────────────────────────────────
# Core dependency: get the authenticated user from the JWT
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT from the Authorization header and return the matching User row.
    Raises HTTP 401 if the token is invalid, expired, or the user doesn't exist.
    """
    try:
        payload = decode_token(token)
        username: str | None = payload.get("sub")
        if username is None:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


# ─────────────────────────────────────────────────────────────────────────────
# Role-based access dependencies
# ─────────────────────────────────────────────────────────────────────────────

def require_role(role: str):
    """
    Returns a FastAPI dependency that only allows users with the given exact role.
    Example: Depends(require_role("admin"))
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to role: {role}",
            )
        return current_user
    return _check


def require_any_role(roles: list[str]):
    """
    Returns a FastAPI dependency that allows any of the given roles.
    Example: Depends(require_any_role(["doctor", "nurse", "admin"]))
    """
    role_set = frozenset(roles)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to roles: {', '.join(sorted(roles))}",
            )
        return current_user
    return _check


def block_patient_role(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that blocks the 'patient' role entirely.
    Used on all ML endpoints — patients must never see ML predictions.
    Raises HTTP 403 for any patient-role user.
    """
    if current_user.role == "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "ML predictions are not accessible to patients. "
                "These are clinical decision-support tools for authorised staff only."
            ),
        )
    return current_user


def require_own_patient_or_staff(
    patient_id: int,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency for patient-portal routes.
    - Patient role: only allowed if patient_id == their own linked_patient_id.
    - All staff/admin roles: allowed for any patient_id.
    Raises HTTP 403 if a patient tries to access another patient's record.
    """
    if current_user.role == "patient":
        if current_user.linked_patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own records.",
            )
    return current_user
