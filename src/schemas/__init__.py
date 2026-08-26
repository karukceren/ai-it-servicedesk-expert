"""
Schemas Package
===============
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

from .auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    LoginResponse,
    MessageResponse
)

from .chat import (
    CreateSessionRequest,
    ChatStreamRequest,
    FeedbackCreateRequest,
    FeedbackResponse,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatHistoryResponse,
    ChatQueryRequest,
    ChatQueryResponse
)

__all__ = [
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserResponse",
    "LoginResponse",
    "MessageResponse",
    "CreateSessionRequest",
    "ChatStreamRequest",
    "FeedbackCreateRequest",
    "FeedbackResponse",
    "ChatMessageResponse",
    "ChatSessionResponse",
    "ChatSessionDetailResponse",
    "ChatHistoryResponse",
    "ChatQueryRequest",
    "ChatQueryResponse"
]
