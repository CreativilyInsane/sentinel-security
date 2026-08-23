# backend/tests/test_service_parsing.py
"""Tests for the parsing logic in recon services — DNS, SSL, HTTP.

These tests exercise the data-shaping logic without touching the network:
we instantiate the service classes and call their private parsing helpers
directly with fixture data.  Network-dependent methods (``lookup``,
``analyze``, ``capture``) are not tested here.
"""
import pytest

from app.recon.services.http_service import HttpService
from app.recon.services.ssl_service import SslService
from app.recon.services.report_service import ReportService
from app.recon.validators.target_validator import ValidatedTarget


class TestHTTPSecurityHeaders:
    """Test the security-header assessment logic in isolation."""

    def test_missing_csp_flagged_high(self):
        svc = HttpService()
        # Use the module-level table to verify severity mapping
        from app.recon.services.http_service import _SECURITY_HEADERS
        csp = next(h for h in _SECURITY_HEADERS if h["header"] == "Content-Security-Policy")
        assert csp["severity"] == "high"

    def test_missing_hsts_flagged_high(self):
        from app.recon.services.http_service import _SECURITY_HEADERS
        hsts = next(h for h in _SECURITY_HEADERS if h["header"] == "Strict-Transport-Security")
        assert hsts["severity"] == "high"

    def test_all_required_headers_present(self):
        from app.recon.services.http_service import _SECURITY_HEADERS
        expected_headers = {
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
        }
        actual = {h["header"] for h in _SECURITY_HEADERS}
        assert expected_headers.issubset(actual)


class TestReportServiceGrouping:
    """Test that ReportService._group_results correctly buckets
    results by result_type."""

    def test_group_empty(self):
        svc = ReportService.__new__(ReportService)  # bypass __init__ (no db)
        grouped = svc._group_results([])
        assert grouped["host_discovery"] == []
        assert grouped["whois"] == {}
        assert grouped["errors"] == []

    def test_group_list_results(self):
        from app.recon.models.scan_result import ScanResult
        svc = ReportService.__new__(ReportService)
        results = [
            ScanResult(scan_id=1, result_type="HOST_DISCOVERY", data={"hosts": [{"host": "1.1.1.1"}]}),
            ScanResult(scan_id=1, result_type="PORT_SCAN", data={"ports": [{"port": 80}]}),
            ScanResult(scan_id=1, result_type="DNS", data={"records": [{"record_type": "A"}]}),
            ScanResult(scan_id=1, result_type="SCREENSHOT", data={"captured": True}),
        ]
        grouped = svc._group_results(results)
        assert len(grouped["host_discovery"]) == 1
        assert len(grouped["port_scan"]) == 1
        assert len(grouped["dns"]) == 1
        assert len(grouped["screenshot"]) == 1

    def test_group_scalar_results(self):
        from app.recon.models.scan_result import ScanResult
        svc = ReportService.__new__(ReportService)
        results = [
            ScanResult(scan_id=1, result_type="WHOIS", data={"registrar": "Example"}),
            ScanResult(scan_id=1, result_type="SSL", data={"expiration_status": "Valid"}),
            ScanResult(scan_id=1, result_type="HTTP", data={"status_code": 200}),
        ]
        grouped = svc._group_results(results)
        assert grouped["whois"]["registrar"] == "Example"
        assert grouped["ssl"]["expiration_status"] == "Valid"
        assert grouped["http"]["status_code"] == 200

    def test_group_errors_collected(self):
        from app.recon.models.scan_result import ScanResult
        svc = ReportService.__new__(ReportService)
        results = [
            ScanResult(scan_id=1, result_type="WHOIS", data={}, error="lookup failed"),
            ScanResult(scan_id=1, result_type="DNS", data={}, error="NXDOMAIN"),
        ]
        grouped = svc._group_results(results)
        assert len(grouped["errors"]) == 2
        modules = {e["module"] for e in grouped["errors"]}
        assert modules == {"WHOIS", "DNS"}

    def test_summary_builder_includes_counts(self):
        from app.recon.models.scan import Scan
        from app.recon.models.scan_result import ScanResult
        svc = ReportService.__new__(ReportService)
        scan = Scan(
            id=1, user_id=1, target="example.com", target_type="DOMAIN",
            status="COMPLETED", modules=["host_discovery", "port_scan"],
            progress=100,
        )
        # created_at is set by the DB; for the test we leave it None and
        # check the summary doesn't crash.
        grouped = {
            "host_discovery": [{"hosts": [{"host": "1.1.1.1"}, {"host": "2.2.2.2"}]}],
            "port_scan": [{"ports": [{"port": 80, "state": "open"}, {"port": 443, "state": "closed"}]}],
            "service": [], "whois": {}, "dns": [], "ssl": {},
            "http": {}, "screenshot": [], "errors": [],
        }
        summary = svc._build_summary(scan, grouped)
        assert "example.com" in summary
        assert "2 host" in summary
        assert "1 open" in summary


class TestServiceDetectionVersionParsing:
    def test_ssh_version_extracted(self):
        from app.recon.services.service_detection import ServiceDetectionService
        svc = ServiceDetectionService()
        v = svc._parse_version("ssh", "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.4")
        # After SSH-2.0-, the next token is "OpenSSH_8.9p1"
        assert v == "OpenSSH_8.9p1"

    def test_mysql_version_extracted(self):
        from app.recon.services.service_detection import ServiceDetectionService
        svc = ServiceDetectionService()
        v = svc._parse_version("mysql", "MySQL 8.0.35")
        assert v == "8.0.35"

    def test_redis_version_extracted(self):
        from app.recon.services.service_detection import ServiceDetectionService
        svc = ServiceDetectionService()
        v = svc._parse_version("redis", "Redis 7.0.11")
        assert v == "7.0.11"

    def test_unknown_service_returns_none(self):
        from app.recon.services.service_detection import ServiceDetectionService
        svc = ServiceDetectionService()
        v = svc._parse_version("unknown", "some random banner")
        assert v is None

    def test_none_banner_returns_none(self):
        from app.recon.services.service_detection import ServiceDetectionService
        svc = ServiceDetectionService()
        assert svc._parse_version("ssh", None) is None
