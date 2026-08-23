# backend/app/schemas/target_assignment.py
"""Pydantic schemas for target assignment + notification APIs."""
from __future__ import annotations

import ipaddress
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List

from app.core.constants import AssignmentType, ClientAssetType


# ---------------------------------------------------------------------------
# Assignment payloads
# ---------------------------------------------------------------------------
class AssignClientPayload(BaseModel):
    """Assign an entire Client to a user."""
    user_id: int
    client_id: int


class AssignDirectTargetPayload(BaseModel):
    """Directly assign a single IP, CIDR, or domain to a user.

    ``client_asset_id`` is optional — when the direct target originates
    from a ClientAsset, the admin can preserve that lineage.
    """
    user_id: int
    target_type: str = Field(..., description="IP, IP_RANGE, or DOMAIN")
    target_value: str = Field(..., min_length=1, max_length=255)
    target_label: Optional[str] = Field(None, max_length=255)
    client_id: Optional[int] = None
    client_asset_id: Optional[int] = None

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, v: str) -> str:
        if v not in (ClientAssetType.IP, ClientAssetType.IP_RANGE, ClientAssetType.DOMAIN):
            raise ValueError("target_type must be 'IP', 'IP_RANGE', or 'DOMAIN'")
        return v

    @model_validator(mode="after")
    def _validate_value(self) -> "AssignDirectTargetPayload":
        import re
        if self.target_type == ClientAssetType.IP:
            try:
                ipaddress.ip_address(self.target_value)
            except ValueError:
                raise ValueError(f"target_value '{self.target_value}' is not a valid IP address")
        elif self.target_type == ClientAssetType.IP_RANGE:
            try:
                ipaddress.ip_network(self.target_value, strict=False)
            except ValueError:
                raise ValueError(f"target_value '{self.target_value}' is not a valid CIDR notation")
        elif self.target_type == ClientAssetType.DOMAIN:
            d = self.target_value.strip().lower().rstrip(".")
            if "://" in d:
                raise ValueError("domain must not include a scheme (http://, https://)")
            if not re.match(
                r"^(?=.{1,253}$)"
                r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
                r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
                d,
            ):
                raise ValueError(f"target_value '{d}' is not a valid domain name")
            if not re.search(r"\.[a-z]{2,}$", d):
                raise ValueError(f"domain '{d}' must include a valid top-level domain")
            self.target_value = d
        return self


class AssignmentUpdate(BaseModel):
    is_active: Optional[bool] = None
    target_label: Optional[str] = Field(None, max_length=255)


# ---------------------------------------------------------------------------
# Assignment reads
# ---------------------------------------------------------------------------
class AssignmentRead(BaseModel):
    id: int
    user_id: int
    client_id: Optional[int] = None
    client_asset_id: Optional[int] = None
    assignment_type: str
    target_type: str
    target_value: str
    target_label: Optional[str] = None
    assigned_by: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Optional joined fields (populated by the service layer)
    client_name: Optional[str] = None
    client_asset_name: Optional[str] = None
    assigner_username: Optional[str] = None
    user_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Notification reads
# ---------------------------------------------------------------------------
class AssignmentNotificationRead(BaseModel):
    id: int
    user_id: int
    assignment_id: Optional[int] = None
    type: str
    message: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationMarkRead(BaseModel):
    notification_ids: Optional[List[int]] = Field(None, description="Specific IDs; if omitted, mark all unread as read")
