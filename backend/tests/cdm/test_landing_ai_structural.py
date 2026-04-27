"""Structural invariant tests for LandingAIAdapter against the real cleanshelf fixture.

These tests run offline — the fixture is committed JSON, no API call required.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.landing_ai import LandingAIAdapter
from app.cdm.models import ParsedDocument

FIXTURE = Path(__file__).parent.parent.parent / "app" / "cdm" / "eval" / "fixtures" / "landing_ai_cleanshelf.json"
SNAPSHOT = FIXTURE.with_name("landing_ai_cleanshelf.expected.json")

_META = SourceMeta(
    source_document_id="structural-test-src",
    parse_run_id="structural-test-run",
    filename="cleanshelf-12-4-26.jpg",
    sha256="0" * 64,
)


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc(raw) -> ParsedDocument:
    return LandingAIAdapter().adapt(raw, _META)


def test_page_count_matches_pages(doc):
    assert doc.page_count == len(doc.pages)


def test_all_block_page_indexes_valid(doc):
    for block in doc.blocks:
        assert 0 <= block.page_index < doc.page_count, (
            f"Block {block.id} has page_index={block.page_index}, "
            f"page_count={doc.page_count}"
        )


def test_all_bboxes_normalized(doc):
    for block in doc.blocks:
        if block.bbox:
            assert 0.0 <= block.bbox.x0 <= block.bbox.x1 <= 1.0, f"x out of range: {block.bbox}"
            assert 0.0 <= block.bbox.y0 <= block.bbox.y1 <= 1.0, f"y out of range: {block.bbox}"
        if block.table:
            for cell in block.table.cells:
                if cell.bbox:
                    assert 0.0 <= cell.bbox.x0 <= cell.bbox.x1 <= 1.0
                    assert 0.0 <= cell.bbox.y0 <= cell.bbox.y1 <= 1.0


def test_all_blocks_have_role_and_native_type(doc):
    for block in doc.blocks:
        assert block.role is not None
        assert block.native_type


def test_page_block_ids_reference_existing_blocks(doc):
    all_ids = {b.id for b in doc.blocks}
    for page in doc.pages:
        for bid in page.block_ids:
            assert bid in all_ids, f"Page {page.index} references unknown block_id {bid}"


def test_full_markdown_non_empty(doc):
    assert doc.full_markdown and len(doc.full_markdown) > 0


def test_source_ids_wired(doc):
    assert doc.source_document_id == _META.source_document_id
    assert doc.parse_run_id == _META.parse_run_id


def test_round_trip(doc):
    serialised = doc.model_dump_json()
    restored = ParsedDocument.model_validate_json(serialised)
    assert restored == doc


def test_deterministic_block_ids(doc, raw):
    # IDs must NOT be the provider's UUIDs — they must use the minted scheme
    for block in doc.blocks:
        assert block.id.startswith(_META.source_document_id), (
            f"Block ID {block.id!r} does not start with source_document_id"
        )
        # Provider UUID should be in parser_extras, not the block ID
        assert "landing_ai_chunk_id" in block.parser_extras


def test_snapshot(doc):
    """Fail if adapter output changes unexpectedly. Update snapshot intentionally."""
    current = doc.model_dump_json(indent=2)
    if not SNAPSHOT.exists():
        SNAPSHOT.write_text(current, encoding="utf-8")
        pytest.skip("Snapshot created — run again to verify")
    expected = SNAPSHOT.read_text(encoding="utf-8")
    # Strip the top-level id (UUID) before comparing — it's random per run
    import json as _json
    cur_dict = _json.loads(current)
    exp_dict = _json.loads(expected)
    cur_dict.pop("id", None)
    exp_dict.pop("id", None)
    assert cur_dict == exp_dict, (
        "Adapter output changed. If intentional, delete the snapshot and re-run."
    )
