"""
Pydantic Data Transfer Objects (DTO) / Schemas Package
======================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    """Payload for user registration."""
    email: str = Field(
        ...,
        description="Corporate or personal user email address",
        json_schema_extra={"example": "support.engineer@corp.local"}
    )
    password: str = Field(
        ...,
        description="Strong password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit)",
        json_schema_extra={"example": "P@ssw0rd2026!"}
    )
    role: Optional[str] = Field(
        "user",
        description="User role ('user' or 'admin')",
        json_schema_extra={"example": "user"}
    )


class UserLoginRequest(BaseModel):
    """Payload for user login."""
    email: str = Field(
        ...,
        description="Registered user email",
        json_schema_extra={"example": "support.engineer@corp.local"}
    )
    password: str = Field(
        ...,
        description="Plaintext password",
        json_schema_extra={"example": "P@ssw0rd2026!"}
    )


class UserResponse(BaseModel):
    """Sanitized user profile response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    created_at: Optional[str] = None


class LoginResponse(BaseModel):
    """Successful authentication token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    expires_in_seconds: int = 86400  # 24 hours default


class MessageResponse(BaseModel):
    """Standard message response."""
    detail: str
    status: str = "success"
