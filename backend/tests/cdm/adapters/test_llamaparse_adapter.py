import pytest

from app.cdm.adapters.llamaparse import (
    _map_role,
    _pdf_points_to_normalized,
    _union_bbox,
)
from app.cdm.models import BBox, BlockRole


def test_pdf_points_to_normalized_basic():
    bbox = _pdf_points_to_normalized(x=10, y=20, w=30, h=40,
                                      page_width=100, page_height=200)
    assert bbox.x0 == pytest.approx(0.10)
    assert bbox.y0 == pytest.approx(0.10)
    assert bbox.x1 == pytest.approx(0.40)
    assert bbox.y1 == pytest.approx(0.30)
    assert bbox.source_space == "pdf_points"
    assert bbox.source_coords == (10.0, 20.0, 30.0, 40.0)


def test_pdf_points_clamps_to_unit_square():
    bbox = _pdf_points_to_normalized(x=0, y=0, w=101, h=201,
                                      page_width=100, page_height=200)
    assert bbox.x0 == 0.0
    assert bbox.y0 == 0.0
    assert bbox.x1 == 1.0
    assert bbox.y1 == 1.0


def test_union_bbox_single():
    b = BBox(x0=0.1, y0=0.2, x1=0.5, y1=0.6)
    assert _union_bbox([b]) == b


def test_union_bbox_multiple():
    b1 = BBox(x0=0.1, y0=0.2, x1=0.4, y1=0.5)
    b2 = BBox(x0=0.2, y0=0.1, x1=0.6, y1=0.4)
    u = _union_bbox([b1, b2])
    assert u.x0 == pytest.approx(0.1)
    assert u.y0 == pytest.approx(0.1)
    assert u.x1 == pytest.approx(0.6)
    assert u.y1 == pytest.approx(0.5)


def test_union_bbox_empty_returns_none():
    assert _union_bbox([]) is None


@pytest.mark.parametrize("llama_type,expected_role", [
    ("heading", BlockRole.HEADING),
    ("text", BlockRole.PARAGRAPH),
    ("list", BlockRole.LIST),
    ("table", BlockRole.TABLE),
    ("image", BlockRole.FIGURE),
    ("header", BlockRole.HEADER),
    ("footer", BlockRole.FOOTER),
    ("code", BlockRole.CODE),
    ("link", BlockRole.LINK),
    ("mystery", BlockRole.OTHER),
])
def test_map_role(llama_type, expected_role):
    assert _map_role(llama_type) == expected_role


from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.llamaparse import LlamaParseAdapter
from app.cdm.models import ParserKind


MINIMAL_RAW = {
    "text": "Title\n\nBody paragraph.",
    "markdown": "# Title\n\nBody paragraph.",
    "items": {
        "pages": [
            {
                "page_number": 1,
                "page_width": 100.0,
                "page_height": 200.0,
                "items": [
                    {
                        "type": "heading",
                        "level": 1,
                        "value": "Title",
                        "md": "# Title",
                        "bbox": [
                            {"x": 10, "y": 10, "w": 30, "h": 10,
                             "confidence": 0.98, "label": "paragraph_title"},
                        ],
                    },
                    {
                        "type": "text",
                        "value": "Body paragraph.",
                        "md": "Body paragraph.",
                        "bbox": [
                            {"x": 10, "y": 30, "w": 80, "h": 20,
                             "confidence": 0.95, "label": "text"},
                        ],
                    },
                ],
            }
        ]
    },
    "metadata": {"pages": [{"page_number": 1, "confidence": 0.97,
                            "original_orientation_angle": 0}]},
    "job_metadata": {
        "job_id": "job-abc",
        "pdf-inputTokens": 100,
        "pdf-outputTokens": 50,
        "pdf-llmTime": 1500,
    },
}


def test_adapter_parser_kind():
    assert LlamaParseAdapter.parser == ParserKind.LLAMAPARSE


