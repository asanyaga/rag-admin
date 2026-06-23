# Source Documents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the existing `source_documents` table as a browsable tenant-level page in the UI, and rename the existing "Documents" section to "Project Documents".

**Architecture:** Add a `list_all` method to `SourceDocumentRepository` that joins with `documents` to compute per-source-document project reference counts. A new `GET /api/v1/source-documents` router endpoint serves this list. On the frontend, a new `SourceDocumentsPage` displays the list; navigation and routing are updated with a rename.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2 · React 18, TypeScript, shadcn/ui, Tailwind CSS, React Router v6, lucide-react

## Global Constraints

- All backend DB access is async (SQLAlchemy `AsyncSession`)
- Backend: data flow is router → repository (no service layer needed here — no business logic)
- Frontend: one hook per feature, one page per route
- shadcn/ui + Tailwind CSS for all UI; no new UI libraries
- camelCase field aliases in all Pydantic response schemas (matching the existing pattern in `backend/app/schemas/document.py`)
- Run backend tests with: `uv run python -m pytest -o "addopts=" <test_path> -v` from `backend/`
- Run frontend lint/build with: `npm run lint` and `npm run build` from `frontend/`

---

## File Map

**Create:**
- `backend/app/schemas/source_document.py` — `SourceDocumentResponse` Pydantic schema
- `backend/app/routers/source_documents.py` — `GET /api/v1/source-documents` endpoint
- `backend/tests/routers/test_source_documents_router.py` — router integration test
- `frontend/src/types/sourceDocument.ts` — `SourceDocument` TypeScript interface
- `frontend/src/api/sourceDocuments.ts` — `listSourceDocuments()` API call
- `frontend/src/hooks/useSourceDocuments.ts` — fetch hook
- `frontend/src/pages/SourceDocumentsPage.tsx` — new page

**Modify:**
- `backend/app/repositories/source_document_repository.py` — add `list_all()` method
- `backend/tests/repositories/test_source_document_repository.py` — add `list_all` tests
- `backend/app/main.py` — register new router
- `frontend/src/config/navigation.ts` — rename + add nav item
- `frontend/src/App.tsx` — add route, update breadcrumb
- `frontend/src/pages/DocumentsPage.tsx` — rename page heading

---

### Task 0: Create GitHub Issue

> Do this before writing any code.

- [ ] **Step 1: Create the issue**

```bash
gh issue create \
  --title "feat: source documents library page" \
  --body "## Acceptance Criteria

- [ ] \`GET /api/v1/source-documents\` returns all source documents with \`projectCount\`
- [ ] Source Documents page lists all source documents: filename, type, size, created date, projects count badge
- [ ] Empty state shown when no source documents exist
- [ ] 'Documents' nav item and page heading renamed to 'Project Documents'
- [ ] New 'Source Documents' nav item at /source-documents

## Spec
docs/superpowers/specs/2026-06-23-source-documents-design.md

## Plan
docs/superpowers/plans/2026-06-23-source-documents.md"
```

- [ ] **Step 2: Note the issue number** — you will reference it in commit messages as `#<N>`

---

### Task 1: Backend — repository, schema, router, registration

**Files:**
- Modify: `backend/app/repositories/source_document_repository.py`
- Create: `backend/app/schemas/source_document.py`
- Create: `backend/app/routers/source_documents.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/repositories/test_source_document_repository.py`
- Create: `backend/tests/routers/test_source_documents_router.py`

**Interfaces:**
- Produces: `SourceDocumentRepository.list_all() -> list[tuple[SourceDocument, int]]`
- Produces: `GET /api/v1/source-documents` → `list[SourceDocumentResponse]` (200)

- [ ] **Step 1: Write the repository test**

