# ParseRun Raw Payload Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the verbatim parser SDK response on every `ParseRun` and expose it via a dedicated read endpoint, so the upcoming ParseRun Viewer can show "what the parser returned" alongside "what we adapted."

**Architecture:** Add a nullable `raw_payload JSONB` column to `parse_runs`. Thread it through the CDM `ParseRun` Pydantic model, the `ParseRunCreate` DTO, the repository `create()` call, and the LlamaParse runner (which already calls `result.model_dump()`). Add `GET /api/v1/parse-runs/{id}/raw-payload` with the same auth pattern as the existing parse-runs router so the standard list/read responses stay slim.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest.

**Spec:** [docs/specs/parse_run_viewer.md](../../specs/parse_run_viewer.md) (Phase 1)

---

## Pre-implementation gate

- [ ] **Step 0: Create GitHub issue**

Per `CLAUDE.md`, this is required before any code lands.

```bash
gh issue create \
  --title "Persist raw LlamaParse payload on ParseRun" \
  --body "$(cat <<'EOF'
## Summary
Persist the verbatim parser SDK response on every `ParseRun` and expose it
via a dedicated endpoint. Unblocks the ParseRun Viewer (Phase 2).

## Acceptance criteria
- New `parse_runs.raw_payload` JSONB column (nullable). Migration runs
  cleanly on a DB at current head.
- LlamaParse successful runs persist the verbatim `result.model_dump()` dict.
- `GET /api/v1/parse-runs/{id}/raw-payload` returns the dict with auth
  identical to the rest of the parse-runs router.
- Repository, service, and router tests pass.

## Spec
docs/specs/parse_run_viewer.md (Phase 1)
EOF
)"
```

Confirm the issue number with the user before continuing. Use it in commit messages (`feat(cdm): … (#NN)`).

---

## File structure

**Created:**
- `backend/alembic/versions/<rev>_add_raw_payload_to_parse_runs.py` — migration
- `backend/tests/repositories/test_parse_run_raw_payload.py` — roundtrip tests
  *(or extend the existing `test_parse_run_repository.py`; see Task 4)*

**Modified:**
- `backend/app/models/parse_run.py` — add `raw_payload` ORM column
- `backend/app/cdm/source.py` — add `raw_payload` to CDM `ParseRun`
- `backend/app/repositories/parse_run_repository.py` — add field to `ParseRunCreate` and pass through in `create()`
- `backend/app/services/parsing/parsing_service.py` — pass `cdm_run.raw_payload` to repo
- `backend/app/services/parsing/llamaparse_runner.py` — set `raw_payload=raw` on the success-path `ParseRun`
- `backend/app/routers/parse_runs.py` — new `GET /{id}/raw-payload` endpoint
- `backend/tests/repositories/test_parse_run_repository.py` — add a roundtrip test for `raw_payload`
- `backend/tests/services/parsing/test_llamaparse_runner.py` — assert raw payload on the returned `ParseRun`
- `backend/tests/services/parsing/test_parsing_service.py` — assert raw payload reaches the persisted row
- `backend/tests/routers/test_parse_runs_router.py` — add tests for the new endpoint

---

### Task 1: Alembic migration — add `raw_payload` column

**Files:**
- Create: `backend/alembic/versions/<rev>_add_raw_payload_to_parse_runs.py`

- [ ] **Step 1.1: Confirm current head**

Run: `uv run --directory backend alembic heads`

Expected: a single head id printed. As of this plan's writing the head is `011ace2ca7ef` (`add_cdm_persistence_tables`). Use whatever the actual head is as `down_revision`.

- [ ] **Step 1.2: Generate the migration scaffold**

Run: `uv run --directory backend alembic revision -m "add raw_payload to parse_runs"`

This creates a file in `backend/alembic/versions/` with a fresh `revision` id. Note that file path; the next step rewrites its body.

- [ ] **Step 1.3: Write the migration body**

