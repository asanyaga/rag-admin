from app.config import settings
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier
from app.services.classification.port import ClassificationPort
from app.services.llm.factory import create_adapter

# Providers that require a user-supplied API key for classification.
# ollama_local is excluded — it uses a dummy key.
_LLM_BYOK_PROVIDERS = {"groq", "ollama_cloud", "anthropic", "openai"}


def _resolve_byok_provider(classifier_type: str, classifier_config: dict) -> str | None:
    """Return the BYOK provider ID if an API key is required, else None."""
    if classifier_type == "llm":
        provider = classifier_config.get("provider", "")
        return provider if provider in _LLM_BYOK_PROVIDERS else None
    return None


def build_classifier(
    classifier_type: str,
    classifier_config: dict,
    api_key: str | None,
    base_url: str | None = None,
) -> ClassificationPort:
    if classifier_type == "llm":
        provider = classifier_config.get("provider", settings.CLASSIFIER_LLM_PROVIDER)
        model = classifier_config.get("model", settings.CLASSIFIER_LLM_MODEL)
        batch_size = int(classifier_config.get("batch_size", 10))
        batch_overlap = int(classifier_config.get("batch_overlap", 3))
        llm_cfg = classifier_config.get("llm_config") or {}
        system_prompt: str | None = llm_cfg.get("system_prompt")
        temperature: float = float(llm_cfg.get("temperature", 0.0))
        max_tokens: int = int(llm_cfg.get("max_tokens", 4096))

        effective_key = api_key if api_key is not None else "ollama"
        # ValueError from create_adapter propagates immediately — no silent swallow
        adapter = create_adapter(provider, effective_key, base_url)

        return LLMClassifier(
            adapter=adapter,
            provider=provider,
            model=model,
            batch_size=batch_size,
            batch_overlap=batch_overlap,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif classifier_type == "llamaindex_split":
        return LlamaIndexSplitClassifier(classifier_config)
    else:
        raise ValueError(
            f"Unknown classifier type: {classifier_type!r}. "
            "Supported: 'llm', 'llamaindex_split'"
        )
