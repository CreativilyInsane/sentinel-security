# backend/app/middleware/error_handler.py
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from app.utils.errors import AppException
from app.core.logging import logger

def register_exception_handlers(app: FastAPI) -> None:
    """Registers global exception handlers for the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"AppException: {exc.message} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled Exception: {str(exc)} - Path: {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "An unexpected internal server error occurred.",
                "details": {}
            }
        )