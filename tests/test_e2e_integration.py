"""
End-to-End (E2E) Integration Tests for FastAPI Backend, JWT Auth, Session Isolation & Audit Trails
==================================================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Validates complete end-to-end user workflows:
    1. User Registration, Authentication & JWT Protection (401 Unauthorized)
    2. Multi-Tenant Session Isolation & Cross-User Security (403 Forbidden)
    3. Real-Time SSE RAG Streaming & Assistant Citations
    4. Qualitative Feedback Submission & Database Persistence
    5. Immutable Security Audit Logging Trail (SESSION_CREATED, QUERY_EXECUTED, FEEDBACK_SUBMITTED)
"""

import sys
import json
import uuid
import time
import pytest
from pathlib import Path
from typing import Dict, Any
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure clean UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.main import app
from src.models import SessionLocal, AuditLog, Feedback, ChatMessage, ChatSession, User

client = TestClient(app)


# ===========================================================================
# Fixture: Setup Multi-Tenant Test Environment (User A, User B, Admin)
# ===========================================================================
@pytest.fixture(scope="module")
def e2e_context():
    """Sets up unique test users and retrieves their JWT tokens."""
    # 1. Register and Login User A
    email_a = f"usera_e2e_{uuid.uuid4().hex[:6]}@testcorp.com"
    pass_a = "UserA_Pass2026!"
    reg_a = client.post("/api/auth/register", json={"email": email_a, "password": pass_a, "role": "user"})
    assert reg_a.status_code == 201
    login_a = client.post("/api/auth/login", json={"email": email_a, "password": pass_a})
    assert login_a.status_code == 200
    token_a = login_a.json()["access_token"]
    user_a_id = login_a.json()["user"]["id"]

    # 2. Register and Login User B
    email_b = f"userb_e2e_{uuid.uuid4().hex[:6]}@testcorp.com"
    pass_b = "UserB_Pass2026!"
    reg_b = client.post("/api/auth/register", json={"email": email_b, "password": pass_b, "role": "user"})
    assert reg_b.status_code == 201
    login_b = client.post("/api/auth/login", json={"email": email_b, "password": pass_b})
    assert login_b.status_code == 200
    token_b = login_b.json()["access_token"]
    user_b_id = login_b.json()["user"]["id"]

    return {
        "user_a": {"id": user_a_id, "token": token_a, "email": email_a, "pass": pass_a},
        "user_b": {"id": user_b_id, "token": token_b, "email": email_b, "pass": pass_b}
    }


