"""PR A is a behaviour-preserving refactor.

`ParsedDocument` must be equivalent to the pre-refactor pipeline for any config
expressible under the old contract. `ParseRun.raw_payload` is exempt — its shape
changes on purpose ("tools" -> "instances"), because it is an audit artifact,
not part of `ParsedDocument`.
"""
from datetime import datetime, timezone

import fitz
import pytest

from app.cdm.models import BlockRole
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline


def _source() -> SourceDocument:
    return SourceDocument(
        id="src-1",
        sha256="b" * 64,
        filename="equiv.pdf",
        mime_type="application/pdf",
        byte_size=1234,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def ruled_table_pdf(tmp_path):
    """Text plus a ruled grid, so both layout_analysis and table_detection fire."""
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Quarterly revenue report", fontsize=14)
    page.insert_text(fitz.Point(72, 92), "Figures are provisional.", fontsize=10)
    col_x, row_y = [72, 236, 400], [200, 250, 300]
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), width=1)
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), width=1)
    page.insert_text(fitz.Point(80, 235), "Name", fontsize=11)
    page.insert_text(fitz.Point(244, 235), "Value", fontsize=11)
    page.insert_text(fitz.Point(80, 285), "alpha", fontsize=11)
    page.insert_text(fitz.Point(244, 285), "1", fontsize=11)
    path = tmp_path / "equiv.pdf"
    d.save(str(path)); d.close()
    return path


@pytest.mark.asyncio
async def test_text_only_pipeline_output_is_stable(ruled_table_pdf):
    run, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(ruled_table_pdf),
        representation_kind="extract_rich",
        config={"tools": {"fitz": {"tool": "fitz", "config": {}}},
                "capabilities": {"layout_analysis": "fitz"}},
        client=None,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    assert parsed.page_count == 1
    assert "Quarterly revenue report" in parsed.full_text

    # Reading order is contiguous from 0 on every page (unchanged (y0, x0) sort).
    orders = [b.reading_order for b in parsed.blocks if b.page_index == 0]
    assert orders == list(range(len(orders)))

    # Block ids follow the documented "<source>:<page>:<order>" scheme.
    assert parsed.blocks[0].id == "src-1:0:0"
    assert all(b.id.startswith("src-1:") for b in parsed.blocks)


@pytest.mark.asyncio
async def test_table_tool_evicts_overlapping_text_exactly_as_before(ruled_table_pdf):
    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "tbl": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"layout_analysis": "fitz", "table_detection": "tbl"},
    }
    run, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(ruled_table_pdf),
        representation_kind="extract_rich", config=config, client=None,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    assert any(b.role == BlockRole.TABLE for b in parsed.blocks)

    # The table won over the text it covers — same rule, same 0.5 threshold.
    assert run.raw_payload["evicted"], "expected the table to evict covered text"
    for rec in run.raw_payload["evicted"]:
        assert rec["capability"] == "layout_analysis"
        assert rec["winner_capability"] == "table_detection"
        assert rec["reason"] == "covered_by"
        assert rec["overlap_fraction"] > 0.5

    # The audit trail changed shape on purpose.
    assert "instances" in run.raw_payload and "tools" not in run.raw_payload


@pytest.mark.asyncio
async def test_table_tool_does_not_change_the_surviving_text(ruled_table_pdf):
    """Adding table_detection must only remove text the table covers — never
    alter the text blocks that survive."""
    base = {"tools": {"fitz": {"tool": "fitz", "config": {}}},
            "capabilities": {"layout_analysis": "fitz"}}
    with_table = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "tbl": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"layout_analysis": "fitz", "table_detection": "tbl"},
    }
    _, text_only = await run_custom_pipeline(
        source=_source(), file_path=str(ruled_table_pdf),
        representation_kind="extract_rich", config=base, client=None)
    _, both = await run_custom_pipeline(
        source=_source(), file_path=str(ruled_table_pdf),
        representation_kind="extract_rich", config=with_table, client=None)

    surviving = {b.text for b in both.blocks if b.role == BlockRole.TEXT}
    original = {b.text for b in text_only.blocks if b.role == BlockRole.TEXT}
    assert surviving <= original
    assert "Quarterly revenue report" in " ".join(surviving)


# ── Golden snapshot: content-identical to the pre-refactor pipeline ──────────

import json
from pathlib import Path

from tests.cdm.adapters.custom_pipeline.fixtures.equivalence_fixtures import (
    EQUIV_CONFIGS, build_for, content_projection,
)

_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "equivalence"


def _relabel(config: dict) -> dict:
    """Rewrite the captured text_extraction key to layout_analysis."""
    caps = dict(config["capabilities"])
    caps["layout_analysis"] = caps.pop("text_extraction")
    return {**config, "capabilities": caps}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(EQUIV_CONFIGS))
async def test_output_matches_pre_refactor_golden(name, tmp_path):
    golden = json.loads((_GOLDEN_DIR / f"{name}.json").read_text())
    pdf = tmp_path / f"{name}.pdf"
    build_for(name, pdf)
    _, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(pdf),
        representation_kind="extract_rich",
        config=_relabel(EQUIV_CONFIGS[name]), client=None)
    assert content_projection(parsed) == golden
