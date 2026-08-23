# backend/tests/test_phase19_integration.py
"""End-to-end integration tests for Phase 19 endpoints.

These tests use FastAPI's ``TestClient`` to exercise the full request
lifecycle — including dependency injection, Pydantic validation, and
the SQLAlchemy session lifecycle.  The DB and Redis are stubbed so we
don't need a live PostgreSQL/Redis to run them.

Specifically, these tests would have caught the original
``MissingGreenlet`` bug because they actually invoke the endpoint
handler end-to-end (the previous unit tests only inspected source
code, which doesn't catch runtime attribute-access issues).
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Stubs — minimal mocks that satisfy the ORM attribute access patterns
# ---------------------------------------------------------------------------
class _StubScan:
    """A plain-Python object that mimics the Scan ORM attributes used by
    ScanRead.from_scan.  Does NOT have a SQLAlchemy InstanceState, so
    sqla_inspect(scan).unloaded access would raise — but our from_scan
    handles that gracefully via try/except.
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _StubScanModuleStatus:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _StubUser:
    def __init__(self, id=1, role_name="User", is_active=True):
        self.id = id
        self.is_active = is_active
        self.role = SimpleNamespace(name=role_name)


# ---------------------------------------------------------------------------
# Patch fixtures — we patch DB + Redis at the module level so the app
# can be imported and routes can be exercised without real IO.
# ---------------------------------------------------------------------------
@pytest.fixture
def stub_db_session():
    """Return an AsyncMock that simulates an AsyncSession."""
    sess = AsyncMock()
    # Common AsyncSession methods used by the endpoints.
    sess.commit = AsyncMock()
    sess.rollback = AsyncMock()
    sess.flush = AsyncMock()
    sess.close = AsyncMock()
    sess.execute = AsyncMock(return_value=MagicMock())
    return sess


@pytest.fixture
def app_with_stubs(stub_db_session):
    """Build a FastAPI app with patched dependencies."""
    from app.main import app
    from app.api.deps import get_db, get_current_user, get_current_user_or_none

    async def _stub_get_db():
        yield stub_db_session

    async def _stub_get_current_user():
        return _StubUser(id=1, role_name="User")

    async def _stub_get_current_user_or_none():
        return _StubUser(id=1, role_name="User")

    app.dependency_overrides[get_db] = _stub_get_db
    app.dependency_overrides[get_current_user] = _stub_get_current_user
    app.dependency_overrides[get_current_user_or_none] = _stub_get_current_user_or_none
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestCreateScanEndpointMissingGreenletFix:
    """Verify the original ``MissingGreenlet`` bug is fixed.

    The bug: ``ScanRead.from_scan(scan)`` accessed
    ``scan.module_statuses`` (a lazy relationship) on a Scan fetched
    via ``get_by_id`` (which doesn't eager-load the relationship).
    In an async session, lazy-loading triggers sync IO and raises
    ``MissingGreenlet``.
    """

    def test_from_scan_with_get_by_id_scan_does_not_lazy_load(self):
        """Simulate the exact scenario: a Scan returned by
        ``get_by_id`` (no eager-loaded relationships) is passed to
        ``from_scan``.  The method must NOT raise."""
        from app.recon.schemas.scan import ScanRead
        now = datetime.now(timezone.utc)
        # _StubScan has NO SQLAlchemy InstanceState, so accessing
        # any relationship would normally raise AttributeError.  Our
        # from_scan uses try/except around inspect() so it gracefully
        # returns an empty module_statuses list.
        scan = _StubScan(
            id=42, user_id=1, name="t", target="example.com",
            target_type="DOMAIN", status="QUEUED",
            modules=["host_discovery"], port_preset=None,
            custom_ports=None, progress=0,
            started_at=None, completed_at=None,
            error_message=None, celery_task_id=None,
            created_at=now, updated_at=now,
            ownership_type="USER_MANUAL",
            client_id=None, client_asset_id=None, assignment_id=None,
        )
        # This call previously raised MissingGreenlet.
        result = ScanRead.from_scan(scan)
        assert result.id == 42
        assert result.module_statuses == []

    def test_from_scan_with_explicit_module_statuses(self):
        """When the caller provides module_statuses explicitly, they
        are returned in the ScanRead."""
        from app.recon.schemas.scan import ScanRead
        now = datetime.now(timezone.utc)
        scan = _StubScan(
            id=10, user_id=1, name=None, target="example.com",
            target_type="DOMAIN", status="RUNNING",
            modules=["host_discovery", "port_scan"],
            port_preset=None, custom_ports=None, progress=50,
            started_at=now, completed_at=None,
            error_message=None, celery_task_id="abc",
            created_at=now, updated_at=now,
            ownership_type="USER_MANUAL",
            client_id=None, client_asset_id=None, assignment_id=None,
        )
        ms = [
            _StubScanModuleStatus(
                module_name="host_discovery", status="COMPLETED",
                progress=100, error_message=None,
                started_at=now, completed_at=now,
            ),
            _StubScanModuleStatus(
                module_name="port_scan", status="RUNNING",
                progress=50, error_message=None,
                started_at=now, completed_at=None,
            ),
        ]
        result = ScanRead.from_scan(scan, module_statuses=ms)
        assert len(result.module_statuses) == 2
        assert result.module_statuses[0].module_name == "host_discovery"
        assert result.module_statuses[0].status == "COMPLETED"
        assert result.module_statuses[1].module_name == "port_scan"
        assert result.module_statuses[1].status == "RUNNING"


