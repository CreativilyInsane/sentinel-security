# backend/app/recon/schemas/asset.py
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime


class AssetRead(BaseModel):
    id: int
    user_id: int
    scan_id: Optional[int] = None
    host: str
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    service: Optional[str] = None
    status: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    metadata: Dict[str, Any] = {}

    # Phase 17 ownership fields
    ownership_type: str = "USER_MANUAL"
    client_id: Optional[int] = None
    client_asset_id: Optional[int] = None
    assignment_id: Optional[int] = None
    client_name: Optional[str] = None
    can_delete: bool = True

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_asset(cls, asset, *, is_admin: bool = False, can_delete: bool = True, client_name: Optional[str] = None) -> "AssetRead":
        # The model column is named `metadata_` (mapped to "metadata" DB column)
        # because `metadata` is reserved on SQLAlchemy declarative classes.
        return cls(
            id=asset.id,
            user_id=asset.user_id,
            scan_id=asset.scan_id,
            host=asset.host,
            ip_address=asset.ip_address,
            hostname=asset.hostname,
            port=asset.port,
            protocol=asset.protocol,
            service=asset.service,
            status=asset.status,
            first_seen=asset.first_seen,
            last_seen=asset.last_seen,
            metadata=asset.metadata_ or {},
            ownership_type=getattr(asset, "ownership_type", "USER_MANUAL") or "USER_MANUAL",
            client_id=getattr(asset, "client_id", None),
            client_asset_id=getattr(asset, "client_asset_id", None),
            assignment_id=getattr(asset, "assignment_id", None),
            client_name=client_name,
            can_delete=can_delete,
        )


class AssetListFilters(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=500)
    host: Optional[str] = None
