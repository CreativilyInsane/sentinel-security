# backend/app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, dashboard

api_router = APIRouter()

# Include Auth endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Include User Management endpoints
api_router.include_router(users.router, prefix="/users", tags=["User Management"])

# Include Dashboard endpoints
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])