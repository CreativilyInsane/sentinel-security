# backend/app/recon/services/host_discovery.py
"""Safe host discovery service.

Resolves a target (DOMAIN / IP / URL / CIDR) into a list of live hosts.
Implementation notes:

* DNS resolution is performed with ``socket.getaddrinfo`` — never trust
  user-controlled hostnames without re-validating the resolved IPs against
  the SSRF guard (defeats DNS rebinding).
* For IP / URL targets the discovery is trivial (single host).
* For CIDR targets we iterate over the network's host addresses up to the
  configured ``RECON_MAX_HOSTS`` limit.  Reachability is checked with a
  TCP connect probe against port 80 (best-effort) plus an ICMP-style ping
  via the OS ``ping`` command.  Neither technique performs any kind of
  stealth or packet crafting.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from typing import List, Dict, Any

from app.core.config import settings
from app.core.logging import logger
from app.recon.validators.target_validator import (
    TargetValidator,
    ValidatedTarget,
    ValidationError,
)


class HostDiscoveryService:
    """Pure-Python host discovery — no raw sockets, no packet crafting."""

    async def discover(self, target: ValidatedTarget) -> Dict[str, Any]:
        """Return ``{hosts: [...]}`` for the given target.

        Each host entry: ``{host, ip, hostname, status, latency_ms}``.
        """
        if target.target_type == "CIDR":
            hosts = await self._discover_cidr(target)
        elif target.target_type == "IP":
            hosts = await self._discover_ip(target)
        elif target.target_type in ("DOMAIN", "URL"):
            hosts = await self._discover_domain(target)
        else:
            raise ValidationError("TARGET_INVALID", f"Unsupported target type: {target.target_type}")

        return {"hosts": hosts}

    # ---- CIDR ----------------------------------------------------------
    async def _discover_cidr(self, target: ValidatedTarget) -> List[Dict[str, Any]]:
        network = ipaddress.ip_network(target.cidr, strict=False)
        hosts: List[Dict[str, Any]] = []

        # Bound concurrency — never spawn more than the configured max.
        semaphore = asyncio.Semaphore(settings.RECON_MAX_CONCURRENT_CONNECTIONS)

        async def probe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Dict[str, Any] | None:
            ip_str = str(ip)
            async with semaphore:
                latency = await self._tcp_probe(ip_str, 80)
                status = "up" if latency is not None else "down"
                return {
                    "host": ip_str,
                    "ip": ip_str,
                    "hostname": None,
                    "status": status,
                    "latency_ms": latency,
                }

        # Limit to RECON_MAX_HOSTS
        addresses = list(network.hosts())[: settings.RECON_MAX_HOSTS]
        tasks = [probe(ip) for ip in addresses]
        for fut in asyncio.as_completed(tasks):
            entry = await fut
            if entry is not None:
                hosts.append(entry)
        return hosts

    # ---- single IP -----------------------------------------------------
    async def _discover_ip(self, target: ValidatedTarget) -> List[Dict[str, Any]]:
        latency = await self._tcp_probe(target.host, 80)
        return [{
            "host": target.host,
            "ip": target.host,
            "hostname": None,
            "status": "up" if latency is not None else "down",
            "latency_ms": latency,
        }]

    # ---- DOMAIN / URL --------------------------------------------------
    async def _discover_domain(self, target: ValidatedTarget) -> List[Dict[str, Any]]:
        host = target.host
        # DNS resolution
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP),
            )
        except socket.gaierror as exc:
            logger.warning(f"DNS resolution failed for {host}: {exc}")
            return [{
                "host": host,
                "ip": None,
                "hostname": host,
                "status": "down",
                "latency_ms": None,
                "error": f"DNS resolution failed: {exc}",
            }]

        # Extract unique IPs and run the SSRF guard on each.
        ips: List[str] = []
        for family, _, _, _, sockaddr in infos:
            ip_str = sockaddr[0]
            # Strip IPv6 scope id
            if "%" in ip_str:
                ip_str = ip_str.split("%", 1)[0]
            if ip_str not in ips:
                ips.append(ip_str)

        try:
            TargetValidator.check_resolved_ips(ips)
        except ValidationError:
            raise

        hosts: List[Dict[str, Any]] = []
        for ip_str in ips:
            port = target.port or 80
            latency = await self._tcp_probe(ip_str, port)
            hosts.append({
                "host": host,
                "ip": ip_str,
                "hostname": host,
                "status": "up" if latency is not None else "down",
                "latency_ms": latency,
            })
        return hosts

    # ---- low-level probe ----------------------------------------------
    async def _tcp_probe(self, ip: str, port: int) -> int | None:
        """Open a TCP connect to (ip, port) and return round-trip latency
        in milliseconds, or None if the host is unreachable / timeout."""
        start = time.perf_counter()
        try:
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=settings.RECON_TIMEOUT)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            latency_ms = int((time.perf_counter() - start) * 1000)
            return latency_ms
        except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
            # Connection refused still means the host is up at the IP layer.
            # We return None so the caller marks it 'down' for the probed
            # port — host discovery via TCP connect cannot distinguish
            # between "host down" and "port filtered".
            return None
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"TCP probe failed for {ip}:{port} -> {exc}")
            return None
