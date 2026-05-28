# Unified LLM Inference Abstraction — Design

**Date:** 2026-05-28
**Status:** Approved

## Problem

The codebase has two parallel LLM inference paths that have diverged in behavior, and several feature entry points that bypass the shared abstraction entirely. The result is:

- Non-OpenAI providers silently fail in golden-set generation and eval runs
- `LLMExtractor` ignores the resolved provider and routes all calls to a hardcoded endpoint
- `max_tokens` is resolved but never forwarded in extraction
- Ollama's known `json_schema` incompatibility is handled in one path and ignored in the other
- Groq is registered in the registry but absent from the factory — unreachable from streaming answers
- Streaming usage is filtered out and the `done` event always reports zero prompt tokens
- Every feature owns its own credential resolution logic

The desired end state is one inference path, one contract, and a structure where adding a new provider means one adapter file plus one line in the factory — nothing else.

---

## Design

### 1. Data model — extend `LLMConfig`

`LLMConfig` in `services/llm/types.py` gains two fields and loses one:

```python
@dataclass
class LLMConfig:
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    structured_output_mode: Literal["json_schema", "json_mode", "prompt_only"] | None = None
    structured_output_schema: dict | None = None
```

- `structured_output_mode` replaces `json_mode: bool`. It is a first-class field available to any feature — not extraction-specific.
- `structured_output_schema` carries the JSON schema enforced when `mode = "json_schema"`. It is `None` for all other modes.
- `json_mode: bool` is removed. All four call sites that pass `json_mode=True` (`LLMClassifier`, `JudgeService`, `GoldenSetGenerationService._process_window`, `AnswerService`) migrate to `structured_output_mode="json_mode"`.

The `provider` field represents intent and is used for tracing and adapter routing. It is never hardcoded to `"openai"` by callers.

---

### 2. Adapter contract

#### Structured output handling

Each adapter's `complete()` inspects `config.structured_output_mode`:

| Mode | OpenAI / Groq | Anthropic | Ollama |
|---|---|---|---|
| `json_schema` | `response_format={type: json_schema, strict: true, schema: config.structured_output_schema}` | Raise `NotImplementedError` | Degrade to `prompt_only` — skip `response_format` entirely (known incompatibility) |
| `json_mode` | `response_format={type: json_object}` | Append a JSON instruction to the system message | `response_format={type: json_object}` |
| `prompt_only` / `None` | No change | No change | No change |

`OllamaAdapter` already extends `OpenAIAdapter`; it overrides only the `json_schema` case. `GroqAdapter` extends `OpenAIAdapter` and inherits all three modes without changes.

#### Streaming usage — `StreamResponse`

`stream_completion` currently returns `AsyncIterator[str]`. To surface usage after the stream ends without changing the iteration call site, the return type becomes `StreamResponse`:

```python
class StreamResponse:
    def __aiter__(self) -> AsyncIterator[str]: ...  # yields content tokens
    usage: TokenUsage | None  # None until iteration is exhausted
```

`LLMPort` is updated to reflect this return type. `OpenAIAdapter` captures the trailing usage-only chunk (currently filtered out by the `chunk.choices and chunk.choices[0].delta.content` guard) and writes it onto the `StreamResponse` object after the stream ends. `answer_service` reads `.usage` after the loop and populates the `done` event with real counts. Adapters that do not surface streaming usage (`AnthropicAdapter`, `OllamaAdapter`) leave `.usage = None`; the `done` event reports `null` rather than a wrong `0`.

#### Connection error handling

`OpenAIAdapter`, `OllamaAdapter`, and `GroqAdapter` catch `openai.APIConnectionError` and raise `LLMConnectionError`. `AnthropicAdapter` catches `anthropic.APIConnectionError` and raises the same. `LLMConnectionError` is a new exception type in `services/llm/`. Features catch it at their own boundary — no per-feature wrapping needed.

---

### 3. Credential resolution

A single async function in `app/services/llm/credentials.py` replaces every ad-hoc credential lookup:

```python
@dataclass
class ProviderCredentials:
    api_key: str
    base_url: str | None  # None = use the adapter's built-in default

async def resolve_provider_credentials(
    provider: str,
    user_id: UUID,
    project_id: UUID,
    db: AsyncSession,
) -> ProviderCredentials:
```

Behaviour:
- Providers that need no user key (`ollama_local`) return `ProviderCredentials(api_key="ollama", base_url=None)` immediately without a database call.
- All other providers query `ProviderKeyRepository.get_for_provider()`. If no key exists, `ValidationError("No API key configured for provider '…'")` is raised immediately.
- The decrypted key and any stored `base_url` are returned together.

