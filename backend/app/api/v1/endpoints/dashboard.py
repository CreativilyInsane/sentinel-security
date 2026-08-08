# backend/app/api/v1/endpoints/dashboard.py
from fastapi import APIRouter, Depends, status
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import DashboardData
from app.schemas.common import StandardResponse
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=StandardResponse[DashboardData], status_code=status.HTTP_200_OK)
async def get_dashboard(
    dashboard_service: DashboardService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """Retrieve dashboard metrics and recent activity."""
    data = await dashboard_service.get_dashboard_data()
    return StandardResponse(success=True, message="Dashboard data retrieved successfully", data=data)