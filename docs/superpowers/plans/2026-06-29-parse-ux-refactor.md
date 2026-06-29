# Parse UX Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Parse page to a two-panel layout, rename nav items and routes, add "Add from Source" capability with a new backend endpoint, and build the `SourceDocumentBrowser` component.

**Architecture:** The Parse page (`DocumentsPage`) is refactored in-place: the folder sidebar + table + Sheet are replaced by a two-column layout with a document list on the left and an inline parse viewer on the right. A new `SourceDocumentBrowser` component opens as a Sheet from the left panel's "From Source" button. The backend gets one new endpoint that creates a project Document from an existing SourceDocument and kicks off parsing.

**Tech Stack:** React 18, TypeScript, shadcn/ui, Tailwind, React Router v6 (frontend); FastAPI, SQLAlchemy async, Pydantic v2, pytest-asyncio (backend).

## Global Constraints

- All frontend commands run from `frontend/` directory using `npm run ...`
- All backend commands run from `backend/` directory using `uv run ...`
- Backend test command: `uv run python -m pytest -o "addopts=" tests/path/to/test.py -v`
- Frontend lint: `npm run lint`
- Frontend build: `npm run build`
- Never use `cd X && Y` compound commands — use absolute paths or per-tool working directory flags
- Follow existing data-flow pattern: router → service → repository
- shadcn/ui components with Tailwind for all UI
- No new comments unless the WHY is non-obvious

---

## File Map

**Modified:**
- `frontend/src/config/navigation.ts` — reorder items, rename labels + hrefs
- `frontend/src/App.tsx` — update route paths + breadcrumb handles
- `frontend/src/pages/DocumentsPage.tsx` — full two-panel refactor (rename stays as-is, file kept)
- `frontend/src/pages/ExtractionPage.tsx` — h1 heading change only
- `frontend/src/pages/IndexPage.tsx` — one navigate() call-site update
- `frontend/src/pages/ParseRunDetailPage.tsx` — two navigate() call-site updates
- `frontend/src/api/documents.ts` — add `addDocumentFromSource` function
- `frontend/src/hooks/useDocuments.ts` — add `addDocumentFromSource` method
- `backend/app/schemas/document.py` — add `DocumentFromSourceRequest`
- `backend/app/services/document_service.py` — add `add_from_source` method
- `backend/app/routers/documents.py` — add `/from-source` route

**Created:**
- `frontend/src/components/documents/SourceDocumentBrowser.tsx` — new Sheet component
- `backend/tests/routers/test_documents_from_source_router.py` — integration tests

---

## Task 1: Nav & Route Rename

