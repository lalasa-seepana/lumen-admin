from __future__ import annotations

import ipaddress
import socket
from typing import Tuple
from urllib.parse import urlparse


def validate_public_http_url(url: str) -> Tuple[str, str]:
    """Return (normalized_url, hostname) or raise ValueError with code."""
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url_scheme_invalid")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("url_host_missing")
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("url_private_host")
    if host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("url_private_host")
    blocked_prefixes = ("169.254.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.")
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError("url_private_host")
    except ValueError:
        if host.startswith(blocked_prefixes):
            raise ValueError("url_private_host")
        # Resolve hostname — block if any A/AAAA is private
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("url_unreachable") from exc
        for info in infos:
            sockaddr = info[4]
            if not sockaddr:
                continue
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("url_private_host")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    normalized = f"{parsed.scheme}://{host}{path}"
    if parsed.port and not ((parsed.scheme == "http" and parsed.port == 80) or (parsed.scheme == "https" and parsed.port == 443)):
        normalized = f"{parsed.scheme}://{host}:{parsed.port}{path}"
    return normalized, host