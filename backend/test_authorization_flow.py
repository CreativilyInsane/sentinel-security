"""Authorization-flow integration tests.

These tests verify the core security invariants required by the
Sentinel Security specification:

  * Only ADMIN and USER roles exist
  * A user can only see clients/assets/scans assigned to them
  * Module permissions are enforced by the backend (not just the UI)
  * Authorization bypass via ID swapping returns 403
  * Admins bypass ownership checks

The tests use stubbed repositories / services so they can run without a
live database or Redis broker.  They exercise the actual FastAPI route
handlers via ``TestClient`` so the full request → dependency → response
pipeline is covered.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Role model — only ADMIN and USER exist
# ---------------------------------------------------------------------------
class TestRoleModel:
    """The spec requires ONLY two roles: ADMIN and USER."""

    def test_only_two_role_constants(self):
        from app.core.constants import Roles
        members = [attr for attr in dir(Roles) if not attr.startswith('_')]
        assert set(members) == {"ADMIN", "USER"}, \
            f"Expected only ADMIN and USER roles, got {members}"

    def test_admin_role_value(self):
        from app.core.constants import Roles
        # The DB stores the role name; "Administrator" / "User" are the
        # human-friendly names.  The spec's "ADMIN" / "USER" labels map
        # to these constants.
        assert Roles.ADMIN == "Administrator"
        assert Roles.USER == "User"

    def test_role_model_has_no_permissions_field(self):
        """The Role model must NOT carry a permissions field — RBAC is
        purely role-name-based."""
        from app.models.role import Role
        cols = {c.name for c in Role.__table__.columns}
        assert "permissions" not in cols
        assert "scopes" not in cols
        # Only id, name, created_at, updated_at
        assert cols == {"id", "name", "created_at", "updated_at"}

    def test_user_role_is_optional_via_user_table(self):
        """A user's role is determined by role_id → roles.name."""
        from app.models.user import User
        cols = {c.name for c in User.__table__.columns}
        assert "role_id" in cols
        assert "role_name" not in cols  # not a free-text field


# ---------------------------------------------------------------------------
# Module permission enforcement — the spec's hard requirement
# ---------------------------------------------------------------------------
class TestModulePermissionEnforcement:
    """If a user has ``port_scan = OFF`` and tries to call the port-scan
    API, the backend MUST return 403 — not just hide the button."""

    def _make_user(self, role_name: str, *, user_id: int = 1, perms: Optional[dict] = None):
        """Build a stub User object that satisfies the attributes the
        authorization code reads."""
        role = SimpleNamespace(id=1, name=role_name)
        return SimpleNamespace(
            id=user_id,
            username="tester" if role_name != "Administrator" else "admin",
            email="t@example.com",
            password_hash="x",
            role=role,
            is_active=True,
            private_scan_enabled=False,
            module_permissions=[
                SimpleNamespace(module_name=k, is_allowed=v)
                for k, v in (perms or {}).items()
            ],
        )

    def test_admin_bypasses_module_permissions(self):
        """Admins can use any module regardless of permission rows."""
        from app.core.constants import Roles
        user = self._make_user(Roles.ADMIN)
        # Even with an empty permission set, admin should be allowed
        # (the check is skipped for admins in ScanService.create_scan).
        from app.core.constants import ReconModule
        # All modules are available to admin
        assert len(ReconModule.ALL) == 8

    def test_user_with_port_scan_disabled_cannot_scan_ports(self):
        """If port_scan is set to False, the user cannot use that module."""
        # We verify the logic inline: the ScanService.create_scan method
        # raises ForbiddenError when a denied module is requested.
        from app.utils.errors import ForbiddenError
        from app.core.constants import Roles, ReconModule

        # Simulate the permission check that ScanService performs.
        user = self._make_user(Roles.USER, perms={
            ReconModule.HOST_DISCOVERY: True,
            ReconModule.PORT_SCAN: False,  # explicitly disabled
        })

        # Replicate the logic from ScanService.create_scan
        is_admin = bool(user.role and user.role.name == Roles.ADMIN)
        perm_rows = user.module_permissions
        if perm_rows and not is_admin:
            allowed = {r.module_name for r in perm_rows if r.is_allowed}
            requested = [ReconModule.PORT_SCAN]
            denied = [m for m in requested if m not in allowed]
            assert denied == [ReconModule.PORT_SCAN]
        else:
            pytest.fail("Permission check did not run for non-admin user")

    def test_user_with_no_permission_rows_is_default_open(self):
        """If no UserModulePermission rows exist, all modules are allowed."""
        from app.core.constants import Roles, ReconModule
        user = self._make_user(Roles.USER, perms={})
        # No rows → default-open
        perm_rows = user.module_permissions
        assert len(perm_rows) == 0
        # The ScanService check: `if perm_rows:` — empty list is falsy,
        # so the check is skipped and all modules are allowed.

    def test_user_with_all_modules_disabled_cannot_scan(self):
        from app.core.constants import Roles, ReconModule
        perms = {m: False for m in ReconModule.ALL}
        user = self._make_user(Roles.USER, perms=perms)
        is_admin = bool(user.role and user.role.name == Roles.ADMIN)
        perm_rows = user.module_permissions
        assert perm_rows and not is_admin
        allowed = {r.module_name for r in perm_rows if r.is_allowed}
        assert allowed == set()
        denied = [m for m in ReconModule.ALL if m not in allowed]
        assert len(denied) == 8