**Files:**
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/DocumentsPage.tsx` (h1 only)
- Modify: `frontend/src/pages/ExtractionPage.tsx` (h1 only)
- Modify: `frontend/src/pages/IndexPage.tsx` (navigate call-site)
- Modify: `frontend/src/pages/ParseRunDetailPage.tsx` (navigate call-sites)

**Interfaces:**
- Produces: `/parse` route serving `DocumentsPage`, `/extract` route serving `ExtractionPage`

- [ ] **Step 1: Update navigation.ts**

Replace the entire `navigationItems` array in `frontend/src/config/navigation.ts`:

```typescript
export const navigationItems: readonly NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard, activeColor: 'border-l-primary' },
  { label: 'Projects', href: '/projects', icon: FolderKanban, activeColor: 'border-l-violet-500' },
  { label: 'Source Documents', href: '/source-documents', icon: Library, activeColor: 'border-l-indigo-500' },
  { label: 'Parse', href: '/parse', icon: FileText, activeColor: 'border-l-blue-500' },
  { label: 'Classify', href: '/classify', icon: Tags, activeColor: 'border-l-pink-500' },
  { label: 'Extract', href: '/extract', icon: FileSearch, activeColor: 'border-l-orange-500' },
  { label: 'Index', href: '/index', icon: Database, activeColor: 'border-l-teal-500' },
  { label: 'Data Stores', href: '/data-stores', icon: HardDrive, activeColor: 'border-l-cyan-500' },
  { label: 'Export', href: '/export', icon: ArrowUpFromLine, activeColor: 'border-l-emerald-500' },
  { label: 'Agents', href: '/agent', icon: Bot, activeColor: 'border-l-purple-500' },
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
  { label: 'Settings', href: '/settings', icon: Settings, activeColor: 'border-l-gray-400' },
]
```

- [ ] **Step 2: Update App.tsx routes**

In `frontend/src/App.tsx`, change three route entries:

```typescript
// Change path 'documents' → 'parse'
{
  path: 'parse',
  element: <DocumentsPage />,
  handle: { breadcrumb: 'Parse' },
},
// Change path 'documents/:documentId/runs/:runId' → 'parse/:documentId/runs/:runId'
{
  path: 'parse/:documentId/runs/:runId',
  element: <ParseRunDetailPage />,
  handle: { breadcrumb: 'Parse Run' },
},
// Change path 'extraction' → 'extract'
{
  path: 'extract',
  element: <ExtractionPage />,
  handle: { breadcrumb: 'Extract' },
},
```

- [ ] **Step 3: Update navigate() call-sites**

In `frontend/src/pages/IndexPage.tsx` line 136:
```typescript
onClick={() => navigate('/parse')}
```

In `frontend/src/pages/ParseRunDetailPage.tsx` — update both occurrences of `navigate('/documents')` to `navigate('/parse')`.

In `frontend/src/pages/DocumentsPage.tsx` — the `handleExtract` function navigates to `/extraction`. Update to `/extract`:
```typescript
const handleExtract = (documentId: string) => {
  navigate(`/extract?documentId=${documentId}`)
}
```

- [ ] **Step 4: Update page headings**

In `frontend/src/pages/DocumentsPage.tsx` line 226, change:
```tsx
<h1 className="text-3xl font-bold">Project Documents</h1>
```
to:
```tsx
<h1 className="text-3xl font-bold">Parse</h1>
```

In `frontend/src/pages/ExtractionPage.tsx` line 182, change:
```tsx
<h1 className="text-lg font-semibold">Extraction</h1>
```
to:
```tsx
<h1 className="text-lg font-semibold">Extract</h1>
```

- [ ] **Step 5: Lint and build**

Run: `npm run lint --prefix frontend`
Run: `npm run build --prefix frontend`

Expected: no errors. If TypeScript errors appear for missing routes, they are import-related — fix them before continuing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/config/navigation.ts frontend/src/App.tsx frontend/src/pages/DocumentsPage.tsx frontend/src/pages/ExtractionPage.tsx frontend/src/pages/IndexPage.tsx frontend/src/pages/ParseRunDetailPage.tsx
git commit -m "feat: rename nav items and routes (Project Documents→Parse, Extraction→Extract)"
```

---

## Task 2: Parse Page Two-Panel Refactor

**Files:**
- Modify: `frontend/src/pages/DocumentsPage.tsx` — full layout refactor

**Interfaces:**
- Consumes: `useDocuments`, `useFolders`, `useParseRuns` hooks (unchanged signatures)
- Consumes: `DocumentProbePanel`, `RunTimeline`, `ParsedDocumentViewer`, `DocumentTextViewer`, `ReParseDialog`, `DocumentUploadDialog`, `DocumentEditDialog`, `DocumentDeleteDialog`, `DocumentStatusBadge`, `FolderEditPopover` components (all unchanged)
- Produces: same `/parse` route, new two-panel layout

- [ ] **Step 1: Replace DocumentsPage layout**

Rewrite `frontend/src/pages/DocumentsPage.tsx` with the two-panel layout. The state management and handlers stay the same — only the JSX structure changes. Remove `BulkActionBar`, `FolderSidebar`, `Sheet`/`SheetContent`/`SheetHeader`/`SheetTitle` imports. Add `Select`/`SelectContent`/`SelectItem`/`SelectTrigger`/`SelectValue`, `DropdownMenu`/`DropdownMenuContent`/`DropdownMenuItem`/`DropdownMenuTrigger`, `Settings`, `MoreHorizontal`, `Pencil`, `Trash2`, `Download` imports.