Replace the generated file's contents with:

```python
"""add raw_payload to parse_runs

Revision ID: <generated_revision_id>
Revises: <current_head_id>
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "<generated_revision_id>"
down_revision: Union[str, None] = "<current_head_id>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parse_runs",
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("parse_runs", "raw_payload")
```

Replace `<generated_revision_id>` with the id alembic put in the scaffold and `<current_head_id>` with the id from Step 1.1.

- [ ] **Step 1.4: Run the migration locally**

Run: `uv run --directory backend alembic upgrade head`

Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> <new_id>, add raw_payload to parse_runs`. No errors.

- [ ] **Step 1.5: Verify the column**

Run: `uv run --directory backend python -c "from sqlalchemy import inspect; from app.database import sync_engine; print([c['name'] for c in inspect(sync_engine).get_columns('parse_runs')])"`

Expected: list contains `'raw_payload'`. (If the project doesn't expose `sync_engine`, instead run `psql` or any equivalent introspection — the goal is just to confirm the column exists.)

- [ ] **Step 1.6: Commit**

```bash
git add backend/alembic/versions/<rev>_add_raw_payload_to_parse_runs.py
git commit -m "feat(cdm): add raw_payload column to parse_runs (#NN)"
```

---

### Task 2: ORM model — add `raw_payload` mapped column

**Files:**
- Modify: `backend/app/models/parse_run.py`

- [ ] **Step 2.1: Add the mapped column**

In `backend/app/models/parse_run.py`, add an import for the `JSONB` postgres type if not already present, and add a column declaration. Place it just after the existing `provider_refs` column (line 47–49 area), keeping ordering consistent with the migration:

Add to the imports block at the top of the file:

```python
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
```

(replace the existing `from sqlalchemy.dialects.postgresql import UUID as PGUUID` line with the combined import above).

Add this column definition just after the existing `provider_refs` mapped column:

```python
    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
```

- [ ] **Step 2.2: Verify the model loads**

Run: `uv run --directory backend python -c "from app.models.parse_run import ParseRun; print(ParseRun.__table__.columns['raw_payload'].type)"`

Expected: prints `JSONB` (or its repr). No import errors.

- [ ] **Step 2.3: Commit**

```bash
git add backend/app/models/parse_run.py
git commit -m "feat(cdm): map raw_payload on ParseRun ORM (#NN)"
```

---

### Task 3: CDM `ParseRun` model — add `raw_payload`

**Files:**
- Modify: `backend/app/cdm/source.py`

- [ ] **Step 3.1: Add the field**

In `backend/app/cdm/source.py`, add `raw_payload` to the `ParseRun` Pydantic model. Place it immediately after `provider_refs` (line 57) for symmetry with the ORM and the migration. Defaults to `None` so existing call-sites compile unchanged.

```python
    provider_refs: Dict[str, Any] = {}
    raw_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
```

(Insert the new line; the surrounding lines are shown for placement.)

- [ ] **Step 3.2: Sanity import**

Run: `uv run --directory backend python -c "from app.cdm.source import ParseRun; print('raw_payload' in ParseRun.model_fields)"`

Expected: `True`.

- [ ] **Step 3.3: Commit**

```bash
git add backend/app/cdm/source.py
git commit -m "feat(cdm): add raw_payload to CDM ParseRun (#NN)"
```

---

### Task 4: `ParseRunCreate` DTO + repository `create()` wiring (TDD)

**Files:**
- Modify: `backend/app/repositories/parse_run_repository.py`
- Modify: `backend/tests/repositories/test_parse_run_repository.py`

- [ ] **Step 4.1: Write the failing test**

Append to `backend/tests/repositories/test_parse_run_repository.py`:

```python
@pytest.mark.asyncio
async def test_create_persists_raw_payload(repo, source_doc):
    payload = {
        "job_metadata": {"job_id": "abc", "pdf-inputTokens": 10},
        "pages": [{"text": "hello", "markdown": "# hello"}],
    }
    run = await repo.create(make_dto(source_doc, raw_payload=payload))
    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.raw_payload == payload