Add to `backend/tests/repositories/test_source_document_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_all_returns_empty_when_no_source_documents(repo: SourceDocumentRepository):
    result = await repo.list_all()
    assert result == []


@pytest.mark.asyncio
async def test_list_all_returns_source_documents_with_zero_project_count(repo: SourceDocumentRepository):
    await repo.create(sha256="a" * 64, storage_uri="local://a.pdf", filename="alpha.pdf")
    await repo.create(sha256="b" * 64, storage_uri="local://b.pdf", filename="beta.pdf")

    result = await repo.list_all()

    assert len(result) == 2
    filenames = {sd.filename for sd, _ in result}
    assert filenames == {"alpha.pdf", "beta.pdf"}
    for _, count in result:
        assert count == 0


@pytest.mark.asyncio
async def test_list_all_orders_by_created_at_desc(repo: SourceDocumentRepository):
    first = await repo.create(sha256="c" * 64, storage_uri="local://c.pdf", filename="first.pdf")
    second = await repo.create(sha256="d" * 64, storage_uri="local://d.pdf", filename="second.pdf")

    result = await repo.list_all()

    # Most recently created first
    assert result[0][0].id == second.id
    assert result[1][0].id == first.id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m pytest -o "addopts=" backend/tests/repositories/test_source_document_repository.py::test_list_all_returns_empty_when_no_source_documents -v
```

Expected: `AttributeError: 'SourceDocumentRepository' object has no attribute 'list_all'`

- [ ] **Step 3: Implement `list_all` in the repository**

In `backend/app/repositories/source_document_repository.py`, add these imports at the top:

```python
from sqlalchemy import func, distinct
from app.models.document import Document
```

Then add the method to `SourceDocumentRepository`:

```python
async def list_all(self) -> list[tuple[SourceDocument, int]]:
    """Return all source documents with the number of distinct projects referencing each."""
    stmt = (
        select(
            SourceDocument,
            func.count(distinct(Document.project_id)).label("project_count"),
        )
        .outerjoin(Document, Document.source_document_id == SourceDocument.id)
        .group_by(SourceDocument.id)
        .order_by(SourceDocument.created_at.desc())
    )
    result = await self.session.execute(stmt)
    return [(row.SourceDocument, row.project_count) for row in result]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run python -m pytest -o "addopts=" backend/tests/repositories/test_source_document_repository.py -v
```

Expected: all repository tests pass including the three new ones.

- [ ] **Step 5: Write the Pydantic schema**

