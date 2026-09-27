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
- Keys are namespaced by user_id to prevent cross-user cache hits.
- Request body hash is stored and verified to prevent body-mismatch replays.
- Per-key asyncio.Lock prevents check-then-act races.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
# Maximum number of cached responses. When full, the oldest entry is evicted.
_MAX_SIZE: int = 1_000

# Seconds a cached response is considered valid. After this window the key is
# expired and the request is processed fresh.
_TTL_SECONDS: int = 300  # 5 minutes

# ── Internal state ────────────────────────────────────────────────────────────
# Each entry: {"response": dict, "request_hash": str, "cached_at": float}
_cache: dict[str, dict[str, Any]] = {}
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _canonical_json(data: Any) -> str:
    """Serialize data to a canonical JSON string for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _compute_request_hash(body: Any) -> str:
    """Compute SHA-256 hash of the canonical JSON representation of a request body."""
    canonical = _canonical_json(body)
    return hashlib.sha256(canonical.encode()).hexdigest()


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
        _locks.pop(key, None)
        logger.debug("Idempotency key '%s' expired after %.1fs.", key, age)
        return None

    logger.info(
        "Cache HIT for idempotency key '%s' (age=%.1fs). Returning cached response.",
        key,
        age,
    )
    return entry["response"]


def store_response(key: str, response: dict[str, Any], request_hash: str) -> None:
    """
    Store a successfully computed response under the given idempotency key.

    When the cache is at capacity the oldest entry is evicted before inserting
    the new one (FIFO, relying on dict insertion-order guarantee in Python 3.7+).

    Args:
        key: The idempotency key.
        response: The agent response dict to cache.
        request_hash: SHA-256 hash of the request body for integrity checking.
    """
    if len(_cache) >= _MAX_SIZE:
        oldest_key = next(iter(_cache))
        _cache.pop(oldest_key)
        _locks.pop(oldest_key, None)
        logger.debug("Idempotency cache full. Evicted oldest key '%s'.", oldest_key)

    _cache[key] = {
        "response": response,
        "request_hash": request_hash,
        "cached_at": time.monotonic(),
    }
    logger.debug("Stored response under idempotency key '%s'.", key)


def cache_size() -> int:
    """Return the current number of entries in the idempotency cache."""
    return len(_cache)


def clear_cache() -> None:
    """
    Clear all cached entries and locks.

    Intended for use in tests to ensure isolation between test cases.
    """
    _cache.clear()
    _locks.clear()


F = TypeVar("F", bound=Callable[..., Any])


def idempotent_endpoint() -> Callable[[F], F]:
    """
    Decorator for FastAPI route handlers to abstract idempotency cache checking.

    It expects the route handler to have `idempotency_key` (str), `response`
    (Response), `current_user_id` (str), and `payload` (request body) as
    injected keyword arguments. The decorator:
    1. Namespaces the cache key by user_id.
    2. Verifies the request body hash matches the cached hash.
    3. Uses per-key asyncio.Lock to prevent check-then-act races.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            idempotency_key = kwargs.get("idempotency_key")
            response = kwargs.get("response")
            current_user_id = kwargs.get("current_user_id")
            payload = kwargs.get("payload")

            if idempotency_key and response and current_user_id:
                # Namespace the cache key by user to prevent cross-user hits
                namespaced_key = f"{current_user_id}:{idempotency_key}"

                # Compute request body hash for integrity checking
                request_body = (
                    payload.model_dump() if payload and hasattr(payload, "model_dump") else payload
                )
                current_request_hash = (
                    _compute_request_hash(request_body) if request_body is not None else ""
                )

                # Atomic cache check with per-key lock
                async with _locks[namespaced_key]:
                    cached = get_cached_response(namespaced_key)
                    if cached is not None:
                        # Verify request body hash matches
                        cached_hash = cached.get("request_hash", "")
                        body_mismatch = (
                            cached_hash
                            and current_request_hash
                            and cached_hash != current_request_hash
                        )
                        if body_mismatch:
                            # Body changed — return 409 Conflict
                            logger.warning(
                                "Idempotency key '%s' reused with different body. Returning 409.",
                                namespaced_key,
                            )
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="Idempotency key reused with a different request body.",
                            )
                        response.headers["X-Idempotent-Replayed"] = "true"
                        response.headers["X-Idempotency-Key"] = idempotency_key
                        return cached

            result = await func(*args, **kwargs)

            if idempotency_key and response and current_user_id:
                namespaced_key = f"{current_user_id}:{idempotency_key}"
                request_body = (
                    payload.model_dump() if payload and hasattr(payload, "model_dump") else payload
                )
                current_request_hash = (
                    _compute_request_hash(request_body) if request_body is not None else ""
                )
                response.headers["X-Idempotency-Key"] = idempotency_key
                if hasattr(result, "model_dump"):
                    store_response(namespaced_key, result.model_dump(), current_request_hash)
                else:
                    store_response(namespaced_key, result, current_request_hash)

            return result

        return wrapper  # type: ignore

    return decorator