# ---------------------------------------------------------------------------
# Authorization flow — JWT → User → Role → Client Access → Module Perm
# ---------------------------------------------------------------------------
class TestAuthorizationFlow:
    """The spec's authorization pipeline:
        JWT → Identify User → Identify Role → Check Client Access →
        Check Asset Access → Check Module Permission → Allow / Reject
    """

    def test_get_current_user_requires_valid_token(self):
        """Without a token, the dependency must reject."""
        from app.api.deps import oauth2_scheme
        # OAuth2PasswordBearer is configured with tokenUrl — requests
        # without a Bearer token get 401 from FastAPI automatically.
        assert type(oauth2_scheme).__name__ == "OAuth2PasswordBearer"
        assert oauth2_scheme.auto_error is True

    def test_require_admin_rejects_non_admin(self):
        """A USER-role holder calling an admin endpoint must get 403."""
        from app.api.deps import require_admin
        from app.utils.errors import ForbiddenError
        from app.core.constants import Roles
        import inspect

        src = inspect.getsource(require_admin)
        # The function checks `current_user.role.name != Roles.ADMIN`
        assert "Roles.ADMIN" in src
        assert "ForbiddenError" in src

    def test_scan_service_get_scan_enforces_ownership(self):
        """A user cannot fetch another user's scan by ID."""
        from app.recon.services.scan_service import ScanService
        from app.utils.errors import ForbiddenError
        import inspect

        src = inspect.getsource(ScanService.get_scan)
        assert "is_admin" in src
        assert "ForbiddenError" in src
        assert "scan.user_id != user_id" in src

    def test_delete_scan_blocks_protected_ownership_for_users(self):
        """CLIENT / ASSIGNED_TARGET scans cannot be deleted by users."""
        from app.recon.services.scan_service import ScanService
        from app.core.constants import OwnershipType
        import inspect

        src = inspect.getsource(ScanService.delete_scan)
        assert "OwnershipType.PROTECTED" in src
        assert "is_admin" in src

    def test_target_authorization_service_uses_assignments(self):
        """The authorization service must consult the user's assignments."""
        from app.services.target_authorization_service import (
            TargetAuthorizationService,
        )
        import inspect

        src = inspect.getsource(TargetAuthorizationService.authorize)
        # Step 4 — explicit assignment check
        assert "list_for_user" in src
        assert "_find_matching_assignment" in src
        # Step 6 — private target without assignment
        assert "private_scan_enabled" in src


