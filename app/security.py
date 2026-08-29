"""
Application security helpers.

1. `verify_api_key` — require a secret `X-API-Key` header on every API call.
2. `validate_public_url` — SSRF guard: the URL the user asks to fetch must not
   resolve to a private, loopback, or link-local address. That blocks attempts
   (intentional or via a compromised redirect) to hit 169.254.169.254, the
   cloud metadata endpoint (Oracle Cloud, AWS, GCP, and others) where instance
   credentials can live.

Honest limits: DNS is resolved once *before* Crawl4AI / Playwright go online.
That blocks direct private IPs and the simple cases, but it is not a 100%
guarantee against:
  - DNS rebinding (public IP during the check, private IP later),
  - SSRF via a chain of HTTP redirects on the target site.

For a personal tool you control, this is a reasonable risk level. To close
those remaining vectors, filter at the network / iptables layer for the
backend container (block outbound traffic to 169.254.169.254 and RFC1918
ranges). That cannot be fully enforced in application code alone.
"""
import ipaddress
import secrets
import socket
from urllib.parse import urlparse

from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency: 401 if `X-API-Key` is missing or wrong.

    Comparison uses `secrets.compare_digest` to reduce timing-attack risk.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (X-API-Key header)",
        )


_FORBIDDEN_REASONS = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
    "is_unspecified",
)


def validate_public_url(url: str) -> str:
    """Return `url` if it is public and safe. Otherwise raise HTTPException(400)."""
    if len(url) > settings.max_url_length:
        raise HTTPException(status_code=400, detail="URL is too long")

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http:// and https:// URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="URL is missing a host")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Could not resolve host: {hostname}")

    if not infos:
        raise HTTPException(status_code=400, detail=f"Host does not resolve to any address: {hostname}")

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if any(getattr(ip, attr) for attr in _FORBIDDEN_REASONS):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"URL resolves to a forbidden (private/local) address ({ip_str}). "
                    "This restriction exists to protect against SSRF attacks."
                ),
            )

    return url
