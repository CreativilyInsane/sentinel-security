"""End-to-end smoke test for the screenshot service file persistence.

This test does NOT run Playwright (no browser installed in CI).  Instead
it stubs the _playwright_capture method to write a real PNG file to a
temp directory, then verifies that:
1. The service reports captured=True
2. The file actually exists on disk
3. The file is non-empty
4. The screenshot_url follows the expected pattern
5. The screenshot_id is a valid UUID hex string
"""
import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Set required env vars before importing app modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("ADMIN_USERNAME", "a")
os.environ.setdefault("ADMIN_PASSWORD", "Aa1!aaaa")
os.environ.setdefault("ADMIN_EMAIL", "a@b.c")


def test_screenshot_persists_file_to_disk():
    """Verify the screenshot service writes a real file and reports success
    only when the file exists + is non-empty."""
    from app.recon.services.screenshot_service import ScreenshotService, ScreenshotStatus
    from app.recon.validators.target_validator import ValidatedTarget
    from app.core.constants import TargetType

    # Create a temp directory to use as the storage path
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the settings.RECON_SCREENSHOT_STORAGE_PATH to point to tmpdir
        from app.core.config import settings
        original_path = settings.RECON_SCREENSHOT_STORAGE_PATH
        settings.RECON_SCREENSHOT_STORAGE_PATH = tmpdir
        try:
            svc = ScreenshotService()

            # Stub the Playwright capture to write a real PNG file
            async def _stub_playwright_capture(url, out_path):
                # Write a minimal valid PNG header + some bytes
                with open(out_path, 'wb') as f:
                    # 8-byte PNG signature + IHDR chunk header
                    f.write(b'\x89PNG\r\n\x1a\n')
                    f.write(b'\x00' * 100)  # padding
                return True

            svc._playwright_capture = _stub_playwright_capture

            # Build a validated target for a public domain
            target = ValidatedTarget(
                raw="https://example.com",
                target_type=TargetType.URL,
                host="example.com",
                scheme="https",
                port=443,
                ip_addresses=[],
                cidr=None,
            )

            result = asyncio.run(svc.capture(target))

            # Verify the result
            assert result["captured"] is True, f"Expected captured=True, got {result}"
            assert result["status"] == ScreenshotStatus.COMPLETED
            assert "screenshot_id" in result
            assert "screenshot_url" in result
            sid = result["screenshot_id"]
            # screenshot_id must be a valid UUID hex
            uuid.UUID(sid)

            # Verify the file actually exists on disk
            file_path = os.path.join(tmpdir, f"{sid}.png")
            assert os.path.isfile(file_path), f"File {file_path} should exist"
            assert os.path.getsize(file_path) > 0, "File should be non-empty"

            # Verify the screenshot_url pattern (relative path for apiClient)
            assert result["screenshot_url"] == f"/recon/screenshots/{sid}"
            # And the full URL pattern (for HTML report img src)
            assert result["screenshot_url_full"] == f"/api/v1/recon/screenshots/{sid}"
        finally:
            settings.RECON_SCREENSHOT_STORAGE_PATH = original_path


def test_screenshot_reports_failure_when_file_not_written():
    """If _playwright_capture returns True but the file doesn't exist,
    the service must report captured=False (not fake success)."""
    from app.recon.services.screenshot_service import ScreenshotService, ScreenshotStatus
    from app.recon.validators.target_validator import ValidatedTarget
    from app.core.constants import TargetType

    with tempfile.TemporaryDirectory() as tmpdir:
        from app.core.config import settings
        original_path = settings.RECON_SCREENSHOT_STORAGE_PATH
        settings.RECON_SCREENSHOT_STORAGE_PATH = tmpdir
        try:
            svc = ScreenshotService()

            # Stub: return True but DON'T write the file
            async def _stub_playwright_capture(url, out_path):
                return True  # lie about success

            svc._playwright_capture = _stub_playwright_capture

            target = ValidatedTarget(
                raw="https://example.com",
                target_type=TargetType.URL,
                host="example.com",
                scheme="https",
                port=443,
                ip_addresses=[],
                cidr=None,
            )

            result = asyncio.run(svc.capture(target))

            # Must NOT report success
            assert result["captured"] is False, \
                "Service must not report success when file is missing"
            assert result["status"] == ScreenshotStatus.FAILED
            assert "error" in result
        finally:
            settings.RECON_SCREENSHOT_STORAGE_PATH = original_path


