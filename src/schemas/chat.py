"""
Chat Session, Message & Streaming Pydantic DTO Schemas
======================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class CreateSessionRequest(BaseModel):
    """Payload for initiating a new chat session."""
    title: Optional[str] = Field(
        "Yeni Sohbet",
        description="Başlık veya konu özeti",
        json_schema_extra={"example": "Active Directory Parola Sıfırlama"}
    )


class ChatStreamRequest(BaseModel):
    """Payload for real-time chat streaming."""
    query: str = Field(
        ...,
        min_length=1,
        description="Kullanıcı teknik sorusu veya problem açıklaması",
        json_schema_extra={"example": "Active Directory üzerinde kilitli hesapları nasıl açarım?"}
    )
    session_id: uuid.UUID = Field(
        ...,
        description="Mesajın ait olduğu sohbet oturumu UUID'si"
    )
    mode: str = Field(
        "general",
        description="Uzmanlık alanı modu: 'general', 'service_desk', 'windows_server', 'oracle_db'",
        json_schema_extra={"example": "windows_server"}
    )


class FeedbackCreateRequest(BaseModel):
    """Payload for submitting user evaluation on an assistant response."""
    message_id: uuid.UUID = Field(
        ...,
        description="Derecelendirilecek asistan mesajının UUID'si"
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="1 ile 5 arasında derecelendirme (1: Olumsuz/Thumb Down, 5: Mükemmel/Thumb Up)",
        json_schema_extra={"example": 5}
    )
    comment: Optional[str] = Field(
        None,
        description="Opsiyonel kullanıcı açıklaması veya geri bildirim notu",
        json_schema_extra={"example": "Komut tam olarak sorunu çözdü, teşekkürler."}
    )


class FeedbackResponse(BaseModel):
    """Feedback detail for a message."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    message_id: str
    rating: int
    comment: Optional[str] = None
    created_at: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Chat message response with RAG sources metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    sources_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    feedback: Optional[FeedbackResponse] = None


class ChatSessionResponse(BaseModel):
    """Chat session metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    created_at: Optional[str] = None
    message_count: Optional[int] = 0


class ChatSessionDetailResponse(BaseModel):
    """Full chat session details with message history."""
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]


class ChatHistoryResponse(BaseModel):
    """Chat history list with session header."""
    session_id: str
    title: str
    total_messages: int
    messages: List[ChatMessageResponse]


class ChatQueryRequest(BaseModel):
    """Synchronous / Direct RAG Query Request Payload."""
    query: str = Field(
        ...,
        min_length=1,
        description="Kullanıcı teknik sorusu",
        json_schema_extra={"example": "Oracle ORA-01555 hatası nasıl giderilir?"}
    )
    mode: str = Field(
        "general",
        description="Uzmanlık alanı modu: 'service_desk', 'windows_server', 'oracle_db', 'general'",
        json_schema_extra={"example": "oracle_db"}
    )
    session_id: Optional[uuid.UUID] = Field(
        None,
        description="Opsiyonel oturum UUID'si"
    )


class ChatQueryResponse(BaseModel):
    """Direct RAG Query Response Payload."""
    status: str
    answer: str
    confidence_score: float
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None

