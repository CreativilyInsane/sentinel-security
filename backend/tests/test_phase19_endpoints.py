# backend/tests/test_phase19_endpoints.py
"""Phase 19 endpoint contract tests.

These tests verify that every new Phase 19 endpoint:
  * Is registered on the FastAPI app
  * Has the expected HTTP method + path
  * Imports cleanly (no NameError / AttributeError at module load time)
  * Uses the new helpers (`ScanRead.from_scan`, `_resolve_report_user`,
    `get_current_user_or_none`) in a way that does NOT trigger a
    lazy-load in async context.

They also verify that the existing endpoints still have the expected
authorization guards (JWT or signed report token) and that the
hierarchical permission model is correctly represented in the
constants + schemas.

These tests do NOT require a live database — they use FastAPI's
TestClient with mocked dependencies where needed.
"""
import os
import sys
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _list_routes(app):
    """Return a list of (method, path) tuples for every registered route."""
    out = []
    for r in app.routes:
        if hasattr(r, "path") and hasattr(r, "methods"):
            for m in sorted(r.methods):
                out.append((m, r.path))
    return out


# ---------------------------------------------------------------------------
# App + route registration
# ---------------------------------------------------------------------------
class TestAppRoutes:
    """Verify the FastAPI app loads and every Phase 19 route is registered."""

    def test_app_loads(self):
        from app.main import app
        assert app is not None

    def test_sse_endpoint_registered(self):
        from app.main import app
        routes = _list_routes(app)
        assert ("GET", "/api/v1/recon/scans/{scan_id}/events") in routes

    def test_scan_report_token_endpoint_registered(self):
        from app.main import app
        routes = _list_routes(app)
        assert ("POST", "/api/v1/recon/scans/{scan_id}/report/token") in routes

    def test_client_report_token_endpoint_registered(self):
        from app.main import app
        routes = _list_routes(app)
        assert ("POST", "/api/v1/recon/clients/{client_id}/report/token") in routes

    def test_client_toggle_endpoint_registered(self):
        from app.main import app
        routes = _list_routes(app)
        assert ("POST", "/api/v1/targets/clients/{client_id}/toggle") in routes

    def test_asset_toggle_endpoint_registered(self):
        from app.main import app
        routes = _list_routes(app)
        assert ("POST", "/api/v1/targets/assets/{asset_id}/toggle") in routes

    def test_existing_active_toggle_still_registered(self):
        """The pre-Phase-19 active-target toggle endpoint is preserved
        for backwards compatibility."""
        from app.main import app
        routes = _list_routes(app)
        assert ("POST", "/api/v1/targets/active/toggle") in routes


