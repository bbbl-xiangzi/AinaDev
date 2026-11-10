"""Choose an explicitly trusted browser origin for SSO callbacks."""
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.config import settings


def _origin(value: str) -> str:
    try:
        parsed = urlsplit(value.rstrip('/'))
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment
                or any(c.isspace() or c in '\\|,' or ord(c) < 32 for c in value)
                or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            raise ValueError()
        return f'{parsed.scheme}://{parsed.netloc.lower()}'
    except ValueError:
        raise HTTPException(400, detail='访问地址无效，请检查公开地址和反向代理配置') from None


def public_origin(request: Request | None = None) -> str:
    primary = _origin(settings.public_base_url)
    if request is None:
        return primary
    allowed = {primary}
    allowed.update(_origin(value.strip()) for value in settings.public_allowed_origins.split(',') if value.strip())
    # Deployment proxies must overwrite these headers. X-Forwarded-Host and
    # caller-provided return URLs are never used as redirect authorities.
    host = request.headers.get('host')
    if not host:
        return primary
    scheme = request.headers.get('x-forwarded-proto', request.url.scheme)
    candidate = _origin(f'{scheme}://{host}')
    # An untrusted Host cannot redirect a token to an attacker-controlled site.
    return candidate if candidate in allowed else primary