Remove these state variables (no longer needed):
- `selectedIds` / `setSelectedIds` (bulk ops gone)

Keep all other state and handlers. Add one new state variable:
```typescript
const [documentSearch, setDocumentSearch] = useState('')
```

The filtered document list for the left panel:
```typescript
const filteredDocuments = documents.filter((doc) => {
  const matchesFolder = selectedFolderId === null || doc.folderId === selectedFolderId
  const matchesSearch = doc.title.toLowerCase().includes(documentSearch.toLowerCase())
  return matchesFolder && matchesSearch
})
```

Replace the entire return statement JSX:

```tsx
return (
  <div className="-m-6 flex h-[calc(100vh-3.5rem)]">
    {/* Left panel */}
    <div className="w-72 border-r shrink-0 flex flex-col">
      {/* Folder filter + management */}
      <div className="p-3 border-b flex items-center gap-2">
        <Select
          value={selectedFolderId ?? '__all__'}
          onValueChange={(v) => {
            setSelectedFolderId(v === '__all__' ? null : v)
            setViewDocumentId(null)
          }}
        >
          <SelectTrigger className="h-8 text-sm flex-1">
            <SelectValue placeholder="All folders" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All folders</SelectItem>
            {folders.map((f) => (
              <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <FolderEditPopover
          trigger={
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <Settings className="h-3.5 w-3.5" />
            </Button>
          }
          onSave={handleCreateFolder}
        />
      </div>

      {/* Search */}
      <div className="p-3 border-b">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={documentSearch}
            onChange={(e) => setDocumentSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
      </div>

      {/* Document list */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading ? (
            <div className="space-y-2 p-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : filteredDocuments.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              {documentSearch ? 'No documents match your search' : 'No documents yet'}
            </p>
          ) : (
            filteredDocuments.map((doc) => (
              <button
                key={doc.id}
                onClick={() => setViewDocumentId(doc.id)}
                className={cn(
                  'w-full text-left rounded-md px-3 py-2.5 mb-1 transition-colors',
                  'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  viewDocumentId === doc.id && 'bg-muted'
                )}
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="text-sm truncate flex-1">{doc.title}</span>
                  <DocumentStatusBadge status={doc.status} />
                </div>
              </button>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Actions */}
      <div className="p-3 border-t space-y-2">
        <Button
          variant="outline"
          className="w-full"
          size="sm"
          onClick={() => setUploadDialogOpen(true)}
        >
          <Plus className="h-4 w-4 mr-2" />
          Upload New
        </Button>
        <Button
          variant="outline"
          className="w-full"
          size="sm"
          onClick={() => setFromSourceOpen(true)}
        >
          <Library className="h-4 w-4 mr-2" />
          From Source
        </Button>
      </div>
    </div>

    {/* Right panel */}
    <div className="flex-1 overflow-y-auto">
      {!viewDocumentId ? (
        <div className="flex items-center justify-center h-full text-muted-foreground">
          <p className="text-sm">Select a document to view parse runs</p>
        </div>
      ) : (
        <div className="p-6 space-y-6 max-w-3xl">
          {/* Document header with actions */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">{viewedDocument?.title}</h2>
              {viewedDocument && (
                <p className="text-xs text-muted-foreground">
                  {new Date(viewedDocument.createdAt).toLocaleDateString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setReparseDialogOpen(true)}
              >
                <RotateCw className="h-4 w-4 mr-2" />
                Re-parse
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={() => viewedDocument && handleEdit(viewedDocument.id)}
                  >
                    <Pencil className="h-4 w-4 mr-2" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => viewedDocument && handleDownload(viewedDocument.id, viewedDocument.title)}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => viewedDocument && handleDelete(viewedDocument.id)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          <DocumentProbePanel documentId={viewDocumentId} />

          <section>
            <h3 className="text-sm font-medium mb-2">Parse runs</h3>
            <RunTimeline
              documentId={viewDocumentId}
              runs={parseRuns}
              onRunDeleted={refreshParseRuns}
            />
          </section>

          <ParsedDocumentViewer documentId={viewDocumentId} />

          {viewedDocument && (
            <DocumentTextViewer
              documentId={viewDocumentId}
              documentTitle={viewedDocument.title}
              onDownload={() => handleDownload(viewDocumentId, viewedDocument.title)}
            />
          )}
        </div>
      )}
    </div>

    {/* Dialogs — unchanged from before */}
    <DocumentEditDialog
      document={selectedDocument}
      open={editDialogOpen}
      onOpenChange={setEditDialogOpen}
      onSave={handleEditSave}
      folders={folders}
    />
    <DocumentDeleteDialog
      document={selectedDocument}
      open={deleteDialogOpen}
      onOpenChange={setDeleteDialogOpen}
      onConfirm={handleDeleteConfirm}
    />
    <DocumentUploadDialog
      open={uploadDialogOpen}
      onOpenChange={setUploadDialogOpen}
      projectId={currentProject.id}
      onUpload={uploadDocument}
      documents={documents}
      folders={folders}
      initialFolderId={selectedFolderId}
    />
    <ReParseDialog
      open={reparseDialogOpen}
      onOpenChange={setReparseDialogOpen}
      onReparse={handleReparse}
    />
  </div>
)
```

