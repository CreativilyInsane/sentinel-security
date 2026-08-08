# backend/app/services/token_service.py
from datetime import datetime, timezone
from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.db.redis import redis_client
from app.core.constants import TokenType
from app.utils.errors import UnauthorizedError
from app.core.config import settings
import uuid

class TokenService:
    """Service for handling JWT operations and blacklisting."""
    
    async def create_tokens(self, subject: str, extra_claims: dict = None) -> dict:
        access_token, access_jti = create_access_token(subject, extra_claims)
        refresh_token, refresh_jti = create_refresh_token(subject)
        
        # Store refresh token jti in redis to track active sessions (optional but good practice)
        # For simplicity, we just handle blacklisting on logout
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    async def validate_token(self, token: str, expected_type: str) -> dict:
        """Validates token type, signature, and checks if it's blacklisted."""
        payload = decode_token(token)
        
        if payload.get("type") != expected_type:
            raise UnauthorizedError("Invalid token type")
            
        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedError("Missing token ID")
            
        # Check if token is blacklisted
        is_blacklisted = await redis_client.get(f"blacklist:{jti}")
        if is_blacklisted:
            raise UnauthorizedError("Token has been revoked")
            
        # Check expiration explicitly (python-jose handles this, but good to be safe)
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise UnauthorizedError("Token expired")
            
        return payload

    async def blacklist_token(self, token: str) -> None:
        """Adds a token's JTI to the Redis blacklist with its remaining TTL."""
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if not jti or not exp:
            return
            
        # Calculate remaining time to live
        now = datetime.now(timezone.utc)
        exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
        ttl = int((exp_datetime - now).total_seconds())
        
        if ttl > 0:
            await redis_client.setex(f"blacklist:{jti}", ttl, "true")