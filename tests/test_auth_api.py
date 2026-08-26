"""
Integration Tests for Authentication API Routes
================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import User, AuditLog, SessionLocal


client = TestClient(app)


# ===========================================================================
# 1. User Registration Tests (POST /api/auth/register)
# ===========================================================================
class TestRegisterEndpoint:
    """Test suite for /api/auth/register endpoint."""

    def test_register_success(self):
        """Valid registration request must return HTTP 201 and create user + audit log."""
        unique_email = f"new_engineer_{uuid.uuid4().hex[:6]}@corp.local"
        password = "SecurePassword2026!"

        response = client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": password,
                "role": "user"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == unique_email.lower()
        assert data["role"] == "user"
        assert "id" in data
        assert "created_at" in data

        # Verify audit log in database
        db = SessionLocal()
        try:
            user_id = uuid.UUID(data["id"])
            audit = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.action == "USER_REGISTERED"
            ).first()
            assert audit is not None
        finally:
            db.close()

    def test_register_duplicate_email(self):
        """Registering with an already existing email must return HTTP 400."""
        duplicate_email = f"duplicate_{uuid.uuid4().hex[:6]}@corp.local"
        password = "SecurePassword2026!"

        # First registration
        res1 = client.post(
            "/api/auth/register",
            json={"email": duplicate_email, "password": password}
        )
        assert res1.status_code == 201

        # Second registration with identical email
        res2 = client.post(
            "/api/auth/register",
            json={"email": duplicate_email, "password": password}
        )
        assert res2.status_code == 400
        assert "zaten mevcut" in res2.json()["detail"]

    def test_register_invalid_email_format(self):
        """Registering with an invalid email format must return HTTP 400."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "invalid_email_no_at_sign",
                "password": "SecurePassword2026!"
            }
        )
        assert response.status_code == 400
        assert "Geçersiz e-posta" in response.json()["detail"]

    def test_register_weak_password(self):
        """Registering with a weak password (<8 chars / missing numbers) must return HTTP 400."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"weak_{uuid.uuid4().hex[:6]}@corp.local",
                "password": "weak"
            }
        )
        assert response.status_code == 400
        assert "karmaşıklık" in response.json()["detail"]


# ===========================================================================
# 2. User Login Tests (POST /api/auth/login)
# ===========================================================================
class TestLoginEndpoint:
    """Test suite for /api/auth/login endpoint."""

    @pytest.fixture(scope="class")
    def registered_user(self):
        """Pre-registers a user for login testing."""
        email = f"login_test_{uuid.uuid4().hex[:6]}@corp.local"
        password = "StrongPassword2026!"

        res = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "role": "admin"}
        )
        assert res.status_code == 201
        return {"email": email, "password": password}

    def test_login_success(self, registered_user):
        """Valid credentials must return HTTP 200, JWT token, and record LOGIN_SUCCESS audit."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == registered_user["email"].lower()
        assert data["user"]["role"] == "admin"
        assert data["expires_in_seconds"] > 0

        # Verify audit log in database
        db = SessionLocal()
        try:
            user_id = uuid.UUID(data["user"]["id"])
            audit = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.action == "LOGIN_SUCCESS"
            ).first()
            assert audit is not None
        finally:
            db.close()

    def test_login_wrong_password(self, registered_user):
        """Incorrect password must return HTTP 401 and record LOGIN_FAILED audit."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": registered_user["email"],
                "password": "WrongPassword123!"
            }
        )

        assert response.status_code == 401
        assert "Geçersiz e-posta veya parola" in response.json()["detail"]

        # Verify LOGIN_FAILED audit log in database
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == registered_user["email"]).first()
            audit = db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.action == "LOGIN_FAILED"
            ).first()
            assert audit is not None
        finally:
            db.close()

    def test_login_nonexistent_email(self):
        """Non-existent email must return HTTP 401."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent_ghost@corp.local",
                "password": "AnyPassword123!"
            }
        )
        assert response.status_code == 401
        assert "Geçersiz e-posta veya parola" in response.json()["detail"]


# ===========================================================================
# 3. Protected Profile Tests (GET /api/auth/me)
# ===========================================================================
class TestProfileEndpoint:
    """Test suite for /api/auth/me protected profile endpoint."""

    def test_get_me_authorized(self):
        """Protected endpoint with valid Bearer token must return authenticated user profile."""
        email = f"profile_user_{uuid.uuid4().hex[:6]}@corp.local"
        password = "P@ssword2026!"

        # Register & Login
        client.post("/api/auth/register", json={"email": email, "password": password, "role": "user"})
        login_res = client.post("/api/auth/login", json={"email": email, "password": password})
        token = login_res.json()["access_token"]

        # Call GET /api/auth/me with Bearer token
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email.lower()
        assert data["role"] == "user"
        assert "id" in data

    def test_get_me_unauthorized_missing_token(self):
        """Protected endpoint without Authorization header must return HTTP 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert "Yetkilendirme başlığı" in response.json()["detail"]

    def test_get_me_invalid_token(self):
        """Protected endpoint with a fake/invalid token must return HTTP 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer fake.invalid.jwt.token"}
        )
        assert response.status_code == 401
        assert "Geçersiz veya yetkisiz" in response.json()["detail"]


# ===========================================================================
# Direct Execution Entrypoint
# ===========================================================================
if __name__ == "__main__":
    pytest.main(["-v", __file__])