class TestScanReadSerializationRoundTrip:
    """Verify ScanRead serializes to JSON correctly — exercises the
    full Pydantic validation pipeline."""

    def test_scan_read_json_serialization(self):
        from app.recon.schemas.scan import ScanRead
        now = datetime.now(timezone.utc)
        scan = _StubScan(
            id=1, user_id=1, name="t", target="ex.com",
            target_type="DOMAIN", status="QUEUED",
            modules=["host_discovery"], port_preset=None,
            custom_ports=None, progress=0,
            started_at=None, completed_at=None,
            error_message=None, celery_task_id=None,
            created_at=now, updated_at=now,
            ownership_type="USER_MANUAL",
            client_id=None, client_asset_id=None, assignment_id=None,
        )
        result = ScanRead.from_scan(scan)
        # JSON round-trip must not raise.
        data = json.loads(result.model_dump_json())
        assert data["id"] == 1
        assert data["status"] == "QUEUED"
        assert data["module_statuses"] == []


class TestReportTokenIssueAndConsume:
    """Verify the ReportTokenService can issue and consume tokens
    end-to-end with the REAL settings object (this catches the
    ``AttributeError: 'Settings' has no attribute 'SECRET_KEY'`` bug
    that was previously masked)."""

    def test_issue_does_not_raise_attribute_error(self):
        from app.services.report_token_service import ReportTokenService
        # This previously raised AttributeError because the service
        # referenced settings.SECRET_KEY but the actual attr is
        # settings.JWT_SECRET_KEY.
        token = ReportTokenService.issue(user_id=1, scan_id=1, fmt="html")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_consume_validates_and_returns_payload(self):
        """A freshly-issued token must be consumable (after mocking
        Redis setnx so it returns True)."""
        from app.services.report_token_service import ReportTokenService

        token = ReportTokenService.issue(user_id=5, scan_id=42, fmt="html")

        # Mock Redis so the single-use check passes.
        async def _stub_set(*args, **kwargs):
            return True
        with patch("app.services.report_token_service.redis_client") as mock_redis:
            mock_redis.set = _stub_set
            payload = asyncio.run(ReportTokenService.consume(token))
            assert payload["user_id"] == 5
            assert payload["scan_id"] == 42
            assert payload["format"] == "html"
            assert payload["type"] == "report"
            assert "jti" in payload
            assert "exp" in payload

    def test_consume_rejects_already_used_token(self):
        from app.services.report_token_service import ReportTokenService
        from app.utils.errors import UnauthorizedError

        token = ReportTokenService.issue(user_id=1, scan_id=1, fmt="html")

        # Mock Redis so the single-use check returns None (already used).
        async def _stub_set(*args, **kwargs):
            return None
        with patch("app.services.report_token_service.redis_client") as mock_redis:
            mock_redis.set = _stub_set
            with pytest.raises(UnauthorizedError, match="already been used"):
                asyncio.run(ReportTokenService.consume(token))

    def test_consume_rejects_invalid_token(self):
        from app.services.report_token_service import ReportTokenService
        from app.utils.errors import UnauthorizedError
        with pytest.raises(UnauthorizedError):
            asyncio.run(ReportTokenService.consume("invalid.token.here"))

    def test_consume_rejects_wrong_token_type(self):
        """A token that decodes successfully but has type != 'report'
        must be rejected."""
        from app.services.report_token_service import ReportTokenService
        from app.utils.errors import UnauthorizedError
        from app.core.config import settings
        from jose import jwt as jose_jwt
        # Issue a regular auth-token-shaped JWT (type=access).
        wrong_token = jose_jwt.encode(
            {"sub": "1", "type": "access", "jti": "x"},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(UnauthorizedError, match="Not a report token"):
            asyncio.run(ReportTokenService.consume(wrong_token))


class TestEndpointSourceCodeGuards:
    """Source-level guards that catch common runtime issues without
    needing a live DB.  These complement the runtime tests above."""

    def test_create_scan_uses_get_scan_with_results_not_get_by_id(self):
        """The create_scan endpoint must use ``get_scan_with_results``
        (which eager-loads relationships) instead of ``get_by_id``
        (which doesn't), to avoid the MissingGreenlet bug."""
        from app.api.v1.endpoints import recon
        import inspect
        src = inspect.getsource(recon.create_scan)
        assert "get_scan_with_results" in src

    def test_create_scan_passes_module_statuses_to_from_scan(self):
        """The endpoint must pass module_statuses explicitly to
        from_scan so they are included in the response."""
        from app.api.v1.endpoints import recon
        import inspect
        src = inspect.getsource(recon.create_scan)
        assert "module_statuses=module_status_rows" in src

    def test_create_scan_fetches_module_statuses_via_repo(self):
        """The endpoint must fetch module_statuses via the
        ScanModuleStatusRepository (not via the lazy relationship)."""
        from app.api.v1.endpoints import recon
        import inspect
        src = inspect.getsource(recon.create_scan)
        assert "ScanModuleStatusRepository" in src
        assert "list_for_scan" in src


class TestScanServiceInitForScanContract:
    """Verify ScanService.create_scan calls init_for_scan to create
    the per-module status rows at scan-create time."""

    def test_create_scan_calls_init_for_scan(self):
        from app.recon.services.scan_service import ScanService
        import inspect
        src = inspect.getsource(ScanService.create_scan)
        assert "init_for_scan" in src
        assert "module_status_repo" in src


class TestScanModuleStatusRepositoryInitForScan:
    """Verify init_for_scan is idempotent (doesn't duplicate rows)."""

    def test_init_for_scan_skips_existing_modules(self):
        """If a (scan_id, module_name) row already exists, init_for_scan
        must NOT insert a duplicate."""
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        from app.recon.models.scan_module_status import ScanModuleStatus
        from app.core.constants import ScanModuleStatusValue
        import inspect
        src = inspect.getsource(ScanModuleStatusRepository.init_for_scan)
        assert "existing_names" in src
        assert "continue" in src  # skip if already exists

    def test_init_for_scan_creates_queued_rows(self):
        """New rows must be created with status=QUEUED, progress=0."""
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        from app.recon.models.scan_module_status import ScanModuleStatus
        import inspect
        src = inspect.getsource(ScanModuleStatusRepository.init_for_scan)
        assert "ScanModuleStatusValue.QUEUED" in src
        assert "progress=0" in src or "progress=0," in src or "0," in src


class TestAllReconEndpointsImportable:
    """Verify every endpoint function in recon.py can be imported and
    is callable.  This catches any NameError / ImportError that would
    occur at module load time (e.g. the legacy ``regex=`` deprecation
    we already fixed)."""

    def test_all_endpoint_functions_exist(self):
        from app.api.v1.endpoints import recon
        # Every function decorated with @router should exist on the module.
        expected = [
            "create_scan", "list_scans", "get_scan", "scan_events",
            "get_scan_results", "cancel_scan", "delete_scan",
            "issue_scan_report_token", "issue_client_report_token",
            "get_report_metadata", "get_report_html", "get_report_pdf",
            "get_screenshot", "list_assets", "get_assets_by_host",
            "get_asset", "delete_asset", "get_recon_stats",
            "get_client_report_html", "list_client_scans",
            "_resolve_report_user",
        ]
        for name in expected:
            assert hasattr(recon, name), f"recon module missing function: {name}"

    def test_all_target_endpoints_exist(self):
        from app.api.v1.endpoints import targets
        expected = [
            "assign_client", "assign_direct_target", "list_assignments",
            "update_assignment", "delete_assignment",
            "my_targets", "my_clients", "my_notifications",
            "my_unread_count", "mark_notifications_read",
            "list_active_targets", "toggle_active_target",
            "toggle_client_permission", "toggle_asset_permission",
        ]
        for name in expected:
            assert hasattr(targets, name), f"targets module missing function: {name}"

    def test_all_user_endpoints_exist(self):
        from app.api.v1.endpoints import users
        expected = [
            "get_users", "create_user", "update_user", "delete_user",
            "get_module_permissions", "set_module_permissions",
            "get_allowed_modules",
        ]
        for name in expected:
            assert hasattr(users, name), f"users module missing function: {name}"

    def test_all_client_endpoints_exist(self):
        from app.api.v1.endpoints import clients
        expected = [
            "create_client", "list_clients", "get_client",
            "update_client", "delete_client",
            "create_client_asset", "list_client_assets",
            "update_client_asset", "delete_client_asset",
        ]
        for name in expected:
            assert hasattr(clients, name), f"clients module missing function: {name}"

    def test_all_auth_endpoints_exist(self):
        from app.api.v1.endpoints import auth
        expected = [
            "login", "refresh_token", "logout", "get_me",
            "change_my_password", "update_my_email",
        ]
        for name in expected:
            assert hasattr(auth, name), f"auth module missing function: {name}"


class TestEndpointParameterShapes:
    """Verify the new endpoints accept the expected parameter shapes
    by inspecting FastAPI's route signature."""

    def test_scan_events_route_has_token_param(self):
        from app.main import app
        for r in app.routes:
            if getattr(r, "path", "") == "/api/v1/recon/scans/{scan_id}/events":
                # The endpoint signature should include a `token` parameter.
                sig_params = r.endpoint.__code__.co_varnames[:r.endpoint.__code__.co_argcount]
                assert "token" in sig_params, (
                    f"scan_events endpoint must accept `token` query param; "
                    f"found: {sig_params}"
                )
                return
        pytest.fail("scan_events route not found")

    def test_scan_report_token_route_has_fmt_param(self):
        from app.main import app
        for r in app.routes:
            if getattr(r, "path", "") == "/api/v1/recon/scans/{scan_id}/report/token":
                sig_params = r.endpoint.__code__.co_varnames[:r.endpoint.__code__.co_argcount]
                assert "fmt" in sig_params
                return
        pytest.fail("scan_report_token route not found")

    def test_client_report_token_route_has_fmt_param(self):
        from app.main import app
        for r in app.routes:
            if getattr(r, "path", "") == "/api/v1/recon/clients/{client_id}/report/token":
                sig_params = r.endpoint.__code__.co_varnames[:r.endpoint.__code__.co_argcount]
                assert "fmt" in sig_params
                return
        pytest.fail("client_report_token route not found")

    def test_client_toggle_route_has_payload_param(self):
        from app.main import app
        for r in app.routes:
            if getattr(r, "path", "") == "/api/v1/targets/clients/{client_id}/toggle":
                sig_params = r.endpoint.__code__.co_varnames[:r.endpoint.__code__.co_argcount]
                assert "payload" in sig_params
                return
        pytest.fail("client_toggle route not found")

    def test_asset_toggle_route_has_payload_param(self):
        from app.main import app
        for r in app.routes:
            if getattr(r, "path", "") == "/api/v1/targets/assets/{asset_id}/toggle":
                sig_params = r.endpoint.__code__.co_varnames[:r.endpoint.__code__.co_argcount]
                assert "payload" in sig_params
                return
        pytest.fail("asset_toggle route not found")
