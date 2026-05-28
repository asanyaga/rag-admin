import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.llm.credentials import ProviderCredentials


USER_ID = uuid4()
PROJECT_ID = uuid4()


def _make_db():
    return MagicMock()


def _make_repo(key_text: str | None, base_url: str | None = None):
    repo = MagicMock()
    if key_text is not None:
        from app.utils.encryption import encrypt
        record = MagicMock()
        record.api_key_encrypted = encrypt(key_text)
        record.base_url = base_url
        repo.get_for_provider = AsyncMock(return_value=record)
    else:
        repo.get_for_provider = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_ollama_local_returns_dummy_key_without_db():
    from app.services.llm.credentials import resolve_provider_credentials
    repo = MagicMock()
    repo.get_for_provider = AsyncMock()
    with pytest.MonkeyPatch().context() as mp:
        import app.services.llm.credentials as creds_mod
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        result = await resolve_provider_credentials("ollama_local", USER_ID, PROJECT_ID, _make_db())
    repo.get_for_provider.assert_not_called()
    assert result.api_key == "ollama"
    assert result.base_url is None


@pytest.mark.asyncio
async def test_returns_decrypted_key_and_base_url():
    from app.services.llm.credentials import resolve_provider_credentials
    repo = _make_repo("sk-real-key", base_url="https://my-vllm.example.com/v1")
    import app.services.llm.credentials as creds_mod
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        result = await resolve_provider_credentials("openai", USER_ID, PROJECT_ID, _make_db())
    assert result.api_key == "sk-real-key"
    assert result.base_url == "https://my-vllm.example.com/v1"


@pytest.mark.asyncio
async def test_returns_none_base_url_when_not_set():
    from app.services.llm.credentials import resolve_provider_credentials
    repo = _make_repo("sk-real-key", base_url=None)
    import app.services.llm.credentials as creds_mod
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        result = await resolve_provider_credentials("openai", USER_ID, PROJECT_ID, _make_db())
    assert result.base_url is None


@pytest.mark.asyncio
async def test_raises_validation_error_when_no_key():
    from app.services.llm.credentials import resolve_provider_credentials
    from app.services.exceptions import ValidationError
    repo = _make_repo(None)
    import app.services.llm.credentials as creds_mod
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        with pytest.raises(ValidationError, match="No API key configured for provider 'anthropic'"):
            await resolve_provider_credentials("anthropic", USER_ID, PROJECT_ID, _make_db())