Add the missing state variable and update imports at the top of the file. Add `fromSourceOpen` state:
```typescript
const [fromSourceOpen, setFromSourceOpen] = useState(false)
```

Add these imports:
```typescript
import { Search, Library } from 'lucide-react'  // add to existing lucide import
import { MoreHorizontal, Pencil, Trash2, Download } from 'lucide-react'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { DocumentStatusBadge } from '@/components/documents/DocumentStatusBadge'
import { cn } from '@/lib/utils'
```

Remove these imports (no longer used):
```typescript
// Remove: FolderSidebar, BulkActionBar
// Remove: Sheet, SheetContent, SheetHeader, SheetTitle
// Remove: selectedIds, setSelectedIds, handleToggleSelect, handleToggleSelectAll, handleBulkMove
```

Also remove the `selectedIds` state, `handleToggleSelect`, `handleToggleSelectAll`, `handleBulkMove` handlers from the component body since `BulkActionBar` is gone.

Also remove `FolderEditPopover` usage from `FolderSidebar` — now import `FolderEditPopover` directly:
```typescript
import { FolderEditPopover } from '@/components/documents/FolderEditPopover'
```

Note: folder create/edit/delete handlers (`handleCreateFolder`, `handleUpdateFolder`, `handleDeleteFolder`) stay in the component. The gear icon button opens a `FolderEditPopover` for creating folders. For editing individual folders, the folder dropdown can include an edit option per folder — but for MVP, the gear creates new folders only. Editing/deleting individual folders is deferred (the `FolderEditPopover` can be wired later; the handlers remain in the component).

- [ ] **Step 2: Lint and verify build**

Run: `npm run lint --prefix frontend`
Run: `npm run build --prefix frontend`

Fix any TypeScript errors before proceeding.

- [ ] **Step 3: Smoke test in browser**

Start the dev server: `npm run dev --prefix frontend`

Verify:
- `/parse` shows two-panel layout
- Left panel: folder dropdown, search, document list, Upload New and From Source buttons
- Clicking a document loads the right panel with parse runs, probe panel, document viewer
- Document actions menu (⋯) shows Edit, Download, Delete — clicking each opens the correct dialog
- Re-parse button opens ReParseDialog
- Upload New opens DocumentUploadDialog
- From Source button doesn't crash (can be a no-op until Task 4)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DocumentsPage.tsx
git commit -m "feat(parse): two-panel layout with inline parse viewer"
```

---

## Task 3: Backend — from-source endpoint

**Files:**
- Modify: `backend/app/schemas/document.py` — add `DocumentFromSourceRequest`
- Modify: `backend/app/services/document_service.py` — add `add_from_source` method
- Modify: `backend/app/routers/documents.py` — add `/from-source` route
- Create: `backend/tests/routers/test_documents_from_source_router.py`

**Interfaces:**
- Produces: `POST /api/v1/documents/from-source` accepting `{ project_id, source_document_id, parser_type, parse_config }`, returning `DocumentResponse` with status 202

- [ ] **Step 1: Write the failing test**

Create `backend/tests/routers/test_documents_from_source_router.py`:

```python
"""Integration tests for POST /documents/from-source."""
import pytest
from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


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


