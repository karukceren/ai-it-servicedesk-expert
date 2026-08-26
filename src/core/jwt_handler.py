"""
JWT Token Generation, Decoding, and Authentication Middleware
=============================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides HMAC-SHA256 (HS256) JWT token generation, payload decoding with
    signature and expiration validation, and FastAPI authentication / RBAC
    dependencies (`get_current_user`, `require_role`).
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

# Load environment variables from .env file
project_root = Path(__file__).resolve().parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

from src.models import get_db, User

# ---------------------------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------------------------
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "ai_servicedesk_super_secret_jwt_key_2026_production_safe_token"
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DEFAULT_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 Hours default

# FastAPI HTTP Bearer token extractor
http_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Custom JWT Exceptions
# ---------------------------------------------------------------------------
class JWTAuthError(Exception):
    """Base exception for JWT authentication errors."""
    pass


class TokenExpiredError(JWTAuthError):
    """Raised when the provided JWT token has expired."""
    pass


class InvalidTokenError(JWTAuthError):
    """Raised when the provided JWT token signature or format is invalid."""
    pass


# ---------------------------------------------------------------------------
# 1. JWT Token Generation
# ---------------------------------------------------------------------------
def create_access_token(
    user_id: Union[str, uuid.UUID],
    email: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
    custom_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a secure HMAC-SHA256 (HS256) signed JSON Web Token (JWT).

    Payload includes:
        - `sub`: User ID (UUID string)
        - `email`: User email address
        - `role`: Role for RBAC ('user' | 'admin')
        - `iat`: Timestamp token was issued at (UTC)
        - `exp`: Timestamp token expires (UTC, default 24h)

    Args:
        user_id (str | UUID): Primary key of user.
        email (str): Validated user email.
        role (str): User role (default: 'user').
        expires_delta (timedelta, optional): Custom expiration duration.
        custom_claims (dict, optional): Additional custom claims to embed.

    Returns:
        str: Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=DEFAULT_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    if custom_claims:
        payload.update(custom_claims)

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


# ---------------------------------------------------------------------------
# 2. JWT Token Decoding & Validation
# ---------------------------------------------------------------------------
def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT token's signature, algorithm, and expiration.

    Args:
        token (str): Raw JWT token string.

    Returns:
        dict: Verified payload dictionary.

    Raises:
        TokenExpiredError: If the token's expiration time (exp) is in the past.
        InvalidTokenError: If the token signature is invalid or malformed.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Token boş veya geçersiz formatta.")

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]}
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token süresi dolmuştur (Expired token).") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError("Geçersiz veya bozulmuş token (Invalid signature).") from e


# ---------------------------------------------------------------------------
# 3. Authentication & Authorization Middleware Dependencies
# ---------------------------------------------------------------------------
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that extracts and validates Bearer token from the
    `Authorization: Bearer <token>` HTTP header, retrieving the authenticated User.

    Args:
        credentials (HTTPAuthorizationCredentials): Bearer token extracted by FastAPI.
        db (Session): Database session dependency.

    Returns:
        User: Authenticated User ORM object.

    Raises:
        HTTPException (401): If authorization header is missing, token is expired,
                            or user does not exist.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yetkilendirme başlığı (Authorization: Bearer <token>) eksik.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Oturum süreniz doldu, lütfen tekrar giriş yapın.",
            headers={"WWW-Authenticate": "Bearer"}
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya yetkisiz kimlik doğrulama tokeni.",
            headers={"WWW-Authenticate": "Bearer"}
        ) from e

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token kullanıcı kimliği içermiyor.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kullanıcı ID formatı.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı veya hesabı kapatılmış.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


def require_role(required_roles: Union[str, List[str]]):
    """
    Factory for Role-Based Access Control (RBAC) dependencies.

    Args:
        required_roles (str | List[str]): Allowed roles (e.g. 'admin' or ['admin', 'manager']).

    Returns:
        Callable dependency that enforces user role check.
    """
    if isinstance(required_roles, str):
        allowed_roles = [required_roles]
    else:
        allowed_roles = list(required_roles)

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için yetkiniz yok. Gerekli rol(ler): {', '.join(allowed_roles)}"
            )
        return current_user

    return role_dependency


# Pre-configured helper for admin-only endpoints
require_admin = require_role(["admin"])
