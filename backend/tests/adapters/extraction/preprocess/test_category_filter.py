from app.adapters.extraction.preprocess.base import apply_preprocess
from app.cdm.models import Block, BlockRole, Page, ParsedDocument


def _doc():
    blocks = [
        Block(id="a", role=BlockRole.TEXT, native_type="t", text="alpha", markdown="alpha", page_index=0),
        Block(id="b", role=BlockRole.TEXT, native_type="t", text="bravo", markdown="bravo", page_index=1),
        Block(id="c", role=BlockRole.TEXT, native_type="t", text="charlie", markdown="charlie", page_index=1),
        Block(id="d", role=BlockRole.TEXT, native_type="t", text="delta", markdown="delta", page_index=2),
    ]
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=3,
        pages=[
            Page(index=0, block_ids=["a"]),
            Page(index=1, block_ids=["b", "c"]),
            Page(index=2, block_ids=["d"]),
        ],
        blocks=blocks,
        full_text="alpha\n\nbravo\n\ncharlie\n\ndelta",
        full_markdown="alpha\n\nbravo\n\ncharlie\n\ndelta",
    )


def _run(config):
    return apply_preprocess(_doc(), [{"stage": "category_filter", "config": config}])


def test_page_mode_keeps_whole_pages_and_reconstructs():
    out = _run({"keepPages": [1], "keepBlockIds": [], "categories": ["fin"]})
    assert [b.id for b in out.blocks] == ["b", "c"]
    assert [p.index for p in out.pages] == [1]           # original index preserved (sparse)
    assert out.pages[0].block_ids == ["b", "c"]
    assert out.page_count == 1
    assert out.full_markdown == "bravo\n\ncharlie"        # regenerated from kept blocks
    assert out.full_text == "bravo\n\ncharlie"
    assert out.blocks[0].page_index == 1                  # original page_index preserved
    assert out.derived_from == "p1"
    assert out.derivation == "preprocess:category_filter"
    assert any(l.name == "fin" and l.source == "classifier" for l in out.labels)


def test_block_mode_keeps_named_blocks_across_pages():
    out = _run({"keepPages": [], "keepBlockIds": ["a", "c"], "categories": ["x"]})
    assert [b.id for b in out.blocks] == ["a", "c"]
    assert [p.index for p in out.pages] == [0, 1]         # pages 0 and 1 retained
    assert out.pages[1].block_ids == ["c"]                # 'b' pruned from page 1
    assert out.page_count == 2


def test_block_mode_with_page_fallback_union():
    # keepBlockIds from attributed regions + keepPages from a fallback region
    out = _run({"keepPages": [2], "keepBlockIds": ["a"], "categories": ["x"]})
    assert [b.id for b in out.blocks] == ["a", "d"]
    assert [p.index for p in out.pages] == [0, 2]


def test_empty_keepset_yields_empty_doc():
    out = _run({"keepPages": [], "keepBlockIds": [], "categories": []})
    assert out.blocks == []
    assert out.pages == []
    assert out.page_count == 0
    assert out.full_markdown is None