async def _create_project(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
    )
    return resp.json()["id"]


async def _upload_doc(client: AsyncClient, token: str, project_id: str) -> dict:
    """Upload a document to get a source_document_id created."""
    resp = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "title": "seed.pdf", "parser_type": "simple"},
        files=[("file", ("seed.pdf", MINIMAL_PDF, "application/pdf"))],
    )
    return resp.json()


@pytest.mark.asyncio
async def test_from_source_returns_202(client: AsyncClient):
    token = await _signup_and_login(client, "fromsource1@example.com")
    project_a = await _create_project(client, token, "Project A")
    project_b = await _create_project(client, token, "Project B")

    # Upload to project A — this creates a SourceDocument
    doc_a = await _upload_doc(client, token, project_a)
    source_document_id = doc_a["sourceDocumentId"]
    assert source_document_id is not None

    # Add that source document to project B without re-uploading
    resp = await client.post(
        "/api/v1/documents/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_b,
            "source_document_id": source_document_id,
            "parser_type": "simple",
        },
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "processing"
    assert data["sourceDocumentId"] == source_document_id
    assert data["projectId"] == project_b


@pytest.mark.asyncio
async def test_from_source_404_on_bad_source_document(client: AsyncClient):
    token = await _signup_and_login(client, "fromsource2@example.com")
    project_id = await _create_project(client, token, "Project C")

    resp = await client.post(
        "/api/v1/documents/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_id,
            "source_document_id": "00000000-0000-0000-0000-000000000000",
            "parser_type": "simple",
        },
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_from_source_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/documents/from-source",
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "source_document_id": "00000000-0000-0000-0000-000000000000",
            "parser_type": "simple",
        },
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run python -m pytest -o "addopts=" backend/tests/routers/test_documents_from_source_router.py -v
```

Expected: all 3 tests FAIL with 404 or connection errors (route doesn't exist yet).

- [ ] **Step 3: Add schema to document.py**

Add to `backend/app/schemas/document.py` after the existing `DocumentCreate` class:

```python
class DocumentFromSourceRequest(PydanticBaseModel):
    """Request body for adding a source document to a project."""
    project_id: UUID
    source_document_id: UUID
    parser_type: str = "simple"
    parse_config: dict | None = None
```

- [ ] **Step 4: Add service method**

Add to `backend/app/services/document_service.py` inside the `DocumentService` class, after `initiate_upload`:

```python
async def add_from_source(
    self,
    user_id: UUID,
    project_id: UUID,
    source_document_id: UUID,
    source_doc_filename: str | None,
    source_doc_storage_uri: str,
    source_doc_sha256: str,
    source_doc_byte_size: int | None,
    source_doc_mime_type: str | None,
) -> DocumentResponse:
    """Create a project Document from an existing SourceDocument (no file transfer).

    The caller is responsible for kicking off parse as a background task.
    """
    project = await self.project_repo.get_by_id(project_id, user_id)
    if not project:
        raise NotFoundError(f"Project {project_id} not found")

    source_metadata = {
        "filename": source_doc_filename,
        "file_path": source_doc_storage_uri,
        "file_size": source_doc_byte_size,
        "mime_type": source_doc_mime_type,
        "checksum": source_doc_sha256,
    }
    try:
        document = await self.document_repo.create(
            project_id=project_id,
            user_id=user_id,
            source_type="upload",
            source_identifier=source_doc_sha256,
            title=source_doc_filename or "Untitled",
            description=None,
            source_metadata=source_metadata,
            source_document_id=source_document_id,
        )
    except IntegrityError:
        raise ConflictError("This source document is already in this project")
    return DocumentResponse.model_validate(document)
