"""
Prometheus Metrics and Observability Instrumentation
=====================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Prometheus counter, histogram, and gauge metrics for RAG retrieval latency,
    query volumes, zero-token fallbacks, and user feedback ratings.
"""

import time
from typing import Optional
from fastapi import Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY
)

# -----------------------------------------------------------------------------
# Prometheus Metric Definitions
# -----------------------------------------------------------------------------
RAG_QUERY_TOTAL = Counter(
    "rag_query_total",
    "Total number of RAG queries executed by mode and status",
    ["mode", "status"]
)

RAG_QUERY_LATENCY_SECONDS = Histogram(
    "rag_query_latency_seconds",
    "End-to-end RAG query processing and streaming latency in seconds",
    ["mode"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

RAG_FALLBACK_TOTAL = Counter(
    "rag_fallback_total",
    "Total number of safe zero-token fallbacks triggered",
    ["reason"]
)

USER_FEEDBACK_TOTAL = Counter(
    "user_feedback_total",
    "Total user satisfaction feedback ratings received",
    ["rating"]
)

ACTIVE_SESSIONS_GAUGE = Gauge(
    "active_chat_sessions_total",
    "Current total count of active user chat sessions"
)


# -----------------------------------------------------------------------------
# Metric Recording Helper Functions
# -----------------------------------------------------------------------------
def record_rag_query(mode: str, status: str, latency: float) -> None:
    """Records a completed RAG query counter and latency observation."""
    RAG_QUERY_TOTAL.labels(mode=mode or "general", status=status or "SUCCESS").inc()
    RAG_QUERY_LATENCY_SECONDS.labels(mode=mode or "general").observe(latency)


def record_rag_fallback(reason: str = "BELOW_CONFIDENCE_THRESHOLD") -> None:
    """Increments the zero-token fallback counter."""
    RAG_FALLBACK_TOTAL.labels(reason=reason).inc()


def record_user_feedback(rating: int) -> None:
    """Records a user feedback rating event (1 to 5)."""
    rating_str = str(rating)
    USER_FEEDBACK_TOTAL.labels(rating=rating_str).inc()


def get_prometheus_metrics_response() -> Response:
    """Generates the latest Prometheus metrics in standard exposition format."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )
