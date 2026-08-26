"""
Integration Tests for Chat Routes, SSE Streaming & Feedback (Week 4 - Step 1)
=============================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Tests the FastAPI Chat Router endpoints:
    - POST /api/chat/stream (SSE streaming, token chunks, done payload)
    - POST /api/chat/feedback (Rating 1-5, comments, updates, isolation)
    - GET /api/chat/sessions/{id}/history (Chronological history, metadata, feedback)
"""

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import ChatMessage, SessionLocal

client = TestClient(app)


# ===========================================================================
# Fixture: Setup Test Users & Auth Tokens
# ===========================================================================
@pytest.fixture(scope="module")
def auth_tokens():
    """Registers User A, User B, and Admin, returning their JWT access tokens."""
    # User A
    email_a = f"usera_w4_{uuid.uuid4().hex[:6]}@corp.local"
    pass_a = "UserA_Pass2026!"
    client.post("/api/auth/register", json={"email": email_a, "password": pass_a, "role": "user"})
    res_a = client.post("/api/auth/login", json={"email": email_a, "password": pass_a})
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]

    # User B
    email_b = f"userb_w4_{uuid.uuid4().hex[:6]}@corp.local"
    pass_b = "UserB_Pass2026!"
    client.post("/api/auth/register", json={"email": email_b, "password": pass_b, "role": "user"})
    res_b = client.post("/api/auth/login", json={"email": email_b, "password": pass_b})
    token_b = res_b.json()["access_token"]
    user_b_id = res_b.json()["user"]["id"]

    return {
        "user_a": {"id": user_a_id, "token": token_a, "email": email_a},
        "user_b": {"id": user_b_id, "token": token_b, "email": email_b}
    }


