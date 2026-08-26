"""
AuditLog ORM Model (Security Trail & Activity Monitoring)
=========================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class AuditLog(Base):
    """
    Immutable security audit trail for user authentication and system actions.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True  # 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'QUERY_EXECUTED', etc.
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs"
    )

    def to_dict(self) -> dict:
        """Serializes audit log to dict."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}', ip='{self.ip_address}')>"
