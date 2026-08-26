"""
Chat Sessions, Streaming & Feedback API Routes
==============================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides REST & Server-Sent Events (SSE) endpoints for real-time RAG streaming,
    session lifecycle management, message history retrieval, and user feedback submission.
"""

import json
import uuid
import asyncio
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models import get_db, User
from src.core.jwt_handler import get_current_user
from src.schemas import (
    CreateSessionRequest,
    ChatStreamRequest,
    FeedbackCreateRequest,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatSessionDetailResponse,
    ChatHistoryResponse,
    FeedbackResponse,
    ChatQueryRequest,
    ChatQueryResponse
)
from src.services import ChatService, AuthService
from src.services.rag_service import rag_service, STANDARD_FALLBACK_MESSAGE
from src.api.metrics import record_rag_query, record_rag_fallback, record_user_feedback

router = APIRouter(tags=["Chat & Real-Time Streaming"])


# ===========================================================================
# 1. Real-Time RAG Streaming Endpoint (SSE)
# ===========================================================================
@router.post(
    "/stream",
    summary="Gerçek Zamanlı Sohbet Akışı (Server-Sent Events / SSE)",
    description=(
        "Kullanıcı sorusunu alır, RAG bağlamını sorgular, kullanıcı mesajını veritabanına kaydeder "
        "ve LLM tarafından üretilen yanıt parçacıklarını (tokens) 'text/event-stream' formatında istemciye akıtır. "
        "Akış bitiminde nihai yanıt ve kaynakçalar kaydedilir."
    )
)
async def chat_stream_endpoint(
    payload: ChatStreamRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    SSE Token streaming endpoint with multi-tenant session validation,
    anti-hallucination confidence gating, and Prometheus observability.
    """
    stream_start_time = time.time()
    # 1. Multi-Tenant Session Ownership Verification
    ChatService.get_session_by_id(db=db, session_id=payload.session_id, current_user=current_user)

    # 2. Record Audit Log for Query Execution
    client_ip = request.client.host if request and request.client else None
    AuthService.log_audit(
        db=db,
        action="QUERY_EXECUTED",
        user_id=current_user.id,
        ip_address=client_ip
    )

    # 3. Persist user question into database
    user_msg = ChatService.save_message(
        db=db,
        session_id=payload.session_id,
        role="user",
        content=payload.query
    )

    # 4. Retrieve conversation history (excluding the current query)
    history = ChatService.get_conversation_history(
        db=db,
        session_id=payload.session_id,
        limit=6,
        exclude_message_id=user_msg.id
    )

    async def event_generator():
        # Retrieve context & check confidence gating
        category_filter = rag_service._get_domain_category_for_mode(payload.mode)
        context_data = rag_service.retriever.retrieve_context(
            query=payload.query,
            category=category_filter,
            top_k=4
        )
        sources = context_data.get("sources_metadata", [])
        retrieval_status = context_data.get("status", "SUCCESS")
        top_confidence = sources[0].get("normalized_score", 0.0) if sources else 0.0

        is_fallback = (retrieval_status == "BELOW_THRESHOLD" or not sources or top_confidence < rag_service.confidence_threshold)

        full_content = ""

        if is_fallback:
            # Record zero-token fallback metrics
            record_rag_fallback(reason="BELOW_CONFIDENCE_THRESHOLD")
            fallback_text = STANDARD_FALLBACK_MESSAGE
            words = fallback_text.split(" ")
            for i, w in enumerate(words):
                chunk = w + (" " if i < len(words) - 1 else "")
                full_content += chunk
                event_data = json.dumps({"type": "token", "content": chunk}, ensure_ascii=False)
                yield f"data: {event_data}\n\n"
                await asyncio.sleep(0.01)

            # Persist assistant fallback response
            fallback_meta = {
                "status": "FALLBACK_TRIGGERED",
                "confidence_score": top_confidence,
                "sources": []
            }
            asst_msg = ChatService.save_message(
                db=db,
                session_id=payload.session_id,
                role="assistant",
                content=full_content,
                sources_metadata=fallback_meta
            )

            record_rag_query(mode=payload.mode, status="FALLBACK", latency=time.time() - stream_start_time)

            done_data = json.dumps({
                "type": "done",
                "status": "FALLBACK_TRIGGERED",
                "message_id": str(asst_msg.id),
                "sources_metadata": []
            }, ensure_ascii=False)
            yield f"data: {done_data}\n\n"
        else:
            # Stream LLM tokens in real-time
            async for token in rag_service.llm.generate_response_stream(
                query=payload.query,
                mode=payload.mode,
                conversation_history=history,
                top_k=4
            ):
                full_content += token
                event_data = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            # Persist assistant successful response with RAG citations
            success_meta = {
                "status": "SUCCESS",
                "confidence_score": top_confidence,
                "sources": sources
            }
            asst_msg = ChatService.save_message(
                db=db,
                session_id=payload.session_id,
                role="assistant",
                content=full_content,
                sources_metadata=success_meta
            )

            record_rag_query(mode=payload.mode, status="SUCCESS", latency=time.time() - stream_start_time)

            done_data = json.dumps({
                "type": "done",
                "status": "SUCCESS",
                "message_id": str(asst_msg.id),
                "sources_metadata": sources
            }, ensure_ascii=False)
            yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ===========================================================================
# 2. Synchronous Direct RAG Query Endpoint
# ===========================================================================
@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Senkron RAG Soru Yanıtlama (Direct RAG Query)",
    description="Kullanıcı teknik sorusunu alır, RAG bağlamını sorgular, güven eşiği kontrolü uygular ve tam yanıtı döner."
)
async def chat_query_endpoint(
    payload: ChatQueryRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ChatQueryResponse:
    """
    Direct synchronous RAG query endpoint for API integrations and benchmark load testing.
    """
    start_time = time.time()
    client_ip = request.client.host if request and request.client else None
    AuthService.log_audit(
        db=db,
        action="QUERY_EXECUTED",
        user_id=current_user.id,
        ip_address=client_ip
    )

    rag_result = await rag_service.execute_rag(
        query=payload.query,
        mode=payload.mode,
        top_k=4
    )
    status_str = rag_result.get("status", "SUCCESS")
    is_fallback = rag_result.get("fallback", False)

    if is_fallback:
        record_rag_fallback(reason="BELOW_CONFIDENCE_THRESHOLD")
        record_rag_query(mode=payload.mode, status="FALLBACK", latency=time.time() - start_time)
    else:
        record_rag_query(mode=payload.mode, status="SUCCESS", latency=time.time() - start_time)

    return ChatQueryResponse(
        status=status_str,
        answer=rag_result.get("response", ""),
        confidence_score=rag_result.get("confidence_score", 0.0),
        sources=rag_result.get("sources_metadata", []),
        session_id=str(payload.session_id) if payload.session_id else None
    )


# ===========================================================================
# 3. User Feedback Submission Endpoint
# ===========================================================================
@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mesaj Geri Bildirimi Kaydet (Submit Feedback)",
    description="Asistan yanıtına kullanıcı tarafından verilen 1-5 puanlık değerlendirme veya başparmak yukarı/aşağı geri bildirimini kaydeder."
)
def submit_feedback(
    payload: FeedbackCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FeedbackResponse:
    """
    Submits or updates qualitative user rating and feedback for a message.
    """
    # 1. Record Audit Log
    client_ip = request.client.host if request and request.client else None
    AuthService.log_audit(
        db=db,
        action="FEEDBACK_SUBMITTED",
        user_id=current_user.id,
        ip_address=client_ip
    )

    feedback = ChatService.save_feedback(
        db=db,
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment,
        current_user=current_user
    )

    # 2. Record Prometheus User Feedback Metric
    record_user_feedback(rating=payload.rating)

    return FeedbackResponse(
        id=str(feedback.id),
        message_id=str(feedback.message_id),
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at.isoformat() if feedback.created_at else None
    )


# ===========================================================================
# 3. Session History & Messages Endpoints
# ===========================================================================
@router.get(
    "/sessions/{session_id}/history",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Oturum Sohbet Geçmişini Listele (Get Session History)",
    description="Belirtilen oturumun tüm mesajlarını, RAG kaynaklarını ve kullanıcı geri bildirimlerini kronolojik sırayla listeler."
)
def get_session_history(
    session_id: uuid.UUID = Path(..., description="Sohbet oturumu UUID'si"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ChatHistoryResponse:
    """
    Retrieves chronological message history with citations and feedback.
    """
    chat_session, messages = ChatService.get_session_messages(
        db=db,
        session_id=session_id,
        current_user=current_user
    )

    formatted_messages = []
    for msg in messages:
        fb_dto = None
        if msg.feedback:
            fb_dto = FeedbackResponse(
                id=str(msg.feedback.id),
                message_id=str(msg.feedback.message_id),
                rating=msg.feedback.rating,
                comment=msg.feedback.comment,
                created_at=msg.feedback.created_at.isoformat() if msg.feedback.created_at else None
            )

        formatted_messages.append(
            ChatMessageResponse(
                id=str(msg.id),
                session_id=str(msg.session_id),
                role=msg.role,
                content=msg.content,
                sources_metadata=msg.sources_metadata or {},
                created_at=msg.created_at.isoformat() if msg.created_at else None,
                feedback=fb_dto
            )
        )

    return ChatHistoryResponse(
        session_id=str(chat_session.id),
        title=chat_session.title,
        total_messages=len(formatted_messages),
        messages=formatted_messages
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Oturum Detayı ve Mesajları (Backwards Compatibility)",
    description="Belirtilen oturumun detaylarını ve mesajlarını getirir."
)
def get_session_messages(
    session_id: uuid.UUID = Path(..., description="Sohbet oturumu UUID'si"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ChatSessionDetailResponse:
    """
    Retrieves messages for a session with strict multi-tenant ownership check.
    """
    chat_session, messages = ChatService.get_session_messages(
        db=db,
        session_id=session_id,
        current_user=current_user
    )

    formatted_messages = []
    for msg in messages:
        fb_dto = None
        if msg.feedback:
            fb_dto = FeedbackResponse(
                id=str(msg.feedback.id),
                message_id=str(msg.feedback.message_id),
                rating=msg.feedback.rating,
                comment=msg.feedback.comment,
                created_at=msg.feedback.created_at.isoformat() if msg.feedback.created_at else None
            )

        formatted_messages.append(
            ChatMessageResponse(
                id=str(msg.id),
                session_id=str(msg.session_id),
                role=msg.role,
                content=msg.content,
                sources_metadata=msg.sources_metadata or {},
                created_at=msg.created_at.isoformat() if msg.created_at else None,
                feedback=fb_dto
            )
        )

    return ChatSessionDetailResponse(
        session=ChatSessionResponse(
            id=str(chat_session.id),
            user_id=str(chat_session.user_id),
            title=chat_session.title,
            created_at=chat_session.created_at.isoformat() if chat_session.created_at else None,
            message_count=len(formatted_messages)
        ),
        messages=formatted_messages
    )


# ===========================================================================
# 4. Session CRUD Endpoints
# ===========================================================================
@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni Sohbet Oturumu Oluştur (Create Session)",
    description="Giriş yapmış kullanıcı adına yeni ve izole bir sohbet oturumu başlatır."
)
def create_session(
    payload: CreateSessionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ChatSessionResponse:
    """Creates a new isolated chat session."""
    client_ip = request.client.host if request and request.client else None
    AuthService.log_audit(
        db=db,
        action="SESSION_CREATED",
        user_id=current_user.id,
        ip_address=client_ip
    )

    session = ChatService.create_session(
        db=db,
        user_id=current_user.id,
        title=payload.title
    )
    return ChatSessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else None,
        message_count=0
    )


@router.get(
    "/sessions",
    response_model=List[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Kullanıcının Sohbet Oturumlarını Listele (List Sessions)",
    description="Yalnızca aktif kullanıcının kendi sohbet oturumlarını listeler. Admin kullanıcılar all=true ile tüm sistem oturumlarını listeleyebilir."
)
def list_sessions(
    all_sessions: bool = Query(
        False,
        alias="all",
        description="Tüm kullanıcıların oturumlarını listele (Yalnızca Admin için)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[ChatSessionResponse]:
    """Lists chat sessions belonging to current user (or all if admin)."""
    is_admin = current_user.is_admin
    fetch_all = all_sessions and is_admin

    session_data = ChatService.get_user_sessions(
        db=db,
        user_id=current_user.id,
        is_admin=is_admin,
        fetch_all=fetch_all
    )

    return [
        ChatSessionResponse(
            id=str(sess.id),
            user_id=str(sess.user_id),
            title=sess.title,
            created_at=sess.created_at.isoformat() if sess.created_at else None,
            message_count=msg_count
        )
        for sess, msg_count in session_data
    ]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Sohbet Oturumunu Sil (Delete Session)",
    description="Belirtilen oturumu ve bağlı tüm mesajları siler."
)
def delete_session(
    session_id: uuid.UUID = Path(..., description="Silinecek oturum UUID'si"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes a chat session and cascades."""
    client_ip = request.client.host if request and request.client else None
    AuthService.log_audit(
        db=db,
        action="SESSION_DELETED",
        user_id=current_user.id,
        ip_address=client_ip
    )

    ChatService.delete_session(
        db=db,
        session_id=session_id,
        current_user=current_user
    )
    return {
        "status": "success",
        "message": "Sohbet oturumu ve tüm mesaj geçmişi başarıyla silindi."
    }
