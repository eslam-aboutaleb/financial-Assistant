"""
Unit tests for application configuration management (Pydantic v2 Settings).

Tests:
- Default settings instantiation and type integrity
- Dynamic parsing of CORS origins (comma-separated, JSON array, list)
- Log level validation and error handling for invalid values
- Port validation (range boundaries 1-65535)
- get_settings() singleton / lru_cache behavior
"""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_default_settings():
    """Verify default settings instantiation with standard defaults."""
    cfg = Settings()
    assert cfg.app_name == "OmniCare Financial API"
    assert cfg.environment in ("dev", "development", "staging", "production", "test")
    assert cfg.port == 8000
    assert cfg.log_level == "INFO"
    assert isinstance(cfg.cors_origins, list)
    assert "http://localhost:3000" in cfg.cors_origins


def test_jwt_secret_key_validation():
    """Verify JWT_SECRET_KEY default and validation."""
    # Default is development, should allow 'change-me'
    cfg = Settings(environment="development")
    assert "change-me" in cfg.jwt_secret_key

    # In production, 'change-me' should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            jwt_secret_key="super-secret-key-for-development-only-change-me",  # noqa: S106
        )
    assert "JWT_SECRET_KEY must be set to a secure random value in production" in str(
        exc_info.value
    )


def test_cors_origins_parsing():
    """Verify that cors_origins accepts comma-separated strings and JSON arrays."""
    # Comma-separated string
    cfg_csv = Settings(cors_origins="http://example.com, https://app.omnicare.com")
    assert cfg_csv.cors_origins == ["http://example.com", "https://app.omnicare.com"]

    # JSON array string
    cfg_json = Settings(cors_origins='["http://alpha.com", "http://beta.com"]')
    assert cfg_json.cors_origins == ["http://alpha.com", "http://beta.com"]

    # Existing list
    cfg_list = Settings(cors_origins=["http://gamma.com"])
    assert cfg_list.cors_origins == ["http://gamma.com"]


def test_invalid_log_level():
    """Verify that an invalid log level raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(log_level="VERBOSE")
    assert "Invalid log_level" in str(exc_info.value)


def test_invalid_port_range():
    """Verify that out-of-range port numbers raise a ValidationError."""
    with pytest.raises(ValidationError):
        Settings(port=0)

    with pytest.raises(ValidationError):
        Settings(port=70000)


def test_get_settings_cached_singleton():
    """Verify that get_settings() returns the same cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
