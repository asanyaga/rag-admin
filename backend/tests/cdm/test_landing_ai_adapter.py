"""Unit tests for LandingAIAdapter using a hand-crafted minimal fixture."""
from __future__ import annotations

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.landing_ai import LandingAIAdapter
from app.cdm.models import BlockRole, ParsedDocument, ParserKind


SOURCE_DOC_ID = "src-0000"
PARSE_RUN_ID = "run-0000"

_META = SourceMeta(
    source_document_id=SOURCE_DOC_ID,
    parse_run_id=PARSE_RUN_ID,
    filename="test.jpg",
    sha256="a" * 64,
)

MINIMAL_RAW = {
    "chunks": [
        {
            "id": "chunk-uuid-1",
            "type": "text",
            "markdown": "Hello world.",
            "grounding": {
                "page": 0,
                "box": {"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.2},
            },
        },
        {
            "id": "chunk-uuid-2",
            "type": "table",
            "markdown": (
                "<table id='page-0'>"
                "<tr><th id='r0c0'>Name</th><th id='r0c1'>Value</th></tr>"
                "<tr><td id='r1c0'>Alpha</td><td id='r1c1'>1</td></tr>"
                "</table>"
            ),
            "grounding": {
                "page": 0,
                "box": {"left": 0.1, "top": 0.3, "right": 0.9, "bottom": 0.8},
            },
        },
    ],
    "markdown": "Hello world.\n\n<!-- PAGE BREAK -->\n",
    "metadata": {
        "filename": "test.jpg",
        "page_count": 1,
        "duration_ms": 800,
        "credit_usage": 0.5,
        "job_id": "job-abc",
        "version": "dpt-2-latest",
        "failed_pages": [],
    },
    "splits": [{"class_": "full", "pages": [0]}],
    "grounding": {
        "chunk-uuid-1": {
            "type": "chunkText",
            "confidence": 0.97,
            "low_confidence_spans": [],
        },
        "chunk-uuid-2": {
            "type": "chunkTable",
            "confidence": 0.92,
            "low_confidence_spans": [],
        },
        "r0c0": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 0, "col": 0, "rowspan": 1, "colspan": 1}, "confidence": 0.95},
        "r0c1": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 0, "col": 1, "rowspan": 1, "colspan": 1}, "confidence": 0.94},
        "r1c0": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 1, "col": 0, "rowspan": 1, "colspan": 1}, "confidence": 0.93},
        "r1c1": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 1, "col": 1, "rowspan": 1, "colspan": 1}, "confidence": 0.91},
    },
}


@pytest.fixture
def doc() -> ParsedDocument:
    return LandingAIAdapter().adapt(MINIMAL_RAW, _META)


def test_ids_are_deterministic(doc):
    for block in doc.blocks:
        assert block.id.startswith(SOURCE_DOC_ID)


def test_provider_uuid_in_extras(doc):
    assert doc.blocks[0].parser_extras["landing_ai_chunk_id"] == "chunk-uuid-1"


def test_page_indexing_zero_based(doc):
    for block in doc.blocks:
        assert block.page_index == 0


def test_bbox_normalized(doc):
    for block in doc.blocks:
        if block.bbox:
            assert 0.0 <= block.bbox.x0 <= block.bbox.x1 <= 1.0
            assert 0.0 <= block.bbox.y0 <= block.bbox.y1 <= 1.0


def test_block_roles(doc):
    roles = {b.role for b in doc.blocks}
    assert BlockRole.PARAGRAPH in roles
    assert BlockRole.TABLE in roles


def test_table_cells_parsed(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    assert table_block.table is not None
    assert len(table_block.table.cells) == 4
    texts = {c.text for c in table_block.table.cells}
    assert "Name" in texts
    assert "Alpha" in texts


def test_table_cell_header_flag(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    headers = [c for c in table_block.table.cells if c.is_header]
    assert len(headers) == 2


def test_table_html_preserved(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    assert table_block.table.html is not None
    assert "<table" in table_block.table.html


def test_quality_from_grounding(doc):
    text_block = next(b for b in doc.blocks if b.role == BlockRole.PARAGRAPH)
    assert text_block.quality is not None
    assert text_block.quality.confidence == pytest.approx(0.97)


def test_full_markdown_populated(doc):
    assert doc.full_markdown is not None
    assert len(doc.full_markdown) > 0


def test_splits_in_parser_extras(doc):
    assert "landing_ai_splits" in doc.parser_extras


def test_page_count(doc):
    assert doc.page_count == 1
    assert len(doc.pages) == 1


def test_page_block_ids_consistent(doc):
    all_block_ids = {b.id for b in doc.blocks}
    for page in doc.pages:
        for bid in page.block_ids:
            assert bid in all_block_ids


def test_source_ids_wired(doc):
    assert doc.source_document_id == SOURCE_DOC_ID
    assert doc.parse_run_id == PARSE_RUN_ID


def test_round_trip(doc):
    assert ParsedDocument.model_validate_json(doc.model_dump_json()) == doc
