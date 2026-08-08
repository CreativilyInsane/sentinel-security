# backend/app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, status, Query
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate, UserRead
from app.schemas.common import StandardResponse, PaginatedResponse
from app.api.deps import require_admin
from app.models.user import User
from typing import List

router = APIRouter()

@router.get("/", response_model=StandardResponse[List[UserRead]], status_code=status.HTTP_200_OK)
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    user_service: UserService = Depends(),
    current_user: User = Depends(require_admin)
):
    """Retrieve a list of all users (Admin only)."""
    users = await user_service.get_users(skip, limit)
    return StandardResponse(success=True, message="Users retrieved successfully", data=users)

@router.post("/", response_model=StandardResponse[UserRead], status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    user_service: UserService = Depends(),
    current_user: User = Depends(require_admin)
):
    """Create a new user (Admin only)."""
    user = await user_service.create_user(user_data)
    return StandardResponse(success=True, message="User created successfully", data=user)

@router.put("/{user_id}", response_model=StandardResponse[UserRead], status_code=status.HTTP_200_OK)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    user_service: UserService = Depends(),
    current_user: User = Depends(require_admin)
):
    """Update an existing user (Admin only)."""
    user = await user_service.update_user(user_id, update_data)
    return StandardResponse(success=True, message="User updated successfully", data=user)

@router.delete("/{user_id}", response_model=StandardResponse, status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    user_service: UserService = Depends(),
    current_user: User = Depends(require_admin)
):
    """Delete a user (Admin only)."""
    await user_service.delete_user(user_id)
    return StandardResponse(success=True, message="User deleted successfully")