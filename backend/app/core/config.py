# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # JWT Settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:8080", "http://localhost:5173"]
    
    # Initial Admin Seed Data
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    ADMIN_EMAIL: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

# Singleton instance
settings = Settings()