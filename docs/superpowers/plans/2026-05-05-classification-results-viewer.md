# Classification Results Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /classification-runs/{run_id}/blocks` and replace the flat region card list on `ClassificationRunDetailPage` with a label-grouped, expandable block viewer.

**Architecture:** The backend stitches classification regions with the source `ParsedDocument` server-side inside a new repository method, returning an annotated flat list of blocks. The frontend groups blocks by label and renders collapsible sections with expandable block rows, fetching blocks independently of the run metadata.

**Tech Stack:** FastAPI (async), Pydantic v2, SQLAlchemy 2.0 (SQLite for tests), React 18, TypeScript, shadcn/ui (`Collapsible`, `Badge`, `Skeleton`, `Alert`), Tailwind CSS, vitest + @testing-library/react

---

## File Map

| File | Change |
|---|---|
| `backend/app/schemas/classification.py` | Add `AnnotatedBlockResponse` |
| `backend/app/repositories/classification_run_repository.py` | Add `AnnotatedBlock` dataclass + `get_annotated_blocks` method |
| `backend/app/routers/classification.py` | Add `GET /{run_id}/blocks` handler; update schema import |
| `backend/tests/repositories/test_classification_run_repository.py` | Add `test_get_annotated_blocks` and `test_get_annotated_blocks_no_parsed_doc` |
| `backend/tests/routers/test_classification_router.py` | New — 404 test + happy-path test for `/blocks` endpoint |
| `frontend/src/types/classification.ts` | Add `AnnotatedBlock` interface |
| `frontend/src/api/classification.ts` | Add `getClassificationRunBlocks` |
| `frontend/src/hooks/useClassificationRuns.ts` | Add `useClassificationRunBlocks` hook |
| `frontend/src/hooks/useClassificationRuns.test.ts` | New — tests for `useClassificationRunBlocks` |
| `frontend/src/components/classification/ClassificationBlockRow.tsx` | New component |
| `frontend/src/components/classification/ClassificationLabelSection.tsx` | New component |
| `frontend/src/components/classification/ClassificationResultsViewer.tsx` | New component |
| `frontend/src/pages/ClassificationRunDetailPage.tsx` | Replace `ClassificationRegionList` with `ClassificationResultsViewer` |

---

### Task 1: Backend schema + read model

**Files:**
- Modify: `backend/app/schemas/classification.py`
- Modify: `backend/app/repositories/classification_run_repository.py`

- [ ] **Step 1: Add `AnnotatedBlockResponse` to schemas**

Open `backend/app/schemas/classification.py` and append at the bottom:

```python
class AnnotatedBlockResponse(BaseModel):
    blockId: str
    pageIndex: int
    role: str
    text: str
    markdown: str | None
    label: str | None
```

- [ ] **Step 2: Add `AnnotatedBlock` dataclass to repository**

In `backend/app/repositories/classification_run_repository.py`, add after the existing `ClassificationRunCreate` dataclass (around line 24):

```python
@dataclass
class AnnotatedBlock:
    block_id: str
    page_index: int
    role: str
    text: str
    markdown: str | None
    label: str | None
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/classification.py backend/app/repositories/classification_run_repository.py
git commit -m "feat(classification): add AnnotatedBlock dataclass and AnnotatedBlockResponse schema"
```

---

### Task 2: Repository method + tests

**Files:**
- Modify: `backend/app/repositories/classification_run_repository.py`
- Modify: `backend/tests/repositories/test_classification_run_repository.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/repositories/test_classification_run_repository.py` and append:

