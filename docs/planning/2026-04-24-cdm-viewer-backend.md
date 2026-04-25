# CDM Viewer Backend — Read Endpoints for ParseRun + ParsedDocument

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose two read-only HTTP endpoints so a frontend viewer can browse persisted CDM records: `GET /documents/{id}/parse-runs` and `GET /parse-runs/{id}/parsed-document`. Persistence already landed in PR #29; the viewer UI is a sibling PR.

**Architecture:** Thin projections of existing ORM rows. New schemas, a new `list_for_source_document` repository method, two route handlers, authorization via the owning `Document`. No migrations.

**Tech Stack:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, pytest-asyncio, `pytest -o "addopts="`.

**Spec:** [docs/specs/cdm_viewer_backend.md](../specs/cdm_viewer_backend.md)

---

## File Structure

**Create:**
- `backend/app/schemas/parse_run.py` — `ParseRunResponse`, `ParsedDocumentResponse`
- `backend/app/routers/parse_runs.py` — `/parse-runs/{id}/parsed-document` handler
- `backend/tests/routers/test_parse_runs_router.py`
- `backend/tests/routers/test_documents_parse_runs_router.py`

**Modify:**
- `backend/app/repositories/parse_run_repository.py` — add `list_for_source_document`
- `backend/app/routers/documents.py` — add `GET /documents/{id}/parse-runs`
- `backend/app/main.py` (or wherever routers are registered) — register `parse_runs.py`
- `backend/tests/repositories/test_parse_run_repository.py` — cover new method

---

## Preflight

- [ ] **Preflight 1: Branch from main**

```bash
git -C /c/Repos/rag-admin checkout -b feat/cdm-viewer-backend main
git -C /c/Repos/rag-admin status
```

Expected: `On branch feat/cdm-viewer-backend`, clean tree.

- [ ] **Preflight 2: Baseline test suite passes**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest -o "addopts=" -x
```

Expected: all tests green.

---

## Task 1 — Response schemas

- [ ] Create `backend/app/schemas/parse_run.py` with two Pydantic v2 `BaseModel`s using camelCase aliases (`populate_by_name=True`):
  - `ParseRunResponse` — all fields listed in spec §2.1. Include `createdAt`.
  - `ParsedDocumentResponse` — fields in spec §2.2 (`parseRunId`, `sourceDocumentId`, `pageCount`, `blockCount`, `fullText`, `fullMarkdown`, `content`).
- [ ] Add `from_orm_row` classmethod on each that accepts the ORM row and returns the schema.

No tests yet (schemas are covered via router tests).

---

## Task 2 — Repository: `list_for_source_document`

- [ ] Add to `ParseRunRepository`:

```python
async def list_for_source_document(self, source_document_id: UUID) -> list[ParseRun]:
    result = await self.session.execute(
        select(ParseRun)
        .where(ParseRun.source_document_id == source_document_id)
        .order_by(ParseRun.created_at.desc())
    )
    return list(result.scalars().all())
```

- [ ] Add a test in `backend/tests/repositories/test_parse_run_repository.py` covering:
  - Returns `[]` for an unknown source_document_id
  - Returns rows in `created_at DESC` order when ≥2 runs exist
  - Does not return rows from other source_documents

Run:

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest -o "addopts=" backend/tests/repositories/test_parse_run_repository.py -x
```

Expected: new test passes, no regressions.

---

## Task 3 — Route: `GET /documents/{id}/parse-runs`

- [ ] In `backend/app/routers/documents.py`, add a new route handler:
  - Path: `/{document_id}/parse-runs`
  - Deps: `get_current_active_user`, `AsyncSession`
  - Load the `Document` (404 if missing). Authorize via existing project/user check pattern used by `GET /documents/{id}`.
  - If `document.source_document_id is None`, return `[]`.
  - Else call `ParseRunRepository(db).list_for_source_document(document.source_document_id)`, map to `ParseRunResponse[]`, return.

- [ ] Write `backend/tests/routers/test_documents_parse_runs_router.py`:
  - `404` for unknown document
  - `403` for doc belonging to another user's project
  - `[]` for doc with `source_document_id=None`
  - Ordered list for doc with ≥2 runs
  - Fields serialize as camelCase

Run the new test file; verify green.

---

## Task 4 — Route: `GET /parse-runs/{id}/parsed-document`

- [ ] Create `backend/app/routers/parse_runs.py` with router `APIRouter(prefix="/parse-runs", tags=["parse-runs"])`.
- [ ] Handler `GET /{parse_run_id}/parsed-document`:
  - Load `ParseRun` (404 if missing).
  - Authorize: fetch all `Document` rows with `source_document_id == run.source_document_id`; 403 unless one is visible to the current user (reuse existing project-visibility helper; if none exists, inline the check).
  - Call `ParsedDocumentRepository(db).get_by_run(run_id)`; 404 if missing (covers failed runs).
  - Return `ParsedDocumentResponse`.
- [ ] Register the router in `backend/app/main.py` alongside the others.
- [ ] Write `backend/tests/routers/test_parse_runs_router.py` covering all 4 status codes (200 / 403 / 404-run / 404-no-parsed-doc) and camelCase output shape.

Run the new test file; verify green.

---

## Task 5 — Full regression

- [ ] Run the full backend suite:

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest -o "addopts="
```

Expected: all green, including the new files.

- [ ] Start the backend locally and hit both endpoints with `curl` against a real CDM-parsed document from a dev database to confirm the wire shape matches the spec.

---

## Task 6 — PR

- [ ] Commit on `feat/cdm-viewer-backend`.
- [ ] Open PR titled `feat(cdm): read endpoints for ParseRun + ParsedDocument`, linked to the GitHub issue.
- [ ] In the PR body: link to `docs/specs/cdm_viewer_backend.md`, list endpoints, list files touched, confirm test run output.
- [ ] Do not merge. Wait for user to review.
