"""
services/auth_service.py
Password hashing and JWT token creation/verification.

Tokens carry the role and the appropriate linked ID:
  - Staff roles → linked_staff_id
  - Patient role → linked_patient_id
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

# bcrypt is the hashing algorithm — strong and industry standard
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─────────────────────────────────────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return the bcrypt hash of a plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ─────────────────────────────────────────────────────────────────────────────
# JWT helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_token_payload(user: User) -> dict:
    """Build the claims dict common to both access and refresh tokens."""
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
    }
    # Attach whichever linked ID applies
    if user.linked_staff_id is not None:
        payload["linked_staff_id"] = user.linked_staff_id
    if user.linked_patient_id is not None:
        payload["linked_patient_id"] = user.linked_patient_id
    return payload


def create_access_token(user: User) -> str:
    """Create a short-lived JWT access token (30 minutes by default)."""
    payload = _build_token_payload(user)
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload["exp"] = expire
    payload["type"] = "access"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user: User) -> str:
    """Create a long-lived JWT refresh token (7 days by default)."""
    payload = _build_token_payload(user)
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload["exp"] = expire
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT.  Raises JWTError on failure.
    Called by the auth dependency — not called directly from routes.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ─────────────────────────────────────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_user_by_username(db: Session, username: str) -> User | None:
    """Fetch a user row by username. Returns None if not found."""
    return db.query(User).filter(User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """
    Verify username + password.
    Returns the User object on success, None on failure.
    """
    user = get_user_by_username(db, username)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
