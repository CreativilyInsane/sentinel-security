# backend/app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.services.module_permission_service import ModulePermissionService
from app.schemas.user import UserCreate, UserUpdate, UserRead
from app.schemas.common import StandardResponse, PaginatedResponse
from app.api.deps import require_admin, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.core.constants import ModulePermission
from typing import List
from pydantic import BaseModel

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


# ===========================================================================
# Module Permissions (admin-only)
# ===========================================================================
class ModulePermissionItem(BaseModel):
    module_name: str
    is_allowed: bool

class ModulePermissionsSet(BaseModel):
    permissions: List[ModulePermissionItem]

class ModulePermissionsRead(BaseModel):
    user_id: int
    permissions: List[ModulePermissionItem]
    # If True, no rows exist → all modules allowed (default-open)
    is_default_open: bool
    # Computed parent toggle: True if ANY of the 8 Network submodules is True.
    # The frontend uses this to render the parent checkbox state; it is
    # not stored in the DB.  When the admin turns the parent OFF, the
    # PUT endpoint receives is_allowed=False for every child; when the
    # admin turns the parent ON, the frontend sends the previous child
    # states (or True for every child if none were previously saved).
    network_module_enabled: bool = True


@router.get(
    "/{user_id}/modules",
    response_model=StandardResponse[ModulePermissionsRead],
    status_code=status.HTTP_200_OK,
)
async def get_module_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return the module permissions for a user.

    If no rows exist, the user has access to all modules (default-open).
    The response ALWAYS contains an entry for every module in
    ``ModulePermission.ALL`` — missing rows are returned as ``True``
    (when default-open) or ``False`` (when the user has at least one
    row but no row for that module).
    """
    svc = ModulePermissionService(db)
    data = await svc.get_permissions_read(user_id)
    return StandardResponse(
        success=True, message="Module permissions retrieved.",
        data=ModulePermissionsRead(**data),
    )


@router.put(
    "/{user_id}/modules",
    response_model=StandardResponse[ModulePermissionsRead],
    status_code=status.HTTP_200_OK,
)
async def set_module_permissions(
    user_id: int,
    payload: ModulePermissionsSet,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Replace a user's module permissions with the provided list.

    This deletes all existing rows and inserts the new ones.
    If the list is empty, the user returns to default-open (all allowed).
    """
    svc = ModulePermissionService(db)
    await svc.set_permissions(
        user_id,
        [{"module_name": p.module_name, "is_allowed": p.is_allowed} for p in payload.permissions],
    )
    data = await svc.get_permissions_read(user_id)
    return StandardResponse(
        success=True, message="Module permissions updated.",
        data=ModulePermissionsRead(**data),
    )


@router.get(
    "/{user_id}/allowed-modules",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def get_allowed_modules(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the list of module names this user is allowed to use.

    Regular users can only query their own; admins can query any user.
    """
    from app.core.constants import Roles
    is_admin = bool(current_user.role and current_user.role.name == Roles.ADMIN)
    if not is_admin and current_user.id != user_id:
        from app.utils.errors import ForbiddenError
        raise ForbiddenError("You can only query your own module permissions.")

    svc = ModulePermissionService(db)
    allowed = await svc.get_allowed_modules(current_user if current_user.id == user_id else await _load_user(db, user_id))
    return StandardResponse(
        success=True, message="Allowed modules retrieved.",
        data={
            "modules": sorted(allowed),
            "is_default_open": len(allowed) == len(ModulePermission.ALL),
        },
    )


async def _load_user(db: AsyncSession, user_id: int) -> User:
    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)
    user = await repo.get_user_with_role(user_id)
    if not user:
        from app.utils.errors import NotFoundError
        raise NotFoundError(f"User with ID {user_id} not found.")
    return user
