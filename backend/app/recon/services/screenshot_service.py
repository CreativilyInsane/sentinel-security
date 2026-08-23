# backend/app/recon/services/screenshot_service.py
"""Website screenshot capture using Playwright.

Safety measures:
* URL is validated by TargetValidator before any browser operation.
* Resolved IPs are re-checked against the SSRF guard right before launch
  (defeats DNS rebinding).
* Downloads are disabled.
* Navigation is bounded to a single page (no crawling).
* Strict timeout (RECON_SCREENSHOT_TIMEOUT).
* Files are stored under RECON_SCREENSHOT_STORAGE_PATH with a generated
  UUID filename — user-controlled filenames are never accepted.

Persistence:
* The screenshot is written to ``RECON_SCREENSHOT_STORAGE_PATH`` which
  is mounted as a Docker named volume (``recon_screenshots``) in
  ``docker-compose.yml``.  This means screenshots survive container
  restarts and ``docker compose down && docker compose up``.
* The screenshot_id (UUID) is stored in the ScanResult.data JSON column
  as ``screenshot_id``.  The retrieval endpoint
  ``GET /api/v1/recon/screenshots/{screenshot_id}`` streams the file
  from disk after verifying it exists.
* The ``screenshot_url`` returned here is the API path the frontend
  uses to display the screenshot — it is NOT a direct filesystem path.

The service reports a clear status:
  * ``captured: True``  → file was successfully written + verified
  * ``captured: False`` → file was NOT written; ``error`` explains why
"""
from __future__ import annotations

import asyncio
import os
import socket
import uuid
from typing import Dict, Any

from app.core.config import settings
from app.core.logging import logger
from app.recon.validators.target_validator import (
    TargetValidator,
    ValidatedTarget,
    ValidationError,
    is_private_ip,
)


# ---------------------------------------------------------------------------
# Screenshot status constants
# ---------------------------------------------------------------------------
class ScreenshotStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScreenshotService:
    async def capture(self, target: ValidatedTarget) -> Dict[str, Any]:
        """Capture a screenshot of the target URL.

        Returns a dict with the following keys:
          * ``url``          — the URL that was captured
          * ``captured``     — bool, True iff the file was written + verified
          * ``status``       — one of ScreenshotStatus constants
          * ``screenshot_id``— UUID hex string (only when captured=True)
          * ``screenshot_url``— API path to retrieve the screenshot
          * ``content_type`` — always ``image/png``
          * ``error``        — error message (only when captured=False)
        """
        # Build URL
        if target.target_type == "URL":
            url = target.raw
        elif target.target_type == "IP":
            url = f"http://{target.host}/"
        else:
            url = f"https://{target.host}/"

        # SSRF guard #2 — re-resolve and check just before launching the
        # browser, so we defeat DNS-rebinding attacks.
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(target.host, None, proto=socket.IPPROTO_TCP),
            )
            ips = list({sa[0].split("%", 1)[0] for sa in [info[4] for info in infos]})
            # Block private IPs at the resolution layer too — even if the
            # target was a domain that resolved to a private IP.
            for ip_str in ips:
                if is_private_ip(ip_str):
                    return {
                        "url": url,
                        "captured": False,
                        "status": ScreenshotStatus.FAILED,
                        "error": f"Resolved IP {ip_str} is private/internal and not authorized for screenshot capture.",
                    }
        except ValidationError:
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": "Target failed SSRF validation.",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": f"DNS resolution failed: {exc}",
            }

        # Storage directory — make sure it exists and is writable.
        storage_path = settings.RECON_SCREENSHOT_STORAGE_PATH
        try:
            os.makedirs(storage_path, exist_ok=True)
        except OSError as exc:
            logger.error(f"Screenshot storage path {storage_path} could not be created: {exc}")
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": f"Screenshot storage path is not writable: {exc}",
            }

        screenshot_id = uuid.uuid4().hex
        out_path = os.path.join(storage_path, f"{screenshot_id}.png")

        try:
            captured = await self._playwright_capture(url, out_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Screenshot capture failed for {url}: {exc}")
            # Clean up partial file
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": f"Capture failed: {exc}",
            }

        if not captured:
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": "Browser did not produce a screenshot.",
            }

        # Verify the file actually exists and is non-empty.  Do NOT
        # report success unless we have a real file on disk.
        if not os.path.isfile(out_path):
            logger.error(
                f"Screenshot capture reported success but file {out_path} "
                f"does not exist."
            )
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": "Screenshot file was not written to disk.",
            }
        file_size = os.path.getsize(out_path)
        if file_size == 0:
            logger.error(f"Screenshot file {out_path} is empty.")
            try:
                os.remove(out_path)
            except OSError:
                pass
            return {
                "url": url,
                "captured": False,
                "status": ScreenshotStatus.FAILED,
                "error": "Screenshot file is empty.",
            }

        logger.info(
            f"Screenshot captured for {url}: id={screenshot_id}, "
            f"size={file_size}b, path={out_path}"
        )

        # Public-facing URL reference — the API serves screenshots via a
        # dedicated endpoint that streams the file from disk.  We never
        # expose the raw filesystem path to the client.
        # The URL is relative to the apiClient's baseURL (/api/v1), so
        # the frontend can call apiClient.get(screenshot_url) directly.
        return {
            "url": url,
            "captured": True,
            "status": ScreenshotStatus.COMPLETED,
            "screenshot_id": screenshot_id,
            "screenshot_url": f"/recon/screenshots/{screenshot_id}",
            "screenshot_url_full": f"/api/v1/recon/screenshots/{screenshot_id}",
            "content_type": "image/png",
            "file_size": file_size,
        }

    async def _playwright_capture(self, url: str, out_path: str) -> bool:
        """Open Playwright Chromium, navigate to URL, capture screenshot.

        Returns True on success.  All errors are propagated to the caller.
        """
        # Import lazily so the module loads cleanly in test environments
        # where playwright browsers may not be installed.
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-pdf",
                    "--disable-printing",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
                # Disable downloads entirely
                accept_downloads=False,
                # 🛠️ Set realistic User-Agent to pass basic WAF/Cloudflare bot checks
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            try:
                # 🛠️ Fall back to 'commit' if 'domcontentloaded' takes too long
                try:
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=settings.RECON_SCREENSHOT_TIMEOUT * 1000,
                    )
                except Exception:
                    await page.goto(
                        url,
                        wait_until="commit",
                        timeout=settings.RECON_SCREENSHOT_TIMEOUT * 1000,
                    )

                # Give dynamic client-rendered content a moment to settle
                await page.wait_for_timeout(1000)
                await page.screenshot(path=out_path, full_page=False, type="png")
                return True
            finally:
                await context.close()
                await browser.close()