# ===========================================================================
# Test Suite 1: POST /api/chat/stream (SSE Real-Time Streaming)
# ===========================================================================
class TestChatStreamingEndpoint:
    """Test suite for Server-Sent Events (SSE) chat streaming."""

    def test_stream_successful_rag_response(self, auth_tokens):
        """User streams a valid Windows Server query and receives token events & done payload."""
        token_a = auth_tokens["user_a"]["token"]

        # 1. Create a session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Active Directory Streaming Test"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert create_res.status_code == 201
        session_id = create_res.json()["id"]

        # 2. Call SSE stream endpoint
        stream_payload = {
            "session_id": session_id,
            "query": "Active Directory üzerinde kilitli hesapları PowerShell ile nasıl tespit edip açarım?",
            "mode": "windows_server"
        }
        res = client.post(
            "/api/chat/stream",
            json=stream_payload,
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        # Parse SSE lines
        body = res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        assert len(lines) > 0, "SSE response should contain data event lines"

        tokens = []
        done_event = None
        for line in lines:
            raw_json = line.replace("data:", "").strip()
            data = json.loads(raw_json)
            if data.get("type") == "token":
                tokens.append(data.get("content", ""))
            elif data.get("type") == "done":
                done_event = data

        assert len(tokens) > 0
        full_text = "".join(tokens)
        assert len(full_text) > 20
        assert done_event is not None
        assert done_event["status"] == "SUCCESS"
        assert "message_id" in done_event
        assert len(done_event["sources_metadata"]) > 0

    def test_stream_fallback_on_out_of_domain_query(self, auth_tokens):
        """Out-of-domain query (weather) triggers FALLBACK_TRIGGERED status in stream."""
        token_a = auth_tokens["user_a"]["token"]

        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Fallback Test"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_id = create_res.json()["id"]

        stream_payload = {
            "session_id": session_id,
            "query": "Bugün İstanbul'da hava durumu nasıl ve yağmur yağacak mı?",
            "mode": "general"
        }
        res = client.post(
            "/api/chat/stream",
            json=stream_payload,
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert res.status_code == 200
        body = res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        done_event = None
        for line in lines:
            data = json.loads(line.replace("data:", "").strip())
            if data.get("type") == "done":
                done_event = data

        assert done_event is not None
        assert done_event["status"] == "FALLBACK_TRIGGERED"

    def test_stream_unauthorized_session_blocked_with_403(self, auth_tokens):
        """User B streaming into User A's session must receive HTTP 403 Forbidden."""
        token_a = auth_tokens["user_a"]["token"]
        token_b = auth_tokens["user_b"]["token"]

        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Private User A Session"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_a_id = create_res.json()["id"]

        res_b = client.post(
            "/api/chat/stream",
            json={"session_id": session_a_id, "query": "Test query", "mode": "general"},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_b.status_code == 403
        assert "erişim yetkiniz bulunmamaktadır" in res_b.json()["detail"]

    def test_stream_nonexistent_session_returns_404(self, auth_tokens):
        """Streaming into a random UUID returns HTTP 404 Not Found."""
        token_a = auth_tokens["user_a"]["token"]
        random_id = str(uuid.uuid4())

        res = client.post(
            "/api/chat/stream",
            json={"session_id": random_id, "query": "Test", "mode": "general"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res.status_code == 404


# ===========================================================================
# Test Suite 2: POST /api/chat/feedback (Feedback & Ratings)
# ===========================================================================
class TestChatFeedbackEndpoint:
    """Test suite for message rating and feedback submission."""

    def test_submit_and_update_feedback(self, auth_tokens):
        """User submits a 5-star rating, then updates it with a comment."""
        token_a = auth_tokens["user_a"]["token"]

        # 1. Create session and run a stream to generate assistant message
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Feedback Test Session"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_id = create_res.json()["id"]

        stream_res = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "query": "ORA-01653 hatası nedir ve nasıl çözülür?",
                "mode": "oracle_db"
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        # Extract assistant message_id from done event
        body = stream_res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        done_event = [json.loads(l.replace("data:", "").strip()) for l in lines if '"type": "done"' in l][0]
        asst_msg_id = done_event["message_id"]

        # 2. Submit initial feedback (Rating 5)
        fb_res1 = client.post(
            "/api/chat/feedback",
            json={"message_id": asst_msg_id, "rating": 5, "comment": "Harika ve eksiksiz çözüm!"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert fb_res1.status_code == 201
        fb_data1 = fb_res1.json()
        assert fb_data1["message_id"] == asst_msg_id
        assert fb_data1["rating"] == 5
        assert fb_data1["comment"] == "Harika ve eksiksiz çözüm!"

        # 3. Update feedback
        fb_res2 = client.post(
            "/api/chat/feedback",
            json={"message_id": asst_msg_id, "rating": 4, "comment": "Güncellendi: Başarılı komutlar."},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert fb_res2.status_code == 201
        fb_data2 = fb_res2.json()
        assert fb_data2["id"] == fb_data1["id"]  # Same feedback ID updated
        assert fb_data2["rating"] == 4
        assert fb_data2["comment"] == "Güncellendi: Başarılı komutlar."

    def test_feedback_unauthorized_user_blocked_with_403(self, auth_tokens):
        """User B cannot submit feedback on User A's assistant message."""
        token_a = auth_tokens["user_a"]["token"]
        token_b = auth_tokens["user_b"]["token"]

        # User A creates session & message
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "User A Private Session"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_id = create_res.json()["id"]

        stream_res = client.post(
            "/api/chat/stream",
            json={"session_id": session_id, "query": "BitLocker anahtarı nedir?", "mode": "service_desk"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        body = stream_res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        done_event = [json.loads(l.replace("data:", "").strip()) for l in lines if '"type": "done"' in l][0]
        asst_msg_id = done_event["message_id"]

        # User B attempts feedback on User A's message -> 403 Forbidden
        fb_res = client.post(
            "/api/chat/feedback",
            json={"message_id": asst_msg_id, "rating": 1, "comment": "Hacker attempt"},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert fb_res.status_code == 403

    def test_feedback_nonexistent_message_returns_404(self, auth_tokens):
        """Feedback on a non-existent message UUID returns HTTP 404."""
        token_a = auth_tokens["user_a"]["token"]
        random_id = str(uuid.uuid4())

        fb_res = client.post(
            "/api/chat/feedback",
            json={"message_id": random_id, "rating": 5},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert fb_res.status_code == 404


# ===========================================================================
# Test Suite 3: GET /api/chat/sessions/{session_id}/history
# ===========================================================================
class TestChatHistoryEndpoint:
    """Test suite for session history and chronological message retrieval."""

    def test_get_session_history_with_citations_and_feedback(self, auth_tokens):
        """Retrieves session history containing user query, assistant reply, citations, and feedback."""
        token_a = auth_tokens["user_a"]["token"]

        # 1. Create session
        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "End-to-End History Test"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_id = create_res.json()["id"]

        # 2. Send query via stream
        stream_res = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "query": "Spooler yazıcı servisi durduğunda hangi komut çalıştırılır?",
                "mode": "service_desk"
            },
            headers={"Authorization": f"Bearer {token_a}"}
        )
        body = stream_res.text
        lines = [line.strip() for line in body.split("\n") if line.startswith("data:")]
        done_event = [json.loads(l.replace("data:", "").strip()) for l in lines if '"type": "done"' in l][0]
        asst_msg_id = done_event["message_id"]

        # 3. Add feedback
        client.post(
            "/api/chat/feedback",
            json={"message_id": asst_msg_id, "rating": 5, "comment": "Çok net bilgi"},
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # 4. Fetch history via GET /api/chat/sessions/{session_id}/history
        hist_res = client.get(
            f"/api/chat/sessions/{session_id}/history",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert hist_data["session_id"] == session_id
        assert hist_data["total_messages"] >= 2
        assert len(hist_data["messages"]) >= 2

        # Check message roles and sequence
        user_msg = hist_data["messages"][0]
        asst_msg = hist_data["messages"][1]
        assert user_msg["role"] == "user"
        assert "Spooler" in user_msg["content"]
        assert asst_msg["role"] == "assistant"
        assert asst_msg["feedback"]["rating"] == 5
        assert asst_msg["feedback"]["comment"] == "Çok net bilgi"
        assert "sources" in asst_msg["sources_metadata"] or "status" in asst_msg["sources_metadata"]

    def test_get_history_unauthorized_blocked_with_403(self, auth_tokens):
        """User B cannot fetch history of User A's session."""
        token_a = auth_tokens["user_a"]["token"]
        token_b = auth_tokens["user_b"]["token"]

        create_res = client.post(
            "/api/chat/sessions",
            json={"title": "Private User A Session"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        session_id = create_res.json()["id"]

        res_b = client.get(
            f"/api/chat/sessions/{session_id}/history",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_b.status_code == 403