def test_adapter_produces_page_count_and_indexing():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.pages[0].index == 0
    assert doc.pages[0].parser_extras["source_page_number"] == 1


def test_adapter_produces_blocks_with_normalized_bboxes():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert len(doc.blocks) == 2
    heading, body = doc.blocks
    assert heading.role.value == "heading"
    assert heading.native_type == "heading"
    assert heading.native_label == "paragraph_title"
    assert heading.page_index == 0
    assert 0.0 <= heading.bbox.x0 <= heading.bbox.x1 <= 1.0
    assert heading.markdown == "# Title"
    assert heading.text == "Title"
    assert body.role.value == "paragraph"


def test_adapter_populates_quality_from_confidence():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert doc.blocks[0].quality.confidence == 0.98
    assert doc.pages[0].quality.confidence == 0.97


def test_adapter_builds_full_text_and_markdown():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert "Title" in doc.full_text
    assert "# Title" in doc.full_markdown


def test_adapter_block_ids_are_deterministic():
    doc1 = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    doc2 = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-2"),
    )
    assert [b.id for b in doc1.blocks] == [b.id for b in doc2.blocks]


def test_adapter_wires_source_and_run_ids():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-7"),
    )
    assert doc.source_document_id == "src-1"
    assert doc.parse_run_id == "run-7"


def test_adapter_page_block_ids_in_reading_order():
    doc = LlamaParseAdapter().adapt(
        MINIMAL_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert doc.pages[0].block_ids == [b.id for b in doc.blocks]


# ---------------------------------------------------------------------------
# Table text extraction
# ---------------------------------------------------------------------------

_TABLE_RAW = {
    "items": {
        "pages": [
            {
                "page_number": 1,
                "page_width": 100.0,
                "page_height": 200.0,
                "items": [
                    {
                        "type": "table",
                        "value": "",  # LlamaParse always leaves this empty for tables
                        "md": "| Name | Date |\n| --- | --- |\n| Alice | 2024-01-01 |\n| Bob | 2024-06-01 |",
                        "bbox": [{"x": 0, "y": 0, "w": 100, "h": 50}],
                    },
                ],
            }
        ]
    },
}


def test_adapter_table_text_populated_from_markdown():
    """Table blocks have empty 'value'; Block.text must be built from 'md'."""
    doc = LlamaParseAdapter().adapt(
        _TABLE_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    block = doc.blocks[0]
    assert block.role == BlockRole.TABLE
    assert block.markdown == "| Name | Date |\n| --- | --- |\n| Alice | 2024-01-01 |\n| Bob | 2024-06-01 |"
    assert "Name" in block.text
    assert "Date" in block.text
    assert "Alice" in block.text
    assert "Bob" in block.text
    assert "2024-01-01" in block.text


def test_adapter_table_text_excludes_separator_rows():
    """Markdown separator rows (| --- |) must not appear in Block.text."""
    doc = LlamaParseAdapter().adapt(
        _TABLE_RAW,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    assert "---" not in doc.blocks[0].text


def test_adapter_table_text_strips_html_br_tags():
    """<br/> within table cells must be replaced so text is clean."""
    raw = {
        "items": {
            "pages": [
                {
                    "page_number": 1,
                    "page_width": 100.0,
                    "page_height": 200.0,
                    "items": [
                        {
                            "type": "table",
                            "value": "",
                            "md": "| Note | 2024<br/>KShs 000 |\n| --- | --- |\n| Revenue | 100 |",
                            "bbox": [{"x": 0, "y": 0, "w": 100, "h": 50}],
                        },
                    ],
                }
            ]
        },
    }
    doc = LlamaParseAdapter().adapt(
        raw,
        SourceMeta(source_document_id="src-1", parse_run_id="run-1"),
    )
    block = doc.blocks[0]
    assert "<br/>" not in block.text
    assert "KShs 000" in block.text
