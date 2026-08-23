# backend/app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, dashboard, recon, network_permissions,
    clients, targets,
)

api_router = APIRouter()

# Include Auth endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Include User Management endpoints
api_router.include_router(users.router, prefix="/users", tags=["User Management"])

# Include Network Permission endpoints (admin only)
api_router.include_router(network_permissions.router, prefix="/users", tags=["Network Permissions"])

# Include Dashboard endpoints
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

# Include Recon endpoints
api_router.include_router(recon.router, prefix="/recon", tags=["Reconnaissance"])

# Phase 17 — Clients + ClientAssets (admin only)
api_router.include_router(clients.router, prefix="", tags=["Clients"])

# Phase 17 — Target assignments + user-side my-targets / notifications
api_router.include_router(targets.router, prefix="", tags=["Targets"])
