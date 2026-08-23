# backend/app/recon/services/service_detection.py
"""Lightweight service identification for discovered open ports.

For each open port the service performs a protocol-aware probe:

* HTTP/HTTPS — issue a minimal ``HEAD /`` request and read the status line +
  Server / Content-Type headers.
* SSH (22) — read the banner line ("SSH-2.0-OpenSSH_8.9p1 …").
* FTP (21), SMTP (25/587), POP3 (110), IMAP (143) — read the greeting line.
* MySQL / PostgreSQL / Redis — read the initial handshake packet (truncated).

The detector never attempts authentication, exploitation, or brute force.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Any, List

from app.core.config import settings
from app.core.logging import logger
from app.recon.validators.target_validator import ValidatedTarget


# Map port -> (service_name, probe_kind)
_PROTOCOL_MAP: Dict[int, tuple[str, str]] = {
    21: ("ftp", "banner"),
    22: ("ssh", "banner"),
    23: ("telnet", "banner"),
    25: ("smtp", "banner"),
    53: ("dns", "skip"),
    80: ("http", "http"),
    110: ("pop3", "banner"),
    143: ("imap", "banner"),
    443: ("https", "http"),
    445: ("smb", "skip"),
    587: ("smtp-submission", "banner"),
    993: ("imaps", "skip"),
    995: ("pop3s", "skip"),
    3306: ("mysql", "banner"),
    3389: ("rdp", "skip"),
    5432: ("postgresql", "banner"),
    6379: ("redis", "banner"),
    8080: ("http-alt", "http"),
    8443: ("https-alt", "http"),
}


class ServiceDetectionService:
    async def detect(
        self,
        target: ValidatedTarget,
        host_ip: str,
        open_ports: List[int],
    ) -> Dict[str, Any]:
        """Probe each open port for service identification.

        Returns ``{host, ip, services: [{port, service, protocol, banner, version, confidence}]}``.
        """
        services: List[Dict[str, Any]] = []
        for port in open_ports:
            entry = await self._probe_port(host_ip, port)
            services.append(entry)
        return {"host": target.host, "ip": host_ip, "services": services}

    # ---- per-port probe ------------------------------------------------
    async def _probe_port(self, ip: str, port: int) -> Dict[str, Any]:
        service_name, probe_kind = _PROTOCOL_MAP.get(port, ("unknown", "banner"))
        base: Dict[str, Any] = {
            "port": port,
            "service": service_name,
            "protocol": "tcp",
            "banner": None,
            "version": None,
            "confidence": "low" if service_name == "unknown" else "medium",
        }
        if probe_kind == "skip":
            base["confidence"] = "low"
            return base

        try:
            if probe_kind == "http":
                banner, version = await self._http_probe(ip, port, tls=(port in (443, 8443)))
            else:
                banner = await self._banner_probe(ip, port)
                version = self._parse_version(service_name, banner)
            base["banner"] = banner
            base["version"] = version
            base["confidence"] = "high" if banner else "medium"
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Service detection failed for {ip}:{port} -> {exc}")
            base["banner"] = None
        return base

    # ---- banner (read-only) --------------------------------------------
    async def _banner_probe(self, ip: str, port: int) -> str | None:
        try:
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=settings.RECON_TIMEOUT)
            try:
                # Some services (MySQL/Postgres/Redis) send a greeting
                # immediately; others (HTTP) wait for a request — but we
                # only call this for banner-kind services.
                data = await asyncio.wait_for(reader.read(512), timeout=3.0)
                banner = data.decode("utf-8", errors="replace").strip().splitlines()[0] if data else None
                return banner
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
        except (asyncio.TimeoutError, OSError):
            return None

    # ---- HTTP probe -----------------------------------------------------
    async def _http_probe(self, ip: str, port: int, *, tls: bool) -> tuple[str | None, str | None]:
        try:
            if tls:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                fut = asyncio.open_connection(ip, port, ssl=ctx, server_hostname=ip)
            else:
                fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=settings.RECON_TIMEOUT)
            try:
                request = (
                    f"HEAD / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: Basir-Recon/1.0\r\n"
                    f"Connection: close\r\n\r\n"
                )
                writer.write(request.encode("ascii"))
                await writer.drain()
                # Read up to 4KB of headers
                data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

            text = data.decode("iso-8859-1", errors="replace")
            first_line = text.splitlines()[0] if text else ""
            server = None
            for line in text.splitlines():
                if line.lower().startswith("server:"):
                    server = line.split(":", 1)[1].strip()
                    break
            banner = first_line or None
            version = server
            return banner, version
        except (asyncio.TimeoutError, OSError):
            return None, None

    # ---- version parsing -----------------------------------------------
    @staticmethod
    def _parse_version(service_name: str, banner: str | None) -> str | None:
        if not banner:
            return None
        # Common patterns:
        #   "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.4"
        #   "ProFTPD 1.3.7a Server (Debian) [::]:21"
        #   "MySQL 8.0.35"
        #   "PostgreSQL 14.9"
        #   "Redis 7.0.11"
        import re

        # Special case: SSH banner — the version follows the second hyphen
        ssh_match = re.match(r"SSH-(\S+)", banner, re.IGNORECASE)
        if ssh_match:
            # banner like "SSH-2.0-OpenSSH_8.9p1 ..." — return the part
            # between the second '-' and the first whitespace.
            parts = banner.split("-", 2)
            if len(parts) >= 3:
                version = parts[2].split()[0].strip()
                return version or None

        # Try named markers — version is the token immediately after the marker
        for marker in ("OpenSSH", "MySQL", "PostgreSQL", "Redis", "ProFTPD", "vsftpd", "Apache"):
            pattern = re.compile(re.escape(marker) + r"[\s/_-]+([^\s/]+)", re.IGNORECASE)
            match = pattern.search(banner)
            if match:
                return match.group(1).strip(" /\x00\r\n")

        # Fall back to the service_name marker
        if service_name and service_name.lower() in banner.lower():
            pattern = re.compile(re.escape(service_name) + r"[\s/_-]+([^\s/]+)", re.IGNORECASE)
            match = pattern.search(banner)
            if match:
                return match.group(1).strip(" /\x00\r\n")
        return None
