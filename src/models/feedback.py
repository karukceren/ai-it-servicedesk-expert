"""
Feedback ORM Model (Ratings & Qualitative Feedback)
===================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .chat_message import ChatMessage


class Feedback(Base):
    """
    Represents user evaluation and feedback on assistant responses.
    """
    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False  # 1-5 stars or 0/1 thumbs
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    message: Mapped["ChatMessage"] = relationship(
        "ChatMessage",
        back_populates="feedback"
    )

    def to_dict(self) -> dict:
        """Serializes feedback to dict."""
        return {
            "id": str(self.id),
            "message_id": str(self.message_id),
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, message_id={self.message_id}, rating={self.rating})>"
