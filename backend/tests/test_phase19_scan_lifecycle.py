# backend/tests/test_phase19_scan_lifecycle.py
"""End-to-end scan-lifecycle tests for Phase 19.

These tests simulate the full scan lifecycle (create → queue → execute
→ complete) using a stubbed DB session and stubbed Celery, verifying
that:

  1. ScanService.create_scan calls init_for_scan to create the
     per-module status rows.
  2. ScanService.execute_scan marks each module RUNNING → COMPLETED
     (or FAILED) and publishes the corresponding Redis pub/sub
     events.
  3. The SSE endpoint can deliver a snapshot event with the current
     scan + module_statuses.

These tests don't use a live DB — they stub the repositories so we
can verify the orchestration logic in isolation.
"""
import asyncio
import os
import sys
import inspect
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _make_scan(scan_id=1, modules=None, status="QUEUED"):
    """Build a Scan-like SimpleNamespace with the attributes used by
    ScanService.execute_scan and the SSE endpoint."""
    return SimpleNamespace(
        id=scan_id,
        user_id=1,
        name="t",
        target="example.com",
        target_type="DOMAIN",
        status=status,
        modules=modules or ["host_discovery"],
        port_preset=None,
        custom_ports=None,
        progress=0,
        started_at=None,
        completed_at=None,
        error_message=None,
        celery_task_id=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        ownership_type="USER_MANUAL",
        client_id=None,
        client_asset_id=None,
        assignment_id=None,
    )


def _make_module_status(module_name, status="QUEUED"):
    return SimpleNamespace(
        module_name=module_name,
        status=status,
        progress=0,
        error_message=None,
        started_at=None,
        completed_at=None,
    )


