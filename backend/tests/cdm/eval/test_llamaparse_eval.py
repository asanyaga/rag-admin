from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.llamaparse import LlamaParseAdapter


def test_invariants(llamaparse_fixture):
    name, raw = llamaparse_fixture
    doc = LlamaParseAdapter().adapt(
        raw, SourceMeta(source_document_id="src-eval", parse_run_id="run-eval"),
    )

    assert doc.page_count == len(doc.pages)

    for b in doc.blocks:
        assert 0 <= b.page_index < doc.page_count

    for b in doc.blocks:
        if b.bbox is not None:
            assert 0.0 <= b.bbox.x0 <= b.bbox.x1 <= 1.0
            assert 0.0 <= b.bbox.y0 <= b.bbox.y1 <= 1.0

    for b in doc.blocks:
        assert b.role is not None
        assert b.native_type

    block_ids = {b.id for b in doc.blocks}
    for p in doc.pages:
        for bid in p.block_ids:
            assert bid in block_ids

    for b in doc.blocks:
        if b.parent_id is not None:
            assert b.parent_id in block_ids

    if doc.blocks:
        assert doc.full_text or doc.full_markdown

    assert doc.source_document_id == "src-eval"
    assert doc.parse_run_id == "run-eval"

    from app.cdm.models import ParsedDocument
    restored = ParsedDocument.model_validate_json(doc.model_dump_json())
    assert restored == doc