def test_screenshot_reports_failure_when_file_empty():
    """If the file is written but is empty, the service must report
    failure."""
    from app.recon.services.screenshot_service import ScreenshotService, ScreenshotStatus
    from app.recon.validators.target_validator import ValidatedTarget
    from app.core.constants import TargetType

    with tempfile.TemporaryDirectory() as tmpdir:
        from app.core.config import settings
        original_path = settings.RECON_SCREENSHOT_STORAGE_PATH
        settings.RECON_SCREENSHOT_STORAGE_PATH = tmpdir
        try:
            svc = ScreenshotService()

            # Stub: write an empty file
            async def _stub_playwright_capture(url, out_path):
                open(out_path, 'wb').close()  # empty file
                return True

            svc._playwright_capture = _stub_playwright_capture

            target = ValidatedTarget(
                raw="https://example.com",
                target_type=TargetType.URL,
                host="example.com",
                scheme="https",
                port=443,
                ip_addresses=[],
                cidr=None,
            )

            result = asyncio.run(svc.capture(target))

            assert result["captured"] is False
            assert result["status"] == ScreenshotStatus.FAILED
            assert "empty" in result["error"].lower()
        finally:
            settings.RECON_SCREENSHOT_STORAGE_PATH = original_path


def test_screenshot_rejects_private_ip_target():
    """The screenshot service must reject private IP targets at the
    DNS-resolution layer."""
    from app.recon.services.screenshot_service import ScreenshotService, ScreenshotStatus
    from app.recon.validators.target_validator import ValidatedTarget
    from app.core.constants import TargetType

    with tempfile.TemporaryDirectory() as tmpdir:
        from app.core.config import settings
        original_path = settings.RECON_SCREENSHOT_STORAGE_PATH
        settings.RECON_SCREENSHOT_STORAGE_PATH = tmpdir
        try:
            svc = ScreenshotService()

            # Build a validated IP target — note the SSRF guard inside
            # capture() uses socket.getaddrinfo which won't resolve
            # private IPs to themselves, so this test exercises the
            # exception path.
            target = ValidatedTarget(
                raw="192.168.1.10",
                target_type=TargetType.IP,
                host="192.168.1.10",
                scheme=None,
                port=None,
                ip_addresses=["192.168.1.10"],
                cidr=None,
            )

            # Stub getaddrinfo to return the private IP
            import socket
            original_getaddrinfo = socket.getaddrinfo
            def _stub_getaddrinfo(host, *args, **kwargs):
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.10', 0))]
            socket.getaddrinfo = _stub_getaddrinfo
            try:
                result = asyncio.run(svc.capture(target))
                assert result["captured"] is False
                assert result["status"] == ScreenshotStatus.FAILED
                assert "private" in result["error"].lower() or "internal" in result["error"].lower()
            finally:
                socket.getaddrinfo = original_getaddrinfo
        finally:
            settings.RECON_SCREENSHOT_STORAGE_PATH = original_path


if __name__ == "__main__":
    test_screenshot_persists_file_to_disk()
    print("test_screenshot_persists_file_to_disk: PASS")
    test_screenshot_reports_failure_when_file_not_written()
    print("test_screenshot_reports_failure_when_file_not_written: PASS")
    test_screenshot_reports_failure_when_file_empty()
    print("test_screenshot_reports_failure_when_file_empty: PASS")
    test_screenshot_rejects_private_ip_target()
    print("test_screenshot_rejects_private_ip_target: PASS")
    print("All screenshot persistence tests passed!")