@pytest.mark.asyncio
async def test_create_defaults_raw_payload_to_none(repo, source_doc):
    run = await repo.create(make_dto(source_doc))
    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.raw_payload is None
```

- [ ] **Step 4.2: Run tests and watch them fail**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/repositories/test_parse_run_repository.py::test_create_persists_raw_payload tests/repositories/test_parse_run_repository.py::test_create_defaults_raw_payload_to_none -v`

Expected: `test_create_persists_raw_payload` FAILS with `TypeError: ... unexpected keyword argument 'raw_payload'` (the DTO doesn't accept it yet).

- [ ] **Step 4.3: Add `raw_payload` to the DTO**

In `backend/app/repositories/parse_run_repository.py`, add the field to `ParseRunCreate` immediately after `provider_refs` (matching the ORM/CDM ordering):

```python
@dataclass
class ParseRunCreate:
    source_document_id: UUID
    parser: str
    representation_kind: str
    config: dict[str, Any]
    config_hash: str
    status: str
    started_at: datetime
    id: UUID | None = None
    parser_version: str | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cost: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    warnings: list[str] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    provider_refs: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] | None = None
    error: str | None = None
```

- [ ] **Step 4.4: Pass `raw_payload` through in `create()`**

In the same file, add `raw_payload=dto.raw_payload` to the `kwargs` dict inside `create()`. The updated block:

```python
    async def create(self, dto: ParseRunCreate) -> ParseRun:
        kwargs: dict[str, Any] = dict(
            source_document_id=dto.source_document_id,
            parser=dto.parser,
            parser_version=dto.parser_version,
            representation_kind=dto.representation_kind,
            config=dto.config,
            config_hash=dto.config_hash,
            status=dto.status,
            started_at=dto.started_at,
            finished_at=dto.finished_at,
            duration_ms=dto.duration_ms,
            cost=dto.cost,
            input_tokens=dto.input_tokens,
            output_tokens=dto.output_tokens,
            warnings=dto.warnings,
            failed_pages=dto.failed_pages,
            provider_refs=dto.provider_refs,
            raw_payload=dto.raw_payload,
            error=dto.error,
        )
        if dto.id is not None:
            kwargs["id"] = dto.id
        row = ParseRun(**kwargs)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
```

- [ ] **Step 4.5: Run tests and verify they pass**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/repositories/test_parse_run_repository.py -v`

Expected: all tests in the file PASS, including the two new ones.

- [ ] **Step 4.6: Commit**

```bash
git add backend/app/repositories/parse_run_repository.py backend/tests/repositories/test_parse_run_repository.py
git commit -m "feat(cdm): thread raw_payload through ParseRun repository (#NN)"
```

---

### Task 5: LlamaParse runner — set `raw_payload` on the success-path `ParseRun` (TDD)

**Files:**
- Modify: `backend/app/services/parsing/llamaparse_runner.py`
- Modify: `backend/tests/services/parsing/test_llamaparse_runner.py`

- [ ] **Step 5.1: Write the failing test**

Open `backend/tests/services/parsing/test_llamaparse_runner.py`. Find the existing test that asserts a successful run (it will already have a fake LlamaParse client returning a known dict). Add a new assertion or a sibling test:

```python
@pytest.mark.asyncio
async def test_run_llamaparse_persists_raw_payload_on_success(monkeypatch):
    # Reuse whatever fake client / SourceDocument helper this file already
    # uses for the success path. The point of this test is the assertion
    # below — that the verbatim model_dump() result is on `run.raw_payload`.
    source, file_path, fake_client, expected_raw = _make_success_fixture()

    run, doc = await run_llamaparse(
        source=source,
        file_path=file_path,
        representation_kind="vector_light",
        config={"tier": "agentic"},
        client=fake_client,
    )

    assert run.raw_payload == expected_raw
```

If the file lacks a `_make_success_fixture()` helper, model the test on whatever existing success-path test is already there — copy its setup verbatim, then add the single `assert run.raw_payload == <the same dict the fake client returns>` assertion. The exact name of the existing helper / fake-client builder doesn't matter; the new assertion is what's load-bearing.

- [ ] **Step 5.2: Run the new test and watch it fail**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/parsing/test_llamaparse_runner.py::test_run_llamaparse_persists_raw_payload_on_success -v`

Expected: FAIL — `assert None == {...}` (the runner doesn't set `raw_payload` yet).

- [ ] **Step 5.3: Set `raw_payload` on the success-path `ParseRun`**

In `backend/app/services/parsing/llamaparse_runner.py`, modify the `ParseRun(...)` construction inside the success branch (currently lines 64–77) to include `raw_payload=raw`:

```python
    raw = result.model_dump()
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    jm = raw.get("job_metadata") or {}
    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LLAMAPARSE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        input_tokens=jm.get("pdf-inputTokens"),
        output_tokens=jm.get("pdf-outputTokens"),
        provider_refs={"llamaparse_job_id": jm.get("job_id")} if jm.get("job_id") else {},
        raw_payload=raw,
    )
```

(The failure branch keeps `raw_payload=None` — there is no `raw` to persist when the SDK call raised.)

- [ ] **Step 5.4: Run the test and verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/parsing/test_llamaparse_runner.py -v`

Expected: all tests PASS.

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/services/parsing/llamaparse_runner.py backend/tests/services/parsing/test_llamaparse_runner.py
git commit -m "feat(cdm): capture raw LlamaParse payload on ParseRun (#NN)"
```

---

### Task 6: Parsing service — persist `raw_payload` end-to-end (TDD)

**Files:**
- Modify: `backend/app/services/parsing/parsing_service.py`
- Modify: `backend/tests/services/parsing/test_parsing_service.py`

- [ ] **Step 6.1: Write the failing test**

In `backend/tests/services/parsing/test_parsing_service.py`, add a test that exercises the success path (or extend an existing one) and asserts the persisted ORM row has `raw_payload` populated.

If a success-path test already exists, modify it to add this assertion at the end. If not, mirror the file's existing setup pattern (fake client returning a dict, real DB session, real repos), then:

```python
@pytest.mark.asyncio
async def test_parse_persists_raw_payload(test_db, ...):
    # Existing setup that drives ParsingService through the success path.
    # ...
    cdm_run, cdm_doc = await service.parse_document(...)

    persisted = await ParseRunRepository(test_db).get(UUID(cdm_run.id))
    assert persisted is not None
    assert persisted.raw_payload is not None
    assert persisted.raw_payload == <the dict the fake client returned>
```

The exact fixture/parameter shape comes from the file's existing patterns — copy them.

- [ ] **Step 6.2: Run and watch it fail**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/parsing/test_parsing_service.py::test_parse_persists_raw_payload -v`

Expected: FAIL — `persisted.raw_payload is None` because `_persist_run` doesn't pass it through yet.

- [ ] **Step 6.3: Pass `raw_payload` through in `_persist_run`**

In `backend/app/services/parsing/parsing_service.py`, modify the `ParseRunCreate(...)` construction inside `_persist_run` (currently lines 170–189) to include `raw_payload=cdm_run.raw_payload`:

```python
    async def _persist_run(
        self,
        cdm_run: ParseRunCDM,
        config_hash: str,
        source_uuid: UUID,
    ) -> ParseRunORM:
        return await self._parse_run_repo.create(ParseRunCreate(
            id=UUID(cdm_run.id),
            source_document_id=source_uuid,
            parser=cdm_run.parser.value,
            parser_version=cdm_run.parser_version,
            representation_kind=cdm_run.representation_kind,
            config=dict(cdm_run.config),
            config_hash=config_hash,
            status=cdm_run.status.value,
            started_at=cdm_run.started_at,
            finished_at=cdm_run.finished_at,
            duration_ms=cdm_run.duration_ms,
            cost=dict(cdm_run.cost),
            input_tokens=cdm_run.input_tokens,
            output_tokens=cdm_run.output_tokens,
            warnings=list(cdm_run.warnings),
            failed_pages=list(cdm_run.failed_pages),
            provider_refs=dict(cdm_run.provider_refs),
            raw_payload=cdm_run.raw_payload,
            error=cdm_run.error,
        ))
```

- [ ] **Step 6.4: Run and verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/parsing/test_parsing_service.py -v`

Expected: all tests PASS.

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/services/parsing/parsing_service.py backend/tests/services/parsing/test_parsing_service.py
git commit -m "feat(cdm): persist raw_payload via ParsingService (#NN)"
```

---

### Task 7: API endpoint — `GET /api/v1/parse-runs/{id}/raw-payload` (TDD)

**Files:**
- Modify: `backend/app/routers/parse_runs.py`
- Modify: `backend/tests/routers/test_parse_runs_router.py`

- [ ] **Step 7.1: Write the failing tests**

Append to `backend/tests/routers/test_parse_runs_router.py`. The test reuses the existing `_signup_and_login`, `_user_by_email`, and `_seed` helpers in that file:

```python
@pytest.mark.asyncio
async def test_raw_payload_200_returns_dict(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "rp1@example.com")
    user = await _user_by_email(test_db, "rp1@example.com")
    run = await _seed(test_db, user)
    run.raw_payload = {"job_metadata": {"job_id": "j1"}, "pages": []}
    await test_db.commit()

    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/raw-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rawPayload"] == {"job_metadata": {"job_id": "j1"}, "pages": []}


@pytest.mark.asyncio
async def test_raw_payload_200_returns_null_when_absent(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "rp2@example.com")
    user = await _user_by_email(test_db, "rp2@example.com")
    run = await _seed(test_db, user)  # raw_payload defaults to NULL

    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/raw-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rawPayload"] is None


@pytest.mark.asyncio
async def test_raw_payload_404_when_run_does_not_exist(
    client: AsyncClient,
):
    token = await _signup_and_login(client, "rp3@example.com")
    resp = await client.get(
        f"/api/v1/parse-runs/{uuid4()}/raw-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_raw_payload_403_when_user_does_not_own_source(
    client: AsyncClient, test_db: AsyncSession
):
    await _signup_and_login(client, "rpA@example.com")
    user_a = await _user_by_email(test_db, "rpA@example.com")
    run = await _seed(test_db, user_a)

    token_b = await _signup_and_login(client, "rpB@example.com")
    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/raw-payload",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_raw_payload_401_when_unauthenticated(
    client: AsyncClient, test_db: AsyncSession
):
    await _signup_and_login(client, "rpC@example.com")
    user = await _user_by_email(test_db, "rpC@example.com")
    run = await _seed(test_db, user)

    resp = await client.get(f"/api/v1/parse-runs/{run.id}/raw-payload")
    # FastAPI's Bearer dependency returns 401 when no token is supplied.
    assert resp.status_code == 401
```

- [ ] **Step 7.2: Run and watch them fail**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_parse_runs_router.py -v -k raw_payload`

Expected: all five new tests FAIL with 404 (route not registered).

- [ ] **Step 7.3: Add the response schema**

In `backend/app/schemas/parse_run.py` add a small response model alongside the existing `ParsedDocumentResponse`. The existing module's style (camelCase serialization) should be matched — find the pattern there and reuse it. If the existing response uses Pydantic's `alias_generator=to_camel` + `populate_by_name=True`, mirror that:

```python
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class RawPayloadResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    raw_payload: Optional[dict[str, Any]] = None
```

If the existing module already imports `to_camel` and defines a base config, extend that instead of duplicating. Open `backend/app/schemas/parse_run.py` and follow whatever pattern is there.

- [ ] **Step 7.4: Add the route handler**

In `backend/app/routers/parse_runs.py`, add this endpoint just below `get_parsed_document_for_run`:

```python
from app.schemas.parse_run import ParsedDocumentResponse, RawPayloadResponse  # update existing import


@router.get(
    "/{parse_run_id}/raw-payload",
    response_model=RawPayloadResponse,
    response_model_by_alias=True,
    summary="Get the verbatim parser SDK payload for a ParseRun",
    description=(
        "Return the raw parser-SDK response that produced this ParseRun, as "
        "captured at run time. Returns `rawPayload: null` for legacy runs or "
        "runs where no payload was captured (e.g. the parser SDK call failed)."
    ),
)
async def get_raw_payload_for_run(
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    run = await ParseRunRepository(db).get(parse_run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ParseRun {parse_run_id} not found",
        )
    owns = await _user_owns_source(
        db, source_document_id=run.source_document_id, user_id=current_user.id
    )
    if not owns:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this ParseRun",
        )
    return RawPayloadResponse(raw_payload=run.raw_payload)
```

- [ ] **Step 7.5: Run and verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_parse_runs_router.py -v`

Expected: all tests in the file PASS.

- [ ] **Step 7.6: Commit**

```bash
git add backend/app/routers/parse_runs.py backend/app/schemas/parse_run.py backend/tests/routers/test_parse_runs_router.py
git commit -m "feat(cdm): add raw-payload endpoint to parse-runs router (#NN)"
```

---

### Task 8: Full backend regression + PR

- [ ] **Step 8.1: Run the targeted suites the spec calls out**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/repositories/ tests/services/parsing/ tests/routers/test_parse_runs_router.py`

Expected: all PASS.

- [ ] **Step 8.2: Run the full backend suite as a regression check**

Run: `uv run --directory backend python -m pytest -o "addopts="`

Expected: same pass/fail counts as `main` (no regressions). If anything that was passing is now failing, fix it before opening the PR.

- [ ] **Step 8.3: Push and open the PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "feat(cdm): persist raw LlamaParse payload on ParseRun" \
  --body "$(cat <<'EOF'
## Summary
- Add `raw_payload JSONB` column to `parse_runs` (Alembic migration).
- Thread the verbatim `result.model_dump()` from LlamaParse through the
  CDM `ParseRun`, the `ParseRunCreate` DTO, and the repository.
- New endpoint `GET /api/v1/parse-runs/{id}/raw-payload` (auth-gated like
  the rest of the parse-runs router).

Unblocks the ParseRun Viewer (Phase 2).

Closes #NN

## Test plan
- [ ] `uv run --directory backend python -m pytest -o "addopts=" tests/repositories/ tests/services/parsing/ tests/routers/test_parse_runs_router.py`
- [ ] `uv run --directory backend alembic upgrade head` on a fresh DB
- [ ] Manual: upload a document, confirm `parse_runs.raw_payload` is non-null

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Wait for user merge before any cleanup.

---

## Self-review notes (writer)

- **Spec coverage:** Phase 1 acceptance criteria from the spec are all covered (column exists & migration clean → Task 1; LlamaParse persists verbatim → Tasks 5–6; endpoint with parity auth → Task 7; tests pass → Task 8).
- **Type consistency:** `raw_payload` is `Optional[Dict[str, Any]]`/`dict[str, Any] | None` everywhere; field placement is "after `provider_refs`, before `error`" in CDM, DTO, and ORM (matches migration).
- **No placeholders:** Every code-changing step has the actual code. The two TDD steps that lean on existing fixtures (5.1, 6.1) explicitly call out "copy the existing success-path setup" rather than leaving a TBD — this is honest about what the engineer needs to do without inventing fixture names that may not exist.
