# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    username: str  # Can be username or email
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Access token expiration in seconds

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str