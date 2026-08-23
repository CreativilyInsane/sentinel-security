# backend/app/recon/services/whois_service.py
"""WHOIS lookup service backed by the ``python-whois`` package.

The library performs RDAP-aware lookups against the appropriate registrar
WHOIS servers and returns parsed fields.  Privacy-protected domains are
handled gracefully — missing registrant fields are simply omitted from
the result rather than raising an error.
"""
from __future__ import annotations

from typing import Dict, Any

import whois

from app.core.logging import logger
from app.recon.validators.target_validator import ValidatedTarget


class WhoisService:
    async def lookup(self, target: ValidatedTarget) -> Dict[str, Any]:
        host = target.host
        try:
            data = whois.whois(host)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"WHOIS lookup failed for {host}: {exc}")
            return {
                "target": host,
                "available": False,
                "error": f"WHOIS lookup failed: {exc}",
            }

        if not data or (hasattr(data, "domain_name") and not data.domain_name):
            return {
                "target": host,
                "available": False,
                "error": "No WHOIS data available for this domain.",
            }

        def _coerce(v: Any) -> Any:
            # python-whois returns lists for some fields; flatten single-item lists.
            if isinstance(v, list):
                if not v:
                    return None
                if len(v) == 1:
                    return v[0]
                return v
            return v

        def _dt(v: Any) -> str | None:
            if v is None:
                return None
            try:
                # python-whois returns datetime objects
                return v.isoformat() if hasattr(v, "isoformat") else str(v)
            except Exception:  # noqa: BLE001
                return str(v)

        result: Dict[str, Any] = {
            "target": host,
            "available": True,
            "domain": _coerce(data.get("domain_name")),
            "registrar": _coerce(data.get("registrar")),
            "creation_date": _dt(_coerce(data.get("creation_date"))),
            "expiration_date": _dt(_coerce(data.get("expiration_date"))),
            "updated_date": _dt(_coerce(data.get("updated_date"))),
            "name_servers": _coerce(data.get("name_servers")) or [],
            "status": _coerce(data.get("status")) or [],
            # Registrant information — only include fields actually returned
            "registrant": {
                "name": _coerce(data.get("name")),
                "organization": _coerce(data.get("org")),
                "country": _coerce(data.get("country")),
                "state": _coerce(data.get("state")),
                "city": _coerce(data.get("city")),
                "address": _coerce(data.get("address")),
                "email": _coerce(data.get("emails")),
            },
        }
        # Privacy-protected domains often have all registrant fields stripped —
        # collapse an all-null registrant object into None for cleaner reports.
        if not any(v for v in result["registrant"].values()):
            result["registrant"] = None
        return result
