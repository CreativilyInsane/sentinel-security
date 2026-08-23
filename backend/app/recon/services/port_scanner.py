# backend/app/recon/services/port_scanner.py
"""Safe TCP connect() port scanner.

Only the TCP three-way handshake is performed — no SYN scanning, no raw
packet crafting, no evasion.  Concurrency is bounded by the application
setting ``RECON_MAX_CONCURRENT_CONNECTIONS``.
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import PortPreset
from app.core.logging import logger
from app.recon.validators.target_validator import ValidatedTarget


# Well-known service guesses for common ports — used purely as a hint
# for display purposes; authoritative service detection happens in
# service_detection.py.
_PORT_SERVICE_GUESS: Dict[int, str] = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 143: "imap", 443: "https", 445: "smb",
    587: "smtp-submission", 993: "imaps", 995: "pop3s",
    3306: "mysql", 3389: "rdp", 5432: "postgresql", 6379: "redis",
    8000: "http-alt", 8080: "http-alt", 8443: "https-alt",
    3000: "http-alt", 5000: "http-alt", 9000: "http-alt",
}


class PortScannerService:
    async def scan(
        self,
        target: ValidatedTarget,
        host_ip: str,
        *,
        port_preset: Optional[str] = None,
        custom_ports: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Scan a single host IP.  Returns ``{host, ip, ports: [...]}``.

        Each port entry: ``{port, state, protocol, service_guess, latency_ms}``.
        """
        ports = self._resolve_ports(port_preset, custom_ports)
        if not ports:
            return {"host": target.host, "ip": host_ip, "ports": []}

        semaphore = asyncio.Semaphore(settings.RECON_MAX_CONCURRENT_CONNECTIONS)
        results: List[Dict[str, Any]] = []

        async def probe(port: int) -> Dict[str, Any]:
            async with semaphore:
                latency = await self._tcp_connect(host_ip, port)
                state = "open" if latency is not None else "closed"
                return {
                    "port": port,
                    "state": state,
                    "protocol": "tcp",
                    "service_guess": _PORT_SERVICE_GUESS.get(port, "unknown"),
                    "latency_ms": latency,
                }

        tasks = [probe(p) for p in ports]
        for fut in asyncio.as_completed(tasks):
            results.append(await fut)

        # Sort by port number for stable output
        results.sort(key=lambda r: r["port"])
        return {"host": target.host, "ip": host_ip, "ports": results}

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def _resolve_ports(
        port_preset: Optional[str],
        custom_ports: Optional[List[int]],
    ) -> List[int]:
        if port_preset == PortPreset.CUSTOM:
            return list(custom_ports or [])
        if port_preset == PortPreset.WEB:
            return list(PortPreset.WEB_PORTS)
        # Default to common ports (also used when preset is None)
        return list(PortPreset.COMMON_PORTS)

    @staticmethod
    async def _tcp_connect(ip: str, port: int) -> Optional[int]:
        start = time.perf_counter()
        try:
            fut = asyncio.open_connection(ip, port)
            _, writer = await asyncio.wait_for(fut, timeout=settings.RECON_TIMEOUT)
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return latency_ms
        except asyncio.TimeoutError:
            return None
        except (ConnectionRefusedError, OSError):
            return None
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Port probe failed for {ip}:{port} -> {exc}")
            return None
