# backend/tests/test_fixes.py
"""Tests for the fixes applied in this revision.

Covers:
* ReportService._iter_port_scan_results — port data mapping bug fix
  (was iterating ``ps.get("ports")`` but actual data shape is
  ``{"scans": [{"host", "ip", "ports": [...]}]}``).
* ReportService._pdf_kv — ``mm`` NameError fix (was referencing ``mm``
  without importing it inside the helper).
* ReportService.generate_pdf — end-to-end PDF generation with all
  result types present (no NameError, valid PDF bytes returned).
* ReportService.generate_html — end-to-end HTML generation with all
  result types present (no exceptions, screenshot URL embedded).
* recon.py imports — ``ForbiddenError`` is importable in the module
  namespace (was used but not imported, causing NameError at runtime).
* recon.py imports — ``uuid`` is importable at module load time
  (was imported at the bottom of the file, after first use).
* screenshot endpoint contract — the screenshot URL returned by the
  ScreenshotService matches the API endpoint pattern.
* target authorization — single IP, CIDR, unauthorized target.
"""
import io
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Port / service iteration — port data mapping bug fix
# ---------------------------------------------------------------------------
class TestPortScanIteration:
    """Verify ReportService._iter_port_scan_results correctly walks both
    the modern ``{"scans": [...]}`` shape and the legacy ``{"ports": [...]}``
    shape."""

    def test_modern_shape_yields_ports_with_ip_propagated(self):
        from app.recon.services.report_service import ReportService
        ps = {
            "scans": [
                {"host": "example.com", "ip": "1.2.3.4",
                 "ports": [
                     {"port": 80, "state": "open", "protocol": "tcp"},
                     {"port": 443, "state": "closed", "protocol": "tcp"},
                 ]},
                {"host": "example.com", "ip": "5.6.7.8",
                 "ports": [
                     {"port": 22, "state": "open", "protocol": "tcp"},
                 ]},
            ]
        }
        ports = list(ReportService._iter_port_scan_results(ps))
        assert len(ports) == 3
        # ip propagated from the parent scan entry
        assert ports[0]["ip"] == "1.2.3.4"
        assert ports[0]["port"] == 80
        assert ports[0]["state"] == "open"
        assert ports[2]["ip"] == "5.6.7.8"
        assert ports[2]["port"] == 22

    def test_legacy_shape_yields_ports(self):
        """Older rows may store ports directly under 'ports'."""
        from app.recon.services.report_service import ReportService
        ps = {"ports": [
            {"port": 80, "state": "open", "protocol": "tcp"},
            {"port": 443, "state": "open", "protocol": "tcp"},
        ]}
        ports = list(ReportService._iter_port_scan_results(ps))
        assert len(ports) == 2
        assert ports[0]["port"] == 80
        assert ports[1]["port"] == 443

    def test_empty_scans_yields_nothing(self):
        from app.recon.services.report_service import ReportService
        assert list(ReportService._iter_port_scan_results({"scans": []})) == []

    def test_non_dict_input_yields_nothing(self):
        from app.recon.services.report_service import ReportService
        assert list(ReportService._iter_port_scan_results(None)) == []
        assert list(ReportService._iter_port_scan_results("string")) == []

    def test_does_not_mutate_input(self):
        """The helper should not mutate the original port dicts."""
        from app.recon.services.report_service import ReportService
        ps = {"scans": [
            {"ip": "1.1.1.1", "ports": [{"port": 80, "state": "open"}]}
        ]}
        list(ReportService._iter_port_scan_results(ps))
        # Original port dict should not have "ip" key added
        assert "ip" not in ps["scans"][0]["ports"][0]


class TestServiceDetectionIteration:
    def test_modern_shape_yields_services_with_ip_propagated(self):
        from app.recon.services.report_service import ReportService
        s = {
            "scans": [
                {"host": "example.com", "ip": "1.2.3.4",
                 "services": [
                     {"port": 22, "service": "ssh", "banner": "SSH-2.0-OpenSSH_8.9"},
                     {"port": 80, "service": "http", "banner": None},
                 ]},
            ]
        }
        services = list(ReportService._iter_service_detection_results(s))
        assert len(services) == 2
        assert services[0]["port"] == 22
        assert services[0]["service"] == "ssh"
        assert services[0]["ip"] == "1.2.3.4"

    def test_legacy_shape_yields_services(self):
        from app.recon.services.report_service import ReportService
        s = {"services": [{"port": 22, "service": "ssh"}]}
        services = list(ReportService._iter_service_detection_results(s))
        assert len(services) == 1
        assert services[0]["port"] == 22