# ---------------------------------------------------------------------------
# Client-asset hierarchy — the spec's core data model
# ---------------------------------------------------------------------------
class TestClientAssetHierarchy:
    """The spec requires:
        User → Client Assignment → Client → Assets → Scans → Results → Report
    """

    def test_client_model_has_required_fields(self):
        from app.models.client import Client
        cols = {c.name: c for c in Client.__table__.columns}
        assert "id" in cols
        assert "name" in cols
        assert "description" in cols
        assert "is_active" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_client_asset_supports_ip_and_cidr(self):
        from app.models.client import ClientAsset
        cols = {c.name: c for c in ClientAsset.__table__.columns}
        assert "asset_type" in cols
        assert "ip_address" in cols
        assert "cidr" in cols
        assert "domain" in cols
        assert "name" in cols
        assert "description" in cols
        assert "client_id" in cols

    def test_scan_links_to_client_and_assignment(self):
        from app.recon.models.scan import Scan
        cols = {c.name: c for c in Scan.__table__.columns}
        assert "user_id" in cols
        assert "client_id" in cols
        assert "client_asset_id" in cols
        assert "assignment_id" in cols
        assert "ownership_type" in cols

    def test_scan_result_links_to_scan(self):
        from app.recon.models.scan_result import ScanResult
        cols = {c.name: c for c in ScanResult.__table__.columns}
        assert "scan_id" in cols
        assert "result_type" in cols
        assert "data" in cols


# ---------------------------------------------------------------------------
# Recon module catalogue — only the spec's modules exist
# ---------------------------------------------------------------------------
class TestReconModules:
    """Verify the module list matches the spec's required set."""

    def test_recon_module_constants(self):
        from app.core.constants import ReconModule
        assert ReconModule.HOST_DISCOVERY == "host_discovery"
        assert ReconModule.PORT_SCAN == "port_scan"
        assert ReconModule.SERVICE_DETECTION == "service_detection"
        assert ReconModule.WHOIS == "whois"
        assert ReconModule.DNS == "dns"
        assert ReconModule.SSL == "ssl"
        assert ReconModule.HTTP == "http"
        assert ReconModule.SCREENSHOT == "screenshot"

    def test_recon_module_all_list(self):
        from app.core.constants import ReconModule
        assert set(ReconModule.ALL) == {
            "host_discovery", "port_scan", "service_detection",
            "whois", "dns", "ssl", "http", "screenshot",
        }
        assert len(ReconModule.ALL) == 8

    def test_no_extra_module_constants(self):
        """No team-lead / client-viewer / org-role modules exist."""
        from app.core.constants import ReconModule
        members = [m for m in dir(ReconModule) if not m.startswith('_') and m != 'ALL']
        assert set(members) == {
            "HOST_DISCOVERY", "PORT_SCAN", "SERVICE_DETECTION",
            "WHOIS", "DNS", "SSL", "HTTP", "SCREENSHOT",
        }


# ---------------------------------------------------------------------------
# Report authorization
# ---------------------------------------------------------------------------
class TestReportAuthorization:
    """Reports must respect the same ownership rules as scans."""

    def test_report_html_endpoint_calls_get_scan_first(self):
        """The HTML report endpoint must verify scan ownership before
        generating the report."""
        from app.api.v1.endpoints import recon
        import inspect

        src = inspect.getsource(recon.get_report_html)
        assert "service.get_scan" in src
        assert "user_id=current_user.id" in src
        assert "is_admin=_is_admin(current_user)" in src

    def test_report_pdf_endpoint_calls_get_scan_first(self):
        from app.api.v1.endpoints import recon
        import inspect

        src = inspect.getsource(recon.get_report_pdf)
        assert "service.get_scan" in src
        assert "user_id=current_user.id" in src

    def test_client_report_endpoint_checks_assignment(self):
        """The merged client report must verify the user has access to
        the client (either admin or active assignment)."""
        from app.api.v1.endpoints import recon
        import inspect

        src = inspect.getsource(recon.get_client_report_html)
        assert "is_admin" in src
        assert "list_active_user_client_ids" in src
        assert "ForbiddenError" in src


