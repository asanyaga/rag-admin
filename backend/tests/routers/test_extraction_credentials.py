"""Tests for extraction router credentials resolution."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.routers.extraction import _resolve_credentials_from_settings

USER_ID = uuid4()


def _make_repo(encrypted_value=None):
    """Create a mock ProviderKeyRepository."""
    repo = AsyncMock()
    if encrypted_value:
        key_record = MagicMock()
        key_record.api_key_encrypted = encrypted_value
        repo.get_for_provider.return_value = key_record
    else:
        repo.get_for_provider.return_value = None
    return repo


@pytest.mark.asyncio
async def test_llamaextract_returns_db_key():
    """LlamaExtract should resolve key from DB (decrypted)."""
    from app.utils.encryption import encrypt
    repo = _make_repo(encrypt("llamacloud-key-456"))
    result = await _resolve_credentials_from_settings(repo, USER_ID, "llamaextract")
    assert result == {"api_key": "llamacloud-key-456"}
    repo.get_for_provider.assert_awaited_once_with(
        user_id=USER_ID, provider="llama_cloud", project_id=None
    )


@pytest.mark.asyncio
async def test_llamaextract_falls_back_to_env():
    """LlamaExtract should fall back to LLAMA_CLOUD_KEY env var."""
    repo = _make_repo()
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.LLAMA_CLOUD_KEY = "env-llama-key"
        mock_settings.GROQ_API_KEY = ""
        mock_settings.VISION_AGENT_API_KEY = ""
        mock_settings.OLLAMA_CLOUD_API_KEY = ""
        result = await _resolve_credentials_from_settings(repo, USER_ID, "llamaextract")
    assert result == {"api_key": "env-llama-key"}


@pytest.mark.asyncio
async def test_ollama_returns_endpoint_and_key():
    """Ollama should return both endpoint and api_key."""
    from app.utils.encryption import encrypt
    repo = _make_repo(encrypt("ollama-key-789"))
    with patch("app.routers.extraction.settings") as mock_settings:
        mock_settings.OLLAMA_ENDPOINT = "http://myollama:11434/v1"
        result = await _resolve_credentials_from_settings(repo, USER_ID, "ollama")
    assert result["endpoint"] == "http://myollama:11434/v1"
    assert result["api_key"] == "ollama-key-789"


@pytest.mark.asyncio
async def test_unknown_method_returns_empty_dict():
    """Unknown extraction methods should return empty dict."""
    repo = AsyncMock()
    result = await _resolve_credentials_from_settings(repo, USER_ID, "unknown_method")
    assert result == {}
    repo.get_for_provider.assert_not_called()
