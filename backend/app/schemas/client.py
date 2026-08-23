# backend/app/schemas/client.py
"""Pydantic schemas for the Client + ClientAsset APIs."""
from __future__ import annotations

import ipaddress
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List

from app.core.constants import ClientAssetType


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    company_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    is_active: bool = True


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    company_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class ClientRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientWithStats(ClientRead):
    """Client row plus aggregate stats used by the listing page."""
    asset_count: int = 0
    assigned_user_count: int = 0
    active_assignment_count: int = 0


# ---------------------------------------------------------------------------
# ClientAsset
# ---------------------------------------------------------------------------
class ClientAssetCreate(BaseModel):
    asset_type: str = Field(..., description="IP, IP_RANGE, or DOMAIN")
    ip_address: Optional[str] = None
    cidr: Optional[str] = None
    domain: Optional[str] = None
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    network_name: Optional[str] = Field(None, max_length=200)
    vlan_name: Optional[str] = Field(None, max_length=100)
    is_active: bool = True

    @field_validator("asset_type")
    @classmethod
    def _validate_asset_type(cls, v: str) -> str:
        if v not in ClientAssetType.ALL:
            raise ValueError(f"asset_type must be one of {ClientAssetType.ALL}")
        return v

    @model_validator(mode="after")
    def _validate_value_present(self) -> "ClientAssetCreate":
        import re
        if self.asset_type == ClientAssetType.IP:
            if not self.ip_address:
                raise ValueError("ip_address is required when asset_type == 'IP'")
            if self.cidr or self.domain:
                raise ValueError("cidr and domain must be empty when asset_type == 'IP'")
            try:
                ipaddress.ip_address(self.ip_address)
            except ValueError:
                raise ValueError(f"ip_address '{self.ip_address}' is not a valid IP address")
        elif self.asset_type == ClientAssetType.IP_RANGE:
            if not self.cidr:
                raise ValueError("cidr is required when asset_type == 'IP_RANGE'")
            if self.ip_address or self.domain:
                raise ValueError("ip_address and domain must be empty when asset_type == 'IP_RANGE'")
            try:
                ipaddress.ip_network(self.cidr, strict=False)
            except ValueError:
                raise ValueError(f"cidr '{self.cidr}' is not a valid CIDR notation")
        elif self.asset_type == ClientAssetType.DOMAIN:
            if not self.domain:
                raise ValueError("domain is required when asset_type == 'DOMAIN'")
            if self.ip_address or self.cidr:
                raise ValueError("ip_address and cidr must be empty when asset_type == 'DOMAIN'")
            # Basic domain validation — must have a TLD and no scheme.
            d = self.domain.strip().lower().rstrip(".")
            if "://" in d:
                raise ValueError("domain must not include a scheme (http://, https://)")
            if d in ("localhost", "db", "redis", "backend", "frontend", "nginx", "worker"):
                raise ValueError(f"domain '{d}' is an internal hostname and not allowed")
            if not re.match(
                r"^(?=.{1,253}$)"
                r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
                r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
                d,
            ):
                raise ValueError(f"domain '{d}' is not a valid domain name")
            if not re.search(r"\.[a-z]{2,}$", d):
                raise ValueError(f"domain '{d}' must include a valid top-level domain (e.g. .com, .org)")
            self.domain = d
        return self


class ClientAssetUpdate(BaseModel):
    asset_type: Optional[str] = None
    ip_address: Optional[str] = None
    cidr: Optional[str] = None
    domain: Optional[str] = None
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    network_name: Optional[str] = Field(None, max_length=200)
    vlan_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class ClientAssetRead(BaseModel):
    id: int
    client_id: int
    asset_type: str
    ip_address: Optional[str] = None
    cidr: Optional[str] = None
    domain: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    network_name: Optional[str] = None
    vlan_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def value(self) -> str:
        return self.ip_address or self.cidr or self.domain or ""
