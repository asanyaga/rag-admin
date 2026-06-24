import pytest
from app.adapters.extraction.chunking.registry import build_strategy, get_chunk_strategies
from app.adapters.extraction.chunking.token_budget import TokenBudgetPagesStrategy


def test_catalogue_lists_none_and_token_budget():
    names = {s["strategy"] for s in get_chunk_strategies()}
    assert {"none", "token_budget_pages"} <= names
    tb = next(s for s in get_chunk_strategies() if s["strategy"] == "token_budget_pages")
    assert "maxInputTokens" in tb["config_schema"]["properties"]


def test_build_none_returns_none():
    assert build_strategy("none", {}) is None


def test_build_token_budget_uses_config():
    strat = build_strategy("token_budget_pages", {"maxInputTokens": 5000, "pageOverlap": 2})
    assert isinstance(strat, TokenBudgetPagesStrategy)
    assert strat.max_input_tokens == 5000
    assert strat.page_overlap == 2


def test_build_unknown_raises():
    with pytest.raises(ValueError):
        build_strategy("nope", {})
