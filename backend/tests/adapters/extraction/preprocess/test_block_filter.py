import pytest
from app.adapters.extraction.preprocess.base import apply_preprocess, get_preprocess_stages
from app.cdm.models import Block, BlockRole, Page, ParsedDocument


def _doc():
    blocks = [
        Block(id="h", role=BlockRole.HEADER, native_type="t", text="hdr", page_index=0),
        Block(id="p", role=BlockRole.TEXT, native_type="t", text="body", page_index=0),
        Block(id="f", role=BlockRole.FOOTER, native_type="t", text="ftr", page_index=0),
    ]
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=1, pages=[Page(index=0, block_ids=["h", "p", "f"])], blocks=blocks,
    )


def test_block_filter_drops_named_roles_preserves_order():
    out = apply_preprocess(_doc(), [{"stage": "block_filter", "config": {"drop": ["header", "footer"]}}])
    assert [b.id for b in out.blocks] == ["p"]
    assert out.parse_run_id == "p1"  # source identity preserved on derived doc


def test_block_filter_no_drop_is_noop():
    doc = _doc()
    out = apply_preprocess(doc, [{"stage": "block_filter", "config": {}}])
    assert [b.id for b in out.blocks] == ["h", "p", "f"]


def test_empty_stages_returns_same_doc():
    doc = _doc()
    assert apply_preprocess(doc, []) is doc


def test_catalogue_lists_block_filter_and_category_filter():
    names = {s["stage"] for s in get_preprocess_stages()}
    assert {"block_filter", "category_filter"} <= names


def test_unknown_stage_raises():
    with pytest.raises(ValueError):
        apply_preprocess(_doc(), [{"stage": "nope", "config": {}}])


def test_category_filter_not_implemented():
    with pytest.raises(NotImplementedError):
        apply_preprocess(_doc(), [{"stage": "category_filter", "config": {"categories": ["spec"]}}])
