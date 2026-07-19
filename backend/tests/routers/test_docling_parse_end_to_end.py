"""POST an upload, let the background task run, assert what got persisted.

Every docling bug on this branch so far lived at a seam between two layers whose
own tests passed: the from-source endpoint reading the wrong config field, the
router injecting `parser` into a config the runner rejected, normalization
emitting nulls the docling options builder could not take, and normalization
emitting stage options its own model refused. Unit tests on either side of each
seam were green throughout.

So this drives the whole chain — router validation, parse_cfg construction, the
background task, config normalization, hashing, the runner, the adapter, and
persistence — and only stubs docling's model inference. `to_pipeline_options()`
runs for real, since that is where two of the bugs surfaced.

Mutation-checked rather than assumed: reverting the `parser`-key fix fails 3 of
these, reverting the disabled-stage fix fails 1, and reverting the null handling
to the state that produced the reported error fails 4 — including the plain
default upload.

One fix is deliberately not pinned here. `_build_ocr_options` excluding None is
unreachable on any current path, because normalization strips nulls before the
runner sees them; reverting it alone leaves these green. It is defence for
direct `run_docling` callers, and `test_config_normalization.py::
test_an_explicit_null_is_treated_as_unspecified` is what guards it.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRun as ParseRunORM
from app.services.parsing.parsing_service import _compute_config_hash

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
FIXTURE = (Path(__file__).parents[1] / "cdm" / "adapters" / "fixtures"
           / "docling_simple_text.json")


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={
        "email": email, "password": "ValidPass123!",
        "password_confirm": "ValidPass123!", "full_name": "Test User",
    })
    resp = await client.post("/api/v1/auth/signin",
                             json={"email": email, "password": "ValidPass123!"})
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str) -> str:
    resp = await client.post("/api/v1/projects",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"name": "Docling E2E"})
    return resp.json()["id"]


def _docling_document():
    from docling_core.types.doc import DoclingDocument
    return DoclingDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


async def _upload_with_docling(client: AsyncClient, test_db: AsyncSession,
                               token: str, project_id: str, parse_config: dict):
    """Upload one PDF with parser_type=docling and wait for the parse to land.

    Only the docling call itself is faked: `_build_converter` so no models load,
    `_convert_batch` so no inference runs. Everything between the HTTP request
    and the persisted row is the real code path.
    """
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=test_db)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    doc = _docling_document()

    with (
        patch("app.database.AsyncSessionLocal", session_factory),
        patch("app.services.parsing.docling_runner._build_converter",
              MagicMock(return_value=MagicMock())),
        patch("app.services.parsing.docling_runner._convert_batch",
              MagicMock(return_value=doc)),
    ):
        from app.services.parsing import docling_runner
        docling_runner.clear_converter_cache()
        return await client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "project_id": project_id,
                "parser_type": "docling",
                "title": "E2E Doc",
                "parse_config": json.dumps(parse_config),
            },
            files=[("file", ("e2e.pdf", MINIMAL_PDF, "application/pdf"))],
        )


async def _the_run(test_db: AsyncSession) -> ParseRunORM:
    result = await test_db.execute(select(ParseRunORM))
    runs = list(result.scalars().all())
    assert len(runs) == 1, f"expected exactly one parse run, got {len(runs)}"
    return runs[0]


# ── The happy path, all the way through ──────────────────────────────────────

@pytest.mark.asyncio
async def test_default_docling_upload_parses_and_persists(
    client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client, "e2e1@example.com")
    project_id = await _create_project(client, token)

    resp = await _upload_with_docling(client, test_db, token, project_id, {})
    assert resp.status_code == 202, resp.text

    run = await _the_run(test_db)
    assert run.status == "succeeded", run.error
    assert run.parser == "docling"


@pytest.mark.asyncio
async def test_the_persisted_config_records_what_ran(
    client: AsyncClient, test_db: AsyncSession):
    """The original complaint: a defaulted run stored {"parser": "docling"} and
    said nothing about how the document was parsed."""
    token = await _signup_and_login(client, "e2e2@example.com")
    project_id = await _create_project(client, token)

    await _upload_with_docling(client, test_db, token, project_id, {})
    run = await _the_run(test_db)

    assert run.config["parser"] == "docling"
    assert run.config["pipeline"] == "standard"
    assert run.config["backend"] == "docling_parse_v4"
    assert run.config["layout_options"]["model"] == "docling_layout_heron"
    assert run.config["ocr_options"]["kind"] == "auto"
    assert run.config["table_structure_options"]["mode"] == "accurate"


@pytest.mark.asyncio
async def test_config_hash_describes_the_config_stored_beside_it(
    client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client, "e2e3@example.com")
    project_id = await _create_project(client, token)

    await _upload_with_docling(client, test_db, token, project_id, {})
    run = await _the_run(test_db)

    assert run.config_hash == _compute_config_hash(run.config)


# ── The shapes that broke ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disabling_ocr_parses_and_records_no_ocr_options(
    client: AsyncClient, test_db: AsyncSession):
    """Normalization used to emit ocr_options alongside do_ocr=False, which the
    model then rejected — so every run with a stage disabled failed."""
    token = await _signup_and_login(client, "e2e4@example.com")
    project_id = await _create_project(client, token)

    resp = await _upload_with_docling(
        client, test_db, token, project_id, {"do_ocr": False})
    assert resp.status_code == 202, resp.text

    run = await _the_run(test_db)
    assert run.status == "succeeded", run.error
    assert run.config["do_ocr"] is False
    assert "ocr_options" not in run.config


@pytest.mark.asyncio
async def test_an_explicit_ocr_engine_survives_to_the_stored_run(
    client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client, "e2e5@example.com")
    project_id = await _create_project(client, token)

    resp = await _upload_with_docling(
        client, test_db, token, project_id,
        {"ocr_options": {"kind": "tesseract", "lang": ["eng"]}})
    assert resp.status_code == 202, resp.text

    run = await _the_run(test_db)
    assert run.status == "succeeded", run.error
    assert run.config["ocr_options"]["kind"] == "tesseract"
    assert run.config["ocr_options"]["lang"] == ["eng"]


@pytest.mark.asyncio
async def test_a_non_default_table_mode_reaches_the_record(
    client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client, "e2e6@example.com")
    project_id = await _create_project(client, token)

    resp = await _upload_with_docling(
        client, test_db, token, project_id,
        {"table_structure_options": {"mode": "fast"}})
    assert resp.status_code == 202, resp.text

    run = await _the_run(test_db)
    assert run.config["table_structure_options"]["mode"] == "fast"
    # and it must not collide with the defaulted run's hash
    assert run.config_hash != _compute_config_hash(
        {**run.config, "table_structure_options": {"mode": "accurate",
                                                   "do_cell_matching": True}})


# ── Bad input is refused before anything is persisted ────────────────────────

@pytest.mark.asyncio
async def test_a_malformed_config_is_refused_without_creating_a_run(
    client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client, "e2e7@example.com")
    project_id = await _create_project(client, token)

    resp = await _upload_with_docling(
        client, test_db, token, project_id, {"ocr_options": {"kind": "not-an-engine"}})
    assert resp.status_code == 422, resp.text

    result = await test_db.execute(select(ParseRunORM))
    assert list(result.scalars().all()) == []


@pytest.mark.asyncio
async def test_an_explicitly_null_option_is_treated_as_unspecified(
    client: AsyncClient, test_db: AsyncSession):
    """A caller can send `lang: null` over the wire. It must mean "docling
    decides" and reach the record as an absent key, not crash the parse.

    Note this does not exercise the options builder's own null handling —
    normalization drops the null first. It pins the wire-to-record behaviour;
    the builder is covered by a unit test.
    """
    token = await _signup_and_login(client, "e2e8@example.com")
    project_id = await _create_project(client, token)

    resp = await _upload_with_docling(
        client, test_db, token, project_id,
        {"ocr_options": {"kind": "easyocr", "lang": None}})
    assert resp.status_code == 202, resp.text

    run = await _the_run(test_db)
    assert run.status == "succeeded", run.error
    # stored as absent rather than null — "not specified" said honestly
    assert "lang" not in run.config["ocr_options"]
