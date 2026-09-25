"""
Rate limiting configuration for the OmniCare backend.

This module instantiates a SlowAPI ``Limiter`` that is applied globally to
protect the backend from abuse and ensure fair resource usage across clients.

Rate limit strategy:
  - Key function: Extracts the user ID from the JWT token. If no valid user ID
    can be extracted (unauthenticated), it falls back to the client IP address.
  - Current limit: 20 requests/minute for chat endpoints, 10/minute for
    session reset. These limits are conservative enough for normal human
    interaction while blocking automated abuse.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

def _user_or_ip_key_func(request):
    """Extract the client IP address or user ID from the incoming request.

    SlowAPI calls this function for every request to determine which rate
    limit bucket to apply. We prioritize user ID from the token for authenticated
    users to implement production-level rate limiting, and fall back to IP.

    Args:
        request: The ASGI request object.

    Returns:
        str: The rate limit key, e.g., 'user:UUID' or 'ip:127.0.0.1'.
    """
    token = None
    # Check Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    # Check cookie fallback
    if not token:
        token = request.cookies.get("omnicare_access_token")

    if token:
        try:
            from app.auth import _decode_token
            user_id = _decode_token(token)
            return f"user:{str(user_id)}"
        except Exception:
            pass

    return f"ip:{get_remote_address(request)}"

# Module-level limiter instance. Import this and apply ``@limiter.limit()``
# decorators to FastAPI route handlers to enforce rate limits.
limiter = Limiter(key_func=_user_or_ip_key_func)
