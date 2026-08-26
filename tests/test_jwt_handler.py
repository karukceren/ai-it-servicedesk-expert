"""
Unit Tests for JWT Token Generation, Decoding, and Middleware
=============================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from datetime import timedelta
import pytest
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from src.core.jwt_handler import (
    create_access_token,
    decode_access_token,
    get_current_user,
    require_role,
    require_admin,
    TokenExpiredError,
    InvalidTokenError,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
)
from src.models import User, SessionLocal


# ===========================================================================
# 1. Token Generation & Decoding Tests
# ===========================================================================
class TestJWTGenerationAndDecoding:
    """Test suite for create_access_token and decode_access_token."""

    def test_create_and_decode_valid_token(self):
        """Tokens generated with valid params must decode with correct claims."""
        user_id = str(uuid.uuid4())
        email = "admin@corp.local"
        role = "admin"

        token = create_access_token(
            user_id=user_id,
            email=email,
            role=role,
            expires_delta=timedelta(hours=2),
            custom_claims={"department": "IT_Security"}
        )

        assert isinstance(token, str)
        assert len(token) > 20

        # Decode & Verify Payload
        payload = decode_access_token(token)
        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["role"] == role
        assert payload["department"] == "IT_Security"
        assert "exp" in payload
        assert "iat" in payload

    def test_token_expiration(self):
        """Expired tokens must raise TokenExpiredError."""
        user_id = str(uuid.uuid4())
        # Create token that expired 10 seconds ago
        expired_token = create_access_token(
            user_id=user_id,
            email="expired@corp.local",
            role="user",
            expires_delta=timedelta(seconds=-10)
        )

        with pytest.raises(TokenExpiredError, match="Token süresi dolmuştur"):
            decode_access_token(expired_token)

    def test_tampered_token_signature(self):
        """Tokens with modified signatures or invalid keys must raise InvalidTokenError."""
        user_id = str(uuid.uuid4())
        valid_token = create_access_token(user_id=user_id, email="user@corp.local")

        # Tamper with token payload (middle segment)
        parts = valid_token.split(".")
        tampered_token = f"{parts[0]}.eyJzdWIiOiAiaGFja2VyIn0.{parts[2]}"

        with pytest.raises(InvalidTokenError):
            decode_access_token(tampered_token)

    def test_token_signed_with_wrong_secret(self):
        """Tokens signed with a different secret must be rejected."""
        foreign_payload = {
            "sub": str(uuid.uuid4()),
            "email": "intruder@domain.com",
            "role": "admin",
            "exp": 9999999999,
            "iat": 1000000000
        }
        foreign_token = jwt.encode(foreign_payload, "wrong_secret_key_12345678901234567890", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            decode_access_token(foreign_token)

    def test_empty_or_malformed_token_string(self):
        """Empty or invalid format strings must raise InvalidTokenError."""
        with pytest.raises(InvalidTokenError):
            decode_access_token("")

        with pytest.raises(InvalidTokenError):
            decode_access_token("not.a.valid.jwt")

        with pytest.raises(InvalidTokenError):
            decode_access_token(None)  # type: ignore


# ===========================================================================
# 2. Auth Middleware Dependency & RBAC Tests
# ===========================================================================
class TestAuthMiddleware:
    """Test suite for get_current_user and require_role dependencies."""

    @pytest.fixture(scope="function")
    def db_session(self):
        """Provides a clean database session for each test."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture(scope="function")
    def sample_users(self, db_session):
        """Creates standard user and admin user in the database."""
        user = User(
            email=f"std_user_{uuid.uuid4().hex[:6]}@corp.local",
            password_hash="hashed_pw_xyz",
            role="user"
        )
        admin = User(
            email=f"admin_user_{uuid.uuid4().hex[:6]}@corp.local",
            password_hash="hashed_pw_abc",
            role="admin"
        )
        db_session.add_all([user, admin])
        db_session.commit()
        db_session.refresh(user)
        db_session.refresh(admin)

        yield {"user": user, "admin": admin}

        # Cleanup
        try:
            db_session.delete(user)
            db_session.delete(admin)
            db_session.commit()
        except Exception:
            db_session.rollback()

    def test_get_current_user_success(self, db_session, sample_users):
        """Valid bearer token must return authenticated User ORM model."""
        target_user = sample_users["user"]
        token = create_access_token(user_id=target_user.id, email=target_user.email, role="user")

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        current_user = get_current_user(credentials=creds, db=db_session)

        assert current_user.id == target_user.id
        assert current_user.email == target_user.email
        assert current_user.role == "user"

    def test_get_current_user_missing_credentials(self, db_session):
        """Missing credentials must raise HTTP 401 Unauthorized."""
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=None, db=db_session)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_nonexistent_user(self, db_session):
        """Token with valid signature but non-existent user_id must raise 401."""
        non_existent_id = uuid.uuid4()
        token = create_access_token(user_id=non_existent_id, email="ghost@corp.local")

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=creds, db=db_session)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "bulunamadı" in exc.value.detail

    def test_rbac_require_admin_success(self, sample_users):
        """Admin user must pass require_admin dependency."""
        admin_user = sample_users["admin"]
        check_admin = require_admin
        result = check_admin(current_user=admin_user)
        assert result.id == admin_user.id
        assert result.is_admin is True

    def test_rbac_require_admin_forbidden_for_standard_user(self, sample_users):
        """Standard user must be rejected with HTTP 403 Forbidden on admin endpoint."""
        standard_user = sample_users["user"]
        check_admin = require_admin

        with pytest.raises(HTTPException) as exc:
            check_admin(current_user=standard_user)

        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
        assert "yetkiniz yok" in exc.value.detail


# ===========================================================================
# Direct Execution Entrypoint
# ===========================================================================
if __name__ == "__main__":
    pytest.main(["-v", __file__])
