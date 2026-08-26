"""
Automated Test Suite for Analytics, Prometheus Metrics & Observability
======================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Validates Prometheus /metrics endpoint exposition, metric recording helpers,
    and GET /api/analytics/summary dashboard KPI data aggregation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import get_db, User, ChatSession, ChatMessage, Feedback, AuditLog
from src.core.jwt_handler import create_access_token
from src.services.analytics_service import analytics_service
from src.api.metrics import (
    record_rag_query,
    record_rag_fallback,
    record_user_feedback,
    RAG_QUERY_TOTAL,
    RAG_FALLBACK_TOTAL,
    USER_FEEDBACK_TOTAL
)

client = TestClient(app)


class TestPrometheusMetrics:
    """Validates Prometheus metric exposition and instrumentation."""

    def test_metrics_endpoint_returns_200_and_prometheus_format(self):
        """GET /metrics must return HTTP 200 with standard Prometheus text/plain exposition format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        text = response.text
        assert "rag_query_total" in text
        assert "rag_query_latency_seconds" in text
        assert "rag_fallback_total" in text
        assert "user_feedback_total" in text

    def test_metric_recording_helpers(self):
        """Helper functions must increment corresponding Prometheus counters."""
        initial_query = RAG_QUERY_TOTAL.labels(mode="oracle_db", status="SUCCESS")._value.get()
        record_rag_query(mode="oracle_db", status="SUCCESS", latency=0.25)
        new_query = RAG_QUERY_TOTAL.labels(mode="oracle_db", status="SUCCESS")._value.get()
        assert new_query == initial_query + 1

        initial_fallback = RAG_FALLBACK_TOTAL.labels(reason="BELOW_CONFIDENCE_THRESHOLD")._value.get()
        record_rag_fallback(reason="BELOW_CONFIDENCE_THRESHOLD")
        new_fallback = RAG_FALLBACK_TOTAL.labels(reason="BELOW_CONFIDENCE_THRESHOLD")._value.get()
        assert new_fallback == initial_fallback + 1

        initial_fb = USER_FEEDBACK_TOTAL.labels(rating="5")._value.get()
        record_user_feedback(rating=5)
        new_fb = USER_FEEDBACK_TOTAL.labels(rating="5")._value.get()
        assert new_fb == initial_fb + 1


class TestAnalyticsServiceAndEndpoint:
    """Validates Analytics Service calculations and GET /api/analytics/summary route."""

    @pytest.fixture
    def test_auth_headers(self):
        """Registers and logs in an admin user and returns Authorization headers."""
        import uuid
        email = f"admin_{uuid.uuid4().hex[:6]}@enterprise.corp"
        password = "AdminPassword2026!"
        client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "role": "admin"}
        )
        login_resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": password}
        )
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_get_analytics_summary_unauthorized_returns_401(self):
        """GET /api/analytics/summary without token must return HTTP 401."""
        response = client.get("/api/analytics/summary")
        assert response.status_code == 401

    def test_get_analytics_summary_authorized_success(self, test_auth_headers):
        """GET /api/analytics/summary with valid token returns comprehensive dashboard KPIs."""
        headers = test_auth_headers
        response = client.get("/api/analytics/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "kpis" in data
        kpis = data["kpis"]
        assert "total_queries" in kpis
        assert "total_sessions" in kpis
        assert "total_users" in kpis
        assert "total_feedbacks" in kpis
        assert "satisfaction_rate_percent" in kpis
        assert "avg_confidence_score_percent" in kpis
        assert "fallback_query_count" in kpis

        assert "category_distribution" in data
        assert "recent_audit_logs" in data
        assert "recent_feedbacks" in data
