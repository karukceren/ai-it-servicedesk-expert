"""
ChatSession ORM Model (Session Management & Multi-Turn History)
===============================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .chat_message import ChatMessage


class ChatSession(Base):
    """
    Represents an isolated multi-turn chat session belonging to a specific user.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Yeni Sohbet"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions"
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()"
    )

    def to_dict(self, include_messages: bool = False) -> dict:
        """Serializes chat session to dict."""
        data = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_messages:
            data["messages"] = [msg.to_dict() for msg in self.messages]
        return data

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, title='{self.title}')>"
