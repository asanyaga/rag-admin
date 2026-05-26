import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.provider_key_service import resolve_api_key

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
async def test_resolve_returns_decrypted_db_key():
    from app.utils.encryption import encrypt
    plaintext = "sk-db-key-123"
    repo = _make_repo(encrypt(plaintext))
    result = await resolve_api_key(repo, USER_ID, "groq")
    assert result == plaintext


@pytest.mark.asyncio
async def test_resolve_falls_back_to_env_var_when_no_db_key():
    repo = _make_repo()
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.GROQ_API_KEY = "env-groq-key"
        mock_settings.LLAMA_CLOUD_KEY = ""
        mock_settings.VISION_AGENT_API_KEY = ""
        mock_settings.OLLAMA_CLOUD_API_KEY = ""
        result = await resolve_api_key(repo, USER_ID, "groq")
    assert result == "env-groq-key"


@pytest.mark.asyncio
async def test_resolve_returns_none_when_env_var_is_empty():
    repo = _make_repo()
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.GROQ_API_KEY = ""
        mock_settings.LLAMA_CLOUD_KEY = ""
        mock_settings.VISION_AGENT_API_KEY = ""
        mock_settings.OLLAMA_CLOUD_API_KEY = ""
        result = await resolve_api_key(repo, USER_ID, "groq")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_returns_none_for_db_only_provider_with_no_key():
    # voyage has no env-var fallback
    repo = _make_repo()
    result = await resolve_api_key(repo, USER_ID, "voyage")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_db_key_takes_precedence_over_env_var():
    from app.utils.encryption import encrypt
    plaintext = "sk-db-key-wins"
    repo = _make_repo(encrypt(plaintext))
    with patch("app.services.provider_key_service.settings") as mock_settings:
        mock_settings.GROQ_API_KEY = "env-key-should-be-ignored"
        result = await resolve_api_key(repo, USER_ID, "groq")
    assert result == plaintext
