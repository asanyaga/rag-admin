"""Tests for extraction router credential resolution — 'llm' method."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.routers.extraction import _resolve_credentials_from_settings

USER_ID = uuid4()


def _make_repo(encrypted_value=None):
    repo = AsyncMock()
    if encrypted_value:
        key_record = MagicMock()
        key_record.api_key_encrypted = encrypted_value
        repo.get_for_provider.return_value = key_record
    else:
        repo.get_for_provider.return_value = None
    return repo


@pytest.mark.asyncio
async def test_llm_ollama_local_returns_local_endpoint_no_key():
    """ollama_local provider uses OLLAMA_LOCAL_BASE_URL; no BYOK key required."""
    repo = _make_repo()
    with patch("app.routers.extraction.settings") as mock_settings:
        mock_settings.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        result = await _resolve_credentials_from_settings(
            repo, USER_ID, "llm", provider="ollama_local"
        )
    assert result["endpoint"] == "http://localhost:11434/v1"
    assert result.get("api_key") in (None, "ollama")


@pytest.mark.asyncio
async def test_llm_ollama_cloud_resolves_byok_key():
    """ollama_cloud provider resolves API key from DB, uses OLLAMA_CLOUD_BASE_URL."""
    from app.utils.encryption import encrypt
    repo = _make_repo(encrypt("cloud-key-123"))
    with patch("app.routers.extraction.settings") as mock_settings:
        mock_settings.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        result = await _resolve_credentials_from_settings(
            repo, USER_ID, "llm", provider="ollama_cloud"
        )
    assert result["endpoint"] == "https://ollama.com/v1"
    assert result["api_key"] == "cloud-key-123"


@pytest.mark.asyncio
async def test_llm_openai_resolves_byok_key():
    """openai provider resolves API key from DB; no endpoint override."""
    from app.utils.encryption import encrypt
    repo = _make_repo(encrypt("openai-key-456"))
    result = await _resolve_credentials_from_settings(
        repo, USER_ID, "llm", provider="openai"
    )
    assert result["api_key"] == "openai-key-456"
    assert "endpoint" not in result


@pytest.mark.asyncio
async def test_llm_defaults_to_ollama_local_when_no_provider():
    """'llm' method with no provider defaults to ollama_local."""
    repo = _make_repo()
    with patch("app.routers.extraction.settings") as mock_settings:
        mock_settings.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        result = await _resolve_credentials_from_settings(
            repo, USER_ID, "llm", provider=None
        )
    assert "endpoint" in result
