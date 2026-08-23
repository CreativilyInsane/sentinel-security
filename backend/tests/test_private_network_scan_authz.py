"""End-to-end authorization tests for the private_network_scan permission.

These tests exercise the TargetAuthorizationService.authorize() method
with a stubbed DB, verifying that:

1. A user WITHOUT the private_network_scan permission is rejected (403)
   when scanning a private IP, even if the IP is explicitly assigned to
   them via a Client assignment.
2. A user WITH the private_network_scan permission is allowed to scan
   a private IP when it's assigned.
3. A user WITHOUT the permission is allowed to scan a PUBLIC target
   (the private_network_scan permission only gates private targets).
4. An admin is always allowed (bypass).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("ADMIN_USERNAME", "a")
os.environ.setdefault("ADMIN_PASSWORD", "Aa1!aaaa")
os.environ.setdefault("ADMIN_EMAIL", "a@b.c")


def _make_user(role_name: str, user_id: int = 1):
    role = SimpleNamespace(id=1, name=role_name)
    return SimpleNamespace(
        id=user_id,
        username="admin" if role_name == "Administrator" else "user",
        email="u@example.com",
        password_hash="x",
        role=role,
        is_active=True,
    )


def _make_assignment(assignment_id, user_id, client_id, target_value, target_type="IP", assignment_type="CLIENT", client_asset_id=None):
    return SimpleNamespace(
        id=assignment_id,
        user_id=user_id,
        client_id=client_id,
        client_asset_id=client_asset_id,
        assignment_type=assignment_type,
        target_type=target_type,
        target_value=target_value,
        target_label=target_value,
        assigned_by=1,
        is_active=True,
    )


def _make_client_asset(asset_id, client_id, asset_type, ip_address=None, cidr=None, domain=None, name=None):
    return SimpleNamespace(
        id=asset_id,
        client_id=client_id,
        asset_type=asset_type,
        ip_address=ip_address,
        cidr=cidr,
        domain=domain,
        name=name,
        description=None,
        network_name=None,
        vlan_name=None,
        is_active=True,
    )


def _build_authz_service(perm_rows: list, assignments: list, client_assets_by_client: dict[int, list]):
    """Build a TargetAuthorizationService with stubbed repositories.

    perm_rows: list of SimpleNamespace(module_name, is_allowed)
    assignments: list of TargetAssignment-like SimpleNamespace
    client_assets_by_client: dict[client_id, list[ClientAsset]]
    """
    from app.services.target_authorization_service import (
        TargetAuthorizationService,
    )

    class _StubNetworkRepo:
        async def get_networks_list(self, user_id):
            return []
    class _StubAssignmentRepo:
        async def list_for_user(self, user_id, active_only=True):
            return [a for a in assignments if a.user_id == user_id and (not active_only or a.is_active)]
        async def list_active_user_client_ids(self, user_id):
            return list({a.client_id for a in assignments if a.user_id == user_id and a.is_active and a.client_id is not None})
    class _StubClientAssetRepo:
        async def list_for_client(self, client_id, is_active=None):
            return list(client_assets_by_client.get(client_id, []))
    class _StubDb:
        async def execute(self, stmt):
            class _R:
                def scalars(self): return self
                def all(self): return list(perm_rows)
            return _R()

    svc = TargetAuthorizationService.__new__(TargetAuthorizationService)
    svc.db = _StubDb()
    svc.assignment_repo = _StubAssignmentRepo()
    svc.client_asset_repo = _StubClientAssetRepo()
    svc.network_repo = _StubNetworkRepo()
    # ModulePermissionService is constructed inside __init__, but since
    # we're using __new__ we need to set it up ourselves.
    from app.services.module_permission_service import ModulePermissionService
    svc.perm_service = ModulePermissionService(svc.db)
    # Monkey-patch the perm_service._load_rows to return our stub rows
    async def _stub_load_rows(_user_id):
        return list(perm_rows)
    svc.perm_service._load_rows = _stub_load_rows

    # Phase 19 — stub the per-user client/asset permission repos.
    # By default these return True (default-open: no row exists).
    class _StubClientPermRepo:
        async def list_for_user(self, user_id):
            return []
        async def get(self, user_id, client_id):
            return None
        async def is_enabled(self, user_id, client_id):
            return True
        async def set_enabled(self, user_id, client_id, enabled):
            return None
        async def disable_all_for_client(self, user_id, client_id):
            return 0
    class _StubAssetPermRepo:
        async def list_for_user(self, user_id):
            return []
        async def get(self, user_id, client_asset_id):
            return None
        async def is_enabled(self, user_id, client_asset_id):
            return True
        async def set_enabled(self, user_id, client_asset_id, enabled):
            return None
    svc.client_perm_repo = _StubClientPermRepo()
    svc.asset_perm_repo = _StubAssetPermRepo()
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestPrivateNetworkScanAuthorization:
    """End-to-end authorization tests for private_network_scan permission."""

    def test_user_without_private_perm_rejected_for_private_assigned_target(self):
        """User A is assigned to Client ABC which contains 192.168.1.10.
        User A does NOT have the private_network_scan permission.
        Expected: 403 Forbidden."""
        from app.core.constants import Roles, ModulePermission, ClientAssetType, AssignmentType
        from app.services.target_authorization_service import TargetAuthorization

        user = _make_user(Roles.USER, user_id=1)
        # User has port_scan=True but private_network_scan is absent (False)
        perm_rows = [
            SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=True),
            SimpleNamespace(module_name=ModulePermission.HOST_DISCOVERY, is_allowed=True),
        ]
        # Assignment: Client ABC (id=1) is assigned to user
        assignment = _make_assignment(
            assignment_id=1, user_id=1, client_id=1,
            target_value="ABC Corp", target_type="CLIENT",
            assignment_type="CLIENT",
        )
        # Client ABC has asset 192.168.1.10 (private IP)
        asset = _make_client_asset(
            asset_id=1, client_id=1, asset_type=ClientAssetType.IP,
            ip_address="192.168.1.10", name="Web Server",
        )
        svc = _build_authz_service(
            perm_rows=perm_rows,
            assignments=[assignment],
            client_assets_by_client={1: [asset]},
        )

        result = asyncio.run(svc.authorize(user, "192.168.1.10"))

        assert result.allowed is False, \
            f"Expected 403 for private target without private_network_scan perm, got allowed={result.allowed}"
        assert "private" in result.reason.lower() or "private network scan" in result.reason.lower()

    def test_user_with_private_perm_allowed_for_private_assigned_target(self):
        """User A is assigned to Client ABC which contains 192.168.1.10.
        User A HAS the private_network_scan permission.
        Expected: ALLOWED with ownership_type=CLIENT."""
        from app.core.constants import Roles, ModulePermission, ClientAssetType, AssignmentType, OwnershipType

        user = _make_user(Roles.USER, user_id=1)
        perm_rows = [
            SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=True),
            SimpleNamespace(module_name=ModulePermission.PRIVATE_NETWORK_SCAN, is_allowed=True),
        ]
        assignment = _make_assignment(
            assignment_id=1, user_id=1, client_id=1,
            target_value="ABC Corp", target_type="CLIENT",
            assignment_type="CLIENT",
        )
        asset = _make_client_asset(
            asset_id=1, client_id=1, asset_type=ClientAssetType.IP,
            ip_address="192.168.1.10", name="Web Server",
        )
        svc = _build_authz_service(
            perm_rows=perm_rows,
            assignments=[assignment],
            client_assets_by_client={1: [asset]},
        )

        result = asyncio.run(svc.authorize(user, "192.168.1.10"))

        assert result.allowed is True, \
            f"Expected allowed for assigned private target with private_network_scan perm, got {result.reason}"
        assert result.ownership_type == OwnershipType.CLIENT
        assert result.client_id == 1
        assert result.client_asset_id == 1

    def test_user_without_private_perm_allowed_for_public_target(self):
        """The private_network_scan permission only gates private targets.
        A user without the permission can still scan public targets."""
        from app.core.constants import Roles, ModulePermission, OwnershipType

        user = _make_user(Roles.USER, user_id=1)
        # No private_network_scan perm, no assignments
        perm_rows = [
            SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=True),
        ]
        svc = _build_authz_service(
            perm_rows=perm_rows,
            assignments=[],
            client_assets_by_client={},
        )

        result = asyncio.run(svc.authorize(user, "8.8.8.8"))

        assert result.allowed is True
        assert result.ownership_type == OwnershipType.USER_MANUAL
        assert result.target_classification == "public"

    def test_admin_bypasses_private_network_scan_permission(self):
        """An admin can scan a private target without any module permission rows."""
        from app.core.constants import Roles, OwnershipType

        user = _make_user(Roles.ADMIN, user_id=1)
        # No perm rows at all — admin should bypass
        svc = _build_authz_service(
            perm_rows=[],
            assignments=[],
            client_assets_by_client={},
        )

        result = asyncio.run(svc.authorize(user, "192.168.1.10"))

        assert result.allowed is True
        assert result.ownership_type == OwnershipType.USER_MANUAL

    def test_user_without_private_perm_rejected_for_private_cidr(self):
        """Same as the IP test but with a CIDR target."""
        from app.core.constants import Roles, ModulePermission, ClientAssetType

        user = _make_user(Roles.USER, user_id=1)
        perm_rows = [
            SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=True),
        ]
        assignment = _make_assignment(
            assignment_id=1, user_id=1, client_id=1,
            target_value="ABC Corp", target_type="CLIENT",
            assignment_type="CLIENT",
        )
        asset = _make_client_asset(
            asset_id=1, client_id=1, asset_type=ClientAssetType.IP_RANGE,
            cidr="192.168.1.0/24", name="Office Network",
        )
        svc = _build_authz_service(
            perm_rows=perm_rows,
            assignments=[assignment],
            client_assets_by_client={1: [asset]},
        )

        result = asyncio.run(svc.authorize(user, "192.168.1.0/24"))

        assert result.allowed is False

    def test_user_default_open_includes_private_network_scan(self):
        """If a user has NO permission rows at all (default-open), they
        have private_network_scan implicitly."""
        from app.core.constants import Roles, OwnershipType

        user = _make_user(Roles.USER, user_id=1)
        # No perm rows → default-open → all permissions True
        svc = _build_authz_service(
            perm_rows=[],
            assignments=[],
            client_assets_by_client={},
        )

        result = asyncio.run(svc.authorize(user, "192.168.1.10"))

        # Default-open means private_network_scan is allowed
        assert result.allowed is True
        assert result.ownership_type == OwnershipType.USER_MANUAL

    def test_user_with_explicit_deny_for_private_network_scan(self):
        """If a user has explicit perm rows AND private_network_scan=False,
        they must be rejected for private targets."""
        from app.core.constants import Roles, ModulePermission, ClientAssetType

        user = _make_user(Roles.USER, user_id=1)
        perm_rows = [
            SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=True),
            SimpleNamespace(module_name=ModulePermission.PRIVATE_NETWORK_SCAN, is_allowed=False),
        ]
        assignment = _make_assignment(
            assignment_id=1, user_id=1, client_id=1,
            target_value="ABC Corp", target_type="CLIENT",
            assignment_type="CLIENT",
        )
        asset = _make_client_asset(
            asset_id=1, client_id=1, asset_type=ClientAssetType.IP,
            ip_address="10.0.0.5", name="Server",
        )
        svc = _build_authz_service(
            perm_rows=perm_rows,
            assignments=[assignment],
            client_assets_by_client={1: [asset]},
        )

        result = asyncio.run(svc.authorize(user, "10.0.0.5"))

        assert result.allowed is False
        assert "private" in result.reason.lower() or "private network scan" in result.reason.lower()

    def test_user_with_perm_allowed_for_172_16_range(self):
        """Test the 172.16.0.0/12 private range."""
        from app.core.constants import Roles, ModulePermission, ClientAssetType, OwnershipType

        user = _make_user(Roles.USER, user_id=1)
        perm_rows = [
            SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=True),
            SimpleNamespace(module_name=ModulePermission.PRIVATE_NETWORK_SCAN, is_allowed=True),
        ]
        assignment = _make_assignment(
            assignment_id=1, user_id=1, client_id=1,
            target_value="ABC Corp", target_type="CLIENT",
            assignment_type="CLIENT",
        )
        asset = _make_client_asset(
            asset_id=1, client_id=1, asset_type=ClientAssetType.IP,
            ip_address="172.16.5.10", name="Server",
        )
        svc = _build_authz_service(
            perm_rows=perm_rows,
            assignments=[assignment],
            client_assets_by_client={1: [asset]},
        )

        result = asyncio.run(svc.authorize(user, "172.16.5.10"))

        assert result.allowed is True
        assert result.ownership_type == OwnershipType.CLIENT
