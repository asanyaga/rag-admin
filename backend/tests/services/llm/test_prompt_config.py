from app.schemas.prompt_config import PromptConfig, ThinkingConfig
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig


def test_resolve_basic_fields():
    config = PromptConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=2048)
    result = resolve_llm_config(config)
    assert isinstance(result, LLMConfig)
    assert result.provider == "openai"
    assert result.model == "gpt-4o"
    assert result.temperature == 0.7
    assert result.max_tokens == 2048


def test_resolve_uses_defaults_when_provider_model_null():
    config = PromptConfig()
    result = resolve_llm_config(config, default_provider="anthropic", default_model="claude-sonnet-4-6")
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-6"


def test_resolve_uses_default_temperature_and_tokens():
    config = PromptConfig(provider="openai", model="gpt-4o")
    result = resolve_llm_config(config, default_temperature=0.5, default_max_tokens=2048)
    assert result.temperature == 0.5
    assert result.max_tokens == 2048


def test_resolve_explicit_temperature_overrides_default():
    config = PromptConfig(provider="openai", model="gpt-4o", temperature=0.9)
    result = resolve_llm_config(config, default_temperature=0.0)
    assert result.temperature == 0.9


def test_resolve_structured_output_sets_json_schema_mode():
    config = PromptConfig(provider="openai", model="gpt-4o", structured_output={"type": "object"})
    result = resolve_llm_config(config)
    assert result.structured_output_mode == "json_schema"


def test_resolve_json_mode_passthrough():
    config = PromptConfig(provider="openai", model="gpt-4o", json_mode=True)
    result = resolve_llm_config(config)
    assert result.structured_output_mode == "json_mode"


def test_resolve_none_config_returns_defaults():
    result = resolve_llm_config(None, default_provider="openai", default_model="gpt-4o")
    assert result.provider == "openai"
    assert result.model == "gpt-4o"
    assert result.temperature == 0.0
    assert result.max_tokens == 1024


def test_prompt_config_defaults():
    config = PromptConfig()
    assert config.provider is None
    assert config.model is None
    assert config.system_prompt is None
    assert config.temperature is None
    assert config.max_tokens is None
    assert config.thinking is None
    assert config.json_mode is False
    assert config.structured_output is None
    assert config.tools is None


def test_thinking_config_defaults():
    t = ThinkingConfig(enabled=True)
    assert t.effort is None
    assert t.budget_tokens is None