# ---------------------------------------------------------------------------
# ScanRead.from_scan — no lazy-load
# ---------------------------------------------------------------------------
class TestScanReadFromScan:
    """Verify ``ScanRead.from_scan`` does NOT trigger a lazy-load of
    the ``module_statuses`` relationship.

    The bug: when a Scan ORM object was fetched via ``get_by_id`` (which
    does NOT eager-load relationships), accessing
    ``scan.module_statuses`` triggered a lazy-load in sync context,
    raising ``MissingGreenlet``.
    """

    def _make_detached_scan(self):
        """Build a Scan-like object that simulates the SQLAlchemy
        ``InstanceState.unloaded`` set including ``module_statuses``,
        so that ``sqla_inspect`` reports the relationship as not loaded.
        """
        from datetime import datetime, timezone
        from app.recon.models.scan import Scan
        scan = Scan(
            id=42, user_id=1, name="t", target="example.com",
            target_type="DOMAIN", status="QUEUED",
            modules=["host_discovery"], progress=0,
            ownership_type="USER_MANUAL",
            client_id=None, client_asset_id=None, assignment_id=None,
            celery_task_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return scan

    def test_from_scan_does_not_raise_on_detached_scan(self):
        """A Scan fetched via get_by_id (no eager-loading) must not
        raise MissingGreenlet when passed to from_scan.

        We simulate the situation by creating a Scan that is NOT
        attached to a session — ``sqla_inspect(scan).unloaded`` will
        contain ``module_statuses``, so from_scan should return an
        empty list instead of triggering a lazy-load.
        """
        from app.recon.schemas.scan import ScanRead
        scan = self._make_detached_scan()
        # This call previously raised MissingGreenlet.
        result = ScanRead.from_scan(scan)
        assert result.module_statuses == []

    def test_from_scan_with_explicit_module_statuses(self):
        """When the caller passes module_statuses explicitly, they are
        included in the result without accessing the relationship."""
        from app.recon.schemas.scan import ScanRead
        scan = self._make_detached_scan()
        ms = [
            SimpleNamespace(
                module_name="host_discovery", status="QUEUED",
                progress=0, error_message=None,
                started_at=None, completed_at=None,
            ),
        ]
        result = ScanRead.from_scan(scan, module_statuses=ms)
        assert len(result.module_statuses) == 1
        assert result.module_statuses[0].module_name == "host_discovery"
        assert result.module_statuses[0].status == "QUEUED"


# ---------------------------------------------------------------------------
# Module permission model — parent Network Module is computed, not stored
# ---------------------------------------------------------------------------
class TestModulePermissionParentToggle:
    """The parent Network Module toggle is NOT stored in the DB — it is
    computed as ``any(child.is_allowed for child in NETWORK_RECON_MODULES)``.
    """

    def test_network_module_constant_exists(self):
        from app.core.constants import ModulePermission
        assert ModulePermission.NETWORK_MODULE == "network_module"

    def test_network_module_not_in_all(self):
        """The parent identifier must NOT be persisted as a row in
        ``user_module_permissions`` — only the 8 child modules + 3
        page-level permissions are stored."""
        from app.core.constants import ModulePermission
        assert ModulePermission.NETWORK_MODULE not in ModulePermission.ALL

    def test_recon_modules_subset(self):
        from app.core.constants import ModulePermission
        # The 8 children of the parent Network Module.
        assert set(ModulePermission.RECON_MODULES) == {
            ModulePermission.HOST_DISCOVERY,
            ModulePermission.DNS,
            ModulePermission.PORT_SCAN,
            ModulePermission.SSL,
            ModulePermission.SERVICE_DETECTION,
            ModulePermission.HTTP,
            ModulePermission.WHOIS,
            ModulePermission.SCREENSHOT,
        }

    def test_get_permissions_read_includes_network_module_enabled(self):
        """``get_permissions_read`` returns the computed parent state."""
        from app.services.module_permission_service import ModulePermissionService
        from app.core.constants import ModulePermission

        svc = ModulePermissionService.__new__(ModulePermissionService)

        # Stub _load_rows to return all-False rows (simulating an
        # admin-disabled user).  Network module should compute to False.
        async def _stub_all_false(_uid):
            return [
                SimpleNamespace(module_name=m, is_allowed=False)
                for m in ModulePermission.ALL
            ]
        svc._load_rows = _stub_all_false
        result = asyncio_run(svc.get_permissions_read(1))
        assert result["network_module_enabled"] is False

        # Stub _load_rows to return at least one True Network child —
        # parent should compute to True.
        async def _stub_some_true(_uid):
            return [
                SimpleNamespace(module_name=ModulePermission.HOST_DISCOVERY, is_allowed=True),
                SimpleNamespace(module_name=ModulePermission.PORT_SCAN, is_allowed=False),
                SimpleNamespace(module_name=ModulePermission.ASSETS, is_allowed=True),
            ]
        svc._load_rows = _stub_some_true
        result = asyncio_run(svc.get_permissions_read(1))
        assert result["network_module_enabled"] is True

    def test_get_permissions_read_default_open_returns_true(self):
        """When no rows exist (default-open), network_module_enabled
        must be True."""
        from app.services.module_permission_service import ModulePermissionService

        svc = ModulePermissionService.__new__(ModulePermissionService)

        async def _stub_empty(_uid):
            return []
        svc._load_rows = _stub_empty
        result = asyncio_run(svc.get_permissions_read(1))
        assert result["is_default_open"] is True
        assert result["network_module_enabled"] is True


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Report endpoints — auth flow (JWT or signed token)
# ---------------------------------------------------------------------------
class TestReportEndpointAuthFlow:
    """The report endpoints must accept EITHER a JWT (via
    ``get_current_user_or_none``) OR a signed report token.  The
    helper that resolves the user is ``_resolve_report_user``.
    """

    def test_resolve_report_user_helper_exists(self):
        from app.api.v1.endpoints import recon
        assert hasattr(recon, "_resolve_report_user")

    def test_get_current_user_or_none_dep_exists(self):
        from app.api.deps import get_current_user_or_none
        assert callable(get_current_user_or_none)

    def test_report_html_endpoint_uses_resolve_helper(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.get_report_html)
        assert "_resolve_report_user" in src
        assert "token" in src  # accepts ?token= query param

    def test_report_pdf_endpoint_uses_resolve_helper(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.get_report_pdf)
        assert "_resolve_report_user" in src
        assert "token" in src

    def test_client_report_html_endpoint_uses_resolve_helper(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.get_client_report_html)
        assert "_resolve_report_user" in src
        assert "token" in src

    def test_resolve_helper_enforces_reports_module(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon._resolve_report_user)
        # The JWT path must run _require_module(ModulePermission.REPORTS).
        assert "_require_module" in src
        assert "ModulePermission.REPORTS" in src

    def test_resolve_helper_validates_token_target(self):
        """When a token is presented, the helper must validate that
        its ``client_id`` / ``scan_id`` claim matches the requested
        resource — prevents token-reuse across resources."""
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon._resolve_report_user)
        assert "expected_client_id" in src
        assert "expected_scan_id" in src

    def test_resolve_helper_audits_token_usage(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon._resolve_report_user)
        assert "AuditAction.REPORT_TOKEN_USED" in src


