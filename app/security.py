"""
Захисні механізми застосунку.

1. verify_api_key   - перевірка секретного заголовка X-API-Key на кожен виклик /api/parse.
2. validate_public_url - захист від SSRF: URL, який просить обробити користувач,
   не повинен резолвитись у приватну/локальну/link-local адресу. Це блокує, зокрема,
   спроби (навмисні чи через редирект на скомпрометованому сайті) достукатись до
   169.254.169.254 - metadata endpoint хмарних провайдерів (Oracle Cloud, AWS, GCP тощо),
   де можуть лежати облікові дані інстансу.

ВАЖЛИВО (чесно про межі захисту): перевірка нижче резолвить DNS ОДИН РАЗ, до того як
crawl4ai/Playwright самі підуть по мережі. Це закриває пряме звернення на приватні IP
та найпростіші випадки, але теоретично не захищає на 100% від:
  - DNS rebinding (домен віддає публічну IP під час перевірки, а потім - приватну),
  - SSRF через ланцюжок HTTP-редиректів на самому сайті.
Для персонального інструменту, яким керуєте лише ви, це прийнятний рівень ризику.
Якщо захочете закрити і ці вектори - додайте фільтрацію на рівні мережі/iptables
для контейнера backend (блокувати вихідний трафік на 169.254.169.254 та RFC1918
діапазони), це вже не обійти на рівні застосунку.
"""
import ipaddress
import secrets
import socket
from urllib.parse import urlparse

from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI-залежність: кидає 401, якщо заголовок X-API-Key відсутній або невірний.
    Порівняння через secrets.compare_digest - захист від timing-атак."""
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний або відсутній API-ключ (заголовок X-API-Key)",
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
    """Повертає url, якщо він публічний та безпечний. Інакше кидає HTTPException(400)."""
    if len(url) > settings.max_url_length:
        raise HTTPException(status_code=400, detail="URL занадто довгий")

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Некоректний URL")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Дозволені лише URL зі схемою http:// або https://")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="У URL відсутній хост")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Не вдалося резолвити хост: {hostname}")

    if not infos:
        raise HTTPException(status_code=400, detail=f"Хост не резолвиться в жодну адресу: {hostname}")

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
                    f"URL резолвиться у заборонену (приватну/локальну) адресу ({ip_str}). "
                    "Це обмеження існує для захисту від SSRF-атак."
                ),
            )

    return url