# backend/app/api/v1/endpoints/network_permissions.py
"""Admin endpoints for managing per-user network scan permissions.

The admin can grant a user the ability to scan specific private CIDR
ranges (e.g. ``192.168.1.0/24``) by adding them to the user's
``UserAllowedNetwork`` list.  This is independent of the per-user
``private_network_scan`` *module* permission — that permission is the
broad on/off switch for private-network scanning, while the per-user
allowed-networks list is a fine-grained CIDR allow-list that the SSRF
guard consults regardless of the module permission.

NOTE: The legacy ``POST /users/toggle-private-scan`` endpoint has been
REMOVED.  Private-network scan access is now controlled by the
``private_network_scan`` module permission on the User Module Settings
page (``/admin/users/:userId/modules``).
"""
from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.logging import logger
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_network_repository import UserNetworkRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import StandardResponse
from app.schemas.network_permission import NetworksSet, NetworksRead
from app.utils.errors import BadRequestError, NotFoundError

router = APIRouter()


# ---- Get user's network permissions ----
@router.get(
    "/{user_id}/networks",
    response_model=StandardResponse[NetworksRead],
    status_code=status.HTTP_200_OK,
)
async def get_user_networks(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Return the allowed private networks for a given user (admin only)."""
    user_repo = UserRepository(db)
    user = await user_repo.get_user_with_role(user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} not found.")

    net_repo = UserNetworkRepository(db)
    networks = await net_repo.get_networks_list(user_id)

    return StandardResponse(
        success=True,
        message="Network permissions retrieved.",
        data=NetworksRead(
            user_id=user.id,
            username=user.username,
            networks=networks,
        ),
    )


# ---- Set user's network permissions ----
@router.put(
    "/{user_id}/networks",
    response_model=StandardResponse[NetworksRead],
    status_code=status.HTTP_200_OK,
)
async def set_user_networks(
    user_id: int,
    payload: NetworksSet,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Set the allowed private networks for a given user (admin only)."""
    # Validate all CIDRs
    validated_networks = []
    for n in payload.networks:
        n = n.strip()
        if not n:
            continue
        try:
            net = ipaddress.ip_network(n, strict=False)
        except ValueError:
            raise BadRequestError(f"Invalid CIDR: '{n}'. Expected format like 192.168.1.0/24.")
        validated_networks.append(str(net))

    user_repo = UserRepository(db)
    user = await user_repo.get_user_with_role(user_id)
    if not user:
        raise NotFoundError(f"User with ID {user_id} not found.")

    net_repo = UserNetworkRepository(db)
    await net_repo.set_networks(user_id, validated_networks)
    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin {current_user.username} set networks for user {user.username}: {validated_networks}")

    return StandardResponse(
        success=True,
        message="Network permissions updated.",
        data=NetworksRead(
            user_id=user.id,
            username=user.username,
            networks=validated_networks,
        ),
    )
