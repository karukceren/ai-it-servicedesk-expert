"""
Integration Tests for Chat Session Isolation & Multi-Tenant Security
====================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import ChatMessage, Feedback, SessionLocal

client = TestClient(app)


# ===========================================================================
# Fixture: Setup Users (User A, User B, Admin)
# ===========================================================================
@pytest.fixture(scope="module")
def auth_tokens():
    """Registers User A, User B, and Admin, returning their JWT access tokens."""
    # 1. Register User A
    email_a = f"usera_{uuid.uuid4().hex[:6]}@corp.local"
    pass_a = "UserA_Pass2026!"
    client.post("/api/auth/register", json={"email": email_a, "password": pass_a, "role": "user"})
    res_a = client.post("/api/auth/login", json={"email": email_a, "password": pass_a})
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]

    # 2. Register User B
    email_b = f"userb_{uuid.uuid4().hex[:6]}@corp.local"
    pass_b = "UserB_Pass2026!"
    client.post("/api/auth/register", json={"email": email_b, "password": pass_b, "role": "user"})
    res_b = client.post("/api/auth/login", json={"email": email_b, "password": pass_b})
    token_b = res_b.json()["access_token"]
    user_b_id = res_b.json()["user"]["id"]

    # 3. Register Admin User
    email_admin = f"admin_{uuid.uuid4().hex[:6]}@corp.local"
    pass_admin = "Admin_Pass2026!"
    client.post("/api/auth/register", json={"email": email_admin, "password": pass_admin, "role": "admin"})
    res_admin = client.post("/api/auth/login", json={"email": email_admin, "password": pass_admin})
    token_admin = res_admin.json()["access_token"]
    admin_id = res_admin.json()["user"]["id"]

    return {
        "user_a": {"id": user_a_id, "token": token_a, "email": email_a},
        "user_b": {"id": user_b_id, "token": token_b, "email": email_b},
        "admin": {"id": admin_id, "token": token_admin, "email": email_admin}
    }


# ===========================================================================
# Test Suite: Chat Session Isolation & RBAC
# ===========================================================================
class TestChatSessionIsolation:
    """Test suite ensuring strict multi-tenant session isolation."""

    def test_session_creation(self, auth_tokens):
        """User A creates a session and receives HTTP 201."""
        token_a = auth_tokens["user_a"]["token"]
        response = client.post(
            "/api/chat/sessions",
            json={"title": "Active Directory Sorunu"},
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Active Directory Sorunu"
        assert data["user_id"] == auth_tokens["user_a"]["id"]
        assert "id" in data

    def test_user_session_listing_isolation(self, auth_tokens):
        """User B must only see their own sessions, not User A's sessions."""
        token_a = auth_tokens["user_a"]["token"]
        token_b = auth_tokens["user_b"]["token"]

        # User A creates a session
        client.post(
            "/api/chat/sessions",
            json={"title": "User A Private Session"},
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # User B queries their session list
        res_b = client.get("/api/chat/sessions", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        sessions_b = res_b.json()

        # None of User B's visible sessions should belong to User A
        for s in sessions_b:
            assert s["user_id"] == auth_tokens["user_b"]["id"]
            assert s["user_id"] != auth_tokens["user_a"]["id"]

    def test_unauthorized_message_access_blocked_with_403(self, auth_tokens):
        """
        User B attempting to read User A's session messages MUST receive HTTP 403 Forbidden.
        """
        token_a = auth_tokens["user_a"]["token"]
        token_b = auth_tokens["user_b"]["token"]

        # 1. User A creates a session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Oracle Tablespace Error"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_a_id = create_res.json()["id"]

        # 2. Add messages to User A's session in DB
        db = SessionLocal()
        try:
            msg1 = ChatMessage(
                session_id=uuid.UUID(session_a_id),
                role="user",
                content="ORA-01653 hatasi aliyorum nasil cozerim?"
            )
            msg2 = ChatMessage(
                session_id=uuid.UUID(session_a_id),
                role="assistant",
                content="ALTER TABLESPACE USERS ADD DATAFILE 'users02.dbf' SIZE 100M AUTOEXTEND ON;",
                sources_metadata={"source": "oracle_db_clean.json", "category": "oracle_db"}
            )
            db.add_all([msg1, msg2])
            db.commit()
            db.refresh(msg2)

            fb = Feedback(message_id=msg2.id, rating=5, comment="Cok yardimci oldu")
            db.add(fb)
            db.commit()
        finally:
            db.close()

        # 3. User A retrieves messages -> SUCCESS (HTTP 200)
        res_a = client.get(
            f"/api/chat/sessions/{session_a_id}/messages",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert len(data_a["messages"]) == 2
        assert data_a["messages"][1]["sources_metadata"]["category"] == "oracle_db"
        assert data_a["messages"][1]["feedback"]["rating"] == 5

        # 4. User B attempts to access User A's session messages -> FORBIDDEN (HTTP 403)
        res_b = client.get(
            f"/api/chat/sessions/{session_a_id}/messages",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_b.status_code == 403
        assert "yetkiniz bulunmamaktadır" in res_b.json()["detail"]

        # 5. User B attempts to delete User A's session -> FORBIDDEN (HTTP 403)
        del_b = client.delete(
            f"/api/chat/sessions/{session_a_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert del_b.status_code == 403

    def test_admin_can_access_any_session(self, auth_tokens):
        """Admin role can access User A's session messages for support/audit."""
        token_a = auth_tokens["user_a"]["token"]
        token_admin = auth_tokens["admin"]["token"]

        # User A creates a session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "VPN Baglanti Sorunu"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_a_id = create_res.json()["id"]

        # Admin accesses User A's session -> SUCCESS (HTTP 200)
        res_admin = client.get(
            f"/api/chat/sessions/{session_a_id}/messages",
            headers={"Authorization": f"Bearer {token_admin}"}
        )
        assert res_admin.status_code == 200
        assert res_admin.json()["session"]["id"] == session_a_id

    def test_admin_can_list_all_sessions(self, auth_tokens):
        """Admin with ?all=true queries all sessions across the organization."""
        token_admin = auth_tokens["admin"]["token"]

        response = client.get(
            "/api/chat/sessions?all=true",
            headers={"Authorization": f"Bearer {token_admin}"}
        )
        assert response.status_code == 200
        all_sessions = response.json()
        assert len(all_sessions) >= 2

    def test_delete_session_success_cascade(self, auth_tokens):
        """User A can delete their own session, cascading to messages."""
        token_a = auth_tokens["user_a"]["token"]

        # Create session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Silinecek Oturum"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_id = create_res.json()["id"]

        # Delete session
        del_res = client.delete(
            f"/api/chat/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

        # Check subsequent access -> 404
        check_res = client.get(
            f"/api/chat/sessions/{session_id}/messages",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert check_res.status_code == 404


# ===========================================================================
# Direct Execution Entrypoint
# ===========================================================================
if __name__ == "__main__":
    pytest.main(["-v", __file__])
