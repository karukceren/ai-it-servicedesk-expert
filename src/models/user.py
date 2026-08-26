"""
User ORM Model (Authentication & RBAC)
=======================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .chat_session import ChatSession
    from .audit_log import AuditLog


class User(Base):
    """
    Represents an authenticated system user with role-based access control (RBAC).
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ChatSession.created_at.desc()"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user"
    )

    @property
    def is_admin(self) -> bool:
        """Returns True if the user has administrator privileges."""
        return self.role == "admin"

    def to_dict(self) -> dict:
        """Serializes user metadata to dict (excluding sensitive password hash)."""
        return {
            "id": str(self.id),
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