# ---------------------------------------------------------------------------
# Report token service — single-use enforcement
# ---------------------------------------------------------------------------
class TestReportTokenService:
    def test_issue_returns_jwt_string(self):
        from app.services.report_token_service import ReportTokenService
        token = ReportTokenService.issue(
            user_id=1, scan_id=42, fmt="html",
        )
        assert isinstance(token, str)
        assert token.count(".") == 2  # JWT shape: header.payload.sig

    def test_issue_includes_correct_claims(self):
        from app.services.report_token_service import ReportTokenService
        from app.core.config import settings
        from jose import jwt as jose_jwt
        token = ReportTokenService.issue(
            user_id=7, client_id=3, fmt="pdf",
        )
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["type"] == "report"
        assert payload["user_id"] == 7
        assert payload["client_id"] == 3
        assert payload["format"] == "pdf"
        assert "jti" in payload
        assert "exp" in payload


# ---------------------------------------------------------------------------
# Client/Asset permission toggles — endpoint shape
# ---------------------------------------------------------------------------
class TestClientAssetToggleEndpoints:
    def test_client_toggle_endpoint_signature(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.toggle_client_permission)
        assert "client_id: int" in src
        assert "payload: dict" in src
        assert "enabled" in src
        # Must verify the user has an active CLIENT assignment (admin bypass).
        assert "list_active_user_client_ids" in src
        # Must audit the toggle.
        assert "AuditAction.CLIENT_TOGGLED" in src

    def test_asset_toggle_endpoint_signature(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.toggle_asset_permission)
        assert "asset_id: int" in src
        assert "payload: dict" in src
        assert "enabled" in src
        # Must verify the user has access to the asset's parent client.
        assert "list_active_user_client_ids" in src
        # Must audit the toggle.
        assert "AuditAction.ASSET_TOGGLED" in src

    def test_client_toggle_endpoint_calls_disable_all_for_client(self):
        """When the parent client is toggled OFF, the endpoint must
        cascade to disable all child asset permissions."""
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.toggle_client_permission)
        assert "disable_all_for_client" in src


