from app.adapters.extraction.pipeline import PipelineExtractor
from app.adapters.extraction.llm import LLMExtractor
from app.routers.extraction import _maybe_wrap_pipeline


class _FakeAdapter:
    async def complete(self, messages, config):  # pragma: no cover - not called here
        raise AssertionError("not called")


def test_wrap_returns_pipeline_when_chunking_present():
    inner = LLMExtractor(adapter=_FakeAdapter(), provider="anthropic")
    wrapped = _maybe_wrap_pipeline(inner, preprocess=None,
                                   chunking={"strategy": "token_budget_pages", "config": {}})
    assert isinstance(wrapped, PipelineExtractor)


def test_wrap_returns_pipeline_when_preprocess_present():
    inner = LLMExtractor(adapter=_FakeAdapter(), provider="anthropic")
    wrapped = _maybe_wrap_pipeline(
        inner, preprocess=[{"stage": "block_filter", "config": {}}], chunking=None)
    assert isinstance(wrapped, PipelineExtractor)


def test_wrap_returns_inner_when_no_pipeline_config():
    inner = LLMExtractor(adapter=_FakeAdapter(), provider="anthropic")
    assert _maybe_wrap_pipeline(inner, preprocess=None, chunking=None) is inner
