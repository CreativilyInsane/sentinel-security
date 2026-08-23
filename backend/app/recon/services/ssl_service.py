# backend/app/recon/services/ssl_service.py
"""SSL/TLS certificate inspection service.

Uses ``ssl`` + ``socket`` from the standard library to retrieve the server
certificate, then parses it with ``cryptography.x509``.  No intrusive TLS
attacks are performed — we simply establish a normal TLS handshake and
read the certificate the server presents.
"""
from __future__ import annotations

import ssl
import socket
from datetime import datetime, timezone
from typing import Dict, Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from app.core.config import settings
from app.core.logging import logger
from app.recon.validators.target_validator import ValidatedTarget


class SslService:
    async def analyze(self, target: ValidatedTarget, host_ip: str | None = None) -> Dict[str, Any]:
        host = target.host
        port = target.port or 443
        # If target is DOMAIN/URL with explicit https port, use that.
        if target.target_type == "URL" and target.scheme == "https" and target.port:
            port = target.port

        cert_pem = await self._fetch_cert(host, port)
        if cert_pem is None:
            return {
                "hostname": host,
                "port": port,
                "available": False,
                "error": "TLS handshake failed or no certificate returned.",
            }
        return self._parse_cert(cert_pem, host, port)

    # ---- fetch ----------------------------------------------------------
    async def _fetch_cert(self, host: str, port: int) -> bytes | None:
        # Run in default executor — the stdlib ssl module is blocking.
        loop = __import__("asyncio").get_running_loop()

        def _do() -> bytes | None:
            ctx = ssl.create_default_context()
            # We intentionally do NOT verify the chain — the goal of the
            # recon module is to *report* the certificate the server
            # presents, including self-signed / expired ones.  Chain
            # verification would prevent us from inspecting those.
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                with socket.create_connection((host, port), timeout=settings.RECON_TIMEOUT) as sock:
                    with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                        # getpeercert(binary_form=True) returns DER even when
                        # verify_mode == CERT_NONE (unlike the dict form).
                        der = ssock.getpeercert(binary_form=True)
                        if not der:
                            return None
                        # Convert DER -> PEM via cryptography for stable parsing
                        cert = x509.load_der_x509_certificate(der, default_backend())
                        return cert.public_bytes(__import__("cryptography").hazmat.primitives.serialization.Encoding.PEM)
            except (ssl.SSLError, OSError, ValueError) as exc:
                logger.debug(f"SSL fetch failed for {host}:{port} -> {exc}")
                return None
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Unexpected SSL error for {host}:{port} -> {exc}")
                return None

        return await loop.run_in_executor(None, _do)

    # ---- parse ----------------------------------------------------------
    def _parse_cert(self, cert_pem: bytes, host: str, port: int) -> Dict[str, Any]:
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())

        def _dt(dt) -> str | None:
            if dt is None:
                return None
            if hasattr(dt, "isoformat"):
                return dt.isoformat()
            return str(dt)

        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        valid_from = _dt(cert.not_valid_before_utc) if hasattr(cert, "not_valid_before_utc") else _dt(cert.not_valid_before)
        valid_until = _dt(cert.not_valid_after_utc) if hasattr(cert, "not_valid_after_utc") else _dt(cert.not_valid_after)

        # Days remaining
        try:
            now = datetime.now(timezone.utc)
            expires_at = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            days_remaining = (expires_at - now).days
        except Exception:  # noqa: BLE001
            days_remaining = None

        # Status
        if days_remaining is None:
            status = "Unknown"
        elif days_remaining < 0:
            status = "Expired"
        elif days_remaining <= 30:
            status = "Expiring Soon"
        else:
            status = "Valid"

        # SANs
        try:
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            sans = san_ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            sans = []

        # Public key info
        try:
            pub = cert.public_key()
            public_key_algorithm = pub.__class__.__name__.replace("PublicKey", "").replace("_", "")
        except Exception:  # noqa: BLE001
            public_key_algorithm = "unknown"

        return {
            "hostname": host,
            "port": port,
            "available": True,
            "tls_version": None,  # Cannot reliably extract without re-handshake
            "certificate_subject": subject,
            "certificate_issuer": issuer,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "days_remaining": days_remaining,
            "serial_number": str(cert.serial_number),
            "signature_algorithm": cert.signature_algorithm_oid._name,
            "public_key_algorithm": public_key_algorithm,
            "sans": sans,
            "chain_status": "self-signed" if subject == issuer else "provided",
            "expiration_status": status,
        }