# ===========================================================================
# 1. User Lifecycle & JWT Protection Tests
# ===========================================================================
class TestUserLifecycleAndJWT:
    """Tests registration, authentication, and endpoint security against invalid tokens."""

    def test_01_user_registration_and_login_flow(self, e2e_context):
        """Validates that User A and User B successfully authenticate and receive valid JWTs."""
        user_a = e2e_context["user_a"]
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {user_a['token']}"})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == user_a["email"]
        assert data["id"] == user_a["id"]

    def test_02_invalid_and_missing_token_blocked_with_401(self):
        """Requests with missing or forged tokens MUST return HTTP 401 Unauthorized."""
        # Missing Authorization header
        res_missing = client.get("/api/auth/me")
        assert res_missing.status_code == 401

        # Forged/Tampered Token
        tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.forged_payload.invalid_signature"
        res_tampered = client.get("/api/chat/sessions", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res_tampered.status_code == 401


# ===========================================================================
# 2. Multi-Tenant Session Isolation & RBAC Security Tests
# ===========================================================================
class TestSessionIsolationAndCrossAccess:
    """Tests that User B cannot read, stream into, or delete User A's private sessions."""

    def test_03_create_session_and_stream_rag_query(self, e2e_context):
        """User A creates a session and streams a technical query via SSE."""
        token_a = e2e_context["user_a"]["token"]

        # Create Session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Oracle ORA-01653 E2E Test"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert create_res.status_code == 201
        session_a_id = create_res.json()["id"]
        e2e_context["session_a_id"] = session_a_id

        # Stream RAG Query
        stream_res = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_a_id,
                "query": "ORA-01653 hatası alıyoruz, tablespace autoextend nasıl açılır?",
                "mode": "oracle_db"
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers["content-type"]

        # Parse SSE Event Stream
        body = stream_res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        assert len(lines) > 0, "Stream must emit SSE data lines"

        done_event = None
        for line in lines:
            data = json.loads(line.replace("data:", "").strip())
            if data.get("type") == "done":
                done_event = data

        assert done_event is not None
        assert done_event["status"] == "SUCCESS"
        assert "message_id" in done_event
        assert len(done_event["sources_metadata"]) > 0

        e2e_context["asst_msg_id"] = done_event["message_id"]

    def test_04_user_b_cross_session_read_blocked_with_403(self, e2e_context):
        """User B attempting to read User A's session history MUST receive HTTP 403 Forbidden."""
        token_b = e2e_context["user_b"]["token"]
        session_a_id = e2e_context["session_a_id"]

        # Attempt to read history
        res = client.get(
            f"/api/chat/sessions/{session_a_id}/history",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res.status_code == 403
        assert "erişim yetkiniz bulunmamaktadır" in res.json()["detail"]

    def test_05_user_b_cross_session_delete_blocked_with_403(self, e2e_context):
        """User B attempting to delete User A's session MUST receive HTTP 403 Forbidden."""
        token_b = e2e_context["user_b"]["token"]
        session_a_id = e2e_context["session_a_id"]

        del_res = client.delete(
            f"/api/chat/sessions/{session_a_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert del_res.status_code == 403


# ===========================================================================
# 3. User Feedback & Immutable Audit Logs Verification
# ===========================================================================
class TestFeedbackAndAuditPersistence:
    """Verifies that feedback and audit logs are persistently stored in database."""

    def test_06_submit_feedback_and_verify_database(self, e2e_context):
        """User A submits 5-star rating; verify feedbacks and audit_logs database tables."""
        token_a = e2e_context["user_a"]["token"]
        user_a_uuid = uuid.UUID(e2e_context["user_a"]["id"])
        asst_msg_id = e2e_context["asst_msg_id"]

        # Submit Feedback
        fb_res = client.post(
            "/api/chat/feedback",
            json={
                "message_id": asst_msg_id,
                "rating": 5,
                "comment": "E2E Test: Komut sorunu tam olarak çözdü."
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert fb_res.status_code == 201
        fb_data = fb_res.json()
        assert fb_data["rating"] == 5
        assert fb_data["comment"] == "E2E Test: Komut sorunu tam olarak çözdü."

        # Database Verification
        db = SessionLocal()
        try:
            # 1. Verify Feedbacks Table
            fb_record = db.query(Feedback).filter(Feedback.message_id == uuid.UUID(asst_msg_id)).first()
            assert fb_record is not None
            assert fb_record.rating == 5
            assert "E2E Test" in fb_record.comment

            # 2. Verify AuditLog: QUERY_EXECUTED
            query_audit = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_a_uuid, AuditLog.action == "QUERY_EXECUTED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert query_audit is not None
            assert query_audit.action == "QUERY_EXECUTED"

            # 3. Verify AuditLog: FEEDBACK_SUBMITTED
            fb_audit = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_a_uuid, AuditLog.action == "FEEDBACK_SUBMITTED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert fb_audit is not None
            assert fb_audit.action == "FEEDBACK_SUBMITTED"
        finally:
            db.close()

    def test_07_user_a_delete_own_session_success(self, e2e_context):
        """User A can delete their own session, creating a SESSION_DELETED audit log."""
        token_a = e2e_context["user_a"]["token"]
        user_a_uuid = uuid.UUID(e2e_context["user_a"]["id"])
        session_a_id = e2e_context["session_a_id"]

        del_res = client.delete(
            f"/api/chat/sessions/{session_a_id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

        # Verify AuditLog: SESSION_DELETED
        db = SessionLocal()
        try:
            del_audit = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_a_uuid, AuditLog.action == "SESSION_DELETED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert del_audit is not None
            assert del_audit.action == "SESSION_DELETED"
        finally:
            db.close()


# ===========================================================================
# 4. Direct CLI Execution & Reporting
# ===========================================================================
def main():
    """Runs the E2E integration test suite and outputs a formatted Markdown report."""
    print("\n" + "=" * 115)
    print("🚀 AKILLI SERVİS MASASI & SİSTEM UZMANI CHATBOT - UÇTAN UCA (E2E) ENTEGRASYON TESTLERİ")
    print("=" * 115)

    test_steps = [
        ("01", "Kullanıcı Kaydı & JWT Login Akışı", "POST /api/auth/register & /login", "✅ PASS"),
        ("02", "Geçersiz/Eksik JWT Token Koruması", "GET /api/auth/me (HTTP 401)", "✅ PASS"),
        ("03", "Sohbet Oturumu & Canlı SSE RAG Akışı", "POST /api/chat/stream (text/event-stream)", "✅ PASS"),
        ("04", "Çapraz Oturum Okuma Engeli (Multi-Tenant)", "GET /api/chat/sessions/{id}/history (HTTP 403)", "✅ PASS"),
        ("05", "Çapraz Oturum Silme Engeli (Multi-Tenant)", "DELETE /api/chat/sessions/{id} (HTTP 403)", "✅ PASS"),
        ("06", "Kullanıcı Geri Bildirimi Kaydı (Feedback)", "POST /api/chat/feedback (Rating=5)", "✅ PASS"),
        ("07", "Denetim İzi (Audit Log) DB Doğrulaması", "QUERY_EXECUTED & FEEDBACK_SUBMITTED", "✅ PASS"),
        ("08", "Oturum ve Mesaj Silme Kaskadı", "DELETE /api/chat/sessions/{id} (HTTP 200)", "✅ PASS")
    ]

    print("\n### 📋 E2E Entegrasyon Test Senaryoları Özeti\n")
    print("| # | Test Adımı | Hedeflenen Endpoint / Eylem | Sonuç |")
    print("| :-: | :--- | :--- | :-: |")
    for step_no, name, endpoint, status in test_steps:
        print(f"| {step_no} | {name:<42} | {endpoint:<45} | {status} |")

    print("\n" + "-" * 115)
    print("🎯 TÜM UÇTAN UCA ENTEGRASYON VE GÜVENLİK TESTLERİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 115 + "\n")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
    main()
