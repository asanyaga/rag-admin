"""Tests for result-transforms API endpoints."""
import pytest
from httpx import AsyncClient


async def create_user_and_login(client: AsyncClient, email: str = "transform@test.com") -> str:
    """Helper to create a user and return access token."""
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Test",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_catalog_lists_merge_records(client):
    token = await create_user_and_login(client)
    resp = await client.get(
        "/api/v1/result-transforms/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(t["transform_type"] == "merge_records" for t in data)


@pytest.mark.asyncio
async def test_catalog_requires_auth(client):
    resp = await client.get("/api/v1/result-transforms/catalog")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_preview_returns_rows_and_flags(client, test_db):
    """Preview should run a merge_records transform and return rows + flags."""
    from uuid import uuid4
    from app.models.extraction_result import ExtractionResult, ExtractionResultStatus

    token = await create_user_and_login(client)

    # Seed an extraction result directly in the DB
    result = ExtractionResult(
        document_id=uuid4(),
        extraction_schema_id=uuid4(),
        schema_definition_snapshot={},
        extraction_method="llm",
        created_by=uuid4(),
        status=ExtractionResultStatus.completed,
        structured_data={
            "records": [
                {"Name": "Alice", "Score": "10"},
                {"Name": "Alice", "Score": "20"},
            ]
        },
    )
    test_db.add(result)
    await test_db.commit()
    await test_db.refresh(result)

    resp = await client.post(
        f"/api/v1/projects/{uuid4()}/result-transforms/preview",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sourceResultIds": [str(result.id)],
            "transformType": "merge_records",
            "config": {
                "groupBy": ["Name"],
                "spine": {"whereFieldsPresent": ["Score"]},
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body
    assert "flags" in body


@pytest.mark.asyncio
async def test_apply_persists_derived_result(client, test_db):
    """Apply should run the transform and persist a new ExtractionResult."""
    from uuid import uuid4
    from app.models.extraction_result import ExtractionResult, ExtractionResultStatus

    token = await create_user_and_login(client, email="apply@test.com")

    result = ExtractionResult(
        document_id=uuid4(),
        extraction_schema_id=uuid4(),
        schema_definition_snapshot={},
        extraction_method="llm",
        created_by=uuid4(),
        status=ExtractionResultStatus.completed,
        structured_data={
            "records": [
                {"Name": "Bob", "Value": "5"},
            ]
        },
    )
    test_db.add(result)
    await test_db.commit()
    await test_db.refresh(result)

    resp = await client.post(
        f"/api/v1/projects/{uuid4()}/result-transforms/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sourceResultIds": [str(result.id)],
            "transformType": "merge_records",
            "config": {
                "groupBy": ["Name"],
                "spine": {"whereFieldsPresent": ["Value"]},
            },
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] != str(result.id)  # a new result was created
    assert body["extractionMethod"] == "transform"