# ---------------------------------------------------------------------------
# TargetAuthorizationService — consults new permission tables
# ---------------------------------------------------------------------------
class TestTargetAuthorizationClientAssetPermissions:
    """The authorization service must consult the per-user client/asset
    permission tables when deciding whether to allow a scan."""

    def test_service_has_perm_repos(self):
        from app.services.target_authorization_service import (
            TargetAuthorizationService,
        )
        svc = TargetAuthorizationService.__new__(TargetAuthorizationService)
        # The repos are set up in __init__, but we just verify the
        # attribute names exist on the class (they will be set when
        # __init__ is called for real).
        # We can check the __init__ source:
        src = inspect.getsource(TargetAuthorizationService.__init__)
        assert "client_perm_repo" in src
        assert "asset_perm_repo" in src

    def test_authorize_checks_client_perm(self):
        from app.services.target_authorization_service import (
            TargetAuthorizationService,
        )
        src = inspect.getsource(TargetAuthorizationService.authorize)
        assert "client_perm_repo" in src
        assert "is_enabled" in src
        # Must check both client_id and client_asset_id when an
        # assignment matches.
        assert "client_id" in src
        assert "client_asset_id" in src

    def test_list_authorized_targets_filters_disabled(self):
        """``list_authorized_targets`` must exclude clients/assets that
        have a per-user permission row with enabled=False."""
        from app.services.target_authorization_service import (
            TargetAuthorizationService,
        )
        src = inspect.getsource(TargetAuthorizationService.list_authorized_targets)
        assert "disabled_client_ids" in src
        assert "disabled_asset_ids" in src


# ---------------------------------------------------------------------------
# ScanService — per-module status tracking
# ---------------------------------------------------------------------------
class TestScanServiceModuleStatusTracking:
    def test_scan_service_has_module_status_repo(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.__init__)
        assert "module_status_repo" in src

    def test_create_scan_initialises_module_statuses(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.create_scan)
        assert "init_for_scan" in src

    def test_execute_scan_marks_modules_running(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.execute_scan)
        assert "ScanModuleStatusValue.RUNNING" in src
        assert "ScanModuleStatusValue.COMPLETED" in src
        assert "ScanModuleStatusValue.FAILED" in src

    def test_execute_scan_publishes_events(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.execute_scan)
        assert "_publish_scan_event" in src
        assert "module_started" in src
        assert "module_completed" in src
        assert "module_failed" in src

    def test_cancel_scan_cancels_pending_modules(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.cancel_scan)
        assert "cancel_pending" in src

    def test_publish_scan_event_uses_redis_pubsub(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService._publish_scan_event)
        assert "redis_client.publish" in src
        assert "scan_events:" in src


# ---------------------------------------------------------------------------
# ScanModuleStatusRepository — methods exist
# ---------------------------------------------------------------------------
class TestScanModuleStatusRepository:
    def test_list_for_scan_exists(self):
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        assert hasattr(ScanModuleStatusRepository, "list_for_scan")

    def test_init_for_scan_exists(self):
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        assert hasattr(ScanModuleStatusRepository, "init_for_scan")

    def test_set_module_status_exists(self):
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        assert hasattr(ScanModuleStatusRepository, "set_module_status")

    def test_cancel_pending_exists(self):
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        assert hasattr(ScanModuleStatusRepository, "cancel_pending")