Every call site becomes the same two-liner:

```python
creds   = await resolve_provider_credentials(provider, user_id, project_id, db)
adapter = create_adapter(provider, creds.api_key, creds.base_url)
```

#### Self-hosted inference

`ProviderKey` model gains an optional `base_url: str | None` column (requires a migration). Users configure a self-hosted OpenAI-compatible endpoint by selecting `openai` as the provider type and supplying a custom base URL alongside their key. The adapter uses `base_url` to override its default; `None` means use the provider's standard endpoint.

`create_adapter` grows one optional parameter:

```python
def create_adapter(provider: str, api_key: str, base_url: str | None = None) -> LLMPort:
```

`OpenAIAdapter` and `GroqAdapter` already accept `base_url` in their constructors. `AnthropicAdapter` ignores it for now. Ollama adapters continue using their settings-based URLs unless overridden.

---

### 4. Factory as single source of truth — retire `LLMRegistry`

`_ADAPTER_FACTORIES` in `factory.py` becomes the single authoritative list:

```python
_ADAPTER_FACTORIES: dict[str, Callable[[str, str | None], LLMPort]] = {
    "openai":       lambda api_key, base_url: OpenAIAdapter(api_key, base_url),
    "anthropic":    lambda api_key, base_url: AnthropicAdapter(api_key),
    "groq":         lambda api_key, base_url: GroqAdapter(api_key=api_key),
    "ollama_cloud": lambda api_key, base_url: OllamaAdapter(
                        base_url=base_url or settings.OLLAMA_CLOUD_BASE_URL, api_key=api_key),
    "ollama_local": lambda api_key, base_url: OllamaAdapter(
                        base_url=base_url or settings.OLLAMA_LOCAL_BASE_URL, api_key=api_key),
}
```

Adding a new provider means adding one entry here. Nothing else needs updating.

`LLMRegistry`, `get_llm_registry()` (`dependencies/llm.py`), and `_build_llm_registry()` (`classifier_factory.py`) are all removed. `LLMClassifier` no longer takes a registry — it takes `adapter: LLMPort` directly (see Section 6).

---

### 5. Rewrite `LLMExtractor` — delete `OpenAICompatMixin`

`OpenAICompatMixin` is deleted entirely. `LLMExtractor` drops the mixin inheritance and is rewritten to use the standard path.

**Constructor** changes from `default_endpoint` / `default_api_key` to:

```python
def __init__(
    self,
    default_provider: str = "ollama_local",
    default_api_key: str = "ollama",
) -> None:
```

**Credential flow:** `LLMExtractor` has no database access and does not call `resolve_provider_credentials` itself. The extraction router/service pre-resolves credentials and writes `provider`, `api_key`, and `base_url` into the `cfg` dict before calling `extract()`. This is consistent with the existing pattern where the router already passes `api_key` in the config.

**`extract()`** resolves credentials from `cfg`, builds `LLMConfig`, and calls the adapter:

```python
provider  = cfg.get("provider")  or self._default_provider
api_key   = cfg.get("api_key")   or self._default_api_key
base_url  = cfg.get("base_url")  # self-hosted override

structured_output_mode = cfg.get("structured_output_mode", "json_schema")

llm_config = LLMConfig(
    provider  = resolved_provider,
    model     = resolved_model,
    temperature = resolved_temperature,
    max_tokens  = resolved_max_tokens,
    structured_output_mode   = structured_output_mode,
    structured_output_schema = aug_schema if structured_output_mode == "json_schema" else None,
)

adapter = create_adapter(provider, api_key, base_url)
result  = await adapter.complete(messages, llm_config)
raw     = json.loads(result.content)  # raises ExtractionError on failure
```

This fixes in one sweep:
- `max_tokens` not forwarded — now in `LLMConfig`, all adapters use it
- Per-call client construction — adapter owns its client; `async with` teardown on every call is gone
- Ollama `json_schema` degradation — handled in `OllamaAdapter.complete()`
- Provider routing — adapter type is determined by the `provider` string
- Token usage — `result.usage` is recorded in `extraction_metadata`

The misleading `BadRequestError` warning ("Consider switching structured_output_mode to 'json_mode'") is removed along with the mixin. Connection errors surface as `LLMConnectionError` from the adapter layer.

---

### 6. Fix remaining entry points

#### `eval_runs.py`

