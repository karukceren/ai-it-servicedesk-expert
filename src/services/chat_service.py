"""
Chat Session & Message Service Layer (Multi-Tenant Isolation & RBAC)
====================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Implements business logic for managing chat sessions, saving messages,
    fetching conversation histories, handling user feedback, and enforcing
    strict multi-tenant session isolation and Admin overrides.
"""

import uuid
import logging
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models import ChatSession, ChatMessage, Feedback, User

logger = logging.getLogger("ChatService")


class ChatService:
    """
    Service layer providing isolated chat session management, message retrieval,
    conversation history compilation, and feedback tracking.
    """

    @staticmethod
    def create_session(
        db: Session,
        user_id: uuid.UUID,
        title: Optional[str] = "Yeni Sohbet"
    ) -> ChatSession:
        """
        Creates a new isolated chat session for the specified user.

        Args:
            db (Session): Database session.
            user_id (UUID): Authenticated user's unique identifier.
            title (str, optional): Session title (default: 'Yeni Sohbet').

        Returns:
            ChatSession: Created session ORM model.
        """
        clean_title = title.strip() if title and title.strip() else "Yeni Sohbet"
        new_session = ChatSession(
            user_id=user_id,
            title=clean_title
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        logger.info(f"Chat session created: id='{new_session.id}', user_id='{user_id}', title='{clean_title}'")
        return new_session

    @staticmethod
    def get_user_sessions(
        db: Session,
        user_id: uuid.UUID,
        is_admin: bool = False,
        fetch_all: bool = False
    ) -> List[Tuple[ChatSession, int]]:
        """
        Retrieves chat sessions with their message counts.
        - Standard users receive only their own sessions.
        - Admins can query all system sessions by passing fetch_all=True.

        Args:
            db (Session): Database session.
            user_id (UUID): User ID to filter by.
            is_admin (bool): True if caller has administrator privileges.
            fetch_all (bool): If True and caller is admin, retrieves all sessions.

        Returns:
            List[Tuple[ChatSession, int]]: List of (ChatSession, message_count) tuples.
        """
        query = (
            db.query(
                ChatSession,
                func.count(ChatMessage.id).label("message_count")
            )
            .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.created_at.desc())
        )

        if not (is_admin and fetch_all):
            query = query.filter(ChatSession.user_id == user_id)

        results = query.all()
        return [(session, count) for session, count in results]

    @staticmethod
    def verify_session_ownership(
        session: ChatSession,
        current_user: User
    ) -> None:
        """
        Enforces user session isolation.
        Raises HTTP 403 Forbidden if the session does not belong to the user
        and the user is not an administrator.

        Args:
            session (ChatSession): Chat session to check.
            current_user (User): Authenticated user requesting access.

        Raises:
            HTTPException (403): Unauthorized session access attempt.
        """
        if session.user_id != current_user.id and not current_user.is_admin:
            logger.warning(
                f"Unauthorized access blocked: user_id='{current_user.id}' attempted to access "
                f"session_id='{session.id}' owned by user_id='{session.user_id}'."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu sohbet oturumuna erişim yetkiniz bulunmamaktadır."
            )

    @classmethod
    def get_session_by_id(
        cls,
        db: Session,
        session_id: uuid.UUID,
        current_user: User
    ) -> ChatSession:
        """
        Retrieves a session by ID and ensures current user is the owner or admin.

        Args:
            db (Session): Database session.
            session_id (UUID): Session UUID.
            current_user (User): Requesting user.

        Returns:
            ChatSession: Verified session object.

        Raises:
            HTTPException (404): Session not found.
            HTTPException (403): Unauthorized access.
        """
        chat_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not chat_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Belirtilen sohbet oturumu bulunamadı."
            )

        cls.verify_session_ownership(chat_session, current_user)
        return chat_session

    @classmethod
    def get_session_messages(
        cls,
        db: Session,
        session_id: uuid.UUID,
        current_user: User
    ) -> Tuple[ChatSession, List[ChatMessage]]:
        """
        Retrieves all messages for a specific session after verifying ownership.

        Args:
            db (Session): Database session.
            session_id (UUID): Target session identifier.
            current_user (User): Authenticated user making request.

        Returns:
            Tuple[ChatSession, List[ChatMessage]]: Session object and list of messages.

        Raises:
            HTTPException (404): Session not found.
            HTTPException (403): User does not own session.
        """
        chat_session = cls.get_session_by_id(db, session_id, current_user)

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return chat_session, messages

    @staticmethod
    def save_message(
        db: Session,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources_metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Persists a user or assistant message in the database.

        Args:
            db (Session): Database session.
            session_id (UUID): Session UUID.
            role (str): 'user' or 'assistant'.
            content (str): Text content.
            sources_metadata (dict, optional): Attached RAG citation metadata.

        Returns:
            ChatMessage: Saved message record.
        """
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources_metadata=sources_metadata or {}
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        logger.info(f"Message saved: id='{msg.id}', session_id='{session_id}', role='{role}'")
        return msg

    @staticmethod
    def get_conversation_history(
        db: Session,
        session_id: uuid.UUID,
        limit: int = 6,
        exclude_message_id: Optional[uuid.UUID] = None
    ) -> List[Dict[str, str]]:
        """
        Retrieves the recent conversation history formatted for LLM context.

        Args:
            db (Session): Database session.
            session_id (UUID): Session UUID.
            limit (int): Maximum message history count.
            exclude_message_id (UUID, optional): Exclude specific message (e.g. current query).

        Returns:
            List[Dict[str, str]]: Messages list formatted as [{'role': 'user', 'content': '...'}, ...]
        """
        query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
        if exclude_message_id:
            query = query.filter(ChatMessage.id != exclude_message_id)

        messages = (
            query.order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )

        # Reverse to chronological order (oldest -> newest)
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

    @classmethod
    def save_feedback(
        cls,
        db: Session,
        message_id: uuid.UUID,
        rating: int,
        comment: Optional[str],
        current_user: User
    ) -> Feedback:
        """
        Saves or updates user feedback for a given assistant message after verifying ownership.

        Args:
            db (Session): Database session.
            message_id (UUID): Message UUID to evaluate.
            rating (int): Score 1 to 5.
            comment (str, optional): User comments.
            current_user (User): Authenticated user submitting feedback.

        Returns:
            Feedback: Created or updated feedback record.

        Raises:
            HTTPException (404): Message not found.
            HTTPException (403): User does not own the message's session.
        """
        msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Belirtilen mesaj bulunamadı."
            )

        # Check session ownership
        chat_session = db.query(ChatSession).filter(ChatSession.id == msg.session_id).first()
        if not chat_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mesajın bağlı olduğu oturum bulunamadı."
            )

        cls.verify_session_ownership(chat_session, current_user)

        # Check if feedback already exists for this message
        existing_fb = db.query(Feedback).filter(Feedback.message_id == message_id).first()
        if existing_fb:
            existing_fb.rating = rating
            existing_fb.comment = comment.strip() if comment else None
            db.commit()
            db.refresh(existing_fb)
            logger.info(f"Feedback updated: id='{existing_fb.id}', message_id='{message_id}', rating={rating}")
            return existing_fb

        new_fb = Feedback(
            message_id=message_id,
            rating=rating,
            comment=comment.strip() if comment else None
        )
        db.add(new_fb)
        db.commit()
        db.refresh(new_fb)
        logger.info(f"Feedback created: id='{new_fb.id}', message_id='{message_id}', rating={rating}")
        return new_fb

    @classmethod
    def delete_session(
        cls,
        db: Session,
        session_id: uuid.UUID,
        current_user: User
    ) -> bool:
        """
        Deletes a session and cascading messages after verifying ownership.

        Args:
            db (Session): Database session.
            session_id (UUID): Session to delete.
            current_user (User): Authenticated user making request.

        Returns:
            bool: True if deleted.
        """
        chat_session = cls.get_session_by_id(db, session_id, current_user)

        db.delete(chat_session)
        db.commit()
        logger.info(f"Chat session deleted: id='{session_id}' by user='{current_user.id}'")
        return True
