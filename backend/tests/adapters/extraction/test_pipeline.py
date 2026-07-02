import pytest
from uuid import uuid4

from app.adapters.extraction.pipeline import PipelineExtractor
from app.ports.data_extraction import DataExtractor, ExtractionError, ExtractionOutput
from app.services.llm.types import LLMRateLimitError
from app.cdm.models import Block, BlockRole, Page, ParsedDocument

_RUN = uuid4()
_SCHEMA = {"type": "object", "properties": {
    "products": {"type": "array", "items": {"type": "object",
        "properties": {"sku": {"type": "string"}}}}}}


def _doc(n_pages: int, chars=400):
    pages, blocks = [], []
    for i in range(n_pages):
        blocks.append(Block(id=f"b{i}", role=BlockRole.TEXT, native_type="t",
                            text="x" * chars, markdown="x" * chars, page_index=i))
        pages.append(Page(index=i, block_ids=[f"b{i}"]))
    return ParsedDocument(id="d", source_document_id="s", parse_run_id=str(_RUN),
                          page_count=n_pages, pages=pages, blocks=blocks)


class _FakeInner(DataExtractor):
    extractor_type = "fake"

    def __init__(self, behavior=None):
        self.calls = []
        self.docs = []
        self._behavior = behavior or (lambda doc, cfg: ExtractionOutput(
            structured_data={"products": [{"sku": f"p{doc.pages[0].index}"}]},
            source_parse_run_id=_RUN, citations=[], provider_response_raw=None,
            extraction_metadata={"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ))

    async def extract(self, parsed_document, schema, config=None):
        self.calls.append(config)
        self.docs.append(parsed_document)
        return self._behavior(parsed_document, config or {})


async def test_none_strategy_is_single_call_passthrough():
    inner = _FakeInner()
    px = PipelineExtractor(inner=inner, preprocess=None, chunking=None)
    out = await px.extract(_doc(3), _SCHEMA)
    assert len(inner.calls) == 1
    assert [p["sku"] for p in out.structured_data["products"]] == ["p0"]


async def test_chunking_merges_multiple_chunks():
    inner = _FakeInner()
    px = PipelineExtractor(inner=inner, preprocess=None,
                           chunking={"strategy": "token_budget_pages",
                                     "config": {"maxInputTokens": 150}})
    out = await px.extract(_doc(3), _SCHEMA)
    assert len(inner.calls) == 3
    assert {p["sku"] for p in out.structured_data["products"]} == {"p0", "p1", "p2"}


async def test_resolved_citation_level_passed_to_inner():
    inner = _FakeInner()
    px = PipelineExtractor(inner=inner, preprocess=None,
                           chunking={"strategy": "none", "citationLevel": "page_only"})
    await px.extract(_doc(1), _SCHEMA)
    assert inner.calls[0]["citation_level"] == "page_only"


async def test_preprocess_runs_before_extraction():
    inner = _FakeInner(behavior=lambda doc, cfg: ExtractionOutput(
        structured_data={"products": []}, source_parse_run_id=_RUN, citations=[],
        provider_response_raw=None, extraction_metadata={}))
    px = PipelineExtractor(
        inner=inner,
        preprocess=[{"stage": "block_filter", "config": {"drop": ["text"]}}],
        chunking=None,
    )
    await px.extract(_doc(1), _SCHEMA)
    # block_filter dropped the only (paragraph) block before the inner extractor ran
    assert inner.docs[0].blocks == []


async def test_failed_chunk_fails_whole_extraction():
    def boom(doc, cfg):
        if doc.pages[0].index == 1:
            raise ExtractionError("truncated chunk")
        return ExtractionOutput(structured_data={"products": []}, source_parse_run_id=_RUN,
                                citations=[], provider_response_raw=None, extraction_metadata={})
    inner = _FakeInner(behavior=boom)
    px = PipelineExtractor(inner=inner, preprocess=None,
                           chunking={"strategy": "token_budget_pages", "config": {"maxInputTokens": 150}})
    with pytest.raises(ExtractionError):
        await px.extract(_doc(3), _SCHEMA)


async def test_retries_on_rate_limit_then_succeeds():
    state = {"n": 0}
    def flaky(doc, cfg):
        state["n"] += 1
        if state["n"] == 1:
            raise LLMRateLimitError("429", retry_after=0)
        return ExtractionOutput(structured_data={"products": [{"sku": "ok"}]},
                                source_parse_run_id=_RUN, citations=[], provider_response_raw=None,
                                extraction_metadata={})
    inner = _FakeInner(behavior=flaky)
    px = PipelineExtractor(inner=inner, preprocess=None, chunking=None, max_retries=2)
    out = await px.extract(_doc(1), _SCHEMA)
    assert out.structured_data["products"] == [{"sku": "ok"}]


async def test_rate_limit_exhausts_retries_and_raises():
    def always_429(doc, cfg):
        raise LLMRateLimitError("429", retry_after=0)
    inner = _FakeInner(behavior=always_429)
    px = PipelineExtractor(inner=inner, preprocess=None, chunking=None, max_retries=1)
    with pytest.raises(LLMRateLimitError):
        await px.extract(_doc(1), _SCHEMA)


import asyncio as _asyncio
from app.adapters.extraction.pipeline import TpmThrottle


async def test_tpm_throttle_allows_within_budget():
    throttle = TpmThrottle(max_tpm=10_000)
    r = await throttle.throttle(5_000)
    assert r.tokens == 5_000


async def test_tpm_throttle_blocks_when_budget_full():
    """Second throttle call must block when the window is saturated."""
    throttle = TpmThrottle(max_tpm=5_000)
    await throttle.throttle(5_000)  # saturate window
    with pytest.raises(_asyncio.TimeoutError):
        await _asyncio.wait_for(throttle.throttle(1_000), timeout=0.05)


async def test_tpm_throttle_oversized_chunk_fires_when_window_empty():
    """A single chunk larger than max_tpm still fires (window is empty)."""
    throttle = TpmThrottle(max_tpm=1_000)
    r = await throttle.throttle(5_000)
    assert r.tokens == 5_000


async def test_tpm_throttle_replace_reservation_mutates_tokens():
    throttle = TpmThrottle(max_tpm=10_000)
    r = await throttle.throttle(5_000)
    throttle.replace_reservation(r, 3_200)
    assert r.tokens == 3_200


async def test_tpm_throttle_rolling_estimate_starts_at_default():
    throttle = TpmThrottle(max_tpm=30_000, default_estimate=8_000)
    assert throttle.rolling_estimate == 8_000


async def test_tpm_throttle_rolling_estimate_adapts_after_replacement():
    throttle = TpmThrottle(max_tpm=30_000, default_estimate=8_000)
    r = await throttle.throttle(8_000)
    throttle.replace_reservation(r, 5_000)
    assert throttle.rolling_estimate == 5_000


async def test_pipeline_with_tpm_throttle_processes_all_chunks():
    """TPM throttle enabled with a high budget must not affect output correctness."""
    inner = _FakeInner()
    px = PipelineExtractor(
        inner=inner,
        preprocess=None,
        chunking={"strategy": "token_budget_pages", "config": {"maxInputTokens": 150}},
        max_tokens_per_minute=100_000,
    )
    out = await px.extract(_doc(3), _SCHEMA)
    assert len(inner.calls) == 3
    assert {p["sku"] for p in out.structured_data["products"]} == {"p0", "p1", "p2"}