# ---------------------------------------------------------------------------
# UserClientPermission + UserAssetPermission models
# ---------------------------------------------------------------------------
class TestUserClientAssetPermissionModels:
    def test_user_client_permission_model_exists(self):
        from app.models.user_client_permission import UserClientPermission
        assert UserClientPermission.__tablename__ == "user_client_permissions"

    def test_user_asset_permission_model_exists(self):
        from app.models.user_client_permission import UserAssetPermission
        assert UserAssetPermission.__tablename__ == "user_asset_permissions"

    def test_user_client_permission_unique_constraint(self):
        from app.models.user_client_permission import UserClientPermission
        # The unique constraint name must match the migration.
        constraint_names = [
            c.name for c in UserClientPermission.__table_args__
            if hasattr(c, "name") and c.name
        ]
        assert "uq_user_client_perm" in constraint_names

    def test_user_asset_permission_unique_constraint(self):
        from app.models.user_client_permission import UserAssetPermission
        constraint_names = [
            c.name for c in UserAssetPermission.__table_args__
            if hasattr(c, "name") and c.name
        ]
        assert "uq_user_asset_perm" in constraint_names


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------
class TestUserClientPermissionRepository:
    def test_is_enabled_exists(self):
        from app.repositories.user_client_permission_repository import (
            UserClientPermissionRepository,
        )
        assert hasattr(UserClientPermissionRepository, "is_enabled")

    def test_set_enabled_exists(self):
        from app.repositories.user_client_permission_repository import (
            UserClientPermissionRepository,
        )
        assert hasattr(UserClientPermissionRepository, "set_enabled")

    def test_disable_all_for_client_exists(self):
        from app.repositories.user_client_permission_repository import (
            UserClientPermissionRepository,
        )
        assert hasattr(UserClientPermissionRepository, "disable_all_for_client")


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------
class TestMigrations:
    def test_migration_0010_exists(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        revs = {r.revision: r for r in script.walk_revisions()}
        assert "0010" in revs
        assert revs["0010"].down_revision == "0009"

    def test_migration_0011_exists(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        revs = {r.revision: r for r in script.walk_revisions()}
        assert "0011" in revs
        assert revs["0011"].down_revision == "0010"

    def test_migration_chain_is_complete(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        revs = {r.revision: r for r in script.walk_revisions()}
        # Walk from head down to base — every down_revision must exist.
        head = script.get_current_head()
        assert head is not None
        cur = head
        count = 0
        while cur is not None and count < 100:
            r = revs.get(cur)
            assert r is not None, f"Revision {cur} not found in script directory"
            cur = r.down_revision
            count += 1
        # We should have walked through all 11 revisions.
        assert count == 11


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
class TestScanModuleStatusConstants:
    def test_scan_module_status_value_exists(self):
        from app.core.constants import ScanModuleStatusValue
        assert ScanModuleStatusValue.QUEUED == "QUEUED"
        assert ScanModuleStatusValue.RUNNING == "RUNNING"
        assert ScanModuleStatusValue.COMPLETED == "COMPLETED"
        assert ScanModuleStatusValue.FAILED == "FAILED"
        assert ScanModuleStatusValue.CANCELLED == "CANCELLED"

    def test_terminal_set(self):
        from app.core.constants import ScanModuleStatusValue
        assert ScanModuleStatusValue.TERMINAL == {
            "COMPLETED", "FAILED", "CANCELLED",
        }

    def test_active_set(self):
        from app.core.constants import ScanModuleStatusValue
        assert ScanModuleStatusValue.ACTIVE == {"QUEUED", "RUNNING"}


class TestAuditActions:
    def test_phase19_audit_actions_exist(self):
        from app.core.constants import AuditAction
        assert AuditAction.CLIENT_TOGGLED == "CLIENT_TOGGLED"
        assert AuditAction.ASSET_TOGGLED == "ASSET_TOGGLED"
        assert AuditAction.REPORT_TOKEN_ISSUED == "REPORT_TOKEN_ISSUED"
        assert AuditAction.REPORT_TOKEN_USED == "REPORT_TOKEN_USED"
        assert AuditAction.MODULE_STATUS_UPDATED == "MODULE_STATUS_UPDATED"


# ---------------------------------------------------------------------------
# SSE endpoint — auth + structure
# ---------------------------------------------------------------------------
class TestSseEndpoint:
    def test_sse_endpoint_accepts_token_query_param(self):
        """EventSource cannot set custom headers, so the SSE endpoint
        must accept the JWT as a ?token= query param fallback."""
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.scan_events)
        assert "token: Optional[str]" in src

    def test_sse_endpoint_sends_snapshot(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.scan_events)
        assert "snapshot" in src

    def test_sse_endpoint_subscribes_to_redis_pubsub(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.scan_events)
        assert "pubsub" in src
        assert "scan_events:" in src

    def test_sse_endpoint_closes_on_terminal_state(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.scan_events)
        assert "ScanStatus.COMPLETED" in src
        assert "ScanStatus.FAILED" in src
        assert "ScanStatus.CANCELLED" in src

    def test_sse_endpoint_sends_keepalive(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.scan_events)
        assert "keepalive" in src


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------
class TestRequirements:
    def test_sse_starlette_in_requirements(self):
        req_path = BACKEND_ROOT / "requirements.txt"
        content = req_path.read_text()
        assert "sse-starlette" in content


# ---------------------------------------------------------------------------
# Pydantic schema shapes
# ---------------------------------------------------------------------------
class TestSchemas:
    def test_scan_read_includes_module_statuses(self):
        from app.recon.schemas.scan import ScanRead
        # Pydantic v2 — model_fields
        assert "module_statuses" in ScanRead.model_fields

    def test_scan_module_status_read_shape(self):
        from app.recon.schemas.scan import ScanModuleStatusRead
        fields = set(ScanModuleStatusRead.model_fields.keys())
        assert fields == {
            "module_name", "status", "progress",
            "error_message", "started_at", "completed_at",
        }

    def test_module_permissions_read_includes_network_module_enabled(self):
        from app.api.v1.endpoints.users import ModulePermissionsRead
        assert "network_module_enabled" in ModulePermissionsRead.model_fields


# ---------------------------------------------------------------------------
# Frontend build artifacts (smoke check)
# ---------------------------------------------------------------------------
class TestFrontendBuildArtifacts:
    """Verify the frontend's new code paths compile.  We can't run
    vite here without npm install, so we just check that the key
    files exist and have the expected exports."""

    def test_scan_details_uses_eventsource(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "ScanDetails.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "EventSource" in src
        assert "scanEventsUrl" in src
        assert "module_started" in src
        assert "module_completed" in src
        assert "module_failed" in src

    def test_user_module_settings_has_parent_toggle(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "UserModuleSettings.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "toggleNetworkParent" in src
        assert "networkParentEnabled" in src
        assert "networkChildrenSnapshotRef" in src

    def test_targets_page_has_client_toggle(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "Targets.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "handleClientToggle" in src
        assert "handleAssetToggle" in src
        assert "toggleClientPermission" in src
        assert "toggleAssetPermission" in src

    def test_targets_page_does_not_use_raw_window_open_for_report(self):
        """The bug fix — Targets.tsx must NOT call window.open() with
        the raw /api/v1/recon/clients/{id}/report/html URL.  It must
        use the blob-download approach via clientsApi.fetchClientReportHtml."""
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "Targets.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "window.open(`/api/v1/recon/clients" not in src
        assert "fetchClientReportHtml" in src

    def test_client_detail_uses_blob_download(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "ClientDetail.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "window.open(`/api/v1/recon/clients" not in src
        assert "fetchClientReportHtml" in src

    def test_user_table_does_not_use_squares_2x2_icon(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "components" / "users" / "UserTable.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "Squares2X2Icon" not in src
        assert "AdjustmentsHorizontalIcon" in src


# ---------------------------------------------------------------------------
# Sentinel v1.1 change request — merged my-clients + Admin Assignments
# page + screenshot data-URI embedding.
# ---------------------------------------------------------------------------
class TestMergedMyClientsEndpoint:
    """The /targets/my-clients endpoint must merge BOTH ``CLIENT``
    assignments AND ``DIRECT_TARGET`` assignments under their parent
    Client — direct targets must NEVER appear as a separate top-level
    group.  Each asset must carry an ``assigned_via`` field so the
    frontend can show a "Direct" vs "Client" distinction badge.
    """

    def test_my_clients_endpoint_merges_direct_targets(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.my_clients)
        # Must load ALL active assignments (not just CLIENT-type).
        assert "list_for_user" in src
        # Must group by client_id.
        assert "by_client" in src or "by_client:" in src
        # Must handle orphan direct targets (no client_id).
        assert "orphan" in src.lower()
        # Must emit the assigned_via field per asset.
        assert "assigned_via" in src
        # Must NOT silently filter out disabled assets — the enabled flag
        # is per-user and toggled separately; assets remain visible.
        assert "asset_perms.get" in src

    def test_my_clients_endpoint_returns_assignment_id_per_asset(self):
        """Each asset in the response must carry an ``assignment_id``
        so the frontend can toggle active-target visibility and know
        which assignment to disable/enable without cross-referencing
        the /targets/my-targets list."""
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.my_clients)
        assert "assignment_id" in src

    def test_my_clients_endpoint_handles_synthetic_assets(self):
        """Direct-target assignments whose value is NOT one of the
        client's existing ClientAsset rows must be surfaced as a
        synthetic asset entry (id=null) under the parent Client."""
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.my_clients)
        # Synthetic asset entry must have id=null
        assert '"id": None' in src or '"id":None' in src

    def test_my_clients_endpoint_handles_client_assignment_only(self):
        """When the user has a CLIENT assignment, ALL active client
        assets must appear in the response (not just the assigned one).
        Each asset is marked ``assigned_via='CLIENT'`` unless the
        same asset is ALSO a direct target (then 'DIRECT_TARGET')."""
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.my_clients)
        assert "has_client_assignment" in src
        assert "list_for_client" in src
        assert '"CLIENT"' in src
        assert '"DIRECT_TARGET"' in src


class TestAdminAssignmentsPage:
    """Section #20 of the Sentinel change request: assignment
    management must move OUT of the Client Details page and into a
    dedicated Admin-only Assignments page at /admin/assignments.
    """

    def test_assignments_route_path_defined(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "routes" / "paths.ts"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "ASSIGNMENTS" in src
        assert "/admin/assignments" in src

    def test_assignments_page_exists(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "Assignments.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "export const Assignments" in src
        # Must support both assignment modes per section #22-24.
        assert "Assign Client" in src
        assert "Assign Direct Target" in src
        # Must show existing assignments with enable/disable/remove per #26-27.
        assert "Enable" in src
        assert "Disable" in src
        assert "Remove" in src
        # Must support the ?client_id= deep-link filter from ClientDetail.
        assert "useSearchParams" in src
        assert "client_id" in src

    def test_assignments_route_is_admin_only(self):
        """The /admin/assignments route MUST be wrapped in <AdminRoute>
        so a regular user cannot access it (section #25)."""
        p = BACKEND_ROOT.parent / "frontend" / "src" / "App.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "ROUTES.ASSIGNMENTS" in src
        # The ASSIGNMENTS route must live INSIDE the <AdminRoute> wrapper
        # (between the <Route element={<AdminRoute />}> opening and the
        # closing </Route>).
        admin_route_block = src.split("<Route element={<AdminRoute />}>")[1]
        assert "ROUTES.ASSIGNMENTS" in admin_route_block

    def test_sidebar_links_to_assignments_page(self):
        p = BACKEND_ROOT.parent / "frontend" / "src" / "components" / "layout" / "Sidebar.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "ROUTES.ASSIGNMENTS" in src
        assert "Assignments" in src

    def test_client_detail_does_not_manage_assignments(self):
        """Per section #20, ClientDetail.tsx must NOT contain
        assignment-management UI (assign button, AssignModal, or
        per-row remove action).  It may keep a read-only list for
        context."""
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "ClientDetail.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        # The AssignModal component must be gone.
        assert "const AssignModal" not in src
        # The "Assign" button must be gone — replaced by a "Manage in
        # Assignments" deep-link.
        assert "Manage in Assignments" in src
        # Mutations for assign / direct-target / delete-assignment must
        # no longer be imported.
        assert "useAssignClient" not in src
        assert "useAssignDirectTarget" not in src
        assert "useDeleteAssignment" not in src


class TestTargetsPageStateSync:
    """Sections #4-12 of the Sentinel change request: asset/client
    toggles must immediately update the UI without a manual refresh,
    and the invalidation must use the CORRECT query-cache keys.
    """

    def test_targets_page_invalidates_correct_query_keys(self):
        """The original bug was that handleClientToggle / handleAssetToggle
        invalidated ``['targets', 'my-clients']`` (wrong prefix) instead
        of ``['my-clients']`` — so the cache never refreshed.  The fix
        uses the actual query keys."""
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "Targets.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        # Correct keys (no 'targets' prefix).
        assert "invalidateQueries({ queryKey: ['my-clients'] })" in src
        assert "invalidateQueries({ queryKey: ['my-targets'] })" in src
        # Old buggy keys must be GONE.
        assert "['targets', 'my-clients']" not in src
        assert "['targets', 'my-targets']" not in src

    def test_targets_page_uses_optimistic_update_with_rollback(self):
        """Per sections #52-53, the UI must update immediately and roll
        back on API failure."""
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "Targets.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        assert "setQueryData" in src  # optimistic update
        assert "getQueryData" in src  # snapshot for rollback
        # Roll back the optimistic update on error.
        assert "qc.setQueryData(['my-clients'], prev)" in src

    def test_targets_page_has_no_separate_direct_targets_section(self):
        """Per sections #17-19, direct targets must NOT appear as a
        separate top-level section — they must be merged under their
        owning Client."""
        p = BACKEND_ROOT.parent / "frontend" / "src" / "pages" / "Targets.tsx"
        if not p.exists():
            pytest.skip("frontend not present in this layout")
        src = p.read_text()
        # The old `directTargets` derived array (from my-targets list)
        # must be gone — we now get assignment_id directly from my-clients.
        assert "directTargets = targets.filter" not in src
        assert "const directTargets" not in src
        # The new assigned_via badge must be present.
        assert "assigned_via" in src
        assert "'DIRECT_TARGET'" in src or '"DIRECT_TARGET"' in src


class TestHtmlReportScreenshotEmbedding:
    """Sections #33-38 of the Sentinel change request: HTML reports
    must embed screenshots so they actually display when the report
    is opened (currently broken because the relative /api/v1/...
    URL cannot resolve against a Blob URL).
    """

    def test_report_service_has_screenshot_data_uri_helper(self):
        from app.recon.services.report_service import ReportService
        assert hasattr(ReportService, "_screenshot_data_uri")
        src = inspect.getsource(ReportService._screenshot_data_uri)
        # Must read the PNG file from disk and base64-encode it.
        assert "base64" in src
        assert "data:image/png;base64," in src
        # Must return None when the file is missing (so callers can
        # render a placeholder instead of a broken img link).
        assert "return None" in src

    def test_html_report_uses_data_uri_not_relative_url(self):
        """The scan-level HTML report must NOT use the relative
        /api/v1/recon/screenshots/{id} URL anymore — it must embed
        the screenshot as a base64 data URI."""
        from app.recon.services.report_service import ReportService
        # Scan-level HTML
        html_src = inspect.getsource(ReportService.generate_html)
        assert "_screenshot_data_uri" in html_src
        assert "screenshot_url_full" not in html_src
        # Client-level (merged) HTML
        client_html_src = inspect.getsource(ReportService.generate_client_html)
        assert "_screenshot_data_uri" in client_html_src
        assert "Screenshots" in client_html_src  # section must exist now

    def test_pdf_report_still_embeds_image_bytes(self):
        """The PDF report must continue to embed the actual PNG bytes
        via reportlab's Image flowable (no regression)."""
        from app.recon.services.report_service import ReportService
        pdf_src = inspect.getsource(ReportService.generate_pdf)
        assert "RLImage" in pdf_src or "Image(" in pdf_src
        assert "RECON_SCREENSHOT_STORAGE_PATH" in pdf_src


# ---------------------------------------------------------------------------
# Admin-only authorization for assignment endpoints — section #25.
# ---------------------------------------------------------------------------
class TestAssignmentEndpointAdminOnly:
    """Section #25: only Admin can manage assignments.  The
    POST /targets/assign/client, POST /targets/assign/direct,
    PUT /targets/assignments/{id}, and DELETE /targets/assignments/{id}
    endpoints must all depend on ``require_admin`` — not just
    ``get_current_user``.
    """

    def test_assign_client_endpoint_requires_admin(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.assign_client)
        assert "require_admin" in src

    def test_assign_direct_target_endpoint_requires_admin(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.assign_direct_target)
        assert "require_admin" in src

    def test_list_assignments_endpoint_requires_admin(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.list_assignments)
        assert "require_admin" in src

    def test_update_assignment_endpoint_requires_admin(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.update_assignment)
        assert "require_admin" in src

    def test_delete_assignment_endpoint_requires_admin(self):
        from app.api.v1.endpoints import targets
        src = inspect.getsource(targets.delete_assignment)
        assert "require_admin" in src

    def test_toggle_endpoints_do_not_require_admin(self):
        """The per-user toggle endpoints (clients/{id}/toggle and
        assets/{id}/toggle) must NOT require admin — the user toggles
        their OWN access.  They must use ``get_current_user`` so
        non-admins can use them."""
        from app.api.v1.endpoints import targets
        client_src = inspect.getsource(targets.toggle_client_permission)
        assert "get_current_user" in client_src
        assert "require_admin" not in client_src
        asset_src = inspect.getsource(targets.toggle_asset_permission)
        assert "get_current_user" in asset_src
        assert "require_admin" not in asset_src