```python
@pytest.mark.asyncio
async def test_get_annotated_blocks(test_db):
    from app.models.parsed_document import ParsedDocument as ParsedDocumentORM

    parse_run_id = uuid4()
    source_doc_id = uuid4()

    pd = ParsedDocumentORM(
        parse_run_id=parse_run_id,
        source_document_id=source_doc_id,
        full_text=None,
        full_markdown=None,
        page_count=2,
        block_count=3,
        content={
            "id": "doc-1",
            "source_document_id": str(source_doc_id),
            "parse_run_id": str(parse_run_id),
            "page_count": 2,
            "pages": [{"index": 0}, {"index": 1}],
            "blocks": [
                {"id": "b-1", "role": "heading", "native_type": "heading", "text": "Balance Sheet", "page_index": 0},
                {"id": "b-2", "role": "paragraph", "native_type": "paragraph", "text": "Assets data", "page_index": 0},
                {"id": "b-3", "role": "paragraph", "native_type": "paragraph", "text": "Notes", "page_index": 1},
            ],
        },
    )
    test_db.add(pd)
    await test_db.commit()

    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=parse_run_id,
        document_id=uuid4(),
        labels_requested=["balance_sheet"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    ))
    await repo.save_regions(run.id, [
        ClassifiedRegion(
            label="balance_sheet",
            page_start=0,
            page_end=0,
            block_ids=["b-1", "b-2"],
        )
    ])

    blocks = await repo.get_annotated_blocks(run.id)

    assert len(blocks) == 3
    assert blocks[0].block_id == "b-1"
    assert blocks[0].label == "balance_sheet"
    assert blocks[0].role == "heading"
    assert blocks[0].text == "Balance Sheet"
    assert blocks[0].page_index == 0
    assert blocks[1].block_id == "b-2"
    assert blocks[1].label == "balance_sheet"
    assert blocks[2].block_id == "b-3"
    assert blocks[2].label is None


@pytest.mark.asyncio
async def test_get_annotated_blocks_no_parsed_doc(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["x"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    ))
    blocks = await repo.get_annotated_blocks(run.id)
    assert blocks == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/repositories/test_classification_run_repository.py::test_get_annotated_blocks tests/repositories/test_classification_run_repository.py::test_get_annotated_blocks_no_parsed_doc -v
```

Expected: `FAILED` with `AttributeError: 'ClassificationRunRepository' object has no attribute 'get_annotated_blocks'`

- [ ] **Step 3: Implement `get_annotated_blocks`**

In `backend/app/repositories/classification_run_repository.py`, add the following imports at the top (after existing imports):

```python
from app.cdm.models import ParsedDocument as CDMParsedDocument
from app.repositories.parsed_document_repository import ParsedDocumentRepository
```

Then add this method to `ClassificationRunRepository` (after the `get_regions` method, around line 108):

```python
async def get_annotated_blocks(self, run_id: UUID) -> list[AnnotatedBlock]:
    run = await self.get(run_id)
    if run is None:
        return []

    pd_repo = ParsedDocumentRepository(self.session)
    pd_orm = await pd_repo.get_by_run(run.parse_run_id)
    if pd_orm is None:
        return []

    doc = CDMParsedDocument.model_validate(pd_orm.content)
    regions = await self.get_regions(run_id)

    block_label: dict[str, str] = {}
    for region in regions:
        for block_id in region.block_ids:
            block_label[block_id] = region.label

    return [
        AnnotatedBlock(
            block_id=str(block.id),
            page_index=block.page_index,
            role=block.role.value if hasattr(block.role, "value") else block.role,
            text=block.text or "",
            markdown=block.markdown,
            label=block_label.get(str(block.id)),
        )
        for block in doc.blocks
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --directory backend python -m pytest tests/repositories/test_classification_run_repository.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/classification_run_repository.py backend/tests/repositories/test_classification_run_repository.py
git commit -m "feat(classification): add get_annotated_blocks repository method"
```

---

### Task 3: Router endpoint + router test

**Files:**
- Modify: `backend/app/routers/classification.py`
- Create: `backend/tests/routers/test_classification_router.py`

- [ ] **Step 1: Write the failing router tests**

Create `backend/tests/routers/test_classification_router.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/routers/test_classification_router.py -v
```

