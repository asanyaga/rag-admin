# Unified Provider Key Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing BYOK provider key system to cover extraction and classification providers, with env-var fallback, so all features resolve API keys through one code path.

**Architecture:** Add 4 new providers to the registry schema; add a `resolve_api_key` module-level function to `provider_key_service.py` that checks the DB first (project-level → account-level) then falls back to env vars; replace the inline decrypt in the playground, the env-var reads in extraction, and the cached registry in classification with calls to this function.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-05-26-unified-provider-keys-design.md`

---

## File Map

| File | Change |
|---|---|
| `backend/app/schemas/provider_key.py` | Add 4 providers to `SUPPORTED_PROVIDERS` and `PROVIDER_MODELS` |
| `backend/app/services/provider_key_service.py` | Add module-level `resolve_api_key` function |
| `backend/app/routers/indexes.py` | Replace inline `repo.get_for_provider` + `decrypt` with `resolve_api_key` |
| `backend/app/routers/extraction.py` | Make `_resolve_credentials_from_settings` async, wire `resolve_api_key` |
| `backend/app/routers/classification.py` | Add `_classification_provider_to_byok`, `_build_llm_registry`; pass resolved key to background task |
| `backend/tests/schemas/test_provider_key_schema.py` | New — registry coverage |
| `backend/tests/services/test_resolve_api_key.py` | New — unit tests for `resolve_api_key` |
| `backend/tests/routers/test_extraction_credentials.py` | New — unit tests for extraction resolver |
| `backend/tests/routers/test_classification_key_resolution.py` | New — unit tests for classification helpers |

---

## Task 1: Extend the provider registry

**Files:**
- Modify: `backend/app/schemas/provider_key.py`
- Create: `backend/tests/schemas/test_provider_key_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/schemas/test_provider_key_schema.py
from app.schemas.provider_key import SUPPORTED_PROVIDERS, PROVIDER_MODELS


def test_new_providers_in_supported_list():
    for p in ("groq", "llama_cloud", "landing_ai", "ollama_cloud"):
        assert p in SUPPORTED_PROVIDERS, f"{p} missing from SUPPORTED_PROVIDERS"


def test_new_providers_in_models_dict():
    for p in ("groq", "llama_cloud", "landing_ai", "ollama_cloud"):
        assert p in PROVIDER_MODELS, f"{p} missing from PROVIDER_MODELS"
        assert PROVIDER_MODELS[p]["requires_key"] is True
