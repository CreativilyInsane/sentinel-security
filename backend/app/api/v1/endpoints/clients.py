# backend/app/api/v1/endpoints/clients.py
"""Admin-only endpoints for Client + ClientAsset management, plus the
target-assignment endpoints (admin assigns, user reads own)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientRead, ClientWithStats,
    ClientAssetCreate, ClientAssetUpdate, ClientAssetRead,
)
from app.schemas.common import StandardResponse
from app.schemas.target_assignment import (
    AssignClientPayload, AssignDirectTargetPayload,
    AssignmentRead, AssignmentUpdate,
)
from app.services.client_service import ClientService
from app.utils.errors import NotFoundError


router = APIRouter()


# ===========================================================================
# Clients
# ===========================================================================
@router.post(
    "/clients",
    response_model=StandardResponse[ClientRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_client(
    payload: ClientCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    client = await service.create_client(admin_id=current_user.id, payload=payload)
    await db.commit()
    await db.refresh(client)
    return StandardResponse(success=True, message="Client created.", data=ClientRead.model_validate(client))


@router.get(
    "/clients",
    response_model=StandardResponse[List[ClientWithStats]],
    status_code=status.HTTP_200_OK,
)
async def list_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    rows = await service.list_clients(skip=skip, limit=limit, search=search, is_active=is_active)
    return StandardResponse(success=True, message="Clients retrieved.", data=rows)


@router.get(
    "/clients/{client_id}",
    response_model=StandardResponse[ClientRead],
    status_code=status.HTTP_200_OK,
)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    client = await service.get_client(client_id)
    return StandardResponse(success=True, message="Client retrieved.", data=ClientRead.model_validate(client))


@router.put(
    "/clients/{client_id}",
    response_model=StandardResponse[ClientRead],
    status_code=status.HTTP_200_OK,
)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    client = await service.update_client(client_id=client_id, admin_id=current_user.id, payload=payload)
    await db.commit()
    await db.refresh(client)
    return StandardResponse(success=True, message="Client updated.", data=ClientRead.model_validate(client))


@router.delete(
    "/clients/{client_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    await service.delete_client(client_id=client_id, admin_id=current_user.id)
    await db.commit()
    return StandardResponse(success=True, message="Client deactivated.")


# ===========================================================================
# Client assets
# ===========================================================================
@router.post(
    "/clients/{client_id}/assets",
    response_model=StandardResponse[ClientAssetRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_client_asset(
    client_id: int,
    payload: ClientAssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    asset = await service.create_asset(client_id=client_id, admin_id=current_user.id, payload=payload)
    await db.commit()
    await db.refresh(asset)
    return StandardResponse(success=True, message="Client asset created.", data=ClientAssetRead.model_validate(asset))


@router.get(
    "/clients/{client_id}/assets",
    response_model=StandardResponse[List[ClientAssetRead]],
    status_code=status.HTTP_200_OK,
)
async def list_client_assets(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    rows = await service.list_assets(client_id)
    return StandardResponse(success=True, message="Client assets retrieved.", data=[ClientAssetRead.model_validate(a) for a in rows])


@router.put(
    "/clients/{client_id}/assets/{asset_id}",
    response_model=StandardResponse[ClientAssetRead],
    status_code=status.HTTP_200_OK,
)
async def update_client_asset(
    client_id: int,
    asset_id: int,
    payload: ClientAssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    asset = await service.update_asset(
        client_id=client_id, asset_id=asset_id, admin_id=current_user.id, payload=payload,
    )
    await db.commit()
    await db.refresh(asset)
    return StandardResponse(success=True, message="Client asset updated.", data=ClientAssetRead.model_validate(asset))


@router.delete(
    "/clients/{client_id}/assets/{asset_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_client_asset(
    client_id: int,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    await service.delete_asset(client_id=client_id, asset_id=asset_id, admin_id=current_user.id)
    await db.commit()
    return StandardResponse(success=True, message="Client asset deleted.")
