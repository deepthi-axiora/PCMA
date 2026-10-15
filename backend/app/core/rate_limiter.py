from datetime import datetime, timezone
from fastapi import HTTPException, Request, status

# In-memory token bucket rate limiter for endpoint hardening
_REQUEST_LOG: dict[str, list[datetime]] = {}
_MAX_REQUESTS_PER_MINUTE = 60


async def check_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = datetime.now(timezone.utc)

    if client_ip not in _REQUEST_LOG:
        _REQUEST_LOG[client_ip] = []

    # Clean timestamps older than 60 seconds
    cutoff = now.timestamp() - 60
    _REQUEST_LOG[client_ip] = [
        ts for ts in _REQUEST_LOG[client_ip] if ts.timestamp() > cutoff
    ]

    if len(_REQUEST_LOG[client_ip]) >= _MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limit_exceeded", "message": "Rate limit exceeded. Try again in a minute."},
        )

    _REQUEST_LOG[client_ip].append(now)
