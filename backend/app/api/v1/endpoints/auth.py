# backend/app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, LogoutRequest
from app.schemas.user import UserRead
from app.schemas.common import StandardResponse
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/login", response_model=StandardResponse[TokenResponse], status_code=status.HTTP_200_OK)
async def login(
    login_data: LoginRequest,
    auth_service: AuthService = Depends()
):
    """Login endpoint to obtain access and refresh tokens."""
    tokens = await auth_service.login(login_data)
    return StandardResponse(success=True, message="Login successful", data=tokens)

@router.post("/refresh", response_model=StandardResponse[TokenResponse], status_code=status.HTTP_200_OK)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    auth_service: AuthService = Depends()
):
    """Refresh endpoint to get new tokens using a refresh token."""
    tokens = await auth_service.refresh_token(refresh_data)
    return StandardResponse(success=True, message="Token refreshed successfully", data=tokens)

@router.post("/logout", response_model=StandardResponse, status_code=status.HTTP_200_OK)
async def logout(
    logout_data: LogoutRequest,
    auth_service: AuthService = Depends()
):
    """Logout endpoint to blacklist the refresh token."""
    await auth_service.logout(logout_data)
    return StandardResponse(success=True, message="Logout successful")

@router.get("/me", response_model=StandardResponse[UserRead], status_code=status.HTTP_200_OK)
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return StandardResponse(success=True, message="User fetched successfully", data=current_user)