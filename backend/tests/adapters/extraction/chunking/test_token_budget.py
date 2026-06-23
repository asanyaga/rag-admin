from app.adapters.extraction.chunking.token_budget import (
    TokenBudgetPagesStrategy, estimate_tokens,
)
from app.cdm.models import Block, BlockRole, Page, ParsedDocument


def _doc(n_pages: int, chars_per_page: int = 400) -> ParsedDocument:
    pages, blocks = [], []
    for i in range(n_pages):
        blocks.append(Block(
            id=f"b{i}", role=BlockRole.PARAGRAPH, native_type="text",
            text="x" * chars_per_page, markdown="x" * chars_per_page,
            page_index=i, reading_order=0,
        ))
        pages.append(Page(index=i, block_ids=[f"b{i}"]))
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=n_pages, pages=pages, blocks=blocks,
    )


def test_estimate_tokens_uses_char_quarter():
    assert estimate_tokens("x" * 400) == 100


def test_single_chunk_when_under_budget():
    strat = TokenBudgetPagesStrategy(max_input_tokens=10_000)
    chunks = strat.split(_doc(3), {}, {})
    assert len(chunks) == 1
    assert chunks[0].page_indices == [0, 1, 2]
    assert chunks[0].document.page_count == 3


def test_packs_pages_to_budget_without_splitting_a_page():
    # each page ~100 tokens; budget 250 -> 2 pages per chunk
    strat = TokenBudgetPagesStrategy(max_input_tokens=250)
    chunks = strat.split(_doc(5), {}, {})
    assert [c.page_indices for c in chunks] == [[0, 1], [2, 3], [4]]
    assert all(c.document.derived_from == "p1" for c in chunks)
    assert chunks[0].document.derivation == "chunk:pages=0-1"


def test_overlap_repeats_trailing_pages():
    # budget 250 = 2 pages/chunk; overlap 1 carries the last page into the next chunk
    strat = TokenBudgetPagesStrategy(max_input_tokens=250, page_overlap=1)
    chunks = strat.split(_doc(5), {}, {})
    assert [c.page_indices for c in chunks] == [[0, 1], [1, 2], [2, 3], [3, 4]]


def test_derived_doc_only_keeps_chunk_blocks():
    strat = TokenBudgetPagesStrategy(max_input_tokens=250)
    chunks = strat.split(_doc(5), {}, {})
    assert [b.page_index for b in chunks[0].document.blocks] == [0, 1]
