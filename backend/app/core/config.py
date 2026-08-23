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

    # ===== Recon Module Settings =====
    RECON_MAX_HOSTS: int = 256
    RECON_MAX_PORTS: int = 100
    RECON_TIMEOUT: int = 10
    RECON_MAX_CONCURRENT_CONNECTIONS: int = 50
    RECON_MAX_ACTIVE_SCANS: int = 2
    RECON_HTTP_MAX_RESPONSE_SIZE: int = 5 * 1024 * 1024  # 5 MB
    RECON_MAX_REDIRECTS: int = 5
    RECON_SCREENSHOT_TIMEOUT: int = 30
    RECON_SCREENSHOT_STORAGE_PATH: str = "/app/recon_storage/screenshots"

    # ===== Celery =====
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

# Singleton instance
settings = Settings()
