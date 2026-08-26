"""
Authentication & User Management Service Layer
==============================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Implements business logic for user registration, authentication,
    password validation, JWT generation, and audit trail logging.
"""

import uuid
import logging
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models import User, AuditLog
from src.core.security import (
    validate_email_format,
    validate_password_strength,
    hash_password,
    verify_password,
    PasswordValidationError,
    EmailValidationError,
)
from src.core.jwt_handler import create_access_token

logger = logging.getLogger("AuthService")


class AuthService:
    """
    Handles authentication business operations adhering to SOLID Single Responsibility.
    """

    @staticmethod
    def log_audit(
        db: Session,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Creates an immutable audit log entry in the audit_logs table.

        Args:
            db (Session): Active database session.
            action (str): Action code ('USER_REGISTERED', 'LOGIN_SUCCESS', 'LOGIN_FAILED', etc.).
            user_id (UUID, optional): Associated user ID if available.
            ip_address (str, optional): Client IP address.

        Returns:
            AuditLog: Created audit log record.
        """
        try:
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                ip_address=ip_address
            )
            db.add(audit_entry)
            db.commit()
            db.refresh(audit_entry)
            logger.info(f"Audit log recorded: action='{action}', user_id='{user_id}', ip='{ip_address}'")
            return audit_entry
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to record audit log for action '{action}': {e}")
            raise

    @classmethod
    def register_user(
        cls,
        db: Session,
        email: str,
        password: str,
        role: str = "user",
        ip_address: Optional[str] = None
    ) -> User:
        """
        Registers a new user after strict email format and password strength validation.

        Args:
            db (Session): Database session.
            email (str): User email.
            password (str): Plaintext candidate password.
            role (str): Desired role ('user' | 'admin').
            ip_address (str, optional): Client IP.

        Returns:
            User: Created User ORM instance.

        Raises:
            HTTPException (400): If email is invalid, password is weak, or user exists.
        """
        # 1. Validate Email Format
        try:
            validate_email_format(email)
        except EmailValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            ) from e

        # 2. Validate Password Complexity
        try:
            validate_password_strength(password)
        except PasswordValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            ) from e

        email_clean = email.strip().lower()
        role_clean = role.strip().lower() if role else "user"
        if role_clean not in ("user", "admin"):
            role_clean = "user"

        # 3. Check for Duplicate Email
        existing_user = db.query(User).filter(User.email == email_clean).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi ile kayıtlı bir kullanıcı zaten mevcut."
            )

        # 4. Salted Hash Password
        password_hash = hash_password(password, validate=False)

        # 5. Create User Record
        new_user = User(
            email=email_clean,
            password_hash=password_hash,
            role=role_clean
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # 6. Audit Trail Logging
        cls.log_audit(
            db=db,
            action="USER_REGISTERED",
            user_id=new_user.id,
            ip_address=ip_address
        )

        logger.info(f"User successfully registered: email='{new_user.email}', id='{new_user.id}'")
        return new_user

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        email: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Tuple[User, str]:
        """
        Authenticates a user by email and password, returning the user and a JWT access token.

        Args:
            db (Session): Database session.
            email (str): User email.
            password (str): Plaintext candidate password.
            ip_address (str, optional): Client IP address.

        Returns:
            Tuple[User, str]: Authenticated User model and generated JWT access token string.

        Raises:
            HTTPException (401): If authentication fails (wrong email or password).
        """
        if not email or not password:
            cls.log_audit(db=db, action="LOGIN_FAILED", user_id=None, ip_address=ip_address)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-posta ve parola boş bırakılamaz.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        email_clean = email.strip().lower()
        user = db.query(User).filter(User.email == email_clean).first()

        # Check user existence and password validity
        if not user or not verify_password(password, user.password_hash):
            user_id_ref = user.id if user else None
            cls.log_audit(db=db, action="LOGIN_FAILED", user_id=user_id_ref, ip_address=ip_address)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz e-posta veya parola.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Record Successful Login
        cls.log_audit(db=db, action="LOGIN_SUCCESS", user_id=user.id, ip_address=ip_address)

        # Generate JWT Access Token
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role
        )

        logger.info(f"User successfully logged in: email='{user.email}', id='{user.id}'")
        return user, access_token
