# CDM Index Unit 5 — Index Detail Parsed Documents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the index detail "Documents" tab to "Parsed Documents" with new columns (Source filename / Parse run / Parsed at / Status / Chunks); restore the Add Documents flow using `ParsedDocumentPicker`; add backend list + delete endpoints for index parsed-documents.

**Architecture:** Two new backend endpoints (`GET` and `DELETE /indexes/{id}/parsed-documents`), two frontend API functions + one new type, a rebuilt IndexDetailPage Documents section, and an Add Documents dialog wired to `ParsedDocumentPicker`.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async (backend); React 18 / TypeScript / Vite / shadcn/ui / Vitest + RTL (frontend)

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/app/schemas/index.py` | Add `IndexParsedDocumentItem` response schema |
| Modify | `backend/app/repositories/index_repository.py` | Add `list_index_parsed_documents()`, `remove_parsed_document()` |
| Modify | `backend/app/services/index_service.py` | Add `list_index_parsed_documents()`, `remove_parsed_document()` |
| Modify | `backend/app/routers/indexes.py` | Add `GET /{index_id}/parsed-documents`, `DELETE /{index_id}/parsed-documents/{parse_run_id}` |
| Create | `backend/tests/routers/test_index_parsed_docs_router.py` | Router tests for both endpoints |
| Modify | `frontend/src/types/index.ts` | Add `IndexParsedDocumentItem` |
| Modify | `frontend/src/api/indexes.ts` | Add `listIndexParsedDocuments()`, `removeIndexParsedDocument()` |
| Modify | `frontend/src/pages/IndexDetailPage.tsx` | Rebuild tab + restore Add dialog |
| Create | `frontend/src/pages/IndexDetailPage.test.tsx` | Frontend tests |

---

### Task 1: Backend `GET /indexes/{id}/parsed-documents`

**Files:**
- Modify: `backend/app/schemas/index.py`
- Modify: `backend/app/repositories/index_repository.py`
- Modify: `backend/app/services/index_service.py`
- Modify: `backend/app/routers/indexes.py`
- Create: `backend/tests/routers/test_index_parsed_docs_router.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/routers/test_index_parsed_docs_router.py`:

```python
"""Tests for GET/DELETE /projects/{project_id}/indexes/{index_id}/parsed-documents."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.index import Index, IndexStatus
from app.models.index_document import IndexDocument, IndexDocumentStatus
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User


async def _signup(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email, "password": "ValidPass123!",
            "password_confirm": "ValidPass123!", "full_name": "T",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


async def _user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one()


async def _make_project(db: AsyncSession, user: User) -> Project:
    project = Project(user_id=user.id, name=f"P{uuid4().hex[:6]}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _seed_index_with_parsed_doc(
    db: AsyncSession,
    *,
    user: User,
    project: Project,
    sha: str = "a" * 64,
    filename: str = "acme-msa.pdf",
    chunks_created: int | None = None,
    status: IndexDocumentStatus = IndexDocumentStatus.pending,
) -> tuple[Index, IndexDocument, ParseRunORM, ParsedDocumentORM]:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf", filename=filename)
    db.add(sd)
    await db.commit()

    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    db.add(doc)

    now = datetime.now(timezone.utc)
    run = ParseRunORM(
        source_document_id=sd.id, parser="llamaparse",
        representation_kind="full_markdown",
        config={"result_type": "markdown"}, config_hash="h" * 64,
        status="succeeded", started_at=now, finished_at=now,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    pd = ParsedDocumentORM(
        parse_run_id=run.id, source_document_id=sd.id,
        full_text="hello", full_markdown="# hi",
        page_count=1, block_count=2,
        content={"blocks": [{"text": "hi"}]},
    )
    db.add(pd)

    idx = Index(
        project_id=project.id, name="idx",
        config={
            "source_representation": "full_markdown",
            "parser": "llamaparse",
            "parse_config_hash": "h" * 64,
        },
        status=IndexStatus.created, created_by=user.id,
    )
    db.add(idx)
    await db.commit()
    await db.refresh(idx)

    idx_doc = IndexDocument(
        index_id=idx.id, document_id=doc.id,
        parse_run_id=run.id,
        processing_status=status,
        chunks_created=chunks_created,
    )
    db.add(idx_doc)
    await db.commit()
    await db.refresh(idx_doc)

    return idx, idx_doc, run, pd


@pytest.mark.asyncio
async def test_list_index_parsed_documents_returns_expected_fields(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    idx, idx_doc, run, _ = await _seed_index_with_parsed_doc(
        test_db, user=user, project=project, filename="acme-msa.pdf"
    )

    resp = await client.get(
        f"/api/v1/projects/{project.id}/indexes/{idx.id}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["parseRunId"] == str(run.id)
    assert item["sourceFilename"] == "acme-msa.pdf"
    assert item["status"] == "pending"
    assert item["chunksCreated"] is None
    assert "parsedAt" in item


@pytest.mark.asyncio
async def test_list_index_parsed_documents_empty_when_no_docs(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    idx = Index(
        project_id=project.id, name="empty",
        config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    resp = await client.get(
        f"/api/v1/projects/{project.id}/indexes/{idx.id}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_index_parsed_documents_returns_404_for_unknown_index(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    resp = await client.get(
        f"/api/v1/projects/{project.id}/indexes/{uuid4()}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
uv run --directory backend python -m pytest tests/routers/test_index_parsed_docs_router.py -o "addopts=" -v 2>&1 | tail -20
```
Expected: FAIL — endpoint does not exist yet.

- [ ] **Step 3: Add `IndexParsedDocumentItem` schema**

In `backend/app/schemas/index.py`, after the `IndexDocumentStatusResponse` class (around line 133), add:

```python
class IndexParsedDocumentItem(BaseModel):
    """One row in the index detail 'Parsed Documents' tab."""
    parse_run_id: UUID = Field(..., alias="parseRunId")
    source_filename: str | None = Field(None, alias="sourceFilename")
    parsed_at: datetime | None = Field(None, alias="parsedAt")
    status: str
    chunks_created: int | None = Field(None, alias="chunksCreated")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
```

Also add `IndexParsedDocumentItem` to the imports list at the top of the file (it already has `from datetime import datetime` and `from uuid import UUID`).

- [ ] **Step 4: Add `list_index_parsed_documents` to the repository**

In `backend/app/repositories/index_repository.py`, add imports at the top:

```python
from app.models.parsed_document import ParsedDocument
from app.models.source_document import SourceDocument
```

Then add this method to `IndexRepository` (after `get_index_documents`, around line 258):

```python
async def list_index_parsed_documents(
    self,
    index_id: UUID,
) -> list:
    """Return parsed-document details for every row in index_documents."""
    from sqlalchemy import Row
    query = (
        select(
            IndexDocument.parse_run_id,
            IndexDocument.processing_status,
            IndexDocument.chunks_created,
            ParseRun.finished_at,
            SourceDocument.filename.label("source_filename"),
        )
        .join(ParseRun, ParseRun.id == IndexDocument.parse_run_id, isouter=True)
        .join(
            ParsedDocument,
            ParsedDocument.parse_run_id == IndexDocument.parse_run_id,
            isouter=True,
        )
        .join(
            SourceDocument,
            SourceDocument.id == ParsedDocument.source_document_id,
            isouter=True,
        )
        .where(IndexDocument.index_id == index_id)
        .order_by(ParseRun.finished_at.desc().nulls_last())
    )
    result = await self.session.execute(query)
    return result.all()
```

- [ ] **Step 5: Add `list_index_parsed_documents` to the service**

In `backend/app/services/index_service.py`, after the `remove_document` method (around line 311), add:

```python
async def list_index_parsed_documents(
    self,
    index_id: UUID,
    project_id: UUID,
) -> list[IndexParsedDocumentItem]:
    """Return parsed-document rows for the index detail tab.

    Raises:
    - NotFoundError: Index not found
    """
    index = await self.index_repo.get_by_id(index_id, project_id)
    if not index:
        raise NotFoundError(f"Index {index_id} not found")

    rows = await self.index_repo.list_index_parsed_documents(index_id)
    return [
        IndexParsedDocumentItem(
            parse_run_id=row.parse_run_id,
            source_filename=row.source_filename,
            parsed_at=row.finished_at,
            status=row.processing_status.value if row.processing_status else "pending",
            chunks_created=row.chunks_created,
        )
        for row in rows
    ]
```

Also add `IndexParsedDocumentItem` to the import from `app.schemas.index` at the top of the service file.

- [ ] **Step 6: Add route to the router**

In `backend/app/routers/indexes.py`, after the `add_parsed_documents` route (around line 435), add:

```python
@router.get(
    "/{index_id}/parsed-documents",
    response_model=list[IndexParsedDocumentItem],
    summary="List index parsed-documents",
    description="List all parsed-documents attached to an index with their processing status.",
)
async def list_index_parsed_documents(
    project_id: UUID,
    index_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.list_index_parsed_documents(index_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

Also add `IndexParsedDocumentItem` to the import from `app.schemas.index` at the top of the router file.

- [ ] **Step 7: Run tests — confirm PASS**

```bash
uv run --directory backend python -m pytest tests/routers/test_index_parsed_docs_router.py -o "addopts=" -v 2>&1 | tail -25
```
Expected: all 3 GET tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/index.py \
        backend/app/repositories/index_repository.py \
        backend/app/services/index_service.py \
        backend/app/routers/indexes.py \
        backend/tests/routers/test_index_parsed_docs_router.py
git commit -m "feat(indexes): add GET /indexes/{id}/parsed-documents endpoint"
```

---

### Task 2: Backend `DELETE /indexes/{id}/parsed-documents/{parse_run_id}`

**Files:**
- Modify: `backend/app/repositories/index_repository.py`
- Modify: `backend/app/services/index_service.py`
- Modify: `backend/app/routers/indexes.py`
- Modify: `backend/tests/routers/test_index_parsed_docs_router.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/routers/test_index_parsed_docs_router.py`:

```python
@pytest.mark.asyncio
async def test_delete_index_parsed_document_removes_row(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    idx, idx_doc, run, _ = await _seed_index_with_parsed_doc(
        test_db, user=user, project=project
    )

    resp = await client.delete(
        f"/api/v1/projects/{project.id}/indexes/{idx.id}/parsed-documents/{run.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Row is gone
    remaining = await test_db.execute(
        select(IndexDocument).where(IndexDocument.index_id == idx.id)
    )
    assert remaining.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_index_parsed_document_returns_404_for_unknown_run(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, f"u{uuid4().hex[:6]}@x.com")
    user = await _user_by_email(test_db, (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["email"])
    project = await _make_project(test_db, user)

    idx = Index(
        project_id=project.id, name="idx",
        config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    resp = await client.delete(
        f"/api/v1/projects/{project.id}/indexes/{idx.id}/parsed-documents/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run new tests — confirm FAIL**

```bash
uv run --directory backend python -m pytest tests/routers/test_index_parsed_docs_router.py::test_delete_index_parsed_document_removes_row tests/routers/test_index_parsed_docs_router.py::test_delete_index_parsed_document_returns_404_for_unknown_run -o "addopts=" -v 2>&1 | tail -10
```
Expected: FAIL — route does not exist yet.

- [ ] **Step 3: Add `remove_parsed_document` to the repository**

In `backend/app/repositories/index_repository.py`, after `list_index_parsed_documents`, add:

```python
async def remove_parsed_document(
    self,
    index_id: UUID,
    parse_run_id: UUID,
) -> bool:
    """Remove a specific parsed-document row from an index and its chunks."""
    result = await self.session.execute(
        delete(IndexDocument).where(
            IndexDocument.index_id == index_id,
            IndexDocument.parse_run_id == parse_run_id,
        )
    )
    if result.rowcount == 0:
        return False
    await self.session.execute(
        delete(Chunk).where(
            Chunk.index_id == index_id,
            Chunk.parse_run_id == parse_run_id,
        )
    )
    await self.session.commit()
    return True
```

- [ ] **Step 4: Add `remove_parsed_document` to the service**

In `backend/app/services/index_service.py`, after `list_index_parsed_documents`, add:

```python
async def remove_parsed_document(
    self,
    index_id: UUID,
    project_id: UUID,
    parse_run_id: UUID,
) -> IndexResponse:
    """Remove a specific parsed-document from an index.

    Raises:
    - NotFoundError: Index or parsed-document row not found
    - ValidationError: Index is currently processing
    """
    index = await self.index_repo.get_by_id(index_id, project_id)
    if not index:
        raise NotFoundError(f"Index {index_id} not found")

    if index.status == IndexStatus.processing:
        raise ValidationError("Cannot remove documents while index is processing")

    removed = await self.index_repo.remove_parsed_document(index_id, parse_run_id)
    if not removed:
        raise NotFoundError(
            f"Parsed document with parse_run_id={parse_run_id} not found in index"
        )

    return await self.get_index(index_id, project_id)
```

- [ ] **Step 5: Add DELETE route to the router**

In `backend/app/routers/indexes.py`, after the `list_index_parsed_documents` route, add:

```python
@router.delete(
    "/{index_id}/parsed-documents/{parse_run_id}",
    response_model=IndexResponse,
    summary="Remove parsed-document from index",
    description="Remove a specific parsed-document row from an index.",
)
async def remove_index_parsed_document(
    project_id: UUID,
    index_id: UUID,
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.remove_parsed_document(index_id, project_id, parse_run_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 6: Run all router tests — confirm PASS**

```bash
uv run --directory backend python -m pytest tests/routers/test_index_parsed_docs_router.py -o "addopts=" -v 2>&1 | tail -15
```
Expected: all 5 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/index_repository.py \
        backend/app/services/index_service.py \
        backend/app/routers/indexes.py \
        backend/tests/routers/test_index_parsed_docs_router.py
git commit -m "feat(indexes): add DELETE /indexes/{id}/parsed-documents/{parse_run_id} endpoint"
```

---

### Task 3: Frontend types + API layer

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/indexes.ts`

- [ ] **Step 1: Add `IndexParsedDocumentItem` to types**

In `frontend/src/types/index.ts`, after `IndexDocumentStatusItem` (around line 96), add:

```ts
// Parsed document row for index detail tab
export interface IndexParsedDocumentItem {
  parseRunId: string
  sourceFilename: string | null
  parsedAt: string | null
  status: string
  chunksCreated: number | null
}
```

- [ ] **Step 2: Add API functions**

In `frontend/src/api/indexes.ts`, after the `removeDocument` function (around line 147), add:

```ts
// List parsed documents attached to an index (for the detail tab)
export async function listIndexParsedDocuments(
  projectId: string,
  indexId: string,
): Promise<IndexParsedDocumentItem[]> {
  const response = await apiClient.get<IndexParsedDocumentItem[]>(
    `/projects/${projectId}/indexes/${indexId}/parsed-documents`,
  )
  return response.data
}

// Remove a specific parsed-document from an index
export async function removeIndexParsedDocument(
  projectId: string,
  indexId: string,
  parseRunId: string,
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectId}/indexes/${indexId}/parsed-documents/${parseRunId}`,
  )
}
```

Also add `IndexParsedDocumentItem` to the import from `@/types/index` at the top of the file.

- [ ] **Step 3: TypeScript check**

```bash
npm run --prefix frontend build 2>&1 | grep "error TS" | head -10
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/indexes.ts
git commit -m "feat(indexes): add IndexParsedDocumentItem type and list/remove API functions"
```

---

### Task 4: Rebuild "Parsed Documents" tab in IndexDetailPage

**Files:**
- Modify: `frontend/src/pages/IndexDetailPage.tsx`
- Create: `frontend/src/pages/IndexDetailPage.test.tsx`

The current "Documents" section reads from `useDocuments` and shows document titles. Unit 5 replaces it with per-parsed-document rows fetched from the new `GET /indexes/{id}/parsed-documents` endpoint.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/pages/IndexDetailPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import IndexDetailPage from './IndexDetailPage'

const mockIndex = {
  id: 'idx-1',
  projectId: 'proj-1',
  name: 'My Index',
  description: null,
  config: {
    sourceRepresentation: 'full_markdown',
    parser: 'llamaparse',
    parseConfigHash: 'abc123',
    chunkingStrategy: 'markdown_heading',
    chunkSize: 512,
    chunkOverlap: 50,
    chunkUnit: 'characters',
    splitHeadingLevel: 2,
    maxSectionChars: 4000,
    embeddingProvider: 'openai',
    embeddingModel: 'text-embedding-3-small',
    embeddingDimensions: null,
  },
  stats: null,
  status: 'ready',
  version: 1,
  configDirty: false,
  errorMessage: null,
  createdBy: 'user-1',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
  documentCount: 1,
  chunkCount: 10,
  documentIds: ['doc-1'],
}

const mockParsedDocs = [
  {
    parseRunId: 'pr-1',
    sourceFilename: 'acme-msa.pdf',
    parsedAt: '2026-04-30T09:11:00Z',
    status: 'completed',
    chunksCreated: 10,
  },
]

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test' } }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ indexId: 'idx-1' }) }
})

vi.mock('@/hooks/useIndexes', () => ({
  useIndexDetail: () => ({
    index: mockIndex,
    chunks: null,
    isLoading: false,
    error: null,
    fetchIndex: vi.fn().mockResolvedValue(undefined),
    fetchChunks: vi.fn().mockResolvedValue(undefined),
    getChunk: vi.fn(),
  }),
  useIndexes: () => ({
    updateIndex: vi.fn(),
    processIndex: vi.fn(),
  }),
}))

vi.mock('@/api/indexes', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/indexes')>()
  return {
    ...actual,
    listIndexParsedDocuments: vi.fn().mockResolvedValue(mockParsedDocs),
    removeIndexParsedDocument: vi.fn().mockResolvedValue(undefined),
    addParsedDocuments: vi.fn().mockResolvedValue(mockIndex),
  }
})

vi.mock('@/lib/parsed-documents', () => ({
  listParsedDocuments: vi.fn().mockResolvedValue([
    {
      id: 'pd-new',
      parseRunId: 'pr-new',
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      sourceDocumentId: 'sd-new',
      sourceFilename: 'vendor.pdf',
      hasFullMarkdown: true,
      blockCount: 5,
      parsedAt: '2026-04-30T10:00:00Z',
    },
  ]),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <IndexDetailPage />
    </MemoryRouter>,
  )
}

describe('IndexDetailPage — Parsed Documents tab', () => {
  it('shows "Parsed Documents" section heading', async () => {
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/parsed documents/i)).toBeInTheDocument(),
    )
  })

  it('renders the source filename column', async () => {
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument(),
    )
  })

  it('renders the chunks created column', async () => {
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('10')).toBeInTheDocument(),
    )
  })
})
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
npm run --prefix frontend test:run -- src/pages/IndexDetailPage.test.tsx 2>&1 | tail -10
```
Expected: FAIL.

- [ ] **Step 3: Rebuild the Parsed Documents section in `IndexDetailPage.tsx`**

Make the following changes to `frontend/src/pages/IndexDetailPage.tsx`:

**3a. Add imports (at top):**
```tsx
import { IndexParsedDocumentItem } from '@/types/index'
import * as indexesApi from '@/api/indexes'
```
(Note: `* as indexesApi` is already imported; just add `IndexParsedDocumentItem` to the types import.)

**3b. Remove these imports (no longer needed):**
- `import { useDocuments } from '@/hooks/useDocuments'`
- `import { DocumentListItem } from '@/types/document'`

**3c. Remove `useDocuments` call and its derived state:**
Remove these lines:
```tsx
const { documents } = useDocuments(projectId)
...
const indexDocuments = documents.filter((d) => indexDocumentIds.includes(d.id))
const availableDocuments = documents.filter(
  (d) => d.status === 'ready' && !indexDocumentIds.includes(d.id)
)
```

**3d. Add parsed-documents state + fetch:**
After `const indexDocumentIds = index?.documentIds ?? []`, add:

```tsx
const [parsedDocs, setParsedDocs] = useState<IndexParsedDocumentItem[]>([])
const [isParsedDocsLoading, setIsParsedDocsLoading] = useState(false)

const fetchParsedDocs = useCallback(async () => {
  if (!projectId || !indexId) return
  setIsParsedDocsLoading(true)
  try {
    const data = await indexesApi.listIndexParsedDocuments(projectId, indexId)
    setParsedDocs(data)
  } catch {
    // silent — tab shows empty state on error
  } finally {
    setIsParsedDocsLoading(false)
  }
}, [projectId, indexId])
```

**3e. Add `fetchParsedDocs` to the initial useEffect:**
```tsx
useEffect(() => {
  if (!currentProject) {
    navigate('/index')
    return
  }
  fetchIndex()
  fetchChunks()
  fetchParsedDocs()
}, [currentProject, navigate, fetchIndex, fetchChunks, fetchParsedDocs])
```

Wait — the existing page already has two `useEffect`s: one for redirecting on no project, and one for polling during processing. Restructure so `fetchParsedDocs` is called in the initial load effect. The existing structure is:
```tsx
useEffect(() => {
  if (!currentProject) { navigate('/index') }
}, [currentProject, navigate])
```
and the `useIndexDetail` hook's own `useEffect` handles the initial fetch.

The safest approach: add a standalone `useEffect` for `fetchParsedDocs`:
```tsx
useEffect(() => {
  fetchParsedDocs()
}, [fetchParsedDocs])
```

Also call `fetchParsedDocs()` after successful remove/add operations.

**3f. Update the remove state to use `parseRunId`:**

Replace:
```tsx
const [docToRemove, setDocToRemove] = useState<string | null>(null)
```
with:
```tsx
const [parsedDocToRemove, setParsedDocToRemove] = useState<string | null>(null)
```

Update `handleRemoveDocument`:
```tsx
const handleRemoveDocument = async () => {
  if (!projectId || !indexId || !parsedDocToRemove) return
  setIsRemovingDoc(true)
  try {
    await indexesApi.removeIndexParsedDocument(projectId, indexId, parsedDocToRemove)
    await fetchIndex()
    await fetchParsedDocs()
    setRemoveDocDialogOpen(false)
    setParsedDocToRemove(null)
    toast.success('Document removed')
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Failed to remove document')
  } finally {
    setIsRemovingDoc(false)
  }
}
```

**3g. Replace the Documents section in the JSX:**

Replace the entire "Documents Section" block (currently inside `{activeTab === 'content' && ...}`) with:

```tsx
{/* Parsed Documents Section */}
<div className="rounded-t-lg border border-b-0">
  <div className="px-4 py-3 flex items-center justify-between border-b">
    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
      Parsed Documents ({parsedDocs.length})
    </h3>
    <div className="flex items-center gap-2">
      {index.status === 'ready' && index.chunkCount > 0 && (
        <button
          onClick={handleProcessIndex}
          disabled={isProcessing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          <Play className="h-3.5 w-3.5" />
          {isProcessing ? 'Starting...' : 'Re-index'}
        </button>
      )}
      {canManageDocs && (
        <button
          onClick={() => setAddDocsDialogOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium text-muted-foreground hover:bg-muted/50 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" /> Add Document
        </button>
      )}
    </div>
  </div>

  {isParsedDocsLoading ? (
    <div className="px-4 py-3 space-y-2">
      {[0, 1].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  ) : parsedDocs.length === 0 ? (
    <div className="px-4 py-8 text-center text-sm text-muted-foreground">
      No parsed documents in this index
    </div>
  ) : (
    <>
      <div className="px-4 py-2 flex items-center gap-3 bg-muted/50 border-b text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
        <span className="flex-1">Source filename</span>
        <span className="w-24">Parse run</span>
        <span className="w-32">Parsed at</span>
        <span className="w-20">Status</span>
        <span className="w-16 text-right">Chunks</span>
        {canManageDocs && <span className="w-8" />}
      </div>
      {parsedDocs.map((pd) => (
        <div
          key={pd.parseRunId}
          className="px-4 py-3 flex items-center gap-3 border-b last:border-b-0 hover:bg-muted/20"
        >
          <span className="flex-1 text-sm font-medium truncate">
            {pd.sourceFilename ?? 'Unknown file'}
          </span>
          <span className="w-24 text-xs font-mono text-muted-foreground truncate">
            {pd.parseRunId.slice(0, 8)}…
          </span>
          <span className="w-32 text-xs text-muted-foreground">
            {pd.parsedAt
              ? new Date(pd.parsedAt).toLocaleDateString('en-US', {
                  month: 'short', day: 'numeric',
                  hour: '2-digit', minute: '2-digit',
                })
              : '—'}
          </span>
          <span className={cn(
            'w-20 text-xs font-medium',
            pd.status === 'completed' ? 'text-green-700 dark:text-green-400' :
            pd.status === 'processing' ? 'text-blue-700 dark:text-blue-400' :
            pd.status === 'failed' ? 'text-red-700 dark:text-red-400' :
            'text-muted-foreground',
          )}>
            {pd.status}
          </span>
          <span className="w-16 text-xs font-mono text-right text-muted-foreground">
            {pd.chunksCreated ?? '—'}
          </span>
          {canManageDocs && (
            <button
              className="w-8 p-1 rounded text-muted-foreground/40 hover:text-red-500 transition-colors"
              onClick={() => {
                setParsedDocToRemove(pd.parseRunId)
                setRemoveDocDialogOpen(true)
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      ))}
    </>
  )}
</div>
```

Update the Remove dialog to use `parsedDocToRemove` and `setParsedDocToRemove` (replacing `docToRemove` and `setDocToRemove`).

- [ ] **Step 4: Run tests — confirm PASS**

```bash
npm run --prefix frontend test:run -- src/pages/IndexDetailPage.test.tsx 2>&1 | tail -10
```
Expected: first 3 tests pass.

If tests fail due to mocking issues (e.g., `useIndexDetail` not returning the mock index), verify that the mock `useIndexDetail` matches what the component accesses: `index`, `fetchIndex`, `fetchChunks`.

- [ ] **Step 5: TypeScript check**

```bash
npm run --prefix frontend build 2>&1 | grep "error TS" | head -10
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/IndexDetailPage.tsx frontend/src/pages/IndexDetailPage.test.tsx
git commit -m "feat(indexes): rebuild IndexDetailPage Documents tab as Parsed Documents with new column shape"
```

---

### Task 5: Restore "Add Documents" dialog with `ParsedDocumentPicker`

**Files:**
- Modify: `frontend/src/pages/IndexDetailPage.tsx`
- Modify: `frontend/src/pages/IndexDetailPage.test.tsx`

The current `handleAddDocuments` shows a toast error. Unit 5 replaces the old checkbox-list dialog with a `ParsedDocumentPicker` scoped to the index's parse-config family.

- [ ] **Step 1: Write failing tests**

Append to `frontend/src/pages/IndexDetailPage.test.tsx`:

```tsx
describe('IndexDetailPage — Add Documents dialog', () => {
  it('opens a dialog with ParsedDocumentPicker when Add Document is clicked', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Parsed Documents (1)'))

    await user.click(screen.getByRole('button', { name: /add document/i }))

    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: 'vendor.pdf' })).toBeInTheDocument(),
    )
  })

  it('calls addParsedDocuments with selected IDs on submit', async () => {
    const { addParsedDocuments } = await import('@/api/indexes')
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Parsed Documents (1)'))

    await user.click(screen.getByRole('button', { name: /add document/i }))
    await waitFor(() => screen.getByRole('checkbox', { name: 'vendor.pdf' }))
    await user.click(screen.getByRole('checkbox', { name: 'vendor.pdf' }))
    await user.click(screen.getByRole('button', { name: /^add$/i }))

    expect(addParsedDocuments).toHaveBeenCalledWith(
      'proj-1',
      'idx-1',
      { parsedDocumentIds: ['pd-new'] },
    )
  })
})
```

- [ ] **Step 2: Run new tests — confirm FAIL**

```bash
npm run --prefix frontend test:run -- src/pages/IndexDetailPage.test.tsx 2>&1 | tail -10
```
Expected: the 2 new dialog tests FAIL.

- [ ] **Step 3: Replace the Add Documents dialog in `IndexDetailPage.tsx`**

**3a. Add import:**
```tsx
import { ParsedDocumentPicker } from '@/components/indexes/ParsedDocumentPicker'
```

**3b. Replace `selectedDocIds` state with `selectedParsedDocIds`:**

Remove:
```tsx
const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
```

Add:
```tsx
const [selectedParsedDocIds, setSelectedParsedDocIds] = useState<string[]>([])
```

**3c. Replace `handleAddDocuments`:**

Remove the entire old `handleAddDocuments` that shows a toast error.

Add:
```tsx
const handleAddDocuments = async () => {
  if (!projectId || !indexId || selectedParsedDocIds.length === 0) return
  try {
    await indexesApi.addParsedDocuments(projectId, indexId, {
      parsedDocumentIds: selectedParsedDocIds,
    })
    await fetchIndex()
    await fetchParsedDocs()
    setAddDocsDialogOpen(false)
    setSelectedParsedDocIds([])
    toast.success(
      `${selectedParsedDocIds.length} parsed document${selectedParsedDocIds.length > 1 ? 's' : ''} added`,
    )
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Failed to add documents')
  }
}
```

**3d. Replace the Add Documents dialog content:**

Replace the existing `<Dialog open={addDocsDialogOpen} ...>` block with:

```tsx
{/* ══════ Add Documents Dialog ══════ */}
<Dialog
  open={addDocsDialogOpen}
  onOpenChange={(open) => {
    setAddDocsDialogOpen(open)
    if (!open) setSelectedParsedDocIds([])
  }}
>
  <DialogContent className="max-w-2xl">
    <DialogHeader>
      <DialogTitle>Add Parsed Documents</DialogTitle>
      <DialogDescription>
        Select parsed documents to add to this index
      </DialogDescription>
    </DialogHeader>
    <div className="max-h-96 overflow-y-auto">
      {index.config.parser && index.config.parseConfigHash ? (
        <ParsedDocumentPicker
          projectId={projectId!}
          parser={index.config.parser}
          parseConfigHash={index.config.parseConfigHash}
          representation={index.config.sourceRepresentation ?? 'full_text'}
          selectedIds={selectedParsedDocIds}
          onChange={setSelectedParsedDocIds}
        />
      ) : (
        <p className="text-center text-muted-foreground py-8">
          This index has no parse-config family set.
        </p>
      )}
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={() => setAddDocsDialogOpen(false)}>
        Cancel
      </Button>
      <Button
        onClick={handleAddDocuments}
        disabled={selectedParsedDocIds.length === 0}
      >
        Add
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**3e. Remove now-unused imports:**
- `import { Checkbox } from '@/components/ui/checkbox'` — remove if only used in the old dialog
- `DocumentListItem` — already removed in Task 4

- [ ] **Step 4: Run all IndexDetailPage tests — confirm all pass**

```bash
npm run --prefix frontend test:run -- src/pages/IndexDetailPage.test.tsx 2>&1 | tail -10
```
Expected: all 5 tests pass.

- [ ] **Step 5: Run full frontend suite — verify no regressions**

```bash
npm run --prefix frontend test:run 2>&1 | tail -10
```
Expected: same pass/fail count as before Unit 5 (only the pre-existing `useParseRuns` timeout fails).

- [ ] **Step 6: TypeScript check**

```bash
npm run --prefix frontend build 2>&1 | grep "error TS" | head -10
```
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/IndexDetailPage.tsx frontend/src/pages/IndexDetailPage.test.tsx
git commit -m "feat(indexes): restore Add Documents dialog with ParsedDocumentPicker"
```

---

## Self-Review Against Spec

### Spec coverage

| Spec requirement | Covered by |
|---|---|
| Index detail "Documents" tab renamed "Parsed Documents" | Task 4, Step 3g |
| Columns: Source filename / Parse run / Parsed at / Status / Chunks | Task 4, Step 3g |
| `GET /indexes/{id}/parsed-documents` backend endpoint | Task 1 |
| `DELETE /indexes/{id}/parsed-documents/{parse_run_id}` backend endpoint | Task 2 |
| Frontend API `listIndexParsedDocuments` + `removeIndexParsedDocument` | Task 3 |
| `IndexParsedDocumentItem` type | Task 3 |
| Add Documents dialog uses `ParsedDocumentPicker` pre-filtered to index family | Task 5 |
| Add Documents calls `addParsedDocuments` + refreshes tab | Task 5, Step 3c |

### Missing from this unit (Unit 6 scope)
- `ALTER COLUMN index_documents.parse_run_id SET NOT NULL`
- Consider dropping denormalized `index_documents.document_id`
- Block chunking implementation (remove `ChunkingDispatcher.NotImplementedError`)
