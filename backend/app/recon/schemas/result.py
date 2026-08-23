# backend/app/recon/schemas/result.py
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime


class ScanResultRead(BaseModel):
    id: int
    scan_id: int
    result_type: str
    data: Dict[str, Any]
    error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanResultGrouped(BaseModel):
    """All results of a scan grouped by result_type for the frontend."""
    scan_id: int
    host_discovery: List[Dict[str, Any]] = []
    port_scan: List[Dict[str, Any]] = []
    service: List[Dict[str, Any]] = []
    whois: Dict[str, Any] = {}
    dns: List[Dict[str, Any]] = []
    ssl: Dict[str, Any] = {}
    http: Dict[str, Any] = {}
    screenshot: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
