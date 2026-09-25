"""
Tests for the idempotency cache module and chat endpoint idempotency behaviour.

Covers:
- Cache miss: first request is processed normally.
- Cache hit: identical retry returns cached response, agent NOT called again.
- X-Idempotent-Replayed header is present only on cached responses.
- X-Idempotency-Key header is echoed back on both fresh and cached responses.
- Explicit Idempotency-Key header is respected and overrides the auto-derived key.
- Different idempotency keys with the same message produce independent responses.
- Errors are NOT cached -- the client can safely retry on 500.
- make_idempotency_key: same inputs produce the same key; different inputs differ.
- TTL expiry: cached entry older than TTL is treated as a cache miss.
- Cache eviction: storing beyond MAX_SIZE evicts the oldest entry (FIFO).
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.idempotency import (
    _TTL_SECONDS,
    _MAX_SIZE,
    cache_size,
    clear_cache,
    get_cached_response,
    make_idempotency_key,
    store_response,
    _cache,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_cache():
    """Ensure every test starts with an empty idempotency cache."""
    clear_cache()
    yield
    clear_cache()


_MOCK_RESPONSE = {
    "response": "Water damage caused by sudden pipe bursts is covered up to $25,000.",
    "sources": ["Section 1: Home Water Damage Coverage (sample_policy.md)"],
    "tool_calls": [],
}


# ── Unit tests: idempotency module ────────────────────────────────────────────


class TestMakeIdempotencyKey:
    def test_same_inputs_produce_same_key(self):
        k1 = make_idempotency_key("usr_1", "water damage")
        k2 = make_idempotency_key("usr_1", "water damage")
        assert k1 == k2

    def test_different_user_same_message_produces_different_key(self):
        k1 = make_idempotency_key("usr_1", "water damage")
        k2 = make_idempotency_key("usr_2", "water damage")
        assert k1 != k2

    def test_same_user_different_message_produces_different_key(self):
        k1 = make_idempotency_key("usr_1", "water damage")
        k2 = make_idempotency_key("usr_1", "fire coverage")
        assert k1 != k2

    def test_key_is_64_char_hex(self):
        key = make_idempotency_key("usr_1", "hello")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestCacheGetSet:
    def test_cache_miss_returns_none(self):
        assert get_cached_response("nonexistent-key") is None

    def test_stored_response_is_retrievable(self):
        store_response("key-1", _MOCK_RESPONSE)
        result = get_cached_response("key-1")
        assert result == _MOCK_RESPONSE

    def test_expired_entry_returns_none(self):
        store_response("key-exp", _MOCK_RESPONSE)
        # Manually backdate the cached_at timestamp
        _cache["key-exp"]["cached_at"] = time.monotonic() - (_TTL_SECONDS + 1)
        assert get_cached_response("key-exp") is None

    def test_expired_entry_is_evicted_from_cache(self):
        store_response("key-evict", _MOCK_RESPONSE)
        _cache["key-evict"]["cached_at"] = time.monotonic() - (_TTL_SECONDS + 1)
        get_cached_response("key-evict")  # triggers lazy eviction
        assert "key-evict" not in _cache

    def test_cache_size_increments(self):
        assert cache_size() == 0
        store_response("k1", _MOCK_RESPONSE)
        assert cache_size() == 1
        store_response("k2", _MOCK_RESPONSE)
        assert cache_size() == 2

    def test_clear_cache_empties_store(self):
        store_response("k1", _MOCK_RESPONSE)
        store_response("k2", _MOCK_RESPONSE)
        clear_cache()
        assert cache_size() == 0

    def test_fifo_eviction_at_max_size(self):
        """Oldest entry is evicted when cache reaches MAX_SIZE."""
        # Fill cache to max
        for i in range(_MAX_SIZE):
            store_response(f"key-{i}", _MOCK_RESPONSE)

        assert cache_size() == _MAX_SIZE

        # Insert one more; key-0 (oldest) should be gone
        store_response("key-overflow", _MOCK_RESPONSE)
        assert cache_size() == _MAX_SIZE
        assert "key-0" not in _cache
        assert "key-overflow" in _cache


# ── Integration tests: chat endpoint ──────────────────────────────────────────


class TestChatIdempotency:
    def test_first_request_calls_agent(self, test_client, mock_current_user):
        """First request must invoke the agent and return a fresh response."""
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _MOCK_RESPONSE

            res = test_client.post(
                "/api/v1/chat",
                json={"message": "water damage"},
                headers=mock_current_user,
            )

        assert res.status_code == 200
        mock_run.assert_awaited_once_with(
            user_id="00000000-0000-0000-0000-000000000001",
            message="water damage",
        )
        assert res.headers.get("X-Idempotent-Replayed") != "true"
        # No Idempotency-Key header when client did not supply one
        assert res.headers.get("X-Idempotency-Key") is None

    def test_no_auto_dedup_without_explicit_key(self, test_client, mock_current_user):
        """Without an explicit Idempotency-Key, every request is processed normally.
        Users legitimately ask the same question multiple times in a conversation."""
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _MOCK_RESPONSE

            payload = {"message": "water damage"}

            # Two identical requests without Idempotency-Key
            res1 = test_client.post(
                "/api/v1/chat", json=payload, headers=mock_current_user
            )
            res2 = test_client.post(
                "/api/v1/chat", json=payload, headers=mock_current_user
            )

        assert res1.status_code == 200
        assert res2.status_code == 200

        # Agent called twice -- no auto-deduplication
        assert mock_run.await_count == 2

        # Neither response is marked as replayed
        assert res1.headers.get("X-Idempotent-Replayed") != "true"
        assert res2.headers.get("X-Idempotent-Replayed") != "true"

    def test_explicit_idempotency_key_header_is_used(self, test_client, mock_current_user):
        """Client-supplied Idempotency-Key enables cache-based deduplication."""
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _MOCK_RESPONSE

            key = "my-explicit-key-abc123"
            headers = {
                **mock_current_user,
                "Idempotency-Key": key,
            }
            payload = {"message": "water damage"}

            res1 = test_client.post(
                "/api/v1/chat", json=payload, headers=headers
            )
            res2 = test_client.post(
                "/api/v1/chat", json=payload, headers=headers
            )

        assert mock_run.await_count == 1
        assert res2.headers.get("X-Idempotent-Replayed") == "true"
        # The echoed key must match the client-supplied key
        assert res1.headers.get("X-Idempotency-Key") == key
        assert res2.headers.get("X-Idempotency-Key") == key

    def test_different_keys_produce_independent_responses(self, test_client, mock_current_user):
        """Two requests with different idempotency keys are processed independently."""
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _MOCK_RESPONSE

            payload = {"message": "water damage"}

            test_client.post(
                "/api/v1/chat",
                json=payload,
                headers={**mock_current_user, "Idempotency-Key": "key-A"},
            )
            test_client.post(
                "/api/v1/chat",
                json=payload,
                headers={**mock_current_user, "Idempotency-Key": "key-B"},
            )

        # Agent called twice -- once per unique key
        assert mock_run.await_count == 2

    def test_errors_are_not_cached(self, test_client, mock_current_user):
        """A 500 response must NOT be cached -- client should retry and get a fresh attempt."""
        from app.main import app
        app.state.limiter.enabled = False
        try:
            with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
                mock_run.side_effect = RuntimeError("Transient LLM error")

                payload = {"message": "crash now"}
                test_client.post(
                    "/api/v1/chat",
                    json=payload,
                    headers={**mock_current_user, "Idempotency-Key": "fail-key"},
                )

            # After the failed attempt, clear the side effect so the retry succeeds
            with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = _MOCK_RESPONSE

                res = test_client.post(
                    "/api/v1/chat",
                    json=payload,
                    headers={**mock_current_user, "Idempotency-Key": "fail-key"},
                )

            assert res.status_code == 200
            # Agent was called again (not replayed from cache)
            assert res.headers.get("X-Idempotent-Replayed") != "true"
            mock_run.assert_awaited_once()
        finally:
            app.state.limiter.enabled = True

    def test_different_users_same_message_not_shared(self, test_client, mock_current_user):
        """Without explicit keys, two users with the same message are processed independently."""
        # Disable rate limiter for this test to avoid 429 blocking the second request
        from app.main import app; app.state.limiter.enabled = False
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _MOCK_RESPONSE

            # First user
            headers1 = mock_current_user
            # Second user with a different user-id
            headers2 = {"Authorization": "Bearer test-token-for-00000000-0000-0000-0000-000000000002"}

            test_client.post(
                "/api/v1/chat",
                json={"message": "water damage"},
                headers=headers1,
            )
            res2 = test_client.post(
                "/api/v1/chat",
                json={"message": "water damage"},
                headers=headers2,
            )

        # Second user should NOT get a replayed response
        assert res2.headers.get("X-Idempotent-Replayed") != "true"
        assert mock_run.await_count == 2