```

- [ ] **Step 2: Run the test and confirm it fails**

```
uv run --directory backend python -m pytest tests/schemas/test_provider_key_schema.py -v
```

Expected: FAIL — "groq missing from SUPPORTED_PROVIDERS"

- [ ] **Step 3: Extend the schema file**

In `backend/app/schemas/provider_key.py`, replace the `SUPPORTED_PROVIDERS` list:

```python
SUPPORTED_PROVIDERS = [
    "openai", "voyage", "local", "anthropic",
    "groq", "llama_cloud", "landing_ai", "ollama_cloud",
]
```

Add these four entries to `PROVIDER_MODELS` after the `"anthropic"` entry:

```python
    "groq": {
        "display_name": "Groq",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
    "llama_cloud": {
        "display_name": "LlamaIndex Cloud",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
    "landing_ai": {
        "display_name": "Landing AI",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
    "ollama_cloud": {
        "display_name": "Ollama Cloud",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
```

- [ ] **Step 4: Run the test and confirm it passes**

```
uv run --directory backend python -m pytest tests/schemas/test_provider_key_schema.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/provider_key.py backend/tests/schemas/test_provider_key_schema.py
git commit -m "feat(provider-keys): add groq, llama_cloud, landing_ai, ollama_cloud to registry"
```

---

## Task 2: Add `resolve_api_key` function

**Files:**
- Modify: `backend/app/services/provider_key_service.py`
- Create: `backend/tests/services/test_resolve_api_key.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/test_resolve_api_key.py
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
```

- [ ] **Step 2: Run tests and confirm they fail**

```
uv run --directory backend python -m pytest tests/services/test_resolve_api_key.py -v
```

Expected: FAIL — "cannot import name 'resolve_api_key'"

- [ ] **Step 3: Add `resolve_api_key` to `backend/app/services/provider_key_service.py`**

Add this import at the top of the file alongside existing imports:

```python
from app.config import settings
```

Add this function at the bottom of the file, after the `ProviderKeyService` class:

```python
async def resolve_api_key(
    repo: ProviderKeyRepository,
    user_id: UUID,
    provider: str,
    project_id: UUID | None = None,
) -> str | None:
    """Resolve an API key: DB first (project-level → account-level), then env-var fallback.

    Returns None if no key is found in either source.
    Empty string env vars are treated as not configured.
    """
    key_record = await repo.get_for_provider(
        user_id=user_id,
        provider=provider,
        project_id=project_id,
    )
    if key_record:
        return decrypt(key_record.api_key_encrypted)

    env_fallbacks: dict[str, str] = {
        "groq":         settings.GROQ_API_KEY,
        "llama_cloud":  settings.LLAMA_CLOUD_KEY,
        "landing_ai":   settings.VISION_AGENT_API_KEY,
        "ollama_cloud": settings.OLLAMA_CLOUD_API_KEY,
    }
    value = env_fallbacks.get(provider, "")
    return value if value else None
```

- [ ] **Step 4: Run tests and confirm they pass**

```
uv run --directory backend python -m pytest tests/services/test_resolve_api_key.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/provider_key_service.py backend/tests/services/test_resolve_api_key.py
git commit -m "feat(provider-keys): add resolve_api_key with DB-first env-var fallback"
```

---

## Task 3: Wire playground (indexes router)

**Files:**
- Modify: `backend/app/routers/indexes.py`

The playground currently does its own `repo.get_for_provider` + `decrypt` inline (around lines 581–596). Replace with `resolve_api_key`.

- [ ] **Step 1: Add the import to `backend/app/routers/indexes.py`**

Find the block of service/utility imports near the top of the file and add:

```python
from app.services.provider_key_service import resolve_api_key
```

- [ ] **Step 2: Replace the inline key resolution in `playground_answer`**

Find this block (around lines 580–596):

```python
    # Resolve the LLM provider API key (reuses embedding key storage)
    llm_provider = data.llm_config.provider
    key_record = await provider_key_repo.get_for_provider(
        user_id=current_user.id,
        provider=llm_provider,
        project_id=project_id,
    )
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No API key configured for provider '{llm_provider}'. "
                "Add one in Settings → API Keys."
            ),
        )

    api_key = decrypt(key_record.api_key_encrypted)
```

Replace it with:

```python
    # Resolve the LLM provider API key: DB first, env-var fallback
    llm_provider = data.llm_config.provider
    api_key = await resolve_api_key(
        repo=provider_key_repo,
        user_id=current_user.id,
        provider=llm_provider,
        project_id=project_id,
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No API key configured for provider '{llm_provider}'. "
                "Add one in Settings → API Keys."
            ),
        )
```

- [ ] **Step 3: Check if `decrypt` import is still needed elsewhere in `indexes.py`**

```bash
grep -n "decrypt" backend/app/routers/indexes.py
```

If the only usage was the line just removed, also remove the `decrypt` import from the imports block at the top.

- [ ] **Step 4: Run the full test suite**

```
uv run --directory backend python -m pytest tests/ -v --ignore=tests/cdm -x
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/indexes.py
git commit -m "feat(playground): resolve LLM key via resolve_api_key"
```

---

## Task 4: Wire extraction router

**Files:**
- Modify: `backend/app/routers/extraction.py`
- Create: `backend/tests/routers/test_extraction_credentials.py`

The current `_resolve_credentials_from_settings(method)` is synchronous and reads directly from env vars. It needs to become async, accept a repo and user_id, and call `resolve_api_key`.

Note: the `ollama` extraction method also returns an `endpoint` URL from `settings.OLLAMA_ENDPOINT`. That URL is config (not a secret) and stays in `.env` — only the API key moves to BYOK.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/routers/test_extraction_credentials.py
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
async def test_llamaextract_returns_db_key():
    from app.utils.encryption import encrypt
    repo = _make_repo(encrypt("llamacloud-key-456"))
    result = await _resolve_credentials_from_settings(repo, USER_ID, "llamaextract")
    assert result == {"api_key": "llamacloud-key-456"}
    repo.get_for_provider.assert_awaited_once_with(
        user_id=USER_ID, provider="llama_cloud", project_id=None
    )


@pytest.mark.asyncio
async def test_llamaextract_falls_back_to_env():
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
    from app.utils.encryption import encrypt
    repo = _make_repo(encrypt("ollama-key-789"))
    with patch("app.routers.extraction.settings") as mock_settings:
        mock_settings.OLLAMA_ENDPOINT = "http://myollama:11434/v1"
        result = await _resolve_credentials_from_settings(repo, USER_ID, "ollama")
    assert result["endpoint"] == "http://myollama:11434/v1"
    assert result["api_key"] == "ollama-key-789"


@pytest.mark.asyncio
async def test_unknown_method_returns_empty_dict():
    repo = AsyncMock()
    result = await _resolve_credentials_from_settings(repo, USER_ID, "unknown_method")
    assert result == {}
    repo.get_for_provider.assert_not_called()
```

- [ ] **Step 2: Run tests and confirm they fail**

```
uv run --directory backend python -m pytest tests/routers/test_extraction_credentials.py -v
```

Expected: FAIL — `_resolve_credentials_from_settings` takes 1 argument, not 3

- [ ] **Step 3: Update `backend/app/routers/extraction.py`**

Add these imports alongside existing imports at the top of the file:

```python
from app.config import settings
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.services.provider_key_service import resolve_api_key
```

Replace the entire `_resolve_credentials_from_settings` function (lines 50–64):

```python
async def _resolve_credentials_from_settings(
    repo: ProviderKeyRepository,
    user_id: UUID,
    method: str,
) -> dict:
    """Resolve adapter credentials: DB first, env-var fallback.

    Maps extraction method names to BYOK provider IDs.
    The Ollama endpoint URL is config (not a secret) and always comes from settings.
    """
    provider_map = {
        "llamaextract": "llama_cloud",
        "ollama":        "ollama_cloud",
        "groq":          "groq",
        "vision_agent":  "landing_ai",
    }
    provider = provider_map.get(method)
    if not provider:
        return {}

    key = await resolve_api_key(repo, user_id, provider)

    if method == "ollama":
        return {
            "endpoint": settings.OLLAMA_ENDPOINT or "http://localhost:11434/v1",
            "api_key": key,
        }
    return {"api_key": key} if key else {}
```

In the `run_extraction` endpoint, find this line (around line 179):

```python
        credentials = _resolve_credentials_from_settings(body.extraction_method)
```

Replace with:

```python
        provider_key_repo = ProviderKeyRepository(db)
        credentials = await _resolve_credentials_from_settings(
            provider_key_repo, current_user.id, body.extraction_method
        )
```

- [ ] **Step 4: Run tests and confirm they pass**

```
uv run --directory backend python -m pytest tests/routers/test_extraction_credentials.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

```
uv run --directory backend python -m pytest tests/ -v --ignore=tests/cdm -x
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/extraction.py backend/tests/routers/test_extraction_credentials.py
git commit -m "feat(extraction): wire BYOK key resolution with env-var fallback"
```

---

## Task 5: Wire classification router

**Files:**
- Modify: `backend/app/routers/classification.py`
- Create: `backend/tests/routers/test_classification_key_resolution.py`

Classification uses a module-level cached `LLMRegistry` built at startup from env vars. We replace this with a per-request registry built from the resolved key, so users can supply their own Groq or Ollama Cloud keys.

`ollama_local` never needs a key and stays as-is. `groq` and `ollama_cloud` are the two providers that benefit from BYOK.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/routers/test_classification_key_resolution.py
from unittest.mock import patch

from app.routers.classification import _classification_provider_to_byok, _build_llm_registry


def test_provider_mapping_groq():
    assert _classification_provider_to_byok("groq") == "groq"


def test_provider_mapping_ollama_cloud():
    assert _classification_provider_to_byok("ollama_cloud") == "ollama_cloud"


def test_provider_mapping_ollama_local_returns_none():
    assert _classification_provider_to_byok("ollama_local") is None


def test_provider_mapping_unknown_returns_none():
    assert _classification_provider_to_byok("some_unknown_provider") is None


def test_build_registry_groq_with_key():
    registry = _build_llm_registry("groq", "my-groq-key")
    assert registry.has("groq")


def test_build_registry_groq_without_key_not_registered():
    registry = _build_llm_registry("groq", None)
    assert not registry.has("groq")


def test_build_registry_ollama_local_always_registered():
    with patch("app.routers.classification.settings") as mock_settings:
        mock_settings.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        registry = _build_llm_registry("ollama_local", None)
    assert registry.has("ollama_local")


def test_build_registry_ollama_cloud_with_key():
    with patch("app.routers.classification.settings") as mock_settings:
        mock_settings.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        registry = _build_llm_registry("ollama_cloud", "cloud-key-abc")
    assert registry.has("ollama_cloud")
```

- [ ] **Step 2: Run tests and confirm they fail**

```
uv run --directory backend python -m pytest tests/routers/test_classification_key_resolution.py -v
```

Expected: FAIL — "cannot import name '_classification_provider_to_byok'"

- [ ] **Step 3: Update `backend/app/routers/classification.py`**

Add these imports alongside existing imports at the top of the file:

```python
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.services.llm.registry import LLMRegistry
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.provider_key_service import resolve_api_key
```

Check that `get_llm_registry` is not used anywhere else in the file, then remove its import:

```bash
grep -n "get_llm_registry" backend/app/routers/classification.py
```

If the only remaining occurrence is the import line itself, remove:

```python
from app.dependencies.llm import get_llm_registry
```

Add these two helper functions before `_run_classification_background`:

```python
def _classification_provider_to_byok(llm_provider: str) -> str | None:
    """Map classification LLM provider names to BYOK provider IDs."""
    return {"groq": "groq", "ollama_cloud": "ollama_cloud"}.get(llm_provider)


def _build_llm_registry(provider: str, api_key: str | None) -> LLMRegistry:
    """Build a per-request LLM registry with the resolved API key."""
    registry = LLMRegistry()
    if provider == "ollama_local":
        registry.register(
            "ollama_local",
            OllamaAdapter(base_url=settings.OLLAMA_LOCAL_BASE_URL, api_key="ollama"),
        )
    elif provider == "ollama_cloud" and api_key:
        registry.register(
            "ollama_cloud",
            OllamaAdapter(base_url=settings.OLLAMA_CLOUD_BASE_URL, api_key=api_key),
        )
    elif provider == "groq" and api_key:
        registry.register("groq", GroqAdapter(api_key=api_key))
    return registry
```

In `_run_classification_background`, add `api_key: str | None` as the last parameter and replace `get_llm_registry()`:

Old signature and registry line:
```python
async def _run_classification_background(
    run_id: UUID,
    parse_run_id: UUID,
    labels: list[str],
    llm_provider: str,
    llm_model: str,
    batch_size: int,
    batch_overlap: int,
) -> None:
```
```python
            registry = get_llm_registry()
```

New:
```python
async def _run_classification_background(
    run_id: UUID,
    parse_run_id: UUID,
    labels: list[str],
    llm_provider: str,
    llm_model: str,
    batch_size: int,
    batch_overlap: int,
    api_key: str | None,
) -> None:
```
```python
            registry = _build_llm_registry(llm_provider, api_key)
```

In `create_classification_run`, add key resolution before `background_tasks.add_task` and pass `api_key`:

```python
    byok_provider = _classification_provider_to_byok(llm_provider)
    api_key: str | None = None
    if byok_provider:
        provider_key_repo = ProviderKeyRepository(db)
        api_key = await resolve_api_key(provider_key_repo, current_user.id, byok_provider)

    background_tasks.add_task(
        _run_classification_background,
        run_id=run.id,
        parse_run_id=body.parse_run_id,
        labels=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
        api_key=api_key,
    )
```

- [ ] **Step 4: Run tests and confirm they pass**

```
uv run --directory backend python -m pytest tests/routers/test_classification_key_resolution.py -v
```

Expected: PASS (8 tests)

- [ ] **Step 5: Run the full test suite**

```
uv run --directory backend python -m pytest tests/ -v --ignore=tests/cdm -x
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/classification.py backend/tests/routers/test_classification_key_resolution.py
git commit -m "feat(classification): wire BYOK key resolution, build per-request LLM registry"
```

---

## Task 6: Verify settings UI shows new providers

**Files:** No code changes — verification only.

- [ ] **Step 1: Start the backend**

```
uv run --directory backend uvicorn app.main:app --reload
```

- [ ] **Step 2: Start the frontend**

```
npm --prefix frontend run dev
```

- [ ] **Step 3: Check the providers API response**

```
curl http://localhost:8000/api/v1/settings/provider-keys/providers
```

Expected: response includes entries for `groq`, `llama_cloud`, `landing_ai`, `ollama_cloud`, each with `"requiresKey": true`.

- [ ] **Step 4: Open the settings UI**

Navigate to `http://localhost:5173` → Settings → API Keys.

Confirm that `Groq`, `LlamaIndex Cloud`, `Landing AI`, and `Ollama Cloud` appear in the provider list alongside the existing providers.

- [ ] **Step 5: Add a test key for one new provider**

Add a Groq key via the UI. Confirm it saves, appears masked, and can be deleted.
