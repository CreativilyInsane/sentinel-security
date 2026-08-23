# backend/app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.session import get_db
from app.services.token_service import TokenService
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.core.constants import TokenType, Roles
from app.utils.errors import ForbiddenError

# We use a custom OAuth2 scheme that looks for Bearer token.
# ``auto_error=False`` is used for the optional variant so that report
# endpoints can accept either a JWT (Authorization header) OR a signed
# report token (query param).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False,
)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    token_service = TokenService()
    
    # Validate access token
    payload = await token_service.validate_token(token, TokenType.ACCESS)
    user_id = payload.get("user_id")
    
    if not user_id:
        raise ForbiddenError("Invalid token payload")
        
    user_repo = UserRepository(db)
    
    # FIX: Use get_user_with_role to eagerly load the role and prevent async crashes
    user = await user_repo.get_user_with_role(user_id)
    
    if not user:
        raise ForbiddenError("User not found")
        
    if not user.is_active:
        raise ForbiddenError("User account is inactive")
        
    return user


async def get_current_user_or_none(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as ``get_current_user`` but returns ``None`` if no JWT is
    provided instead of raising 401.  Used by report endpoints that
    accept either a JWT or a signed report token.
    """
    if not token:
        return None
    try:
        token_service = TokenService()
        payload = await token_service.validate_token(token, TokenType.ACCESS)
        user_id = payload.get("user_id")
        if not user_id:
            return None
        user_repo = UserRepository(db)
        user = await user_repo.get_user_with_role(user_id)
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role.name != Roles.ADMIN:
        raise ForbiddenError("Administrator privileges required")
    return current_user