Create `backend/app/schemas/source_document.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceDocumentResponse(BaseModel):
    id: UUID
    sha256: str
    filename: str | None
    mime_type: str | None = Field(None, alias="mimeType")
    byte_size: int | None = Field(None, alias="byteSize")
    created_at: datetime = Field(..., alias="createdAt")
    project_count: int = Field(..., alias="projectCount")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 6: Write the router integration test**

Create `backend/tests/routers/test_source_documents_router.py`:

```python
"""Integration tests for GET /source-documents."""
import pytest
from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient, email: str = "src@example.com") -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Src User",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_list_source_documents_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/source-documents")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_source_documents_returns_empty_list(client: AsyncClient):
    token = await _signup_and_login(client)
    resp = await client.get(
        "/api/v1/source-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_source_documents_returns_uploaded_files(client: AsyncClient):
    token = await _signup_and_login(client, "src2@example.com")

    # Create a project
    proj = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Src Test Project"},
    )
    project_id = proj.json()["id"]

    # Upload a document (creates a source_document)
    await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "title": "My Doc", "parser_type": "simple"},
        files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
    )

    resp = await client.get(
        "/api/v1/source-documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["filename"] == "test.pdf"
    assert item["projectCount"] == 1
    assert "id" in item
    assert "sha256" in item
    assert "createdAt" in item
```

- [ ] **Step 7: Run router test to verify it fails**

```bash
uv run python -m pytest -o "addopts=" backend/tests/routers/test_source_documents_router.py -v
```

Expected: tests fail because the router doesn't exist yet (404 or import error).

- [ ] **Step 8: Create the router**

Create `backend/app/routers/source_documents.py`:

```python
"""Source Documents API router."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.source_document import SourceDocumentResponse

router = APIRouter(prefix="/source-documents", tags=["source-documents"])


@router.get("", response_model=list[SourceDocumentResponse])
async def list_source_documents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[SourceDocumentResponse]:
    """List all source documents at tenant level with project reference counts."""
    repo = SourceDocumentRepository(db)
    rows = await repo.list_all()
    return [
        SourceDocumentResponse(
            id=sd.id,
            sha256=sd.sha256,
            filename=sd.filename,
            mime_type=sd.mime_type,
            byte_size=sd.byte_size,
            created_at=sd.created_at,
            project_count=count,
        )
        for sd, count in rows
    ]
```

- [ ] **Step 9: Register the router in `main.py`**

In `backend/app/main.py`, add the import to the existing imports line:

```python
from app.routers import auth, oauth, otel_proxy, projects, users, documents, folders, indexes, provider_keys, golden_sets, eval_runs, experiments, parse_runs, parse_run_configs, parsed_documents, extraction, extraction_ground_truth, extraction_eval, agent, data_stores, export_mappings, classification, source_documents
```

Then add the registration after the existing `app.include_router(data_stores.router, ...)` line:

```python
app.include_router(source_documents.router, prefix="/api/v1")
```

- [ ] **Step 10: Run all router tests to verify they pass**

```bash
uv run python -m pytest -o "addopts=" backend/tests/routers/test_source_documents_router.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 11: Commit**

```bash
git add backend/app/repositories/source_document_repository.py \
        backend/app/schemas/source_document.py \
        backend/app/routers/source_documents.py \
        backend/app/main.py \
        backend/tests/repositories/test_source_document_repository.py \
        backend/tests/routers/test_source_documents_router.py
git commit -m "feat: add GET /source-documents endpoint with project count"
```

---

### Task 2: Frontend — types, API, hook, page, nav, routing, rename

**Files:**
- Create: `frontend/src/types/sourceDocument.ts`
- Create: `frontend/src/api/sourceDocuments.ts`
- Create: `frontend/src/hooks/useSourceDocuments.ts`
- Create: `frontend/src/pages/SourceDocumentsPage.tsx`
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/DocumentsPage.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/source-documents` → `SourceDocument[]`
- Produces: `useSourceDocuments()` → `{ sourceDocuments, isLoading, error, refresh }`

- [ ] **Step 1: Create the TypeScript type**

Create `frontend/src/types/sourceDocument.ts`:

```typescript
export interface SourceDocument {
  id: string
  sha256: string
  filename: string | null
  mimeType: string | null
  byteSize: number | null
  createdAt: string
  projectCount: number
}
```

- [ ] **Step 2: Create the API function**

Create `frontend/src/api/sourceDocuments.ts`:

```typescript
import apiClient from './client'
import { SourceDocument } from '@/types/sourceDocument'

export async function listSourceDocuments(): Promise<SourceDocument[]> {
  const response = await apiClient.get<SourceDocument[]>('/source-documents')
  return response.data
}
```

- [ ] **Step 3: Create the hook**

Create `frontend/src/hooks/useSourceDocuments.ts`:

```typescript
import { useState, useEffect, useCallback } from 'react'
import { SourceDocument } from '@/types/sourceDocument'
import * as sourceDocumentsApi from '@/api/sourceDocuments'

interface UseSourceDocumentsReturn {
  sourceDocuments: SourceDocument[]
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useSourceDocuments(): UseSourceDocumentsReturn {
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await sourceDocumentsApi.listSourceDocuments()
      setSourceDocuments(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load source documents')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { sourceDocuments, isLoading, error, refresh: fetch }
}
```

- [ ] **Step 4: Create the Source Documents page**

Create `frontend/src/pages/SourceDocumentsPage.tsx`:

```tsx
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function SourceDocumentsPage(): JSX.Element {
  const { sourceDocuments, isLoading, error } = useSourceDocuments()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Source Documents</h1>
        <p className="text-muted-foreground mt-1">
          Tenant-wide document library. Files here persist even when project documents are deleted.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : sourceDocuments.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="font-medium">No source documents yet</p>
          <p className="text-sm mt-1">
            Upload documents via Project Documents to populate this library.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filename</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Projects</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sourceDocuments.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell className="font-medium">{doc.filename ?? '—'}</TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {doc.mimeType ?? '—'}
                </TableCell>
                <TableCell>{formatBytes(doc.byteSize)}</TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {new Date(doc.createdAt).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{doc.projectCount}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Update navigation**

In `frontend/src/config/navigation.ts`:

Replace the `Library` import — add it to the existing import block:

```typescript
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  Database,
  BarChart3,
  Settings,
  FileSearch,
  Bot,
  HardDrive,
  ArrowUpFromLine,
  Tags,
  Library,
  type LucideIcon,
} from 'lucide-react'
```

Then update the navigation items array — rename Documents and add Source Documents after it:

```typescript
export const navigationItems: readonly NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard, activeColor: 'border-l-primary' },
  { label: 'Projects', href: '/projects', icon: FolderKanban, activeColor: 'border-l-violet-500' },
  { label: 'Project Documents', href: '/documents', icon: FileText, activeColor: 'border-l-blue-500' },
  { label: 'Source Documents', href: '/source-documents', icon: Library, activeColor: 'border-l-indigo-500' },
  { label: 'Index', href: '/index', icon: Database, activeColor: 'border-l-teal-500' },
  { label: 'Extraction', href: '/extraction', icon: FileSearch, activeColor: 'border-l-orange-500' },
  { label: 'Classify', href: '/classify', icon: Tags, activeColor: 'border-l-pink-500' },
  { label: 'Data Stores', href: '/data-stores', icon: HardDrive, activeColor: 'border-l-cyan-500' },
  { label: 'Export', href: '/export', icon: ArrowUpFromLine, activeColor: 'border-l-emerald-500' },
  {
    label: 'Evaluation',
    href: '',
    icon: BarChart3,
    activeColor: 'border-l-amber-500',
    children: [
      { label: 'Retrieval', href: '/evaluation/retrieval' },
      { label: 'Extraction', href: '/evaluation/extraction' },
    ],
  },
  { label: 'Agents', href: '/agent', icon: Bot, activeColor: 'border-l-purple-500' },
  { label: 'Settings', href: '/settings', icon: Settings, activeColor: 'border-l-gray-400' },
]
```

- [ ] **Step 6: Add the route and update the breadcrumb in App.tsx**

In `frontend/src/App.tsx`, add the import:

```typescript
import SourceDocumentsPage from './pages/SourceDocumentsPage'
```

Update the documents route breadcrumb (find the existing route and update `handle`):

```typescript
{
  path: 'documents',
  element: <DocumentsPage />,
  handle: { breadcrumb: 'Project Documents' },
},
```

Add the new route directly after the documents route:

```typescript
{
  path: 'source-documents',
  element: <SourceDocumentsPage />,
  handle: { breadcrumb: 'Source Documents' },
},
```

- [ ] **Step 7: Rename the heading in DocumentsPage**

In `frontend/src/pages/DocumentsPage.tsx`, line 280, change:

```tsx
<h1 className="text-3xl font-bold">Documents</h1>
```

to:

```tsx
<h1 className="text-3xl font-bold">Project Documents</h1>
```

- [ ] **Step 8: Run frontend lint and build**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: no errors. Fix any TypeScript or lint errors before continuing.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/sourceDocument.ts \
        frontend/src/api/sourceDocuments.ts \
        frontend/src/hooks/useSourceDocuments.ts \
        frontend/src/pages/SourceDocumentsPage.tsx \
        frontend/src/config/navigation.ts \
        frontend/src/App.tsx \
        frontend/src/pages/DocumentsPage.tsx
git commit -m "feat: add Source Documents page and rename Documents to Project Documents"
```

---

## Manual Verification

After both tasks complete, verify in the browser:

1. Sign in and navigate — confirm sidebar shows "Project Documents" and "Source Documents"
2. Go to Project Documents — confirm page heading reads "Project Documents"
3. Upload a PDF via Project Documents
4. Navigate to Source Documents — confirm the uploaded file appears in the table with filename, size, type, created date, and "Projects: 1" badge
5. Delete the project document — navigate back to Source Documents and confirm the source document row is still present with "Projects: 0"
6. Navigate to `/source-documents` with no uploads — confirm the empty state message is shown
