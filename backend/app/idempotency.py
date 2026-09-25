from __future__ import annotations

"""
Request idempotency cache for the OmniCare chat endpoint.

Industry standard: clients supply an ``Idempotency-Key`` header (UUID or any
opaque string). If the server has already successfully processed a request
with that key it returns the cached response instead of executing the agent
again. This prevents duplicate LLM calls when clients retry on network errors.

If the client omits the header, a deterministic key is derived from
``sha256(user_id + ":" + message)`` — ensuring that byte-identical retries
of the same message from the same user are naturally deduplicated.

Design:
- In-process TTL cache: simple, zero-dependency, correct for single-process
  deployment (uvicorn --workers 1, which is standard for ADK async agents).
- Configurable TTL (default: 5 min) and max size (default: 1 000 entries).
- Entries are evicted in FIFO order when the cache is full, in addition to
  TTL expiry on access.
- Thread-safe for async use (single event-loop, no cross-thread mutations).
"""

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
# Maximum number of cached responses. When full, the oldest entry is evicted.
_MAX_SIZE: int = 1_000

# Seconds a cached response is considered valid. After this window the key is
# expired and the request is processed fresh.
_TTL_SECONDS: int = 300  # 5 minutes

# ── Internal state ────────────────────────────────────────────────────────────
# Each entry: {"response": dict, "cached_at": float}
_cache: dict[str, dict[str, Any]] = {}


def make_idempotency_key(user_id: str, message: str) -> str:
    """
    Derive a deterministic idempotency key from user and message content.

    Used as the fallback when the client does not supply an explicit
    ``Idempotency-Key`` header.  The SHA-256 digest ensures:
    - Identical (user_id, message) pairs always map to the same key.
    - Different users with the same message text get different keys.
    - The key is a fixed-length hex string safe for use as a dict key.

    Args:
        user_id: The authenticated user identifier.
        message: The raw message text.

    Returns:
        64-character hex SHA-256 digest.
    """
    payload = f"{user_id}:{message}".encode()
    return hashlib.sha256(payload).hexdigest()


def get_cached_response(key: str) -> dict[str, Any] | None:
    """
    Return a cached response if the key exists and has not expired.

    Args:
        key: The idempotency key to look up.

    Returns:
        The cached response dict, or ``None`` if absent or expired.
    """
    entry = _cache.get(key)
    if entry is None:
        return None

    age = time.monotonic() - entry["cached_at"]
    if age > _TTL_SECONDS:
        # Lazily evict expired entry
        _cache.pop(key, None)
        logger.debug("Idempotency key '%s' expired after %.1fs.", key, age)
        return None

    logger.info(
        "Cache HIT for idempotency key '%s' (age=%.1fs). Returning cached response.",
        key,
        age,
    )
    return entry["response"]


def store_response(key: str, response: dict[str, Any]) -> None:
    """
    Store a successfully computed response under the given idempotency key.

    When the cache is at capacity the oldest entry is evicted before inserting
    the new one (FIFO, relying on dict insertion-order guarantee in Python 3.7+).

    Args:
        key: The idempotency key.
        response: The agent response dict to cache.
    """
    if len(_cache) >= _MAX_SIZE:
        oldest_key = next(iter(_cache))
        _cache.pop(oldest_key)
        logger.debug("Idempotency cache full. Evicted oldest key '%s'.", oldest_key)

    _cache[key] = {"response": response, "cached_at": time.monotonic()}
    logger.debug("Stored response under idempotency key '%s'.", key)


def cache_size() -> int:
    """Return the current number of entries in the idempotency cache."""
    return len(_cache)


def clear_cache() -> None:
    """
    Clear all cached entries.

    Intended for use in tests to ensure isolation between test cases.
    """
    _cache.clear()


from functools import wraps
from typing import TypeVar
from collections.abc import Callable

F = TypeVar("F", bound=Callable[..., Any])


def idempotent_endpoint() -> Callable[[F], F]:
    """
    Decorator for FastAPI route handlers to abstract idempotency cache checking.
    It expects the route handler to have `idempotency_key` (str) and `response` (Response)
    as injected keyword arguments.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            idempotency_key = kwargs.get("idempotency_key")
            response = kwargs.get("response")

            if idempotency_key and response:
                cached = get_cached_response(idempotency_key)
                if cached is not None:
                    response.headers["X-Idempotent-Replayed"] = "true"
                    response.headers["X-Idempotency-Key"] = idempotency_key
                    # The route expects a Pydantic model response, so we just return the dict
                    # (FastAPI will cast it automatically to the response_model)
                    return cached

            result = await func(*args, **kwargs)

            if idempotency_key and response:
                response.headers["X-Idempotency-Key"] = idempotency_key
                # Store the Pydantic dump or dict
                if hasattr(result, "model_dump"):
                    store_response(idempotency_key, result.model_dump())
                else:
                    store_response(idempotency_key, result)

            return result

        return wrapper  # type: ignore

    return decorator
