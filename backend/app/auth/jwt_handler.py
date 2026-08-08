# backend/app/auth/jwt_handler.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from app.core.config import settings
from app.core.constants import TokenType
from app.utils.errors import UnauthorizedError
import uuid

def create_access_token(subject: str, extra_claims: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    """Creates an access token and returns (token, jti)."""
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": TokenType.ACCESS,
        "jti": jti
    }
    if extra_claims:
        to_encode.update(extra_claims)
        
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, jti

def create_refresh_token(subject: str) -> tuple[str, str]:
    """Creates a refresh token and returns (token, jti)."""
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expires_delta
    
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": TokenType.REFRESH,
        "jti": jti
    }
        
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, jti

def decode_token(token: str) -> Dict[str, Any]:
    """Decodes a JWT token and raises UnauthorizedError if invalid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {str(e)}")