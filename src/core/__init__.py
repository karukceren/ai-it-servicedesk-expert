"""
Core Security & Configuration Package
======================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

from .security import (
    validate_password_strength,
    validate_email_format,
    hash_password,
    verify_password,
    PasswordValidationError,
    EmailValidationError,
    SecurityValidationError,
)

from .jwt_handler import (
    create_access_token,
    decode_access_token,
    get_current_user,
    require_role,
    require_admin,
    JWTAuthError,
    TokenExpiredError,
    InvalidTokenError,
)

from .prompts import (
    PromptMode,
    BASE_GUARDRAILS,
    SERVICE_DESK_PROMPT,
    WINDOWS_SERVER_PROMPT,
    ORACLE_DB_PROMPT,
    GENERAL_SYSTEM_PROMPT,
    get_system_prompt_for_mode,
    build_prompt_messages,
)

__all__ = [
    # Password & Email Security
    "validate_password_strength",
    "validate_email_format",
    "hash_password",
    "verify_password",
    "PasswordValidationError",
    "EmailValidationError",
    "SecurityValidationError",
    # JWT & Auth Dependencies
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "require_role",
    "require_admin",
    "JWTAuthError",
    "TokenExpiredError",
    "InvalidTokenError",
    # Domain Prompts & Guardrails
    "PromptMode",
    "BASE_GUARDRAILS",
    "SERVICE_DESK_PROMPT",
    "WINDOWS_SERVER_PROMPT",
    "ORACLE_DB_PROMPT",
    "GENERAL_SYSTEM_PROMPT",
    "get_system_prompt_for_mode",
    "build_prompt_messages",
]