```

The `IntegrityError` import is already present at the top of `document_service.py`.

- [ ] **Step 5: Add router endpoint**

Add to `backend/app/routers/documents.py`, after the bulk upload endpoint. First add the import at the top of the file:

```python
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    BulkUploadItemResponse,
    BulkUploadResponse,
    BulkMoveRequest,
    BulkMoveResponse,
    DocumentFromSourceRequest,  # add this
)
```

Then add the endpoint:

```python
@router.post(
    "/from-source",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a source document to a project and parse it",
    description="Links an existing source document into a project without re-uploading "
                "the file, then kicks off a background parse run.",
)
async def add_document_from_source(
    body: DocumentFromSourceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Link source document to project and initiate parsing."""
    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, body.parser_type
    )

    source_doc_repo = SourceDocumentRepository(db)
    source_doc = await source_doc_repo.get(body.source_document_id)
    if source_doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found")

    try:
        document = await document_service.add_from_source(
            user_id=current_user.id,
            project_id=body.project_id,
            source_document_id=body.source_document_id,
            source_doc_filename=source_doc.filename,
            source_doc_storage_uri=source_doc.storage_uri,
            source_doc_sha256=source_doc.sha256,
            source_doc_byte_size=source_doc.byte_size,
            source_doc_mime_type=source_doc.mime_type,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if document.source_document_id is not None:
        config = dict(body.parse_config or {})
        representation_kind = config.pop("representation_kind", "extract_rich")
        config["parser"] = body.parser_type
        background_tasks.add_task(
            process_cdm_parsing,
            document_id=document.id,
            source_document_id=document.source_document_id,
            project_id=body.project_id,
            representation_kind=representation_kind,
            config=config,
            storage_service=storage_service,
            llamaparse_api_key=llamaparse_api_key,
            landingai_api_key=landingai_api_key,
        )

    return document
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
uv run python -m pytest -o "addopts=" backend/tests/routers/test_documents_from_source_router.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Run the full backend test suite**

```bash
uv run python -m pytest -o "addopts=" backend/tests/ -v --tb=short
```

Expected: no regressions. Fix any failures before committing.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/document.py backend/app/services/document_service.py backend/app/routers/documents.py backend/tests/routers/test_documents_from_source_router.py
git commit -m "feat(parse): add POST /documents/from-source endpoint"
```

---

## Task 4: SourceDocumentBrowser component + API wiring

**Files:**
- Modify: `frontend/src/api/documents.ts` — add `addDocumentFromSource`
- Modify: `frontend/src/hooks/useDocuments.ts` — add `addDocumentFromSource` method
- Create: `frontend/src/components/documents/SourceDocumentBrowser.tsx`
- Modify: `frontend/src/pages/DocumentsPage.tsx` — wire SourceDocumentBrowser

**Interfaces:**
- Consumes: `POST /api/v1/documents/from-source` (from Task 3)
- Consumes: `useSourceDocuments` hook (existing)
- Consumes: `ParseMethodSelector` + parser config components (existing, same as ReParseDialog)
- Produces: `SourceDocumentBrowser` component props:
  ```typescript
  interface SourceDocumentBrowserProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    projectId: string
    existingSourceDocumentIds: Set<string>
    onAdded: (documentId: string) => void
  }
  ```

- [ ] **Step 1: Add API function**

Add to `frontend/src/api/documents.ts`:

```typescript
export interface AddFromSourceRequest {
  projectId: string
  sourceDocumentId: string
  parserType: string
  parseConfig?: Record<string, unknown>
}

export async function addDocumentFromSource(
  data: AddFromSourceRequest,
): Promise<Document> {
  const response = await apiClient.post<Document>('/documents/from-source', {
    project_id: data.projectId,
    source_document_id: data.sourceDocumentId,
    parser_type: data.parserType,
    parse_config: data.parseConfig,
  })
  return response.data
}
```

Check the existing import of `Document` type in `documents.ts` — if it's not imported, add:
```typescript
import type { Document } from '@/types/document'
```

- [ ] **Step 2: Add hook method**

Add `addDocumentFromSource` to `useDocuments.ts`. In the `UseDocumentsReturn` interface, add:
```typescript
addDocumentFromSource: (data: AddFromSourceRequest) => Promise<Document>
```

Add the import at the top:
```typescript
import { type AddFromSourceRequest } from '@/api/documents'
```

Add the method implementation inside `useDocuments`, after `uploadDocument`:

```typescript
const addDocumentFromSource = useCallback(
  async (data: AddFromSourceRequest): Promise<Document> => {
    const newDocument = await documentsApi.addDocumentFromSource(data)
    setDocuments((prev) => [
      {
        id: newDocument.id,
        projectId: newDocument.projectId,
        folderId: newDocument.folderId,
        sourceType: newDocument.sourceType,
        title: newDocument.title,
        description: newDocument.description,
        status: newDocument.status,
        statusMessage: newDocument.statusMessage,
        createdAt: newDocument.createdAt,
        updatedAt: newDocument.updatedAt,
      },
      ...prev,
    ])
    if (newDocument.status === 'processing') {
      startPollingRef.current?.(newDocument.id)
    }
    return newDocument
  },
  [],
)
```

Add `addDocumentFromSource` to the return object of `useDocuments`.

- [ ] **Step 3: Create SourceDocumentBrowser**

Create `frontend/src/components/documents/SourceDocumentBrowser.tsx`:

```tsx
import { useState } from 'react'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import type { ParseConfig } from '@/types/parsing'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Search, FileText, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface SourceDocumentBrowserProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  existingSourceDocumentIds: Set<string>
  onAdd: (sourceDocumentId: string, parserType: string, parseConfig?: ParseConfig) => Promise<void>
}

export function SourceDocumentBrowser({
  open,
  onOpenChange,
  existingSourceDocumentIds,
  onAdd,
}: SourceDocumentBrowserProps) {
  const { sourceDocuments, isLoading } = useSourceDocuments()
  const [search, setSearch] = useState('')
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [parserType, setParserType] = useState('simple')
  const [parseConfig, setParseConfig] = useState<ParseConfig>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const available = sourceDocuments.filter(
    (sd) =>
      !existingSourceDocumentIds.has(sd.id) &&
      (sd.filename?.toLowerCase().includes(search.toLowerCase()) ?? true),
  )

  const handleAdd = async () => {
    if (!selectedSourceId) return
    setIsSubmitting(true)
    try {
      await onAdd(
        selectedSourceId,
        parserType,
        Object.keys(parseConfig).length ? parseConfig : undefined,
      )
      onOpenChange(false)
      setSelectedSourceId(null)
      setSearch('')
    } catch (err) {
      console.error('Failed to add from source', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg flex flex-col p-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle>Add from Source</SheetTitle>
        </SheetHeader>

        {/* Search */}
        <div className="px-4 py-3 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search source documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </div>

        {/* Source doc list */}
        <ScrollArea className="flex-1">
          <div className="p-3 space-y-1">
            {isLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
              </div>
            ) : available.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {search ? 'No source documents match your search' : 'All source documents are already in this project'}
              </p>
            ) : (
              available.map((sd) => (
                <button
                  key={sd.id}
                  onClick={() => setSelectedSourceId(sd.id)}
                  className={cn(
                    'w-full text-left rounded-md px-3 py-2.5 transition-colors',
                    'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    selectedSourceId === sd.id && 'bg-muted ring-2 ring-ring',
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate flex-1">{sd.filename ?? 'Untitled'}</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 shrink-0">
                      {formatBytes(sd.byteSize)}
                    </Badge>
                  </div>
                </button>
              ))
            )}
          </div>
        </ScrollArea>

        {/* Parse config */}
        <div className="px-4 py-4 border-t space-y-3">
          <ParseMethodSelector
            parserType={parserType}
            config={parseConfig}
            onParserTypeChange={(type, defaultConfig) => {
              setParserType(type)
              setParseConfig(defaultConfig)
            }}
            onConfigChange={setParseConfig}
          />
        </div>

        {/* Footer */}
        <div className="px-4 py-4 border-t flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            onClick={handleAdd}
            disabled={!selectedSourceId || isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Adding...
              </>
            ) : (
              'Add & Parse'
            )}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

Check `ParseMethodSelector`'s actual prop names before committing — open `frontend/src/components/documents/ParseMethodSelector.tsx` and match props exactly. If the interface differs, adjust the props in `SourceDocumentBrowser` accordingly.

- [ ] **Step 4: Wire SourceDocumentBrowser into ParsePage**

In `frontend/src/pages/DocumentsPage.tsx`:

Add the import:
```typescript
import { SourceDocumentBrowser } from '@/components/documents/SourceDocumentBrowser'
```

Destructure `addDocumentFromSource` from `useDocuments`:
```typescript
const {
  documents,
  isLoading,
  error,
  uploadDocument,
  addDocumentFromSource,
  updateDocument,
  deleteDocument,
  downloadDocument,
} = useDocuments(currentProject?.id || null, undefined, selectedFolderId)
```

Build the set of existing source document IDs. Add this derived value before the return statement:
```typescript
const existingSourceIds = new Set(
  documents.flatMap((d) => (d.sourceDocumentId ? [d.sourceDocumentId] : []),
)
```

Note: `sourceDocumentId` may not be on `DocumentListItem`. Check `frontend/src/types/document.ts`. If it's absent, add it:
```typescript
// In DocumentListItem interface, add:
sourceDocumentId?: string | null
```

And ensure the API response maps it (the backend `DocumentListResponse` does not currently include `sourceDocumentId` — if it's missing, add it to the schema):

In `backend/app/schemas/document.py`, add to `DocumentListResponse`:
```python
source_document_id: UUID | None = Field(None, alias="sourceDocumentId")
```

Add the handler that calls the hook and auto-selects the new document:
```typescript
const handleFromSourceAdd = async (
  sourceDocumentId: string,
  parserType: string,
  parseConfig?: ParseConfig,
) => {
  const doc = await addDocumentFromSource({
    projectId: currentProject.id,
    sourceDocumentId,
    parserType,
    parseConfig,
  })
  setViewDocumentId(doc.id)
}
```

Add `ParseConfig` to the imports at the top: `import type { ParseConfig } from '@/types/parsing'`

Replace the `SourceDocumentBrowser` placeholder in the JSX (add it in the "Dialogs" section from Task 2):
```tsx
<SourceDocumentBrowser
  open={fromSourceOpen}
  onOpenChange={setFromSourceOpen}
  existingSourceDocumentIds={existingSourceIds}
  onAdd={handleFromSourceAdd}
/>
```

- [ ] **Step 5: Check ParseMethodSelector props**

Open `frontend/src/components/documents/ParseMethodSelector.tsx` and read the actual `ParseMethodSelectorProps` interface. Adjust the props passed in `SourceDocumentBrowser` Step 3 to match exactly.

- [ ] **Step 6: Lint and build**

Run: `npm run lint --prefix frontend`
Run: `npm run build --prefix frontend`

Fix any TypeScript errors before continuing.

- [ ] **Step 7: Smoke test From Source flow**

Start the dev server: `npm run dev --prefix frontend`

Verify:
- "From Source" button opens the sheet
- Source documents not already in the project are listed
- Selecting a source doc highlights it
- Parse config selector works
- "Add & Parse" button calls the backend, closes the sheet, and the new document appears in the left panel list with processing status
- After parsing completes (poll), document appears as ready and is auto-selected in the left panel

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/documents.ts frontend/src/hooks/useDocuments.ts frontend/src/components/documents/SourceDocumentBrowser.tsx frontend/src/pages/DocumentsPage.tsx backend/app/schemas/document.py
git commit -m "feat(parse): add SourceDocumentBrowser and From Source flow"
```
