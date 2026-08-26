"""
Analytics & System Observability API Endpoints
===============================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    FastAPI routes for providing dashboard metrics, KPI summaries,
    satisfaction statistics, and audit activity feeds to the Admin Panel.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.models import get_db, User
from src.core.jwt_handler import get_current_user
from src.services.analytics_service import analytics_service

logger = logging.getLogger("AnalyticsRoutes")

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Observability"])


@router.get("/summary", status_code=status.HTTP_200_OK)
def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns executive KPI metrics, category distributions, satisfaction rates,
    and recent security audit logs for the Admin Analytics Dashboard.
    """
    logger.info(f"Analytics summary requested by user={current_user.email} (role={current_user.role})")
    data = analytics_service.get_system_analytics_summary(db=db)
    return data
