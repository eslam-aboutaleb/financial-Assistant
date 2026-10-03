"""
Tests for the embedding outbox drainer loop.

The drainer is the process that turns ``embedding_jobs`` rows into pgvector entries.
These tests drive ``drain_forever`` with a stubbed ``process_pending_jobs`` so the loop
is verified without touching the database or the embedding API.
"""

import asyncio
import signal
from unittest.mock import patch

import pytest

from app.workers import embedding_drain


@pytest.fixture
def fast_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the loop's idle wait short so tests do not sleep."""
    monkeypatch.setattr(embedding_drain, "_interval_seconds", lambda: 0.05)
    monkeypatch.setattr(embedding_drain, "_batch_size", lambda: 2)

    async def _no_reclaim() -> int:
        return 0

    monkeypatch.setattr(embedding_drain, "reclaim_stale_jobs", _no_reclaim)


@pytest.mark.usefixtures("fast_loop")
def test_drain_stops_when_event_is_set() -> None:
    """The loop exits promptly once the stop event is set."""

    async def _scenario() -> int:
        passes = 0
        stop = asyncio.Event()

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            nonlocal passes
            passes += 1
            stop.set()
            return 0

        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)
        return passes

    assert asyncio.run(_scenario()) == 1


@pytest.mark.usefixtures("fast_loop")
def test_drain_passes_the_batch_size_through() -> None:
    """The configured batch size reaches the processor on every pass."""
    seen: list[int] = []

    async def _scenario() -> None:
        stop = asyncio.Event()

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            seen.append(limit)
            if len(seen) >= 3:
                stop.set()
            return 0

        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)

    asyncio.run(_scenario())
    assert seen == [2, 2, 2]


@pytest.mark.usefixtures("fast_loop")
def test_drain_passes_its_worker_id_to_the_processor() -> None:
    """The configured worker identity is stamped onto every claimed batch."""

    async def _scenario() -> list[str | None]:
        stop = asyncio.Event()
        seen: list[str | None] = []

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            seen.append(worker_id)
            stop.set()
            return 0

        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)
        return seen

    from app.config import settings

    assert asyncio.run(_scenario()) == [settings.worker_id]


@pytest.mark.usefixtures("fast_loop")
def test_drain_reclaims_stale_jobs_before_claiming() -> None:
    """Every pass reclaims abandoned locks before claiming new work."""

    async def _scenario() -> int:
        stop = asyncio.Event()
        reclaims = 0

        async def _fake_reclaim() -> int:
            nonlocal reclaims
            reclaims += 1
            return 0

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            stop.set()
            return 0

        embedding_drain.reclaim_stale_jobs = _fake_reclaim
        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)
        return reclaims

    assert asyncio.run(_scenario()) == 1


@pytest.mark.usefixtures("fast_loop")
def test_drain_survives_a_failing_pass() -> None:
    """A raising pass is logged and retried; it does not terminate the worker."""

    async def _scenario() -> int:
        calls = 0
        stop = asyncio.Event()

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("transient embedding API failure")
            stop.set()
            return 0

        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)
        return calls

    assert asyncio.run(_scenario()) == 2


@pytest.mark.usefixtures("fast_loop")
def test_drain_keeps_draining_while_work_remains() -> None:
    """A pass that processes jobs is followed immediately by another, without sleeping."""

    async def _scenario() -> int:
        calls = 0
        stop = asyncio.Event()

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            nonlocal calls
            calls += 1
            if calls < 4:
                return 3
            stop.set()
            return 0

        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)
        return calls

    assert asyncio.run(_scenario()) == 4


def test_drain_config_comes_from_validated_settings() -> None:
    """The drainer reads its configuration from Settings, not from raw os.environ.

    Reading the environment directly meant the values were never validated and never
    appeared on ``settings``, while the module docstring claimed otherwise.
    """
    from app.config import settings

    assert embedding_drain._interval_seconds() == settings.embedding_drain_interval_seconds
    assert embedding_drain._batch_size() == settings.embedding_drain_batch_size


def test_drain_settings_reject_out_of_range_values() -> None:
    """Settings enforce the documented bounds rather than clamping at runtime."""
    import pytest as _pytest
    from pydantic import ValidationError

    from app.config import Settings

    with _pytest.raises(ValidationError):
        Settings(embedding_drain_interval_seconds=0)

    with _pytest.raises(ValidationError):
        Settings(embedding_drain_batch_size=0)


@pytest.mark.usefixtures("fast_loop")
def test_drain_logs_when_stale_jobs_are_reclaimed() -> None:
    """A pass that reclaims abandoned locks logs the reclaimed count."""

    async def _scenario() -> int:
        stop = asyncio.Event()

        async def _fake_reclaim() -> int:
            return 2

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            stop.set()
            return 0

        embedding_drain.reclaim_stale_jobs = _fake_reclaim
        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)
        return 1

    asyncio.run(_scenario())


@pytest.mark.usefixtures("fast_loop")
def test_drain_propagates_cancellation() -> None:
    """A cancelled pass re-raises CancelledError instead of being swallowed."""

    async def _scenario() -> None:
        stop = asyncio.Event()

        async def _fake(limit: int, worker_id: str | None = None) -> int:
            raise asyncio.CancelledError

        embedding_drain.process_pending_jobs = _fake
        await embedding_drain.drain_forever(stop)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_scenario())


def test_install_signal_handlers_registers_both_signals() -> None:
    """SIGINT and SIGTERM are wired to the stop event on the running loop."""
    stop = asyncio.Event()
    registered: list[object] = []

    class _FakeLoop:
        def add_signal_handler(self, sig, callback):  # noqa: ANN001, ANN202
            registered.append(sig)

    with patch.object(embedding_drain.asyncio, "get_running_loop", return_value=_FakeLoop()):
        embedding_drain._install_signal_handlers(stop)

    assert set(registered) == {signal.SIGINT, signal.SIGTERM}


def test_install_signal_handlers_tolerates_unsupported_loops() -> None:
    """Loops without signal support (e.g. Windows) do not crash the worker."""

    class _UnsupportedLoop:
        def add_signal_handler(self, sig, callback):  # noqa: ANN001, ANN202
            raise NotImplementedError

    with patch.object(embedding_drain.asyncio, "get_running_loop", return_value=_UnsupportedLoop()):
        embedding_drain._install_signal_handlers(asyncio.Event())


def test_main_returns_zero_after_clean_shutdown() -> None:
    """The console entry point installs logging and returns 0 on exit."""
    with patch.object(embedding_drain.asyncio, "run", return_value=None) as mock_run:
        assert embedding_drain.main() == 0
    mock_run.assert_called_once()


def test_main_swallows_keyboard_interrupt() -> None:
    """Ctrl-C during shutdown is expected and still exits 0."""
    with patch.object(
        embedding_drain.asyncio,
        "run",
        side_effect=KeyboardInterrupt,
    ):
        assert embedding_drain.main() == 0
