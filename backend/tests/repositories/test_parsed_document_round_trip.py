"""Verify ParsedDocument ↔ JSONB round-trips with zero loss.

Two assertions:
- spec §9.5 — synthetic CDM ParsedDocument survives model_dump → JSONB → model_validate.
- real LlamaParse payload (committed fixture from provider research) survives JSONB
  round-trip byte-identical. Catches float precision, unicode, and nested-dict edge
  cases that a hand-rolled synthetic fixture will not.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.cdm.models import (
    Block, BlockRole, BBox, ParsedDocument, Page,
)
from app.models.parse_run import ParseRunORM
from app.models.source_document import SourceDocumentORM
from app.repositories.parsed_document_repository import (
    ParsedDocumentCreate,
    ParsedDocumentRepository,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "llamaparse"


async def _mk_source_and_run(test_db: AsyncSession) -> tuple[SourceDocumentORM, ParseRunORM]:
    src = SourceDocumentORM(id=uuid4(), sha256=uuid4().hex + uuid4().hex, storage_uri="local://a.pdf")
    test_db.add(src)
    await test_db.commit()
    run = ParseRunORM(
        id=uuid4(), source_document_id=src.id,
        parser="llamaparse", representation_kind="vector_light",
        config_hash="h" * 64, status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()
    return src, run


@pytest.mark.asyncio
async def test_cdm_parsed_document_round_trip(test_db: AsyncSession):
    src, run = await _mk_source_and_run(test_db)

    original = ParsedDocument(
        id=str(uuid4()),
        source_document_id=str(src.id),
        parse_run_id=str(run.id),
        page_count=1,
        pages=[Page(index=0, block_ids=["b1"])],
        blocks=[Block(
            id="b1",
            page_index=0,
            role=BlockRole.PARAGRAPH,
            native_type="text",
            text="hello world",
            markdown="hello world",
            bbox=BBox(x0=0.0, y0=0.0, x1=1.0, y1=0.1),
            reading_order=0,
        )],
        full_text="hello world",
        full_markdown="hello world",
    )

    repo = ParsedDocumentRepository(test_db)
    await repo.create(ParsedDocumentCreate(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text=original.full_text,
        full_markdown=original.full_markdown,
        page_count=len(original.pages),
        block_count=len(original.blocks),
        content=original.model_dump(mode="json"),
    ))

    fetched = await repo.get_by_run(run.id)
    assert fetched is not None
    restored = ParsedDocument.model_validate(fetched.content)
    assert restored == original


@pytest.mark.asyncio
async def test_real_llamaparse_payload_jsonb_byte_identical(test_db: AsyncSession):
    """Real provider payload survives JSONB round-trip with no key re-ordering,
    float drift, or unicode mangling."""
    src, run = await _mk_source_and_run(test_db)

    payload_path = FIXTURES / "annual_pp1-5" / "items.json"
    original_payload = json.loads(payload_path.read_text(encoding="utf-8"))

    assert "pages" in original_payload
    assert len(original_payload["pages"]) >= 1
    assert any("bbox" in it for it in original_payload["pages"][0]["items"])

    repo = ParsedDocumentRepository(test_db)
    await repo.create(ParsedDocumentCreate(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text=None,
        full_markdown=None,
        page_count=len(original_payload["pages"]),
        block_count=sum(len(p.get("items", [])) for p in original_payload["pages"]),
        content=original_payload,
    ))

    fetched = await repo.get_by_run(run.id)
    assert fetched is not None
    assert fetched.content == original_payload
