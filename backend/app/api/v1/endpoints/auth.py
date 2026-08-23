# backend/app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, LogoutRequest
from app.schemas.user import UserRead
from app.schemas.common import StandardResponse
from app.api.deps import get_current_user
from app.auth.passwords import verify_password, hash_password
from app.models.user import User
from app.utils.errors import BadRequestError
from app.services.audit_service import AuditService
from app.core.constants import AuditAction

router = APIRouter()


# ---------------------------------------------------------------------------
# Self-service settings request schemas
# ---------------------------------------------------------------------------
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("New password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("New password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("New password must contain at least one digit")
        if not any(c in "@$!%*?&" for c in v):
            raise ValueError("New password must contain at least one special character (@$!%*?&)")
        return v


class UpdateEmailRequest(BaseModel):
    email: str = Field(..., min_length=3)


@router.post("/login", response_model=StandardResponse[TokenResponse], status_code=status.HTTP_200_OK)
async def login(
    login_data: LoginRequest,
    auth_service: AuthService = Depends()
):
    """Login endpoint to obtain access and refresh tokens."""
    tokens = await auth_service.login(login_data)
    return StandardResponse(success=True, message="Login successful", data=tokens)

@router.post("/refresh", response_model=StandardResponse[TokenResponse], status_code=status.HTTP_200_OK)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    auth_service: AuthService = Depends()
):
    """Refresh endpoint to get new tokens using a refresh token."""
    tokens = await auth_service.refresh_token(refresh_data)
    return StandardResponse(success=True, message="Token refreshed successfully", data=tokens)

@router.post("/logout", response_model=StandardResponse, status_code=status.HTTP_200_OK)
async def logout(
    logout_data: LogoutRequest,
    auth_service: AuthService = Depends()
):
    """Logout endpoint to blacklist the refresh token."""
    await auth_service.logout(logout_data)
    return StandardResponse(success=True, message="Logout successful")

@router.get("/me", response_model=StandardResponse[UserRead], status_code=status.HTTP_200_OK)
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return StandardResponse(success=True, message="User fetched successfully", data=current_user)


# ---------------------------------------------------------------------------
# Self-service settings — change password, update email
# ---------------------------------------------------------------------------
@router.post(
    "/me/change-password",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def change_my_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow the authenticated user to change their own password.

    Requires the current password for verification.  The new password
    must satisfy the same complexity policy enforced at user creation.
    """
    # Verify the current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise BadRequestError("Current password is incorrect.")

    # Disallow identical new password
    if verify_password(payload.new_password, current_user.password_hash):
        raise BadRequestError("New password must be different from the current password.")

    # Validate complexity
    try:
        ChangePasswordRequest.validate_new_password(payload.new_password)
    except ValueError as exc:
        raise BadRequestError(str(exc))

    # Persist
    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()

    # Audit
    audit = AuditService(db)
    await audit.log(
        user_id=current_user.id,
        action=AuditAction.PASSWORD_CHANGED,
        resource="user.password",
        details={"username": current_user.username},
    )
    await db.commit()

    return StandardResponse(success=True, message="Password updated successfully.")


@router.put(
    "/me/email",
    response_model=StandardResponse[UserRead],
    status_code=status.HTTP_200_OK,
)
async def update_my_email(
    payload: UpdateEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow the authenticated user to update their own email address.

    Email uniqueness is enforced against other users — the user cannot
    steal another user's email.
    """
    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)

    new_email = payload.email.strip().lower()
    if new_email == current_user.email:
        raise BadRequestError("New email is the same as the current email.")

    existing = await repo.get_by_email(new_email)
    if existing and existing.id != current_user.id:
        raise BadRequestError("Email is already registered to another user.")

    current_user.email = new_email
    await db.commit()
    await db.refresh(current_user, attribute_names=["role"])

    audit = AuditService(db)
    await audit.log(
        user_id=current_user.id,
        action=AuditAction.EMAIL_CHANGED,
        resource="user.email",
        details={"username": current_user.username, "new_email": new_email},
    )
    await db.commit()

    return StandardResponse(success=True, message="Email updated successfully.", data=current_user)