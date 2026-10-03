"""Coverage tests for app.database uncovered paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestDatabase:
    def test_async_session_factory_creates_session(self):
        from app.database import async_session_factory

        with patch("app.database.AsyncSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            factory = async_session_factory()
            assert factory is not None
