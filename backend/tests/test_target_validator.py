# backend/tests/test_target_validator.py
"""Tests for the SSRF / target validation module.

These are pure-Python unit tests — no database, no network, no external
services.  They cover the security-critical path that protects the
application from being used as an SSRF pivot.
"""
import pytest

from app.recon.validators.target_validator import (
    TargetValidator, ValidationError, validate_ports,
)


class TestDomainValidation:
    def test_valid_domain(self):
        v = TargetValidator.validate("example.com")
        assert v.target_type == "DOMAIN"
        assert v.host == "example.com"
        assert v.scheme is None

    def test_domain_lowercase_normalised(self):
        v = TargetValidator.validate("EXAMPLE.COM")
        assert v.host == "example.com"

    def test_subdomain(self):
        v = TargetValidator.validate("api.sub.example.com")
        assert v.target_type == "DOMAIN"
        assert v.host == "api.sub.example.com"

    def test_invalid_domain_missing_tld(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("localhost-like-name")
        assert exc.value.code == "INVALID_DOMAIN"

    def test_invalid_domain_chars(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("exa_mple.com")
        assert exc.value.code in ("INVALID_DOMAIN", "TARGET_NOT_ALLOWED")

    def test_empty_target(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("")
        assert exc.value.code == "TARGET_REQUIRED"

    def test_none_target(self):
        with pytest.raises(ValidationError):
            TargetValidator.validate(None)


class TestIPValidation:
    def test_valid_public_ipv4(self):
        v = TargetValidator.validate("8.8.8.8")
        assert v.target_type == "IP"
        assert v.host == "8.8.8.8"
        assert v.ip_addresses == ["8.8.8.8"]

    def test_valid_public_ipv6(self):
        v = TargetValidator.validate("2606:4700:4700::1111")
        assert v.target_type == "IP"

    def test_loopback_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("127.0.0.1")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_loopback_v6_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("::1")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_private_10_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("10.0.0.1")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_private_172_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("172.16.5.4")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_private_192_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("192.168.1.1")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_link_local_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("169.254.169.254")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_unspecified_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("0.0.0.0")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_cgnat_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("100.64.0.1")
        assert exc.value.code == "TARGET_NOT_ALLOWED"


class TestCIDRValidation:
    def test_valid_public_cidr(self):
        # 8.0.0.0/29 — only 8 addresses, well under RECON_MAX_HOSTS (256)
        v = TargetValidator.validate("8.0.0.0/29")
        assert v.target_type == "CIDR"
        assert v.cidr == "8.0.0.0/29"

    def test_private_cidr_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("192.168.0.0/24")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_loopback_cidr_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("127.0.0.0/8")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_cidr_too_large(self):
        # 8.0.0.0/8 — 16M addresses, way over RECON_MAX_HOSTS
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("8.0.0.0/8")
        assert exc.value.code == "CIDR_TOO_LARGE"

    def test_invalid_cidr(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("not.a.cidr/24")
        assert exc.value.code == "INVALID_CIDR"


class TestURLValidation:
    def test_valid_http_url(self):
        v = TargetValidator.validate("http://example.com/path")
        assert v.target_type == "URL"
        assert v.host == "example.com"
        assert v.scheme == "http"
        assert v.port == 80

    def test_valid_https_url(self):
        v = TargetValidator.validate("https://example.com:8443/secure")
        assert v.target_type == "URL"
        assert v.host == "example.com"
        assert v.scheme == "https"
        assert v.port == 8443

    def test_url_to_localhost_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("http://localhost/admin")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_url_to_127_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("http://127.0.0.1/admin")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_url_to_metadata_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("http://169.254.169.254/latest/meta-data/")
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_unsupported_scheme(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("file:///etc/passwd")
        # file:// doesn't start with http/https so falls through to domain
        # validation which rejects "file" as not having a valid TLD.
        assert exc.value.code in ("UNSUPPORTED_PROTOCOL", "INVALID_DOMAIN")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("ftp://example.com/")
        # ftp:// is parsed by urlparse but scheme not in (http, https)
        assert exc.value.code == "UNSUPPORTED_PROTOCOL"


class TestInternalHostnames:
    def test_db_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("db")
        assert exc.value.code in ("INVALID_DOMAIN", "TARGET_NOT_ALLOWED")

    def test_redis_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("redis")
        assert exc.value.code in ("INVALID_DOMAIN", "TARGET_NOT_ALLOWED")

    def test_metadata_google_internal_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.validate("metadata.google.internal")
        assert exc.value.code == "TARGET_NOT_ALLOWED"


class TestPortValidation:
    def test_valid_ports(self):
        result = validate_ports([80, 443, 8080])
        assert result == [80, 443, 8080]

    def test_dedup_ports(self):
        result = validate_ports([80, 80, 443])
        assert result == [80, 443]

    def test_port_too_low(self):
        with pytest.raises(ValidationError) as exc:
            validate_ports([0])
        assert exc.value.code == "PORT_INVALID"

    def test_port_too_high(self):
        with pytest.raises(ValidationError) as exc:
            validate_ports([70000])
        assert exc.value.code == "PORT_INVALID"

    def test_empty_port_list(self):
        with pytest.raises(ValidationError) as exc:
            validate_ports([])
        assert exc.value.code == "PORTS_REQUIRED"

    def test_too_many_ports(self, monkeypatch):
        # Override the configured max for this test
        from app.core.config import settings
        monkeypatch.setattr(settings, "RECON_MAX_PORTS", 5)
        with pytest.raises(ValidationError) as exc:
            validate_ports([1, 2, 3, 4, 5, 6])
        assert exc.value.code == "PORTS_TOO_MANY"


class TestResolvedIPGuard:
    """SSRF guard invoked AFTER DNS resolution at scan time."""

    def test_resolved_loopback_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.check_resolved_ips(["127.0.0.1"])
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_resolved_metadata_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.check_resolved_ips(["169.254.169.254"])
        assert exc.value.code == "TARGET_NOT_ALLOWED"

    def test_resolved_public_allowed(self):
        # Should not raise
        TargetValidator.check_resolved_ips(["8.8.8.8", "1.1.1.1"])

    def test_resolved_mixed_blocked(self):
        with pytest.raises(ValidationError) as exc:
            TargetValidator.check_resolved_ips(["8.8.8.8", "127.0.0.1"])
        assert exc.value.code == "TARGET_NOT_ALLOWED"
