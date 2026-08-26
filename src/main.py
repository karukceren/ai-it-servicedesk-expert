"""
FastAPI Application Entry Point
================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Initializes the FastAPI application, CORS middleware, API routers (Auth & Chat),
    health checks, and database connections using modern lifespan handlers.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth_routes import router as auth_router
from src.api.chat_routes import router as chat_router
from src.api.analytics_routes import router as analytics_router
from src.api.metrics import get_prometheus_metrics_response
from src.models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database schema on startup and cleans up on shutdown."""
    init_db()
    yield


# Initialize application
app = FastAPI(
    title="Akıllı Servis Masası ve Sistem Uzmanı Chatbot API",
    description="IT Destek, Windows Server ve Oracle DB uzmanı RAG tabanlı yapay zeka asistanı backend API'si.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers (Supporting both /api and /api/v1 prefixes)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(chat_router, prefix="/api/chat")
app.include_router(chat_router, prefix="/api/v1/chat")
app.include_router(analytics_router)


@app.get("/health", tags=["Health & System"])
@app.get("/api/health", tags=["Health & System"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Akıllı Servis Masası ve Sistem Uzmanı Chatbot API",
        "version": "1.0.0"
    }


@app.get("/metrics", tags=["Observability & Metrics"])
def prometheus_metrics():
    """Prometheus exposition metrics endpoint."""
    return get_prometheus_metrics_response()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
