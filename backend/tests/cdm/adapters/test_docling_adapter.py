"""Tests for DoclingAdapter — structural invariants and helper functions."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.cdm.models import ParserKind
from app.services.parsing.errors import DoclingRunError, ParseRunError


# ── Task 1: Bootstrap tests ───────────────────────────────────────────────────

def test_parser_kind_docling_value():
    assert ParserKind("docling") == ParserKind.DOCLING
    assert ParserKind.DOCLING.value == "docling"


def test_docling_run_error_is_parse_run_error():
    assert issubclass(DoclingRunError, ParseRunError)


def test_docling_run_error_carries_run():
    from datetime import datetime, timezone
    from app.cdm.source import ParseRun, ParseRunStatus

    run = ParseRun(
        id="r1",
        source_document_id="s1",
        parser=ParserKind.DOCLING,
        representation_kind="extract_rich",
        status=ParseRunStatus.FAILED,
        started_at=datetime.now(timezone.utc),
    )
    err = DoclingRunError("failed", run=run)
    assert err.run is run


# ── Shared fixture helpers (used by Tasks 2 and 3) ───────────────────────────

def _fake_bbox(l=50.0, t=750.0, r=545.0, b=700.0, origin="BOTTOMLEFT"):
    return SimpleNamespace(l=l, t=t, r=r, b=b, coord_origin=origin)


def _fake_prov(page_no=1, bbox=None):
    return SimpleNamespace(page_no=page_no, bbox=bbox or _fake_bbox())


def _fake_text_item(text: str, label_value: str = "text", page_no: int = 1,
                    l=50.0, t=750.0, r=545.0, b=700.0):
    bbox = _fake_bbox(l=l, t=t, r=r, b=b, origin="BOTTOMLEFT")
    prov = _fake_prov(page_no=page_no, bbox=bbox)
    label = SimpleNamespace(value=label_value)
    return SimpleNamespace(
        label=label,
        text=text,
        prov=[prov],
        export_to_markdown=lambda: (f"# {text}" if label_value == "title" else text),
    )


def _fake_table_item(page_no: int = 1):
    cell = SimpleNamespace(
        start_row_offset=0, start_col_offset=0,
        end_row_offset=1, end_col_offset=1,
        row_span=1, col_span=1,
        text="Header", column_header=True,
    )
    bbox = _fake_bbox(l=50.0, t=600.0, r=545.0, b=500.0, origin="BOTTOMLEFT")
    prov = _fake_prov(page_no=page_no, bbox=bbox)
    label = SimpleNamespace(value="table")
    return SimpleNamespace(
        label=label,
        text="",
        prov=[prov],
        data=SimpleNamespace(grid=[[cell]]),
        export_to_markdown=lambda: "| Header |\n|---|",
        export_to_html=lambda: "<table><tr><th>Header</th></tr></table>",
    )


def _fake_page_item(width: float = 595.0, height: float = 842.0):
    return SimpleNamespace(size=SimpleNamespace(width=width, height=height))


def _make_fake_doc(items, page_no: int = 1, width: float = 595.0, height: float = 842.0):
    pages = {page_no: _fake_page_item(width, height)}
    items_with_level = [(item, 0) for item in items]
    full_md = "\n\n".join(getattr(i, "text", "") for i in items if getattr(i, "text", ""))
    return SimpleNamespace(
        pages=pages,
        iterate_items=lambda: iter(items_with_level),
        export_to_markdown=lambda: full_md,
    )


# ── Task 2: BBox and role-mapping helper tests ────────────────────────────────

def test_to_cdm_bbox_bottomleft_full_page():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Full page in bottom-left: l=0, t=842 (top from bottom), r=595, b=0
    bbox = _fake_bbox(l=0.0, t=842.0, r=595.0, b=0.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.0)
    assert result.x1 == pytest.approx(1.0)
    assert result.y1 == pytest.approx(1.0)


def test_to_cdm_bbox_bottomleft_bottom_half():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Bottom half: l=0, t=421, r=595, b=0 → CDM y0=0.5, y1=1.0
    bbox = _fake_bbox(l=0.0, t=421.0, r=595.0, b=0.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.5, abs=0.01)
    assert result.x1 == pytest.approx(1.0)
    assert result.y1 == pytest.approx(1.0)


def test_to_cdm_bbox_topleft():
    from app.cdm.adapters.docling import _to_cdm_bbox
    # Top-left quarter: l=0, t=0, r=297.5, b=421
    bbox = _fake_bbox(l=0.0, t=0.0, r=297.5, b=421.0, origin="TOPLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert result.x0 == pytest.approx(0.0)
    assert result.y0 == pytest.approx(0.0)
    assert result.x1 == pytest.approx(0.5)
    assert result.y1 == pytest.approx(0.5)


def test_to_cdm_bbox_clamped():
    from app.cdm.adapters.docling import _to_cdm_bbox
    bbox = _fake_bbox(l=-10.0, t=900.0, r=700.0, b=-5.0, origin="BOTTOMLEFT")
    result = _to_cdm_bbox(bbox, page_width=595.0, page_height=842.0)
    assert 0.0 <= result.x0 <= result.x1 <= 1.0
    assert 0.0 <= result.y0 <= result.y1 <= 1.0


def test_map_role_known_labels():
    from app.cdm.adapters.docling import _map_role
    from app.cdm.models import BlockRole

    cases = [
        ("title",          BlockRole.TITLE),
        ("section_header", BlockRole.HEADING),
        ("text",           BlockRole.TEXT),
        ("paragraph",      BlockRole.TEXT),
        ("list_item",      BlockRole.LIST),
        ("table",          BlockRole.TABLE),
        ("picture",        BlockRole.FIGURE),
        ("caption",        BlockRole.CAPTION),
        ("code",           BlockRole.CODE),
        ("formula",        BlockRole.FORMULA),
        ("page_header",    BlockRole.HEADER),
        ("page_footer",    BlockRole.FOOTER),
        ("footnote",       BlockRole.OTHER),
    ]
    for label_value, expected_role in cases:
        label = SimpleNamespace(value=label_value)
        assert _map_role(label) == expected_role, f"failed for {label_value}"


def test_map_role_unknown_falls_back_to_other():
    from app.cdm.adapters.docling import _map_role
    from app.cdm.models import BlockRole
    label = SimpleNamespace(value="some_future_label")
    assert _map_role(label) == BlockRole.OTHER


def test_mint_block_id_format():
    from app.cdm.adapters.docling import _mint_block_id
    result = _mint_block_id("doc-abc", page_index=2, reading_order=7)
    assert result == "doc-abc:p2:b7"


# ── Task 3: DoclingAdapter.adapt() tests ──────────────────────────────────────

from app.cdm.adapters.base import SourceMeta
from app.cdm.models import BlockRole, ParsedDocument

_META = SourceMeta(
    source_document_id="test-src-id",
    parse_run_id="test-run-id",
    filename="sample.pdf",
    sha256="a" * 64,
)


@pytest.fixture
def simple_doc():
    items = [
        _fake_text_item("Annual Report", label_value="title"),
        _fake_text_item("Introduction", label_value="section_header"),
        _fake_text_item("This is body text.", label_value="text"),
        _fake_table_item(),
    ]
    return _make_fake_doc(items)


@pytest.fixture
def adapted(simple_doc):
    from app.cdm.adapters.docling import DoclingAdapter
    return DoclingAdapter().adapt(simple_doc, _META)


def test_page_count_matches_pages(adapted):
    assert adapted.page_count == len(adapted.pages)


def test_block_page_indexes_valid(adapted):
    for block in adapted.blocks:
        assert 0 <= block.page_index < adapted.page_count, (
            f"Block {block.id} has out-of-range page_index={block.page_index}"
        )


def test_all_bboxes_normalized(adapted):
    for block in adapted.blocks:
        if block.bbox:
            assert 0.0 <= block.bbox.x0 <= block.bbox.x1 <= 1.0
            assert 0.0 <= block.bbox.y0 <= block.bbox.y1 <= 1.0


def test_table_block_has_table(adapted):
    table_blocks = [b for b in adapted.blocks if b.role == BlockRole.TABLE]
    assert len(table_blocks) == 1
    assert table_blocks[0].table is not None
    assert table_blocks[0].table.cells[0].text == "Header"
    assert table_blocks[0].table.cells[0].is_header is True


def test_page_block_ids_reference_existing_blocks(adapted):
    all_ids = {b.id for b in adapted.blocks}
    for page in adapted.pages:
        for bid in page.block_ids:
            assert bid in all_ids


def test_block_ids_use_minted_scheme(adapted):
    for block in adapted.blocks:
        assert block.id.startswith(_META.source_document_id)


def test_full_markdown_non_empty(adapted):
    assert adapted.full_markdown and len(adapted.full_markdown) > 0


def test_source_ids_wired(adapted):
    assert adapted.source_document_id == _META.source_document_id
    assert adapted.parse_run_id == _META.parse_run_id


def test_round_trip_serialization(adapted):
    serialised = adapted.model_dump_json()
    restored = ParsedDocument.model_validate_json(serialised)
    assert restored == adapted


def test_page_offset_shifts_page_indexes(simple_doc):
    from app.cdm.adapters.docling import DoclingAdapter
    doc = DoclingAdapter().adapt(simple_doc, _META, page_offset=5)
    for block in doc.blocks:
        assert block.page_index >= 5
    for page in doc.pages:
        assert page.index >= 5


def test_items_without_prov_are_skipped():
    from app.cdm.adapters.docling import DoclingAdapter
    no_prov_item = SimpleNamespace(
        label=SimpleNamespace(value="text"),
        text="orphan",
        prov=[],
        export_to_markdown=lambda: "orphan",
    )
    doc = _make_fake_doc([no_prov_item])
    result = DoclingAdapter().adapt(doc, _META)
    assert len(result.blocks) == 0