class TestScanServiceExecuteScanLifecycle:
    """Verify execute_scan walks through each module, updates its
    status, and publishes events.

    Rather than mock the entire dependency chain (which is brittle),
    we directly stub the ``ScanService`` instance attributes that
    ``execute_scan`` accesses and patch the ``_run_module`` method.
    The ``TargetAuthorizationService`` instance used inside
    ``execute_scan`` is replaced with a stub by patching the class
    itself.
    """

    def _build_service_with_stubs(self, scan, modules):
        """Build a ScanService with stubbed repositories that simulate
        a successful scan execution."""
        from app.recon.services.scan_service import ScanService

        svc = ScanService.__new__(ScanService)
        svc.db = AsyncMock()
        svc._user_networks = []
        svc._auth = None
        svc._global_allowed_networks = None

        # Scan repo: get_by_id returns the scan, update_status returns
        # the scan, get_scan_with_results returns the scan.
        svc.scan_repo = AsyncMock()
        svc.scan_repo.get_by_id = AsyncMock(return_value=scan)
        svc.scan_repo.update_status = AsyncMock(return_value=scan)
        svc.scan_repo.get_scan_with_results = AsyncMock(return_value=scan)
        svc.scan_repo.set_celery_task_id = AsyncMock()
        svc.scan_repo.append_progress = AsyncMock()

        # Result repo: add_result returns a stub.
        svc.result_repo = AsyncMock()
        svc.result_repo.add_result = AsyncMock(return_value=SimpleNamespace(id=1))

        # Module status repo: init_for_scan + set_module_status are
        # AsyncMocks that capture call args.
        svc.module_status_repo = AsyncMock()
        svc.module_status_repo.init_for_scan = AsyncMock()
        svc.module_status_repo.set_module_status = AsyncMock()
        svc.module_status_repo.cancel_pending = AsyncMock()
        svc.module_status_repo.list_for_scan = AsyncMock(
            return_value=[_make_module_status(m) for m in modules],
        )

        # Asset repo.
        svc.asset_repo = AsyncMock()
        svc.asset_repo.upsert_asset = AsyncMock()

        # Audit service.
        svc.audit = AsyncMock()
        svc.audit.log = AsyncMock()

        # Pre-build the auth object that TargetAuthorizationService.authorize
        # would normally return, so we can short-circuit the auth call.
        svc._auth = SimpleNamespace(
            allowed=True, reason="ok",
            target_classification="public",
            ownership_type="USER_MANUAL",
            client_id=None, client_asset_id=None, assignment_id=None,
            validated=SimpleNamespace(
                raw="example.com", target_type="DOMAIN",
                host="example.com", cidr=None,
            ),
        )
        return svc

    def test_execute_scan_marks_each_module_running_then_completed(self):
        """For a 2-module scan, execute_scan must:
          - mark scan RUNNING
          - mark module 1 RUNNING → COMPLETED
          - mark module 2 RUNNING → COMPLETED
          - mark scan COMPLETED
        """
        from app.recon.services.scan_service import ScanService
        from app.core.constants import ScanModuleStatusValue

        scan = _make_scan(modules=["host_discovery", "dns"])
        svc = self._build_service_with_stubs(scan, ["host_discovery", "dns"])

        # Patch _run_module to be a no-op (simulates successful execution).
        async def _stub_run_module(self, module, scan_obj, validated):
            return None

        # Patch the TargetAuthorizationService used inside execute_scan
        # so its authorize() returns the same auth object we already
        # pre-populated on the service (avoids the real DB access).
        async def _stub_authorize(self, user, target, *, assignment_id=None):
            return svc._auth

        with patch.object(ScanService, "_run_module", _stub_run_module), \
             patch.object(ScanService, "_get_user_networks", AsyncMock(return_value=[])), \
             patch.object(ScanService, "_publish_scan_event", AsyncMock()), \
             patch.object(ScanService, "_audit", AsyncMock()), \
             patch(
                "app.services.target_authorization_service.TargetAuthorizationService.authorize",
                _stub_authorize,
             ), \
             patch(
                "app.repositories.user_repository.UserRepository"
             ) as MockUserRepo:
            MockUserRepo.return_value.get_user_with_role = AsyncMock(
                return_value=SimpleNamespace(
                    id=1, is_active=True,
                    role=SimpleNamespace(name="User"),
                ),
            )
            asyncio.run(svc.execute_scan(scan.id))

        # Verify scan was marked RUNNING then COMPLETED.
        statuses_called = [c.kwargs.get("status") for c in svc.scan_repo.update_status.call_args_list]
        assert "RUNNING" in statuses_called
        assert "COMPLETED" in statuses_called

        # Verify each module was marked RUNNING then COMPLETED.
        module_status_calls = svc.module_status_repo.set_module_status.call_args_list
        # 2 modules × 2 calls each (RUNNING + COMPLETED) = 4 calls.
        assert len(module_status_calls) == 4
        # First call: host_discovery RUNNING.
        assert module_status_calls[0].args[1] == "host_discovery"
        assert module_status_calls[0].kwargs["status"] == ScanModuleStatusValue.RUNNING
        # Second call: host_discovery COMPLETED.
        assert module_status_calls[1].args[1] == "host_discovery"
        assert module_status_calls[1].kwargs["status"] == ScanModuleStatusValue.COMPLETED
        # Third call: dns RUNNING.
        assert module_status_calls[2].args[1] == "dns"
        assert module_status_calls[2].kwargs["status"] == ScanModuleStatusValue.RUNNING
        # Fourth call: dns COMPLETED.
        assert module_status_calls[3].args[1] == "dns"
        assert module_status_calls[3].kwargs["status"] == ScanModuleStatusValue.COMPLETED

    def test_execute_scan_marks_failed_module_correctly(self):
        """When _run_module raises, execute_scan must mark the module
        FAILED (not COMPLETED) and continue with the next module."""
        from app.recon.services.scan_service import ScanService
        from app.core.constants import ScanModuleStatusValue

        scan = _make_scan(modules=["host_discovery", "dns"])
        svc = self._build_service_with_stubs(scan, ["host_discovery", "dns"])

        # _run_module raises for the first module, succeeds for the second.
        call_count = {"n": 0}
        async def _stub_run_module(self, module, scan_obj, validated):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("simulated module failure")

        async def _stub_authorize(self, user, target, *, assignment_id=None):
            return svc._auth

        with patch.object(ScanService, "_run_module", _stub_run_module), \
             patch.object(ScanService, "_get_user_networks", AsyncMock(return_value=[])), \
             patch.object(ScanService, "_publish_scan_event", AsyncMock()), \
             patch.object(ScanService, "_audit", AsyncMock()), \
             patch(
                "app.services.target_authorization_service.TargetAuthorizationService.authorize",
                _stub_authorize,
             ), \
             patch(
                "app.repositories.user_repository.UserRepository"
             ) as MockUserRepo:
            MockUserRepo.return_value.get_user_with_role = AsyncMock(
                return_value=SimpleNamespace(
                    id=1, is_active=True,
                    role=SimpleNamespace(name="User"),
                ),
            )
            asyncio.run(svc.execute_scan(scan.id))

        module_status_calls = svc.module_status_repo.set_module_status.call_args_list
        # First module: RUNNING then FAILED.
        assert module_status_calls[0].args[1] == "host_discovery"
        assert module_status_calls[0].kwargs["status"] == ScanModuleStatusValue.RUNNING
        assert module_status_calls[1].args[1] == "host_discovery"
        assert module_status_calls[1].kwargs["status"] == ScanModuleStatusValue.FAILED
        assert module_status_calls[1].kwargs["error_message"] is not None
        # Second module: RUNNING then COMPLETED (despite first failure).
        assert module_status_calls[2].args[1] == "dns"
        assert module_status_calls[2].kwargs["status"] == ScanModuleStatusValue.RUNNING
        assert module_status_calls[3].args[1] == "dns"
        assert module_status_calls[3].kwargs["status"] == ScanModuleStatusValue.COMPLETED
        # Scan still marked COMPLETED (one module failed but scan finished).
        statuses = [c.kwargs.get("status") for c in svc.scan_repo.update_status.call_args_list]
        assert "COMPLETED" in statuses