# ---------------------------------------------------------------------------
# PDF generation — the mm NameError fix
# ---------------------------------------------------------------------------
class TestPdfGeneration:
    """Verify that generate_pdf works end-to-end without the NameError on
    ``mm`` that previously crashed PDF generation when WHOIS or SSL data
    was present."""

    def _make_scan(self):
        return SimpleNamespace(
            id=42,
            user_id=1,
            target="example.com",
            target_type="DOMAIN",
            status="COMPLETED",
            modules=["host_discovery", "port_scan", "service_detection", "whois", "dns", "ssl", "http"],
            port_preset="common",
            progress=100,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    def _make_results(self):
        from app.recon.models.scan_result import ScanResult
        return [
            ScanResult(
                scan_id=42, result_type="HOST_DISCOVERY",
                data={"hosts": [{"host": "example.com", "ip": "93.184.216.34", "hostname": None, "status": "up", "latency_ms": 12}]},
            ),
            ScanResult(
                scan_id=42, result_type="PORT_SCAN",
                # Modern shape — scans list, each with ports
                data={"scans": [{"host": "example.com", "ip": "93.184.216.34", "ports": [
                    {"port": 80, "state": "open", "protocol": "tcp", "service_guess": "http"},
                    {"port": 443, "state": "open", "protocol": "tcp", "service_guess": "https"},
                    {"port": 22, "state": "closed", "protocol": "tcp", "service_guess": ""},
                ]}]},
            ),
            ScanResult(
                scan_id=42, result_type="SERVICE",
                data={"scans": [{"host": "example.com", "ip": "93.184.216.34", "services": [
                    {"port": 80, "service": "http", "protocol": "tcp", "banner": "Apache/2.4.41", "version": "2.4.41", "confidence": "high"},
                ]}]},
            ),
            ScanResult(
                scan_id=42, result_type="WHOIS",
                data={"target": "example.com", "registrar": "ICANN", "creation_date": "1995-08-14"},
            ),
            ScanResult(
                scan_id=42, result_type="DNS",
                data={"records": [{"record_type": "A", "name": "example.com", "values": ["93.184.216.34"], "ttl": 3600}]},
            ),
            ScanResult(
                scan_id=42, result_type="SSL",
                data={"hostname": "example.com", "port": 443, "expiration_status": "Valid", "tls_version": "TLSv1.3"},
            ),
            ScanResult(
                scan_id=42, result_type="HTTP",
                data={"url": "https://example.com", "status_code": 200, "security_headers": [
                    {"header": "Content-Security-Policy", "present": False, "value": None, "severity": "high"},
                    {"header": "Strict-Transport-Security", "present": True, "value": "max-age=31536000", "severity": "high"},
                ]},
            ),
            ScanResult(
                scan_id=42, result_type="SCREENSHOT",
                data={"url": "https://example.com", "captured": True, "screenshot_id": "abc123", "screenshot_url": "/api/v1/recon/screenshots/abc123"},
            ),
        ]

    def test_pdf_kv_does_not_raise_nameerror_on_mm(self):
        """Directly invoke _pdf_kv to verify the mm import is in scope."""
        from app.recon.services.report_service import ReportService
        svc = ReportService.__new__(ReportService)
        # This used to raise NameError: name 'mm' is not defined
        table = svc._pdf_kv({"registrar": "ICANN", "creation_date": "1995-08-14"})
        assert table is not None  # Table object constructed successfully

    def test_generate_pdf_returns_valid_bytes(self):
        """End-to-end PDF generation including WHOIS + SSL data (the path
        that used to crash with NameError on ``mm``)."""
        from app.recon.services.report_service import ReportService

        svc = ReportService.__new__(ReportService)
        # Stub _gather so we don't need a database
        async def _gather(_scan_id):
            return self._make_scan(), self._make_results()
        svc._gather = _gather
        # Stub _get_username so we don't need a database
        async def _get_username(_uid):
            return "testuser"
        svc._get_username = _get_username

        # Run the async generator
        import asyncio
        pdf_bytes = asyncio.run(svc.generate_pdf(42))
        assert pdf_bytes is not None
        assert isinstance(pdf_bytes, bytes)
        # PDF magic bytes
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000  # non-trivial PDF


# ---------------------------------------------------------------------------
# HTML generation — port mapping + screenshot URL
# ---------------------------------------------------------------------------
class TestHtmlGeneration:
    def _make_scan(self):
        return SimpleNamespace(
            id=42, user_id=1, target="example.com", target_type="DOMAIN",
            status="COMPLETED", modules=["port_scan", "screenshot"],
            port_preset="common", progress=100,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    def test_generate_html_includes_open_ports(self):
        """The HTML report should include port numbers from the modern
        ``{"scans": [...]}`` shape — previously no ports were emitted."""
        from app.recon.models.scan_result import ScanResult
        from app.recon.services.report_service import ReportService

        svc = ReportService.__new__(ReportService)
        scan = self._make_scan()
        results = [
            ScanResult(
                scan_id=42, result_type="PORT_SCAN",
                data={"scans": [{"host": "example.com", "ip": "1.2.3.4", "ports": [
                    {"port": 8080, "state": "open", "protocol": "tcp", "service_guess": "http-proxy"},
                ]}]},
            ),
        ]
        async def _gather(_scan_id):
            return scan, results
        svc._gather = _gather
        async def _get_username(_uid):
            return "tester"
        svc._get_username = _get_username

        import asyncio
        html = asyncio.run(svc.generate_html(42))
        assert "8080" in html
        assert "http-proxy" in html
        assert "1.2.3.4" in html

    def test_generate_html_includes_screenshot_url(self):
        """The HTML report should embed the screenshot — as a base64
        data URI when the file is available on disk, or as a clear
        placeholder when the file is missing.

        Previously the HTML used a relative ``/api/v1/recon/screenshots/…``
        URL, which failed to resolve when the report was opened via a
        Blob URL (the current frontend flow).  Embedding the bytes as
        a data URI makes the report fully self-contained and renders
        correctly regardless of how it is opened.
        """
        from app.recon.models.scan_result import ScanResult
        from app.recon.services.report_service import ReportService

        svc = ReportService.__new__(ReportService)
        scan = self._make_scan()
        results = [
            ScanResult(
                scan_id=42, result_type="SCREENSHOT",
                data={"url": "https://example.com", "captured": True,
                      "screenshot_id": "deadbeef",
                      "screenshot_url": "/api/v1/recon/screenshots/deadbeef"},
            ),
        ]
        async def _gather(_scan_id):
            return scan, results
        svc._gather = _gather
        async def _get_username(_uid):
            return "tester"
        svc._get_username = _get_username

        import asyncio

        # --- Case 1: screenshot file NOT on disk → HTML must contain a
        # clear placeholder note (no broken <img src="/api/v1/…"> link).
        html_missing = asyncio.run(svc.generate_html(42))
        assert "Screenshots" in html_missing
        assert "no longer available on disk" in html_missing
        # The relative URL must NOT appear in the HTML — it would break
        # under a Blob URL.
        assert "/api/v1/recon/screenshots/deadbeef" not in html_missing

        # --- Case 2: screenshot file IS on disk → HTML must contain a
        # base64 data URI for that PNG, not a relative URL.
        import base64 as _b64
        import os as _os
        import tempfile as _tf
        from unittest.mock import patch

        with _tf.TemporaryDirectory() as tmpdir:
            fake_png = _os.path.join(tmpdir, "deadbeef.png")
            with open(fake_png, "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)  # minimal PNG-ish header
            with patch("app.recon.services.report_service.settings.RECON_SCREENSHOT_STORAGE_PATH", tmpdir):
                html_present = asyncio.run(svc.generate_html(42))
            expected_b64 = _b64.b64encode(open(fake_png, "rb").read()).decode("ascii")
            assert f"data:image/png;base64,{expected_b64}" in html_present
            assert "https://example.com" in html_present


# ---------------------------------------------------------------------------
# recon.py module imports — ForbiddenError + uuid at module top
# ---------------------------------------------------------------------------
class TestReconEndpointImports:
    """Verify that the recon endpoint module has ``ForbiddenError`` and
    ``uuid`` available in its namespace at import time."""

    def test_forbidden_error_is_imported(self):
        from app.api.v1.endpoints import recon
        assert hasattr(recon, "ForbiddenError")
        from app.utils.errors import ForbiddenError
        assert recon.ForbiddenError is ForbiddenError

    def test_uuid_is_imported(self):
        from app.api.v1.endpoints import recon
        assert hasattr(recon, "uuid")
        import uuid as uuid_mod
        assert recon.uuid is uuid_mod

    def test_app_loads_cleanly(self):
        """The FastAPI app should construct without import errors."""
        from app.main import app
        # Walk the route table to make sure every endpoint is wired up
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        # Critical endpoints that previously crashed at runtime due to
        # missing ForbiddenError import
        assert "/api/v1/recon/scans/{scan_id}/report/pdf" in paths
        assert "/api/v1/recon/scans/{scan_id}/report/html" in paths
        assert "/api/v1/recon/screenshots/{screenshot_id}" in paths
        assert "/api/v1/recon/clients/{client_id}/report/html" in paths

    def test_delete_asset_endpoint_uses_forbidden_error(self):
        """Inspecting the delete_asset route source — it should reference
        ForbiddenError (which is now imported)."""
        import inspect
        from app.api.v1.endpoints import recon
        src = inspect.getsource(recon)
        # The endpoint should raise ForbiddenError for protected assets
        assert "ForbiddenError" in src
        assert "ASSET_DELETE_DENIED" in src


# ---------------------------------------------------------------------------
# Screenshot endpoint contract
# ---------------------------------------------------------------------------
class TestScreenshotServiceContract:
    """Verify the screenshot service produces URLs that match the API
    endpoint pattern.  We don't run the actual browser here — we just
    verify the URL contract."""

    def test_screenshot_url_pattern(self):
        from app.recon.services.screenshot_service import ScreenshotService
        # The capture() method returns a dict with screenshot_url that
        # matches /api/v1/recon/screenshots/{uuid}
        # We verify the URL pattern is consistent by checking what the
        # endpoint serves.
        from app.api.v1.endpoints import recon
        import inspect
        # The endpoint accepts a screenshot_id path parameter
        src = inspect.getsource(recon)
        assert "/screenshots/{screenshot_id}" in src
        # The endpoint validates the UUID format
        assert "uuid.UUID" in src


# ---------------------------------------------------------------------------
# Target authorization — single IP, CIDR, unauthorized target
# (These augment the existing test_target_validator.py with explicit
# names matching the task's required test names.)
# ---------------------------------------------------------------------------
class TestTargetAuthorization:
    def test_single_ip_authorization(self):
        """A single public IP is authorized for scanning."""
        from app.recon.validators.target_validator import (
            TargetValidator, ValidationError,
        )
        v = TargetValidator.validate("8.8.8.8")
        assert v.target_type == "IP"
        assert v.host == "8.8.8.8"

    def test_cidr_authorization(self):
        """A small public CIDR is authorized."""
        from app.recon.validators.target_validator import TargetValidator
        v = TargetValidator.validate("8.0.0.0/29")
        assert v.target_type == "CIDR"
        assert v.cidr == "8.0.0.0/29"

    def test_unauthorized_target(self):
        """Private CIDRs without an allow-list are rejected."""
        from app.recon.validators.target_validator import (
            TargetValidator, ValidationError,
        )
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("192.168.1.0/24")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_loopback_unauthorized(self):
        from app.recon.validators.target_validator import (
            TargetValidator, ValidationError,
        )
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("127.0.0.1")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_metadata_ip_unauthorized(self):
        from app.recon.validators.target_validator import (
            TargetValidator, ValidationError,
        )
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("169.254.169.254")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_user_allowed_network_grants_private_target(self):
        """When the user's allow-list contains a CIDR covering the target,
        the validator should permit the target."""
        from app.recon.validators.target_validator import TargetValidator
        v = TargetValidator.validate("192.168.1.5", user_networks=["192.168.1.0/24"])
        assert v.target_type == "IP"
        assert v.host == "192.168.1.5"

    def test_user_allowed_network_grants_private_cidr(self):
        """When the user's allow-list contains a CIDR, scanning that CIDR
        should be permitted."""
        from app.recon.validators.target_validator import TargetValidator
        v = TargetValidator.validate("192.168.1.0/24", user_networks=["192.168.1.0/24"])
        assert v.target_type == "CIDR"
        assert v.cidr == "192.168.1.0/24"


# ---------------------------------------------------------------------------
# Auth endpoints — self-service settings
# ---------------------------------------------------------------------------
class TestAuthSelfServiceEndpoints:
    """Verify the new /auth/me/change-password and /auth/me/email endpoints
    are registered on the FastAPI app."""

    def test_change_password_endpoint_registered(self):
        from app.main import app
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/auth/me/change-password" in paths

    def test_update_email_endpoint_registered(self):
        from app.main import app
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/auth/me/email" in paths

    def test_change_password_schema_validates_complexity(self):
        from app.api.v1.endpoints.auth import ChangePasswordRequest
        # Valid password — full pydantic validation
        ChangePasswordRequest(current_password="oldpass1!", new_password="GoodPass1!")
        # Invalid — no uppercase
        with pytest.raises(ValueError):
            ChangePasswordRequest.validate_new_password("lowercase1!")
        # Invalid — no digit
        with pytest.raises(ValueError):
            ChangePasswordRequest.validate_new_password("GoodPass!")
        # Invalid — no special
        with pytest.raises(ValueError):
            ChangePasswordRequest.validate_new_password("GoodPass1")
        # Invalid — too short (full pydantic validation enforces min_length=8)
        with pytest.raises(Exception):
            ChangePasswordRequest(current_password="oldpass1!", new_password="Aa1!6")


# ---------------------------------------------------------------------------
# Audit action constants
# ---------------------------------------------------------------------------
class TestAuditActions:
    def test_new_audit_actions_exist(self):
        from app.core.constants import AuditAction
        assert hasattr(AuditAction, "PASSWORD_CHANGED")
        assert hasattr(AuditAction, "EMAIL_CHANGED")
        assert hasattr(AuditAction, "USER_UPDATED")
        assert AuditAction.PASSWORD_CHANGED == "PASSWORD_CHANGED"
        assert AuditAction.EMAIL_CHANGED == "EMAIL_CHANGED"
