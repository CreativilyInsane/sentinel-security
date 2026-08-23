# backend/app/recon/services/http_service.py
"""HTTP header analysis service.

Issues a single normal GET request to the target URL with strict timeouts
and resource limits, then evaluates the security headers in the response.
"""
from __future__ import annotations

from typing import Dict, Any, List

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.recon.validators.target_validator import ValidatedTarget, TargetValidator


# Header → severity mapping when the header is MISSING.
_SECURITY_HEADERS: List[Dict[str, Any]] = [
    {"header": "Content-Security-Policy",       "severity": "high"},
    {"header": "Strict-Transport-Security",     "severity": "high"},
    {"header": "X-Content-Type-Options",        "severity": "medium"},
    {"header": "X-Frame-Options",               "severity": "medium"},
    {"header": "Referrer-Policy",               "severity": "low"},
    {"header": "Permissions-Policy",            "severity": "low"},
    {"header": "Cross-Origin-Opener-Policy",    "severity": "low"},
    {"header": "Cross-Origin-Resource-Policy",  "severity": "low"},
]


class HttpService:
    async def analyze(self, target: ValidatedTarget) -> Dict[str, Any]:
        # Build the URL to probe.
        if target.target_type == "URL":
            url = target.raw
        elif target.target_type == "IP":
            url = f"http://{target.host}/"
        else:
            # DOMAIN — try https first, fall back to http on failure
            url = f"https://{target.host}/"

        result = await self._fetch(url)
        if result.get("error") and url.startswith("https://") and target.target_type != "URL":
            # Fall back to http
            url = f"http://{target.host}/"
            result = await self._fetch(url)

        return result

    # ---- fetch ----------------------------------------------------------
    async def _fetch(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.RECON_TIMEOUT,
                follow_redirects=True,
                max_redirects=settings.RECON_MAX_REDIRECTS,
                verify=False,  # Recon reports whatever cert the server presents
            ) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Basir-Recon/1.0 (+security scanning)"},
                )
                # Read up to RECON_HTTP_MAX_RESPONSE_SIZE
                content_length = int(response.headers.get("content-length", 0) or 0)
                if content_length > settings.RECON_HTTP_MAX_RESPONSE_SIZE:
                    return {
                        "url": url,
                        "available": False,
                        "error": "Response exceeds maximum allowed size.",
                    }
                headers_dict = {k: v for k, v in response.headers.items()}
                body_preview = response.text[:1024] if response.text else ""
        except httpx.TimeoutException:
            return {"url": url, "available": False, "error": "Request timed out."}
        except httpx.RequestError as exc:
            logger.debug(f"HTTP fetch failed for {url} -> {exc}")
            return {"url": url, "available": False, "error": f"Request failed: {exc}"}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Unexpected HTTP error for {url} -> {exc}")
            return {"url": url, "available": False, "error": f"Unexpected error: {exc}"}

        # --- Analyze security headers ---
        security_headers: List[Dict[str, Any]] = []
        for spec in _SECURITY_HEADERS:
            name = spec["header"]
            present = name.lower() in {k.lower() for k in headers_dict}
            value = next((v for k, v in headers_dict.items() if k.lower() == name.lower()), None)
            security_headers.append({
                "header": name,
                "present": present,
                "value": value,
                "severity": "good" if present else spec["severity"],
            })

        # Server / Content-Type / Content-Length for the report
        return {
            "url": url,
            "available": True,
            "status_code": response.status_code,
            "server": headers_dict.get("server"),
            "content_type": headers_dict.get("content-type"),
            "content_length": content_length or len(response.content),
            "headers": headers_dict,
            "body_preview": body_preview,
            "security_headers": security_headers,
            "redirected": len(response.history) > 0,
            "final_url": str(response.url),
        }
