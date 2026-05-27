"""Shared PromptConfig schema used across all LLM-using features."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ThinkingConfig(BaseModel):
    """Provider-agnostic reasoning/thinking control."""
    enabled: bool = True
    effort: Literal["low", "medium", "high"] | None = None
    budget_tokens: int | None = Field(None, alias="budgetTokens")

    model_config = ConfigDict(populate_by_name=True)


class PromptConfig(BaseModel):
    """User-expressed LLM configuration.

    Stores what the user configured. Converted to adapter-ready LLMConfig
    via resolve_llm_config() before being passed to LLM adapters.
    provider/model are nullable — None means use the feature's default.
    """
    system_prompt: str | None = Field(None, alias="systemPrompt")
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(None, alias="maxTokens")
    top_p: float | None = Field(None, alias="topP")
    thinking: ThinkingConfig | None = None
    json_mode: bool = Field(False, alias="jsonMode")
    structured_output: dict | None = Field(None, alias="structuredOutput")
    tools: list[dict] | None = None

    model_config = ConfigDict(populate_by_name=True)
