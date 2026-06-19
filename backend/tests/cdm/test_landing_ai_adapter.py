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


# ---------------------------------------------------------------------------
# Gap-fix tests
# ---------------------------------------------------------------------------

def test_table_markdown_preserved(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    assert table_block.table is not None
    assert table_block.table.markdown is not None
    assert "<table" in table_block.table.markdown


def test_full_text_populated(doc):
    assert doc.full_text is not None
    assert len(doc.full_text) > 0
    assert "Hello world." in doc.full_text


def test_block_id_full_format(doc):
    first_block = doc.blocks[0]
    assert first_block.id == "src-0000:p0:b0"


def test_native_type_logo():
    raw = {
        "chunks": [
            {
                "id": "chunk-logo-1",
                "type": "logo",
                "markdown": "![logo](logo.png)",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 0.1, "bottom": 0.1}},
            },
            {
                "id": "chunk-attest-1",
                "type": "attestation",
                "markdown": "Attestation text",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.2, "right": 0.5, "bottom": 0.3}},
            },
            {
                "id": "chunk-scan-1",
                "type": "scan_code",
                "markdown": "![qr](qr.png)",
                "grounding": {"page": 0, "box": {"left": 0.5, "top": 0.2, "right": 0.6, "bottom": 0.3}},
            },
        ],
        "markdown": None,
        "metadata": {},
        "splits": [],
        "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    native_types = {b.native_type for b in doc.blocks}
    assert "logo" in native_types
    assert "attestation" in native_types
    assert "scan_code" in native_types
    logo_block = next(b for b in doc.blocks if b.native_type == "logo")
    assert logo_block.native_type == "logo"
    attest_block = next(b for b in doc.blocks if b.native_type == "attestation")
    assert attest_block.native_type == "attestation"
    scan_block = next(b for b in doc.blocks if b.native_type == "scan_code")
    assert scan_block.native_type == "scan_code"


def test_cell_quality_confidence(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    assert table_block.table is not None
    cells_by_id = {}
    # Map cells by (row, col) to expected confidences from MINIMAL_RAW grounding
    # r0c0 → 0.95, r0c1 → 0.94, r1c0 → 0.93, r1c1 → 0.91
    expected = {
        (0, 0): pytest.approx(0.95),
        (0, 1): pytest.approx(0.94),
        (1, 0): pytest.approx(0.93),
        (1, 1): pytest.approx(0.91),
    }
    for cell in table_block.table.cells:
        key = (cell.row, cell.col)
        if key in expected:
            assert cell.quality is not None, f"Cell {key} has no quality"
            assert cell.quality.confidence == expected[key], f"Cell {key} confidence mismatch"


def test_low_confidence_spans():
    raw = {
        "chunks": [
            {
                "id": "chunk-lcs-1",
                "type": "text",
                "markdown": "Some uncertain text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None,
        "metadata": {},
        "splits": [],
        "grounding": {
            "chunk-lcs-1": {
                "type": "chunkText",
                "confidence": 0.70,
                "low_confidence_spans": [[0, 4], [10, 19]],
            },
        },
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    block = doc.blocks[0]
    assert block.quality is not None
    assert block.quality.low_confidence_spans == [(0, 4), (10, 19)]


# ---------------------------------------------------------------------------
# _detect_text_role unit tests
# ---------------------------------------------------------------------------
from app.cdm.adapters.landing_ai import _detect_text_role


def test_detect_plain_text_is_paragraph():
    assert _detect_text_role("Hello world.") == BlockRole.PARAGRAPH


def test_detect_anchor_then_plain_text_is_paragraph():
    assert _detect_text_role("<a id='x'></a>\n\nPlain paragraph.") == BlockRole.PARAGRAPH


def test_detect_h1_is_title():
    assert _detect_text_role("<a id='x'></a>\n\n# Main Title") == BlockRole.TITLE


def test_detect_h1_with_body_is_title():
    # heading + body text in one chunk — role is determined by the first content line
    assert _detect_text_role("<a id='x'></a>\n\n# Main Title\n\nBody text here.") == BlockRole.TITLE


def test_detect_h2_is_heading():
    assert _detect_text_role("<a id='x'></a>\n\n## Section") == BlockRole.HEADING


def test_detect_h3_is_heading():
    assert _detect_text_role("<a id='x'></a>\n\n### Subsection\n\nContent.") == BlockRole.HEADING


def test_detect_h4_is_heading():
    assert _detect_text_role("#### Deep heading") == BlockRole.HEADING


def test_detect_hash_without_space_is_paragraph():
    # ##NoSpace is not a valid ATX heading; treat as paragraph
    assert _detect_text_role("##NoSpace") == BlockRole.PARAGRAPH


def test_detect_empty_markdown_is_paragraph():
    assert _detect_text_role("") == BlockRole.PARAGRAPH


def test_detect_anchor_only_is_paragraph():
    assert _detect_text_role("<a id='x'></a>\n\n") == BlockRole.PARAGRAPH


# ---------------------------------------------------------------------------
# Heading role integration tests
# ---------------------------------------------------------------------------

def test_h1_chunk_gets_title_role():
    raw = {
        "chunks": [
            {
                "id": "chunk-title",
                "type": "text",
                "markdown": "<a id='chunk-title'></a>\n\n# Main Title\n\nIntro text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    assert doc.blocks[0].role == BlockRole.TITLE


def test_h2_chunk_gets_heading_role():
    raw = {
        "chunks": [
            {
                "id": "chunk-h2",
                "type": "text",
                "markdown": "<a id='chunk-h2'></a>\n\n## Section Heading",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    assert doc.blocks[0].role == BlockRole.HEADING


def test_plain_text_chunk_remains_paragraph():
    raw = {
        "chunks": [
            {
                "id": "chunk-para",
                "type": "text",
                "markdown": "<a id='chunk-para'></a>\n\nPlain paragraph text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    assert doc.blocks[0].role == BlockRole.PARAGRAPH


def test_mixed_roles_across_chunks():
    raw = {
        "chunks": [
            {
                "id": "c-title",
                "type": "text",
                "markdown": "<a id='c-title'></a>\n\n# Document Title",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.05}},
            },
            {
                "id": "c-h2",
                "type": "text",
                "markdown": "<a id='c-h2'></a>\n\n## Chapter One",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.1, "right": 1.0, "bottom": 0.15}},
            },
            {
                "id": "c-h3",
                "type": "text",
                "markdown": "<a id='c-h3'></a>\n\n### 1.1 Background\n\nSome body text.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.2, "right": 1.0, "bottom": 0.3}},
            },
            {
                "id": "c-para",
                "type": "text",
                "markdown": "No anchor, no heading.",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.3, "right": 1.0, "bottom": 0.4}},
            },
        ],
        "markdown": None, "metadata": {}, "splits": [], "grounding": {},
    }
    doc = LandingAIAdapter().adapt(raw, _META)
    by_id = {b.parser_extras["landing_ai_chunk_id"]: b for b in doc.blocks}
    assert by_id["c-title"].role == BlockRole.TITLE
    assert by_id["c-h2"].role == BlockRole.HEADING
    assert by_id["c-h3"].role == BlockRole.HEADING
    assert by_id["c-para"].role == BlockRole.PARAGRAPH
