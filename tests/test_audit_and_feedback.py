"""
Integration Tests for Audit Logs, Feedback & Citations (Week 4 - Step 3)
========================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Verifies that:
    1. Query execution generates an immutable AuditLog with action='QUERY_EXECUTED'.
    2. Feedback submission records both Feedback and AuditLog ('FEEDBACK_SUBMITTED').
    3. Session creation/deletion records AuditLogs ('SESSION_CREATED', 'SESSION_DELETED').
    4. Citations contain normalized confidence percentage, titles, categories, and chunk snippets.
"""

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import SessionLocal, AuditLog, Feedback, ChatMessage

client = TestClient(app)


# ===========================================================================
# Fixture: Setup Authenticated Test User
# ===========================================================================
@pytest.fixture(scope="module")
def auth_user():
    """Registers a unique test user and returns ID & JWT token."""
    email = f"audit_user_{uuid.uuid4().hex[:6]}@corp.local"
    password = "Audit_User2026!"
    client.post("/api/auth/register", json={"email": email, "password": password, "role": "user"})
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]

    return {"id": user_id, "token": token, "email": email}


# ===========================================================================
# Test Suite: Audit Trail & Feedback Verification
# ===========================================================================
class TestAuditTrailAndFeedback:
    """Verifies database persistence of audit logs and user evaluation feedback."""

    def test_session_creation_records_audit_log(self, auth_user):
        """Creating a session must insert an AuditLog record with action='SESSION_CREATED'."""
        token = auth_user["token"]
        user_uuid = uuid.UUID(auth_user["id"])

        res = client.post(
            "/api/chat/sessions",
            json={"title": "Audit Test Session"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 201
        session_id = res.json()["id"]

        # Verify AuditLog in DB
        db = SessionLocal()
        try:
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_uuid, AuditLog.action == "SESSION_CREATED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert audit is not None
            assert audit.action == "SESSION_CREATED"
            assert str(audit.user_id) == auth_user["id"]
        finally:
            db.close()

    def test_query_execution_records_audit_log_and_citations(self, auth_user):
        """Streaming a query must insert an AuditLog ('QUERY_EXECUTED') and return rich citations."""
        token = auth_user["token"]
        user_uuid = uuid.UUID(auth_user["id"])

        # 1. Create session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Citation Audit Session"},
            headers={"Authorization": f"Bearer {token}"}
        )
        session_id = create_res.json()["id"]

        # 2. Execute SSE stream
        stream_res = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "query": "BitLocker 48 haneli kurtarma anahtarı nasıl temin edilir?",
                "mode": "service_desk"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert stream_res.status_code == 200

        # Parse SSE done event
        body = stream_res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        done_event = [json.loads(l.replace("data:", "").strip()) for l in lines if '"type": "done"' in l][0]

        # Verify Citations Structure
        sources = done_event.get("sources_metadata", [])
        assert len(sources) > 0
        first_src = sources[0]
        assert "title" in first_src
        assert "category" in first_src
        assert "formatted_confidence" in first_src
        assert "snippet" in first_src or "content" in first_src

        # 3. Verify QUERY_EXECUTED AuditLog in DB
        db = SessionLocal()
        try:
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_uuid, AuditLog.action == "QUERY_EXECUTED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert audit is not None
            assert audit.action == "QUERY_EXECUTED"
        finally:
            db.close()

    def test_feedback_submission_records_db_and_audit_log(self, auth_user):
        """Submitting feedback must insert into feedbacks table and create FEEDBACK_SUBMITTED audit log."""
        token = auth_user["token"]
        user_uuid = uuid.UUID(auth_user["id"])

        # 1. Create session & send query
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Feedback Audit Session"},
            headers={"Authorization": f"Bearer {token}"}
        )
        session_id = create_res.json()["id"]

        stream_res = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "query": "PowerShell ile AD kilitli kullanıcı açma komutu nedir?",
                "mode": "windows_server"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        body = stream_res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        done_event = [json.loads(l.replace("data:", "").strip()) for l in lines if '"type": "done"' in l][0]
        asst_msg_id = done_event["message_id"]

        # 2. Submit Thumbs Up (Rating 5) Feedback
        fb_res = client.post(
            "/api/chat/feedback",
            json={
                "message_id": asst_msg_id,
                "rating": 5,
                "comment": "Komut anında sorunu çözdü!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert fb_res.status_code == 201

        # 3. Verify Feedbacks table and AuditLog table
        db = SessionLocal()
        try:
            fb_record = db.query(Feedback).filter(Feedback.message_id == uuid.UUID(asst_msg_id)).first()
            assert fb_record is not None
            assert fb_record.rating == 5
            assert fb_record.comment == "Komut anında sorunu çözdü!"

            audit_fb = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_uuid, AuditLog.action == "FEEDBACK_SUBMITTED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert audit_fb is not None
            assert audit_fb.action == "FEEDBACK_SUBMITTED"
        finally:
            db.close()

    def test_session_deletion_records_audit_log(self, auth_user):
        """Deleting a session must record a SESSION_DELETED audit log."""
        token = auth_user["token"]
        user_uuid = uuid.UUID(auth_user["id"])

        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "To be deleted session"},
            headers={"Authorization": f"Bearer {token}"}
        )
        session_id = create_res.json()["id"]

        del_res = client.delete(
            f"/api/chat/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert del_res.status_code == 200

        db = SessionLocal()
        try:
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_uuid, AuditLog.action == "SESSION_DELETED")
                .order_by(AuditLog.timestamp.desc())
                .first()
            )
            assert audit is not None
            assert audit.action == "SESSION_DELETED"
        finally:
            db.close()
