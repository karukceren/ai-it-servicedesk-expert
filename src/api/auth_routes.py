"""
Authentication & Authorization API Routes
=========================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides REST endpoints for user registration, user login, JWT issuance,
    and profile retrieval.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from src.models import get_db, User
from src.core.jwt_handler import get_current_user, DEFAULT_EXPIRE_MINUTES
from src.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    LoginResponse
)
from src.services import AuthService

router = APIRouter(tags=["Authentication & Security"])


def get_client_ip(request: Request) -> str:
    """Extracts client IP address considering proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni Kullanıcı Kaydı (Register)",
    description="Kullanıcı e-posta ve parola karmaşıklığını denetler, salted hash ile kaydeder ve denetim logu üretir."
)
def register(
    payload: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Registers a new user account with validated credentials.
    """
    ip_address = get_client_ip(request)
    new_user = AuthService.register_user(
        db=db,
        email=payload.email,
        password=payload.password,
        role=payload.role or "user",
        ip_address=ip_address
    )
    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        role=new_user.role,
        created_at=new_user.created_at.isoformat() if new_user.created_at else None
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Kullanıcı Girişi (Login & JWT Issuance)",
    description="Kullanıcı kimliğini doğrular, JWT Access Token üretir ve denetim loguna (audit_logs) başarılı/başarısız durumunu işler."
)
def login(
    payload: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """
    Authenticates user credentials and returns a secure JWT access token.
    """
    ip_address = get_client_ip(request)
    user, access_token = AuthService.authenticate_user(
        db=db,
        email=payload.email,
        password=payload.password,
        ip_address=ip_address
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            created_at=user.created_at.isoformat() if user.created_at else None
        ),
        expires_in_seconds=DEFAULT_EXPIRE_MINUTES * 60
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Mevcut Kullanıcı Profili (Protected Profile)",
    description="JWT Bearer token ile korunan, aktif giriş yapmış kullanıcının profil bilgilerini döndürür."
)
def get_me(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Returns the authenticated user's profile.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None
    )
