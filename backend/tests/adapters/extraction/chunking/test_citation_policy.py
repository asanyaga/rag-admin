import pytest
from app.adapters.extraction.chunking.citation_policy import (
    AUTO_PAGE_ONLY_THRESHOLD_TOKENS, resolve_level,
)


def test_explicit_levels_pass_through():
    assert resolve_level("full", 1) == "full"
    assert resolve_level("page_only", 10**9) == "page_only"
    assert resolve_level("off", 1) == "off"


def test_auto_small_doc_is_full():
    assert resolve_level("auto", AUTO_PAGE_ONLY_THRESHOLD_TOKENS - 1) == "full"


def test_auto_large_doc_is_page_only_never_off():
    assert resolve_level("auto", AUTO_PAGE_ONLY_THRESHOLD_TOKENS + 1) == "page_only"
    assert resolve_level("auto", 10**9) == "page_only"


def test_unknown_level_raises():
    with pytest.raises(ValueError):
        resolve_level("nonsense", 1)
