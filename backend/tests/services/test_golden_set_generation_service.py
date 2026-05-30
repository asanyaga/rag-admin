"""Tests for GoldenSetGenerationService — system prompt threading."""
import pytest
from unittest.mock import AsyncMock
from app.services.golden_set_generation_service import (
    GoldenSetGenerationService,
    DEFAULT_GENERATION_SYSTEM_PROMPT,
)


def test_default_generation_system_prompt_is_non_empty():
    assert isinstance(DEFAULT_GENERATION_SYSTEM_PROMPT, str)
    assert len(DEFAULT_GENERATION_SYSTEM_PROMPT) > 100


def test_build_generation_prompt_uses_default_when_none():
    svc = GoldenSetGenerationService(
        golden_set_repo=AsyncMock(),
        document_repo=AsyncMock(),
        provider_key_repo=AsyncMock(),
    )
    messages = svc._build_generation_prompt(
        page_text="some text",
        page_range=[1],
        doc_title="Doc",
        queries_count=2,
        question_types=["factual"],
        system_prompt=None,
    )
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == DEFAULT_GENERATION_SYSTEM_PROMPT


def test_build_generation_prompt_uses_custom_when_provided():
    svc = GoldenSetGenerationService(
        golden_set_repo=AsyncMock(),
        document_repo=AsyncMock(),
        provider_key_repo=AsyncMock(),
    )
    custom = "Custom system prompt for testing."
    messages = svc._build_generation_prompt(
        page_text="some text",
        page_range=[1],
        doc_title="Doc",
        queries_count=2,
        question_types=["factual"],
        system_prompt=custom,
    )
    assert messages[0]["content"] == custom
