# backend/app/recon/services/dns_service.py
"""DNS lookup service backed by ``dnspython``.

Supports the record types enumerated in the requirements: A, AAAA, CNAME,
MX, NS, TXT, SOA, PTR, CAA.
"""
from __future__ import annotations

from typing import List, Dict, Any

import dns.resolver
import dns.reversename
import dns.exception

from app.core.config import settings
from app.core.logging import logger
from app.recon.validators.target_validator import ValidatedTarget


_SUPPORTED_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA"]


class DnsService:
    def __init__(self) -> None:
        # Use the system resolver by default; the service is intentionally
        # stateless and creates a fresh resolver per call to avoid leaking
        # configuration between requests.
        pass

    async def lookup(self, target: ValidatedTarget) -> Dict[str, Any]:
        """Run all supported DNS lookups for the target's host.

        Returns ``{records: [{record_type, name, values, ttl}], target}``.
        """
        host = target.host
        records: List[Dict[str, Any]] = []
        for rtype in _SUPPORTED_TYPES:
            entry = await self._resolve(host, rtype)
            if entry:
                records.append(entry)

        # PTR lookup — reverse-resolve the first resolved A/AAAA address if any
        ptr = await self._ptr_lookup(host, records)
        if ptr:
            records.append(ptr)

        return {"target": host, "records": records}

    # ---- helpers --------------------------------------------------------
    async def _resolve(self, host: str, rtype: str) -> Dict[str, Any] | None:
        try:
            resolver = dns.resolver.Resolver()
            resolver.lifetime = settings.RECON_TIMEOUT
            answer = resolver.resolve(host, rtype)
            values: List[str] = []
            ttl = 0
            for rdata in answer:
                values.append(str(rdata).strip('"'))
                try:
                    ttl = max(ttl, int(rdata.ttl))
                except (AttributeError, ValueError):
                    pass
            return {
                "record_type": rtype,
                "name": host,
                "values": values,
                "ttl": ttl,
            }
        except dns.resolver.NoAnswer:
            return None
        except dns.resolver.NXDOMAIN:
            return None
        except dns.exception.DNSException as exc:
            logger.debug(f"DNS {rtype} lookup for {host} failed: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Unexpected DNS error for {host}/{rtype}: {exc}")
            return None

    async def _ptr_lookup(self, host: str, records: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        # Find the first A record value
        ip = None
        for rec in records:
            if rec["record_type"] == "A" and rec["values"]:
                ip = rec["values"][0]
                break
        if not ip:
            return None
        try:
            resolver = dns.resolver.Resolver()
            resolver.lifetime = settings.RECON_TIMEOUT
            rev = dns.reversename.from_address(ip)
            answer = resolver.resolve(rev, "PTR")
            values = [str(rdata).rstrip(".") for rdata in answer]
            return {
                "record_type": "PTR",
                "name": ip,
                "values": values,
                "ttl": 0,
            }
        except Exception:  # noqa: BLE001
            return None
