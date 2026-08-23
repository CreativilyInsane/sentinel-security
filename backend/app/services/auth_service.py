# backend/app/services/auth_service.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.auth.passwords import verify_password
from app.services.token_service import TokenService
from app.schemas.auth import LoginRequest, RefreshTokenRequest, LogoutRequest
from app.utils.errors import UnauthorizedError
from app.core.constants import TokenType

class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_repo = UserRepository(db)
        self.role_repo = RoleRepository(db)
        self.token_service = TokenService()

    async def login(self, login_data: LoginRequest) -> dict:
        # Check if input is email or username
        if "@" in login_data.username:
            user = await self.user_repo.get_by_email(login_data.username)
        else:
            user = await self.user_repo.get_by_username(login_data.username)
            
        if not user:
            raise UnauthorizedError("Incorrect username or password")
            
        if not verify_password(login_data.password, user.password_hash):
            raise UnauthorizedError("Incorrect username or password")
            
        if not user.is_active:
            raise UnauthorizedError("Account is inactive. Please contact an administrator.")
            
        # Role is now safely loaded via selectinload in the repository
        claims = {
            "user_id": user.id,
            "role": user.role.name,
            "username": user.username
        }
        
        tokens = await self.token_service.create_tokens(subject=str(user.id), extra_claims=claims)
        return tokens

    async def refresh_token(self, refresh_data: RefreshTokenRequest) -> dict:
        payload = await self.token_service.validate_token(refresh_data.refresh_token, TokenType.REFRESH)
        user_id = payload.get("sub")
        
        user = await self.user_repo.get_user_with_role(int(user_id))
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        claims = {
            "user_id": user.id,
            "role": user.role.name,
            "username": user.username
        }
        
        return await self.token_service.create_tokens(subject=str(user.id), extra_claims=claims)

    async def logout(self, logout_data: LogoutRequest) -> None:
        try:
            await self.token_service.blacklist_token(logout_data.refresh_token)
        except UnauthorizedError:
            pass