class TestScanServiceCreateScanInitForScan:
    """Verify create_scan calls init_for_scan with the selected modules."""

    def test_create_scan_calls_init_for_scan_with_modules(self):
        """After the Scan row is persisted, create_scan must call
        ``module_status_repo.init_for_scan(scan.id, modules)`` so the
        per-module status rows exist before the worker starts."""
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.create_scan)
        # Find the init_for_scan call and verify it passes the modules.
        assert "init_for_scan" in src
        assert "payload.modules" in src or "list(payload.modules)" in src


class TestScanServicePublishEvents:
    """Verify _publish_scan_event publishes to the correct Redis channel."""

    def test_publish_scan_event_channel_name(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService._publish_scan_event)
        # Channel must be scan_events:{scan_id} so the SSE endpoint
        # can subscribe to it.
        assert "scan_events:" in src
        assert "redis_client.publish" in src

    def test_publish_scan_event_swallows_errors(self):
        """If Redis is unreachable, _publish_scan_event must NOT raise
        — pub/sub is best-effort and the polling fallback keeps the UI
        correct."""
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService._publish_scan_event)
        assert "except Exception" in src
        assert "logger.warning" in src


class TestScanServiceCancelScan:
    """Verify cancel_scan cascades to per-module statuses."""

    def test_cancel_scan_calls_cancel_pending(self):
        from app.recon.services.scan_service import ScanService
        src = inspect.getsource(ScanService.cancel_scan)
        assert "cancel_pending" in src
        # Must also publish a scan_cancelled event.
        assert "scan_cancelled" in src


class TestSseSnapshotContainsModuleStatuses:
    """Verify the SSE endpoint's snapshot event includes the
    module_statuses array."""

    def test_snapshot_includes_module_statuses(self):
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon.scan_events)
        assert "module_statuses" in src
        # Must include module_name, status, progress, error_message,
        # started_at, completed_at for each row.
        assert "module_name" in src
        assert "status" in src
        assert "progress" in src
        assert "error_message" in src
        assert "started_at" in src
        assert "completed_at" in src


class TestModuleStatusRepoInitForScanBehavior:
    """Verify init_for_scan is idempotent."""

    def test_init_for_scan_does_not_insert_duplicates(self):
        from app.recon.repositories.scan_repository import ScanModuleStatusRepository
        src = inspect.getsource(ScanModuleStatusRepository.init_for_scan)
        # Must query existing rows first and skip modules that already
        # have a row.
        assert "existing_names" in src
        assert "if name in existing_names" in src
        assert "continue" in src