Remove `_resolve_adapter` helper, remove imports of `OpenAIAdapter` and `AnthropicAdapter`. Replace with:

```python
creds = await resolve_provider_credentials(provider, user_id, project_id, db)
adapter = create_adapter(provider, creds.api_key, creds.base_url)
```

Groq, Ollama, and all future providers now work automatically. No local whitelist.

#### `golden_set_generation_service.py`

Three targeted fixes:
1. Replace `OpenAIAdapter(api_key=api_key)` with `create_adapter(llm_provider, api_key, key_record.base_url)` — the existing credential fetch via `provider_key_repo` is correct and stays; `base_url` is read from the key record (new column) and forwarded.
2. Change `_process_window`'s type hint from `adapter: OpenAIAdapter` to `adapter: LLMPort`.
3. Change `LLMConfig(provider="openai", ...)` to use the actual `llm_provider` value.

#### `answer_service.py`

Already uses `create_adapter()` correctly. Change: iterate `StreamResponse` for tokens, read `.usage` after exhaustion, populate the `done` event with real token counts.

#### `classifier_factory.py`

Remove `_build_llm_registry`, `LLMRegistry` import, and the `except ValueError: pass` that silently returned an empty registry. `LLMClassifier.__init__` takes `adapter: LLMPort` directly. `build_classifier` calls `create_adapter(provider, api_key, base_url)` — a `ValueError` from an unknown provider now raises immediately at build time.

---

## Files changed

| File | Change |
|---|---|
| `services/llm/types.py` | Add `structured_output_mode`, `structured_output_schema`; remove `json_mode`; add `StreamResponse` |
| `services/llm/port.py` | Update `stream_completion` return type to `StreamResponse` |
| `services/llm/factory.py` | Add `groq`; add `base_url` param to signature and lambdas |
| `services/llm/openai_adapter.py` | Handle `structured_output_mode`; fix streaming usage capture; catch `APIConnectionError` |
| `services/llm/anthropic_adapter.py` | Handle `structured_output_mode`; catch `APIConnectionError` |
| `services/llm/ollama_adapter.py` | Handle `structured_output_mode` (degrade `json_schema` → `prompt_only`) |
| `services/llm/groq_adapter.py` | Inherits OpenAI changes; no direct changes needed |
| `services/llm/credentials.py` | **New** — `ProviderCredentials`, `resolve_provider_credentials()` |
| `models/provider_key.py` | Add `base_url: str \| None` column |
| `adapters/extraction/llm.py` | Rewrite — use `create_adapter` + `LLMPort.complete()` |
| `adapters/extraction/openai_compat_mixin.py` | **Deleted** |
| `services/classification/llm_classifier.py` | Take `adapter: LLMPort` instead of `llm_registry: LLMRegistry` |
| `services/classification/classifier_factory.py` | Remove `_build_llm_registry`; use `create_adapter`; remove silent `except ValueError` |
| `services/golden_set_generation_service.py` | Use `create_adapter`; fix `_process_window` type hint; fix `LLMConfig.provider` |
| `services/answer_service.py` | Consume `StreamResponse.usage` for accurate `done` event |
| `routers/eval_runs.py` | Remove `_resolve_adapter`; remove concrete adapter imports; use `resolve_provider_credentials` + `create_adapter` |
| `dependencies/llm.py` | **Deleted** — `get_llm_registry()` no longer needed |
| `alembic/versions/` | New migration adding `provider_key.base_url` column |

---

## Extension path

Adding a new provider (Cohere, AWS Bedrock, etc.) requires:
1. A new adapter file implementing `LLMPort`
2. One line in `_ADAPTER_FACTORIES`
3. One entry in `SUPPORTED_PROVIDERS` in `schemas/provider_key.py` (for the BYOK UI)

No changes to `LLMExtractor`, `answer_service`, `eval_runs`, `golden_set_generation_service`, `classifier_factory`, or the credential resolver.

---

## Design constraints

- The `LLMPort` protocol is provider-agnostic. The message format (`[{"role": "...", "content": "..."}]`) is OpenAI's wire format and is the de-facto standard; non-OpenAI adapters translate internally (as `AnthropicAdapter` already does).
- `LLMConfig` fields represent *intent*. Adapters decide *how* to fulfil each intent. A field added to `LLMConfig` should mean something to at least two providers.
- `structured_output_mode="json_schema"` is an OpenAI capability. Adapters that do not support it raise `NotImplementedError` rather than silently producing wrong output.
