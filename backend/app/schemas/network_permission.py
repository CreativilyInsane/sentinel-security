# backend/app/schemas/network_permission.py
from pydantic import BaseModel, Field
from typing import List


class NetworksSet(BaseModel):
    """Payload to set a user's allowed networks."""
    networks: List[str] = Field(..., min_length=0, max_length=50, description="List of CIDR strings")


class NetworksRead(BaseModel):
    """Response with a user's allowed networks.

    NOTE: ``private_scan_enabled`` has been removed — private-network scan
    access is now controlled by the per-user ``private_network_scan``
    module permission stored in the ``user_module_permissions`` table.
    Use the User Module Settings page (/admin/users/:userId/modules) to
    toggle it.
    """
    user_id: int
    username: str
    networks: List[str]