Expected: `FAILED` — 404 test passes (endpoint doesn't exist yet so all requests 404) but the 200 test fails.

- [ ] **Step 3: Add the endpoint to the router**

In `backend/app/routers/classification.py`, update the schema import (around line 19):

```python
from app.schemas.classification import (
    AnnotatedBlockResponse,
    ClassificationRegionResponse,
    ClassificationRunCreateRequest,
    ClassificationRunResponse,
)
```

Then append the new handler at the end of the file (after `delete_classification_run`):

```python
@runs_router.get("/{run_id}/blocks", response_model=list[AnnotatedBlockResponse])
async def get_classification_run_blocks(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    blocks = await repo.get_annotated_blocks(run_id)
    return [
        AnnotatedBlockResponse(
            blockId=b.block_id,
            pageIndex=b.page_index,
            role=b.role,
            text=b.text,
            markdown=b.markdown,
            label=b.label,
        )
        for b in blocks
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --directory backend python -m pytest tests/routers/test_classification_router.py -v
```

Expected: both tests `PASSED`

- [ ] **Step 5: Run full backend test suite to check for regressions**

```bash
uv run --directory backend python -m pytest -o "addopts=" -v
```

Expected: all tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/classification.py backend/tests/routers/test_classification_router.py
git commit -m "feat(classification): add GET /classification-runs/{run_id}/blocks endpoint"
```

---

### Task 4: Frontend type + API function

**Files:**
- Modify: `frontend/src/types/classification.ts`
- Modify: `frontend/src/api/classification.ts`

- [ ] **Step 1: Add `AnnotatedBlock` type**

In `frontend/src/types/classification.ts`, append at the bottom:

```typescript
export interface AnnotatedBlock {
  blockId: string
  pageIndex: number
  role: string
  text: string
  markdown: string | null
  label: string | null
}
```

- [ ] **Step 2: Add `getClassificationRunBlocks` API function**

In `frontend/src/api/classification.ts`, add the import for `AnnotatedBlock` at the top:

```typescript
import type { AnnotatedBlock, ClassificationRun, ClassificationRunCreateRequest } from '@/types/classification'
```

Then append at the bottom of the file:

```typescript
export async function getClassificationRunBlocks(runId: string): Promise<AnnotatedBlock[]> {
  const response = await apiClient.get<AnnotatedBlock[]>(`/classification-runs/${runId}/blocks`)
  return response.data
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/classification.ts frontend/src/api/classification.ts
git commit -m "feat(classification): add AnnotatedBlock type and getClassificationRunBlocks API function"
```

---

### Task 5: Frontend hook + hook test

**Files:**
- Modify: `frontend/src/hooks/useClassificationRuns.ts`
- Create: `frontend/src/hooks/useClassificationRuns.test.ts`

- [ ] **Step 1: Write the failing hook tests**

Create `frontend/src/hooks/useClassificationRuns.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useClassificationRunBlocks } from './useClassificationRuns'
import type { AnnotatedBlock } from '@/types/classification'

vi.mock('@/api/classification', () => ({
  getClassificationRunBlocks: vi.fn(),
}))

import * as api from '@/api/classification'

const mockGetBlocks = vi.mocked(api.getClassificationRunBlocks)

const mockBlocks: AnnotatedBlock[] = [
  { blockId: 'b-1', pageIndex: 0, role: 'paragraph', text: 'Hello', markdown: null, label: 'intro' },
  { blockId: 'b-2', pageIndex: 1, role: 'paragraph', text: 'World', markdown: null, label: null },
]

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useClassificationRunBlocks', () => {
  it('fetches blocks and returns them on success', async () => {
    mockGetBlocks.mockResolvedValue(mockBlocks)
    const { result } = renderHook(() => useClassificationRunBlocks('run-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.blocks).toEqual(mockBlocks)
    expect(result.current.error).toBeNull()
    expect(mockGetBlocks).toHaveBeenCalledWith('run-1')
  })

  it('sets error when fetch fails', async () => {
    mockGetBlocks.mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useClassificationRunBlocks('run-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Network error')
    expect(result.current.blocks).toEqual([])
  })

  it('does not fetch when runId is null', () => {
    const { result } = renderHook(() => useClassificationRunBlocks(null))
    expect(result.current.isLoading).toBe(false)
    expect(result.current.blocks).toEqual([])
    expect(mockGetBlocks).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npx --prefix frontend vitest run src/hooks/useClassificationRuns.test.ts
```

Expected: `FAILED` — `useClassificationRunBlocks` is not exported

- [ ] **Step 3: Add `useClassificationRunBlocks` to the hook file**

In `frontend/src/hooks/useClassificationRuns.ts`, add the `AnnotatedBlock` import at the top:

```typescript
import type { AnnotatedBlock, ClassificationRun, ClassificationRunStatus } from '@/types/classification'
```

Then append at the bottom of the file:

```typescript
interface UseClassificationRunBlocksReturn {
  blocks: AnnotatedBlock[]
  isLoading: boolean
  error: string | null
}

export function useClassificationRunBlocks(runId: string | null): UseClassificationRunBlocksReturn {
  const [blocks, setBlocks] = useState<AnnotatedBlock[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    setIsLoading(true)
    setError(null)
    classificationApi.getClassificationRunBlocks(runId)
      .then((data) => { setBlocks(data) })
      .catch((err) => { setError(err instanceof Error ? err.message : 'Failed to fetch blocks') })
      .finally(() => { setIsLoading(false) })
  }, [runId])

  return { blocks, isLoading, error }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx --prefix frontend vitest run src/hooks/useClassificationRuns.test.ts
```

Expected: all 3 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useClassificationRuns.ts frontend/src/hooks/useClassificationRuns.test.ts
git commit -m "feat(classification): add useClassificationRunBlocks hook"
```

---

### Task 6: `ClassificationBlockRow` component

**Files:**
- Create: `frontend/src/components/classification/ClassificationBlockRow.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/classification/ClassificationBlockRow.tsx`:

```typescript
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  block: AnnotatedBlock
}

export function ClassificationBlockRow({ block }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border rounded-md overflow-hidden">
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <Badge variant="secondary" className="shrink-0 font-mono text-xs">
          p.{block.pageIndex + 1}
        </Badge>
        <Badge variant="outline" className="shrink-0 text-xs">
          {block.role}
        </Badge>
        <span className="flex-1 truncate text-muted-foreground line-clamp-1">
          {block.text}
        </span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t bg-muted/20">
          <pre className="text-xs leading-relaxed whitespace-pre-wrap break-words font-mono">
            {block.markdown ?? block.text}
          </pre>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Lint**

```bash
npm --prefix frontend run lint
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/classification/ClassificationBlockRow.tsx
git commit -m "feat(classification): add ClassificationBlockRow component"
```

---

### Task 7: `ClassificationLabelSection` component

**Files:**
- Create: `frontend/src/components/classification/ClassificationLabelSection.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/classification/ClassificationLabelSection.tsx`:

```typescript
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ClassificationBlockRow } from './ClassificationBlockRow'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  label: string | null
  blocks: AnnotatedBlock[]
}

function pageRange(blocks: AnnotatedBlock[]): string {
  if (blocks.length === 0) return ''
  const pages = blocks.map((b) => b.pageIndex)
  const min = Math.min(...pages) + 1
  const max = Math.max(...pages) + 1
  return min === max ? `Page ${min}` : `Pages ${min}–${max}`
}

export function ClassificationLabelSection({ label, blocks }: Props) {
  const displayName = label ?? 'Unmatched'
  const [open, setOpen] = useState(label !== null)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 rounded-lg hover:bg-muted/50 text-sm font-medium">
          <div className="flex items-center gap-2">
            {open ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <span>{displayName}</span>
            <Badge variant="secondary">{blocks.length}</Badge>
          </div>
          {blocks.length > 0 && (
            <span className="text-xs text-muted-foreground">{pageRange(blocks)}</span>
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1 space-y-1">
        {blocks.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 py-2">
            No regions identified for this label.
          </p>
        ) : (
          blocks.map((block) => (
            <ClassificationBlockRow key={block.blockId} block={block} />
          ))
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
```

- [ ] **Step 2: Lint**

```bash
npm --prefix frontend run lint
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/classification/ClassificationLabelSection.tsx
git commit -m "feat(classification): add ClassificationLabelSection component"
```

---

### Task 8: `ClassificationResultsViewer` component

**Files:**
- Create: `frontend/src/components/classification/ClassificationResultsViewer.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/classification/ClassificationResultsViewer.tsx`:

```typescript
import { useClassificationRunBlocks } from '@/hooks/useClassificationRuns'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ClassificationLabelSection } from './ClassificationLabelSection'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  runId: string
  labelsRequested: string[]
}

export function ClassificationResultsViewer({ runId, labelsRequested }: Props) {
  const { blocks, isLoading, error } = useClassificationRunBlocks(runId)

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  const grouped = new Map<string | null, AnnotatedBlock[]>()
  for (const label of labelsRequested) {
    grouped.set(label, [])
  }
  grouped.set(null, [])
  for (const block of blocks) {
    const key = block.label ?? null
    if (!grouped.has(key)) {
      grouped.set(key, [])
    }
    grouped.get(key)!.push(block)
  }

  const unmatchedBlocks = grouped.get(null) ?? []

  return (
    <div className="space-y-2">
      {labelsRequested.map((label) => (
        <ClassificationLabelSection
          key={label}
          label={label}
          blocks={grouped.get(label) ?? []}
        />
      ))}
      {unmatchedBlocks.length > 0 && (
        <ClassificationLabelSection key="__unmatched__" label={null} blocks={unmatchedBlocks} />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Lint**

```bash
npm --prefix frontend run lint
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/classification/ClassificationResultsViewer.tsx
git commit -m "feat(classification): add ClassificationResultsViewer component"
```

---

### Task 9: Wire `ClassificationResultsViewer` into detail page

**Files:**
- Modify: `frontend/src/pages/ClassificationRunDetailPage.tsx`

- [ ] **Step 1: Update the detail page**

In `frontend/src/pages/ClassificationRunDetailPage.tsx`, replace:

```typescript
import { ClassificationRegionList } from '@/components/classification/ClassificationRegionList'
```

with:

```typescript
import { ClassificationResultsViewer } from '@/components/classification/ClassificationResultsViewer'
```

Then replace the completed-run section (around line 98):

```typescript
      {run.status === 'completed' && (
        <section>
          <h2 className="text-lg font-medium mb-3">Identified regions</h2>
          <ClassificationRegionList regions={run.regions} />
        </section>
      )}
```

with:

```typescript
      {run.status === 'completed' && (
        <section>
          <h2 className="text-lg font-medium mb-3">Classification results</h2>
          <ClassificationResultsViewer runId={run.id} labelsRequested={run.labelsRequested} />
        </section>
      )}
```

- [ ] **Step 2: Lint and build**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: no errors, successful build

- [ ] **Step 3: Run frontend tests**

```bash
npx --prefix frontend vitest run
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ClassificationRunDetailPage.tsx
git commit -m "feat(classification): wire ClassificationResultsViewer into detail page"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| `GET /classification-runs/{run_id}/blocks` endpoint | Task 3 |
| `AnnotatedBlockResponse` with blockId, pageIndex, role, text, markdown, label | Tasks 1 & 3 |
| 404 if run not found | Task 3 |
| `get_annotated_blocks` stitches ParsedDocument + regions | Task 2 |
| Block-to-label index from `region.block_ids` | Task 2 |
| Blocks in document order | Task 2 (doc.blocks is already ordered) |
| `AnnotatedBlock` type in frontend | Task 4 |
| `getClassificationRunBlocks` API function | Task 4 |
| `useClassificationRunBlocks` hook | Task 5 |
| `ClassificationBlockRow` with page badge, role badge, text preview, expand | Task 6 |
| Expanded state shows `block.markdown ?? block.text` in `<pre>` | Task 6 |
| `ClassificationLabelSection` collapsible, page range, block count | Task 7 |
| Labeled sections open by default; Unmatched collapsed | Task 7 |
| Empty state "No regions identified for this label" | Task 7 |
| `ClassificationResultsViewer` groups by label, fetches independently | Task 8 |
| Skeleton while loading; error alert on failure | Task 8 |
| Labels rendered in `labelsRequested` order; Unmatched appended | Task 8 |
| Replace `ClassificationRegionList` in detail page | Task 9 |

All spec requirements are covered. No gaps found.

### Placeholder scan

No TBD, TODO, or placeholder patterns present.

### Type consistency

- `AnnotatedBlock.block_id` (dataclass, snake_case) → `AnnotatedBlockResponse.blockId` (schema, camelCase alias) ✓
- `AnnotatedBlock` interface (frontend, camelCase) → `getClassificationRunBlocks` return type ✓
- `useClassificationRunBlocks` returns `{ blocks: AnnotatedBlock[], ... }` → `ClassificationResultsViewer` passes to `ClassificationLabelSection` ✓
- `ClassificationLabelSection` receives `blocks: AnnotatedBlock[]` → passes each `block: AnnotatedBlock` to `ClassificationBlockRow` ✓
- `block.blockId` used as React key in `ClassificationLabelSection` ✓
