# backend/app/recon/schemas/scan.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.constants import ReconModule, PortPreset, ScanStatus


class ScanCreate(BaseModel):
    target: str = Field(..., min_length=1, max_length=512, description="Domain, IP, URL, or authorized CIDR")
    modules: List[str] = Field(
        default_factory=lambda: list(ReconModule.ALL),
        description="List of recon module names to run.",
    )
    name: Optional[str] = Field(None, max_length=255)
    port_preset: Optional[str] = Field(
        None,
        description=f"One of: {PortPreset.COMMON}, {PortPreset.WEB}, {PortPreset.CUSTOM}",
    )
    custom_ports: Optional[List[int]] = Field(
        None,
        description="Custom port list — only used when port_preset == 'custom'.",
    )

    # --- Phase 17 — optional assignment context (validated server-side) -----
    assignment_id: Optional[int] = Field(
        None,
        description="If the scan target is sourced from an assignment, the assignment row ID. "
                    "The backend re-validates ownership before accepting the scan.",
    )

    @field_validator("modules")
    @classmethod
    def _validate_modules(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one recon module must be selected.")
        cleaned: List[str] = []
        for m in v:
            if m not in ReconModule.ALL:
                raise ValueError(f"Unknown recon module: {m}")
            if m not in cleaned:
                cleaned.append(m)
        return cleaned

    @field_validator("port_preset")
    @classmethod
    def _validate_preset(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in (PortPreset.COMMON, PortPreset.WEB, PortPreset.CUSTOM):
            raise ValueError(f"port_preset must be one of: {PortPreset.COMMON}, {PortPreset.WEB}, {PortPreset.CUSTOM}")
        return v


class ScanModuleStatusRead(BaseModel):
    """Per-module lifecycle row for a scan."""

    module_name: str
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ScanRead(BaseModel):
    id: int
    user_id: int
    name: Optional[str] = None
    target: str
    target_type: str
    status: str
    modules: List[str]
    port_preset: Optional[str] = None
    custom_ports: Optional[List[int]] = None
    progress: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Phase 17 ownership fields
    ownership_type: str = "USER_MANUAL"
    client_id: Optional[int] = None
    client_asset_id: Optional[int] = None
    assignment_id: Optional[int] = None
    client_name: Optional[str] = None

    # Phase 19 — per-module status (populated by the API layer).
    module_statuses: List[ScanModuleStatusRead] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_scan(cls, scan, *, module_statuses: Optional[List] = None) -> "ScanRead":
        """Build a ScanRead from a Scan ORM object, optionally attaching
        module_statuses (a list of ScanModuleStatus ORM rows).

        This method MUST NOT trigger a lazy-load of the ``module_statuses``
        relationship — in an async SQLAlchemy session, lazy-loading from
        a sync context raises ``MissingGreenlet``.  We use SQLAlchemy's
        ``inspect()`` to check whether the relationship is already
        loaded before accessing it.  Callers that need module_statuses
        populated for a freshly-fetched scan must either:

        * Use ``ScanRepository.get_scan_with_results`` (which eager-loads
          the relationship), OR
        * Pass ``module_statuses=...`` explicitly with the rows fetched
          via ``ScanModuleStatusRepository.list_for_scan``.
        """
        data = {
            "id": scan.id,
            "user_id": scan.user_id,
            "name": scan.name,
            "target": scan.target,
            "target_type": scan.target_type,
            "status": scan.status,
            "modules": scan.modules,
            "port_preset": scan.port_preset,
            "custom_ports": scan.custom_ports,
            "progress": scan.progress,
            "started_at": scan.started_at,
            "completed_at": scan.completed_at,
            "error_message": scan.error_message,
            "celery_task_id": scan.celery_task_id,
            "created_at": scan.created_at,
            "updated_at": scan.updated_at,
            "ownership_type": scan.ownership_type or "USER_MANUAL",
            "client_id": scan.client_id,
            "client_asset_id": scan.client_asset_id,
            "assignment_id": scan.assignment_id,
            "module_statuses": [],
        }
        # client_name is set by the caller if available.
        if hasattr(scan, "client_name") and scan.client_name:
            data["client_name"] = scan.client_name
        if module_statuses is None:
            # Only access the relationship if it's already loaded —
            # never trigger a lazy-load here.  ``sqlalchemy.inspect``
            # returns the InstanceState which exposes ``unloaded``.
            try:
                from sqlalchemy import inspect as sqla_inspect
                insp = sqla_inspect(scan)
                if "module_statuses" not in insp.unloaded:
                    module_statuses = list(getattr(scan, "module_statuses", []) or [])
            except Exception:
                # If inspection fails (e.g. detached instance), skip.
                module_statuses = []
        data["module_statuses"] = [
            ScanModuleStatusRead.model_validate(ms) for ms in (module_statuses or [])
        ]
        return cls(**data)


class ScanSummary(BaseModel):
    """Compact representation used in list/dashboard contexts."""
    id: int
    user_id: int
    name: Optional[str] = None
    target: str
    target_type: str
    status: str
    progress: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    modules: List[str]

    # Phase 17 ownership fields
    ownership_type: str = "USER_MANUAL"
    client_id: Optional[int] = None
    assignment_id: Optional[int] = None
    client_name: Optional[str] = None
    user_username: Optional[str] = None

    model_config = {"from_attributes": True}


class ScanUpdate(BaseModel):
    """Internal update model used by the worker; not exposed via API."""
    status: Optional[str] = None
    progress: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    celery_task_id: Optional[str] = None


class ScanListFilters(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)
    status: Optional[str] = None
    target: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        allowed = {
            ScanStatus.QUEUED, ScanStatus.RUNNING, ScanStatus.COMPLETED,
            ScanStatus.FAILED, ScanStatus.CANCELLED,
        }
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class CancelResponse(BaseModel):
    id: int
    status: str
    message: str
