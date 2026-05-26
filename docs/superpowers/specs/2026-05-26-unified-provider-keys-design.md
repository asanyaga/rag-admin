# Unified Provider Key Storage

**Date:** 2026-05-26
**Status:** Approved

## Problem

Provider API keys are stored in two inconsistent places:

- **Playground** uses BYOK: keys stored encrypted in the `provider_keys` DB table, resolved per user/project.
- **Extraction** uses `.env`: keys read directly from application settings at runtime.
- **Classification** — to be confirmed during implementation (may also read env vars directly).

This means users cannot bring their own extraction keys, and there is no single place to manage credentials.

## Goal

Unify all provider API keys under the existing BYOK system with an env-var fallback, so:

- Users can configure any provider key via the settings UI.
- Deployments that set env vars continue to work without any UI configuration.
- All features (playground, extraction, classification) resolve keys through one code path.

## Design

### 1. Provider Registry

Extend `SUPPORTED_PROVIDERS` in `backend/app/schemas/provider_key.py` with four new providers:

| Provider ID    | Display Name      | Replaces env var        |
|----------------|-------------------|-------------------------|
| `groq`         | Groq              | `GROQ_API_KEY`          |
| `llama_cloud`  | LlamaIndex Cloud  | `LLAMA_CLOUD_KEY`       |
| `landing_ai`   | Landing AI        | `VISION_AGENT_API_KEY`  |
| `ollama_cloud` | Ollama Cloud      | `OLLAMA_CLOUD_API_KEY`  |

Existing providers remain unchanged:

| Provider ID | Display Name    | Notes                        |
|-------------|-----------------|------------------------------|
| `openai`    | OpenAI          | Embeddings + LLM             |
| `voyage`    | Voyage AI       | Embeddings only              |
| `anthropic` | Anthropic       | LLM only                     |
| `local`     | Local (Ollama)  | No key required              |

No database migration required — `provider` is a free-form string column.

Grouping or capability tagging (e.g. "Embeddings", "LLM", "Extraction") is intentionally deferred. Adding optional display metadata to provider entries later is backward-compatible and requires no data model changes.

The env var name `VISION_AGENT_API_KEY` is kept as-is to avoid breaking existing deployments. Only the provider ID exposed in the API changes to `landing_ai`.

### 2. Resolver Function

Add `resolve_api_key` to `backend/app/services/provider_key_service.py`:

```python
async def resolve_api_key(
    db: AsyncSession,
    user_id: UUID,
    provider: str,
    project_id: UUID | None = None,
) -> str | None:
    # 1. DB: project-level key → account-level key (existing logic)
    key_record = await repo.get_for_provider(db, user_id, provider, project_id)
    if key_record:
        return decrypt(key_record.api_key_encrypted)

    # 2. Env var fallback (only providers that currently live in .env)
    env_fallbacks = {
        "groq":         settings.GROQ_API_KEY,
        "llama_cloud":  settings.LLAMA_CLOUD_KEY,
        "landing_ai":   settings.VISION_AGENT_API_KEY,
        "ollama_cloud": settings.OLLAMA_CLOUD_API_KEY,
    }
    return env_fallbacks.get(provider)
```

`openai`, `anthropic`, `voyage`, and `local` have no env var equivalent and are DB-only (no change from today).

### 3. Wiring

**Extraction** (`backend/app/routers/extraction.py`):

Replace the body of `_resolve_credentials_from_settings()` — the existing seam comment marks exactly this point — with calls to `resolve_api_key`. The function signature stays the same; only the body changes.

```python
async def _resolve_credentials_from_settings(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    extractor_type: str,
) -> dict:
    provider_map = {
        "llama_cloud":  "llama_cloud",
        "ollama":       "ollama_cloud",
        "groq":         "groq",
        "vision_agent": "landing_ai",
    }
    provider = provider_map.get(extractor_type)
    if not provider:
        return {}
    key = await resolve_api_key(db, user_id, provider, project_id)
    return {"api_key": key} if key else {}
```

**Playground** (`backend/app/routers/indexes.py`):

Replace the inline `repo.get_for_provider` + `decrypt` block with a single `resolve_api_key` call. The error handling (HTTP 400 if no key found) stays in the router.

**Classification** — check during implementation whether it reads env vars directly. If so, wire it through `resolve_api_key` the same way.

### 4. UI

No new components. The settings page already renders all providers where `requiresKey: true`. The four new providers will appear automatically once added to the registry.

The provider list is flat — no grouping or capability badges in this iteration.

## Out of Scope

- Non-AI integrations (Slack, etc.) — deferred until use case is defined (user-facing vs. admin-configured).
- Ollama local endpoint URL (`OLLAMA_LOCAL_BASE_URL`, `OLLAMA_CLOUD_BASE_URL`) — these are config values, not secrets; they stay in `.env`.
- Per-user encryption keys — the app-wide `ENCRYPTION_KEY` is sufficient.
- Capability/category metadata on providers — can be added later as optional display-only fields.
