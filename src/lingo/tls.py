"""Self-signed TLS certs so phones on LAN can use the microphone over HTTPS."""

from __future__ import annotations

import ipaddress
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from loguru import logger


def discover_lan_ips() -> list[str]:
    """Best-effort list of non-loopback IPv4 addresses on this machine."""
    ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass

    return sorted(ips)


def ensure_self_signed_cert(
    cert_dir: Path,
    *,
    extra_hosts: list[str] | None = None,
) -> tuple[Path, Path]:
    """Return (cert_file, key_file), generating a fresh self-signed pair if needed."""
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"

    hosts = sorted({"localhost", "127.0.0.1", *(extra_hosts or []), *discover_lan_ips()})
    marker = cert_dir / "sans.txt"
    desired = "\n".join(hosts)

    if cert_file.exists() and key_file.exists() and marker.exists():
        if marker.read_text(encoding="utf-8") == desired:
            return cert_file, key_file

    logger.info("Generating self-signed TLS certificate for hosts: {}", ", ".join(hosts))

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Lingo Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Lingo"),
        ]
    )

    alt_names: list[x509.GeneralName] = []
    for host in hosts:
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            alt_names.append(x509.DNSName(host))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    marker.write_text(desired, encoding="utf-8")
    return cert_file, key_file
