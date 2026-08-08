# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.middleware.error_handler import register_exception_handlers
from app.api.v1.router import api_router

def create_app() -> FastAPI:
    """Application factory pattern."""
    app = FastAPI(
        title="Security Management System",
        description="API for managing security scans, assets, and reports.",
        version="1.0.0"
    )

    # Set up CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register global exception handlers
    register_exception_handlers(app)

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "healthy", "message": "System is operational"}

    logger.info("Security Management System application initialized.")
    return app

app = create_app()