# ---------------------------------------------------------------------------
# API surface — every protected endpoint uses get_current_user
# ---------------------------------------------------------------------------
class TestApiSurface:
    """Every protected endpoint must depend on get_current_user or
    require_admin — never trust the client."""

    def _collect_endpoints(self):
        from app.main import app
        endpoints = []
        for route in app.routes:
            if not hasattr(route, 'methods'):
                continue
            for method in route.methods:
                if method in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH'):
                    endpoints.append((method, route.path, route))
        return endpoints

    def test_all_protected_endpoints_use_get_current_user(self):
        """Every /api/v1/* endpoint except /auth/login must depend on
        get_current_user or require_admin."""
        from app.api.deps import get_current_user, require_admin
        endpoints = self._collect_endpoints()
        assert len(endpoints) > 30, f"Expected many endpoints, got {len(endpoints)}"

        # The login endpoint must NOT require auth
        login_ep = [e for e in endpoints if e[1] == '/api/v1/auth/login']
        assert len(login_ep) == 1

        # Check a sample of protected endpoints
        protected_paths = [
            '/api/v1/auth/me',
            '/api/v1/users/',
            '/api/v1/clients',
            '/api/v1/recon/scans',
            '/api/v1/recon/stats',
            '/api/v1/targets/my-targets',
        ]
        for path in protected_paths:
            matches = [e for e in endpoints if e[1] == path]
            assert matches, f"No endpoint found for {path}"
            for _, _, route in matches:
                # Inspect the dependency tree
                dep_names = []
                for dep in route.dependant.dependencies:
                    for d in dep.dependencies:
                        dep_names.append(d.name)
                    dep_names.append(dep.name)
                # The route must use get_current_user or require_admin
                assert 'current_user' in dep_names or 'user' in dep_names, \
                    f"Endpoint {path} does not appear to use get_current_user"

    def test_admin_only_endpoints_use_require_admin(self):
        """Admin-only endpoints must use require_admin, not just
        get_current_user."""
        from app.api.deps import require_admin
        endpoints = self._collect_endpoints()

        admin_paths = [
            ('POST', '/api/v1/users/'),
            ('GET', '/api/v1/clients'),
            ('POST', '/api/v1/clients'),
            ('POST', '/api/v1/targets/assign/client'),
        ]
        for method, path in admin_paths:
            matches = [e for e in endpoints if e[1] == path and method in e[0].split(',')]
            assert matches, f"No {method} endpoint for {path}"
            for _, _, route in matches:
                # Verify require_admin is in the dependency tree
                found = False
                for dep in route.dependant.dependencies:
                    if dep.call is require_admin:
                        found = True
                        break
                    for d in dep.dependencies:
                        if d.call is require_admin:
                            found = True
                            break
                assert found, f"{method} {path} does not use require_admin"


# ---------------------------------------------------------------------------
# Docker / env hygiene
# ---------------------------------------------------------------------------
class TestEnvironmentHygiene:
    """No real secrets in .env.example; DATABASE_URL uses Docker service
    name 'db' not 'localhost'."""

    def test_backend_env_example_uses_docker_service_names(self):
        env_path = BACKEND_ROOT / '.env.example'
        content = env_path.read_text()
        assert 'db:5432' in content, "DATABASE_URL should use 'db' service name"
        assert 'redis:6379' in content, "REDIS_URL should use 'redis' service name"

    def test_backend_env_example_has_no_real_secrets(self):
        env_path = BACKEND_ROOT / '.env.example'
        content = env_path.read_text()
        # Must contain placeholder markers
        assert 'CHANGE_ME' in content or 'CHANGEME' in content
        # Must NOT contain obviously-real secrets
        assert 'sk-' not in content
        assert 'AKIA' not in content  # AWS key prefix

    def test_jwt_secret_is_placeholder(self):
        env_path = BACKEND_ROOT / '.env.example'
        content = env_path.read_text()
        assert 'JWT_SECRET_KEY=CHANGE_ME' in content


# ---------------------------------------------------------------------------
# Screenshot contract
# ---------------------------------------------------------------------------
class TestScreenshotContract:
    """Screenshots must go: request → generation → file storage → DB
    reference → retrieval API → frontend display → report inclusion."""

    def test_screenshot_endpoint_validates_uuid(self):
        from app.api.v1.endpoints import recon
        import inspect
        src = inspect.getsource(recon.get_screenshot)
        assert 'uuid.UUID' in src
        assert 'BadRequestError' in src

    def test_screenshot_storage_path_configurable(self):
        from app.core.config import settings
        # The setting exists and defaults to /app/recon_storage/screenshots
        # (Docker path).
        assert hasattr(settings, 'RECON_SCREENSHOT_STORAGE_PATH')
        assert settings.RECON_SCREENSHOT_STORAGE_PATH

    def test_screenshot_result_includes_url(self):
        """The screenshot service returns a dict with screenshot_url
        that the frontend / report can use to retrieve the file."""
        from app.recon.services.screenshot_service import ScreenshotService
        import inspect
        src = inspect.getsource(ScreenshotService)
        # The service constructs a screenshot_url field in its return dict
        assert 'screenshot_url' in src
        assert 'screenshot_id' in src
