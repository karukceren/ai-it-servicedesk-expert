"""
ChatMessage ORM Model (Multi-Turn Dialogue & RAG Sources Metadata)
==================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .chat_session import ChatSession
    from .feedback import Feedback


class ChatMessage(Base):
    """
    Represents an individual message exchanged in a conversation session,
    enriched with RAG retrieval references and sources metadata.
    """
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False  # 'user' | 'assistant' | 'system'
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    sources_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages"
    )
    feedback: Mapped[Optional["Feedback"]] = relationship(
        "Feedback",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Serializes chat message to dict."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "sources_metadata": self.sources_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "feedback": self.feedback.to_dict() if self.feedback else None
        }

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, role='{self.role}')>"
