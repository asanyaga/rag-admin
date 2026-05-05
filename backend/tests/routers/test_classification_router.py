"""Tests for GET /classification-runs/{run_id}/blocks."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.classification_region import ClassificationRegion as ClassificationRegionORM
from app.models.classification_run import ClassificationRun as ClassificationRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Test User",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_get_blocks_404(client: AsyncClient, test_db: AsyncSession) -> None:
    token = await _signup_and_login(client, "blocks404@test.com")
    resp = await client.get(
        f"/api/v1/classification-runs/{uuid4()}/blocks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_blocks_returns_annotated_list(
    client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    token = await _signup_and_login(client, "blocks200@test.com")

    parse_run_id = uuid4()
    source_doc_id = uuid4()

    pd = ParsedDocumentORM(
        parse_run_id=parse_run_id,
        source_document_id=source_doc_id,
        full_text=None,
        full_markdown=None,
        page_count=1,
        block_count=2,
        content={
            "id": "doc-router-test",
            "source_document_id": str(source_doc_id),
            "parse_run_id": str(parse_run_id),
            "page_count": 1,
            "pages": [{"index": 0}],
            "blocks": [
                {"id": "b-1", "role": "paragraph", "native_type": "paragraph", "text": "Foo", "page_index": 0},
                {"id": "b-2", "role": "paragraph", "native_type": "paragraph", "text": "Bar", "page_index": 0},
            ],
        },
    )
    test_db.add(pd)
    await test_db.commit()

    run = ClassificationRunORM(
        parse_run_id=parse_run_id,
        document_id=uuid4(),
        labels_requested=["section_a"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
        status="completed",
    )
    test_db.add(run)
    await test_db.commit()
    await test_db.refresh(run)

    region = ClassificationRegionORM(
        run_id=run.id,
        label="section_a",
        page_start=0,
        page_end=0,
        block_ids=["b-1"],
        source="llm",
    )
    test_db.add(region)
    await test_db.commit()

    resp = await client.get(
        f"/api/v1/classification-runs/{run.id}/blocks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["blockId"] == "b-1"
    assert data[0]["label"] == "section_a"
    assert data[0]["role"] == "paragraph"
    assert data[0]["text"] == "Foo"
    assert data[0]["pageIndex"] == 0
    assert data[1]["blockId"] == "b-2"
    assert data[1]["label"] is None
