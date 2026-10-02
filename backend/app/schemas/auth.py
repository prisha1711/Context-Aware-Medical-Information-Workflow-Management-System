"""
schemas/auth.py
Pydantic schemas for authentication request/response validation.
Pydantic ensures the API rejects malformed requests before they reach service code.
"""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Body of POST /api/v1/auth/login"""
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Response body of POST /api/v1/auth/login"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Body of POST /api/v1/auth/refresh"""
    refresh_token: str


class UserMeResponse(BaseModel):
    """Response body of GET /api/v1/auth/me — the caller's own profile."""
    user_id: int
    username: str
    email: str
    role: str
    is_active: bool
    linked_staff_id: int | None = None
    linked_patient_id: int | None = None

    model_config = {"from_attributes": True}
