# Delete Parse Run — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a delete action for parse runs, blocking deletion when dependent entities (index documents, classification runs, or extraction results) still reference the run.

**Architecture:** A new `DELETE /parse-runs/{id}` endpoint checks for blockers via a repository method before deleting; the DB cascade removes `parsed_documents` automatically. The frontend adds a shared `ParseRunDeleteDialog` component wired into both `RunTimeline` (document panel) and `RunHeader` (detail page).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async (backend); React 18 / TypeScript / Vitest / shadcn/ui / Axios (frontend).

## Global Constraints

- No `cd X && Y` compound shell commands — use absolute paths or tool working-directory flags.
- Backend tests: `uv run --directory backend python -m pytest <path> -o "addopts=" -v`
- Frontend tests: `npx --prefix frontend vitest run <path>`
- Frontend lint: `npm run --prefix frontend lint`
- shadcn/ui + Tailwind for all UI; no new CSS files.
- Follow existing router → service → repository data-flow; services raise, routers catch.
- TDD: write the failing test first, then implement.

---

## File Map

**Created:**
- `frontend/src/components/parse-runs/ParseRunDeleteDialog.tsx` — shared delete confirmation dialog; handles 409 blocker state internally.
- `frontend/src/components/parse-runs/ParseRunDeleteDialog.test.tsx` — unit tests for dialog states.

**Modified:**
- `backend/app/repositories/parse_run_repository.py` — add `get_blockers` and `delete` methods.
- `backend/app/routers/parse_runs.py` — add `DELETE /{parse_run_id}` endpoint.
- `backend/tests/routers/test_parse_runs_router.py` — add DELETE test cases.
- `frontend/src/api/parseRuns.ts` — add `deleteParseRun`.
- `frontend/src/components/parse-runs/RunTimeline.tsx` — add `onRunDeleted` prop, trash icon, and dialog.
- `frontend/src/components/parse-runs/RunTimeline.test.tsx` — update to pass new prop and assert delete button renders.
- `frontend/src/pages/DocumentsPage.tsx` — pass `onRunDeleted={refreshParseRuns}` to `RunTimeline`.
- `frontend/src/components/parse-runs/RunHeader.tsx` — add `onDelete` prop and Delete button.
- `frontend/src/pages/ParseRunDetailPage.tsx` — add `deleteOpen` state and `ParseRunDeleteDialog`.

---

## Task 1: Backend — blocker check + DELETE endpoint

**Files:**
- Modify: `backend/app/repositories/parse_run_repository.py`
- Modify: `backend/app/routers/parse_runs.py`
- Test: `backend/tests/routers/test_parse_runs_router.py`

**Interfaces:**
- Produces: `DELETE /api/v1/parse-runs/{id}` — 204 on success, 409 with `{"detail": {"message": str, "blockers": {"index_documents": int, "classification_runs": int, "extraction_results": int}}}` when blocked, 404/403/401 as appropriate.

---

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/routers/test_parse_runs_router.py`:

```python
# ── new imports at the top of the file ──────────────────────────────────────
from app.models.classification_run import ClassificationRun


# ── helper: seed a run that has a ClassificationRun dependency ───────────────
async def _seed_with_classification_run(
    test_db: AsyncSession,
    user: User,
) -> ParseRunORM:
    """Seed a ParseRun + ClassificationRun so the delete endpoint returns 409."""
    project = Project(user_id=user.id, name="Blocker")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    sd = SourceDocument(id=uuid4(), sha256="e" * 64, storage_uri="local://e.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)

    doc = DocumentORM(
        project_id=project.id,
        source_document_id=sd.id,
        source_type="upload",
        source_identifier="e.pdf",
        title="E",
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)

    run = ParseRunORM(
        source_document_id=sd.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config={},
        config_hash="e" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()
    await test_db.refresh(run)
    await test_db.refresh(doc)

    clf = ClassificationRun(
        parse_run_id=run.id,
        document_id=doc.id,
        labels_requested=[],
        classifier_type="simple",
        classifier_config={},
        status="succeeded",
    )
    test_db.add(clf)
    await test_db.commit()

    return run


# ── DELETE tests ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_delete_204_removes_run_and_parsed_document(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "del1@example.com")
    user = await _user_by_email(test_db, "del1@example.com")
    run = await _seed(test_db, user)

    resp = await client.delete(
        f"/api/v1/parse-runs/{run.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204, resp.text

    # Run is gone.
    assert (await test_db.execute(
        select(ParseRunORM).where(ParseRunORM.id == run.id)
    )).scalar_one_or_none() is None

    # ParsedDocument is cascade-deleted.
    from app.models.parsed_document import ParsedDocument as ParsedDocumentORM2
    assert (await test_db.execute(
        select(ParsedDocumentORM2).where(ParsedDocumentORM2.parse_run_id == run.id)
    )).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_409_when_classification_run_exists(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "del2@example.com")
    user = await _user_by_email(test_db, "del2@example.com")
    run = await _seed_with_classification_run(test_db, user)

    resp = await client.delete(
        f"/api/v1/parse-runs/{run.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["detail"]["blockers"]["classification_runs"] >= 1
    assert "index_documents" in body["detail"]["blockers"]
    assert "extraction_results" in body["detail"]["blockers"]


@pytest.mark.asyncio
async def test_delete_404_when_run_missing(client: AsyncClient):
    token = await _signup_and_login(client, "del3@example.com")
    resp = await client.delete(
        f"/api/v1/parse-runs/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_403_when_user_does_not_own_source(
    client: AsyncClient, test_db: AsyncSession
):
    await _signup_and_login(client, "delA@example.com")
    user_a = await _user_by_email(test_db, "delA@example.com")
    run = await _seed(test_db, user_a)

    token_b = await _signup_and_login(client, "delB@example.com")
    resp = await client.delete(
        f"/api/v1/parse-runs/{run.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_401_when_unauthenticated(
    client: AsyncClient, test_db: AsyncSession
):
    await _signup_and_login(client, "delC@example.com")
    user = await _user_by_email(test_db, "delC@example.com")
    run = await _seed(test_db, user)

    resp = await client.delete(f"/api/v1/parse-runs/{run.id}")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest backend/tests/routers/test_parse_runs_router.py::test_delete_204_removes_run_and_parsed_document -o "addopts=" -v
```

Expected: `FAILED` — `405 Method Not Allowed` (endpoint does not exist yet).

- [ ] **Step 3: Add `get_blockers` and `delete` to the repository**

In `backend/app/repositories/parse_run_repository.py`, add these imports at the top of the file (after the existing imports):

```python
from app.models.classification_run import ClassificationRun
from app.models.extraction_result import ExtractionResult
from app.models.index_document import IndexDocument
```

Append these two methods to `ParseRunRepository` (after `update_status`):

```python
    async def get_blockers(self, run_id: UUID) -> dict[str, int]:
        """Count rows in dependent tables that would block deletion."""
        index_count = (await self.session.execute(
            select(func.count()).select_from(IndexDocument)
            .where(IndexDocument.parse_run_id == run_id)
        )).scalar_one()
        classification_count = (await self.session.execute(
            select(func.count()).select_from(ClassificationRun)
            .where(ClassificationRun.parse_run_id == run_id)
        )).scalar_one()
        extraction_count = (await self.session.execute(
            select(func.count()).select_from(ExtractionResult)
            .where(ExtractionResult.source_parse_run_id == run_id)
        )).scalar_one()
        return {
            "index_documents": index_count,
            "classification_runs": classification_count,
            "extraction_results": extraction_count,
        }

    async def delete(self, run: ParseRun) -> None:
        await self.session.delete(run)
        await self.session.commit()
```

- [ ] **Step 4: Add the DELETE endpoint**

Append to `backend/app/routers/parse_runs.py`:

```python
@router.delete(
    "/{parse_run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ParseRun",
    description=(
        "Delete a ParseRun and its ParsedDocument (via DB cascade). "
        "Returns 409 if any index documents, classification runs, or extraction results "
        "still reference this run."
    ),
)
async def delete_parse_run(
    parse_run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ParseRunRepository(db)
    run = await repo.get(parse_run_id)
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
            detail="Not authorized to delete this ParseRun",
        )
    blockers = await repo.get_blockers(parse_run_id)
    if any(blockers.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Parse run has dependent entities that must be removed first.",
                "blockers": blockers,
            },
        )
    await repo.delete(run)
```

- [ ] **Step 5: Run all DELETE tests**

```
uv run --directory backend python -m pytest backend/tests/routers/test_parse_runs_router.py -k "delete" -o "addopts=" -v
```

Expected: all 5 DELETE tests PASS.

- [ ] **Step 6: Run the full router test file to check for regressions**

```
uv run --directory backend python -m pytest backend/tests/routers/test_parse_runs_router.py -o "addopts=" -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```
git add backend/app/repositories/parse_run_repository.py backend/app/routers/parse_runs.py backend/tests/routers/test_parse_runs_router.py
git commit -m "feat(parse-runs): add DELETE endpoint with dependency blocker check"
```

---

## Task 2: Frontend API function + ParseRunDeleteDialog

**Files:**
- Modify: `frontend/src/api/parseRuns.ts`
- Create: `frontend/src/components/parse-runs/ParseRunDeleteDialog.tsx`
- Create: `frontend/src/components/parse-runs/ParseRunDeleteDialog.test.tsx`

**Interfaces:**
- Produces: `deleteParseRun(runId: string): Promise<void>` — throws `AxiosError` on non-2xx.
- Produces: `<ParseRunDeleteDialog open runId onOpenChange onDeleted />` — renders confirm or blocker state.

---

- [ ] **Step 1: Write failing dialog tests**

Create `frontend/src/components/parse-runs/ParseRunDeleteDialog.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios from 'axios'
import { ParseRunDeleteDialog } from './ParseRunDeleteDialog'

vi.mock('@/api/parseRuns', () => ({
  deleteParseRun: vi.fn(),
}))

import * as parseRunsApi from '@/api/parseRuns'

describe('ParseRunDeleteDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the confirm message when open', () => {
    render(
      <ParseRunDeleteDialog
        open={true}
        onOpenChange={vi.fn()}
        runId="r1"
        onDeleted={vi.fn()}
      />
    )
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^delete$/i })).toBeInTheDocument()
  })

  it('calls onDeleted and closes on successful delete', async () => {
    vi.mocked(parseRunsApi.deleteParseRun).mockResolvedValueOnce(undefined)
    const onDeleted = vi.fn()
    const onOpenChange = vi.fn()
    render(
      <ParseRunDeleteDialog
        open={true}
        onOpenChange={onOpenChange}
        runId="r1"
        onDeleted={onDeleted}
      />
    )
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(parseRunsApi.deleteParseRun).toHaveBeenCalledWith('r1')
    expect(onDeleted).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('shows blocker counts when the API returns 409', async () => {
    const err = new axios.AxiosError('Conflict')
    Object.assign(err, {
      response: {
        status: 409,
        data: {
          detail: {
            message: 'Parse run has dependent entities.',
            blockers: { index_documents: 2, classification_runs: 0, extraction_results: 0 },
          },
        },
        headers: {},
        config: {},
        statusText: 'Conflict',
      },
    })
    vi.mocked(parseRunsApi.deleteParseRun).mockRejectedValueOnce(err)

    render(
      <ParseRunDeleteDialog
        open={true}
        onOpenChange={vi.fn()}
        runId="r1"
        onDeleted={vi.fn()}
      />
    )
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(await screen.findByText(/2 index document/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^delete$/i })).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```
npx --prefix frontend vitest run src/components/parse-runs/ParseRunDeleteDialog.test.tsx
```

Expected: `FAILED` — module `./ParseRunDeleteDialog` not found.

- [ ] **Step 3: Add `deleteParseRun` to the API module**

In `frontend/src/api/parseRuns.ts`, append:

```ts
export async function deleteParseRun(runId: string): Promise<void> {
  await apiClient.delete(`/parse-runs/${runId}`)
}
```

- [ ] **Step 4: Create `ParseRunDeleteDialog`**

Create `frontend/src/components/parse-runs/ParseRunDeleteDialog.tsx`:

```tsx
import { useState } from 'react'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { deleteParseRun } from '@/api/parseRuns'

interface Blockers {
  index_documents: number
  classification_runs: number
  extraction_results: number
}

interface ParseRunDeleteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  runId: string
  onDeleted: () => void
}

function formatBlockers(b: Blockers): string {
  return [
    b.index_documents > 0 && `${b.index_documents} index document(s)`,
    b.classification_runs > 0 && `${b.classification_runs} classification run(s)`,
    b.extraction_results > 0 && `${b.extraction_results} extraction result(s)`,
  ]
    .filter(Boolean)
    .join(', ')
}

export function ParseRunDeleteDialog({
  open,
  onOpenChange,
  runId,
  onDeleted,
}: ParseRunDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [blockers, setBlockers] = useState<Blockers | null>(null)

  const handleConfirm = async () => {
    setIsDeleting(true)
    setError(null)
    setBlockers(null)
    try {
      await deleteParseRun(runId)
      onOpenChange(false)
      onDeleted()
    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        err.response?.status === 409
      ) {
        const body = err.response.data as {
          detail: { blockers: Blockers }
        }
        setBlockers(body.detail.blockers)
      } else {
        setError(
          err instanceof Error ? err.message : 'Failed to delete parse run',
        )
      }
    } finally {
      setIsDeleting(false)
    }
  }

  const handleClose = () => {
    if (!isDeleting) {
      setError(null)
      setBlockers(null)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Parse Run</DialogTitle>
          <DialogDescription>
            {blockers
              ? `This run cannot be deleted: ${formatBlockers(blockers)}. Remove these references first.`
              : 'Are you sure you want to delete this parse run? This cannot be undone.'}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isDeleting}>
            Cancel
          </Button>
          {!blockers && (
            <Button
              variant="destructive"
              onClick={handleConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 5: Run dialog tests**

```
npx --prefix frontend vitest run src/components/parse-runs/ParseRunDeleteDialog.test.tsx
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Lint**

```
npm run --prefix frontend lint
```

Expected: no errors.

- [ ] **Step 7: Commit**

```
git add frontend/src/api/parseRuns.ts frontend/src/components/parse-runs/ParseRunDeleteDialog.tsx frontend/src/components/parse-runs/ParseRunDeleteDialog.test.tsx
git commit -m "feat(parse-runs): add deleteParseRun API fn and ParseRunDeleteDialog component"
```

---

## Task 3: Wire RunTimeline (document panel)

**Files:**
- Modify: `frontend/src/components/parse-runs/RunTimeline.tsx`
- Modify: `frontend/src/components/parse-runs/RunTimeline.test.tsx`
- Modify: `frontend/src/pages/DocumentsPage.tsx`

**Interfaces:**
- Consumes: `ParseRunDeleteDialog` from `./ParseRunDeleteDialog`
- Produces: `RunTimeline` now accepts `onRunDeleted?: () => void`; renders a Trash2 icon button per row.

---

- [ ] **Step 1: Update RunTimeline tests**

Replace the contents of `frontend/src/components/parse-runs/RunTimeline.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RunTimeline } from './RunTimeline'
import type { ParseRunListItem } from '@/types/cdm'

vi.mock('@/api/parseRuns', () => ({
  deleteParseRun: vi.fn(),
}))

const run = (over: Partial<ParseRunListItem> = {}): ParseRunListItem => ({
  id: 'r1',
  sourceDocumentId: 's1',
  parser: 'llamaparse',
  parserVersion: 'v1',
  representationKind: 'vector_light',
  status: 'succeeded',
  startedAt: '2026-04-25T10:00:00Z',
  finishedAt: '2026-04-25T10:00:04Z',
  durationMs: 4200,
  inputTokens: null,
  outputTokens: null,
  cost: {},
  warnings: [],
  failedPages: [],
  providerRefs: {},
  error: null,
  config: {},
  createdAt: '2026-04-25T10:00:00Z',
  ...over,
})

describe('RunTimeline', () => {
  it('renders an empty state', () => {
    render(
      <MemoryRouter>
        <RunTimeline documentId="d1" runs={[]} />
      </MemoryRouter>
    )
    expect(screen.getByText(/no parse runs/i)).toBeInTheDocument()
  })

  it('renders a row per run with an Open viewer link', () => {
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'r1' }), run({ id: 'r2', status: 'failed' })]}
        />
      </MemoryRouter>
    )
    const links = screen.getAllByRole('link', { name: /open viewer/i })
    expect(links).toHaveLength(2)
    expect(links[0].getAttribute('href')).toBe('/documents/d1/runs/r1')
  })

  it('renders a delete button per run row', () => {
    render(
      <MemoryRouter>
        <RunTimeline
          documentId="d1"
          runs={[run({ id: 'r1' }), run({ id: 'r2' })]}
          onRunDeleted={vi.fn()}
        />
      </MemoryRouter>
    )
    expect(screen.getAllByRole('button', { name: /delete/i })).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Run tests to confirm the new test fails**

```
npx --prefix frontend vitest run src/components/parse-runs/RunTimeline.test.tsx
```

Expected: first 2 tests PASS, 3rd FAILS — "delete" buttons not found.

- [ ] **Step 3: Update RunTimeline component**

Replace `frontend/src/components/parse-runs/RunTimeline.tsx` with:

```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ExternalLink, Trash2 } from 'lucide-react'
import type { ParseRunListItem } from '@/types/cdm'
import { ParseRunDeleteDialog } from './ParseRunDeleteDialog'

interface RunTimelineProps {
  documentId: string
  runs: ParseRunListItem[]
  onRunDeleted?: () => void
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function relTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const s = Math.round(diffMs / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export function RunTimeline({ documentId, runs, onRunDeleted }: RunTimelineProps) {
  const [deletingRunId, setDeletingRunId] = useState<string | null>(null)

  if (runs.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-2">
        No parse runs yet.
      </div>
    )
  }

  return (
    <>
      <ul className="divide-y rounded-md border">
        {runs.map((r) => (
          <li key={r.id} className="flex items-center gap-3 px-3 py-2 text-sm">
            <Badge
              variant={
                r.status === 'failed'
                  ? 'destructive'
                  : r.status === 'succeeded'
                    ? 'default'
                    : 'secondary'
              }
            >
              {r.status}
            </Badge>
            <span className="font-medium">{r.parser}</span>
            <span className="text-xs text-muted-foreground">
              {r.representationKind}
            </span>
            <span className="text-xs text-muted-foreground">
              {relTime(r.startedAt)}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatDuration(r.durationMs)}
            </span>
            {r.error && (
              <span className="text-xs text-destructive truncate max-w-[20ch]">
                {r.error}
              </span>
            )}
            <div className="ml-auto flex items-center gap-1">
              <Button asChild size="sm" variant="ghost">
                <Link to={`/documents/${documentId}/runs/${r.id}`}>
                  <ExternalLink className="h-3 w-3 mr-1" /> Open viewer
                </Link>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label="Delete"
                onClick={() => setDeletingRunId(r.id)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {deletingRunId && (
        <ParseRunDeleteDialog
          open={true}
          onOpenChange={(open) => {
            if (!open) setDeletingRunId(null)
          }}
          runId={deletingRunId}
          onDeleted={() => {
            setDeletingRunId(null)
            onRunDeleted?.()
          }}
        />
      )}
    </>
  )
}
```

- [ ] **Step 4: Run RunTimeline tests**

```
npx --prefix frontend vitest run src/components/parse-runs/RunTimeline.test.tsx
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Pass `onRunDeleted` from DocumentsPage**

In `frontend/src/pages/DocumentsPage.tsx`, find the `<RunTimeline` usage (around line 315) and add the prop:

```tsx
// Before:
<RunTimeline
  documentId={viewDocumentId}
  runs={parseRuns}
/>

// After:
<RunTimeline
  documentId={viewDocumentId}
  runs={parseRuns}
  onRunDeleted={refreshParseRuns}
/>
```

- [ ] **Step 6: Lint**

```
npm run --prefix frontend lint
```

Expected: no errors.

- [ ] **Step 7: Commit**

```
git add frontend/src/components/parse-runs/RunTimeline.tsx frontend/src/components/parse-runs/RunTimeline.test.tsx frontend/src/pages/DocumentsPage.tsx
git commit -m "feat(parse-runs): add delete button to RunTimeline rows"
```

---

## Task 4: Wire RunHeader + ParseRunDetailPage

**Files:**
- Modify: `frontend/src/components/parse-runs/RunHeader.tsx`
- Modify: `frontend/src/components/parse-runs/RunHeader.test.tsx`
- Modify: `frontend/src/pages/ParseRunDetailPage.tsx`

**Interfaces:**
- Consumes: `ParseRunDeleteDialog` from `./ParseRunDeleteDialog`
- Produces: `RunHeader` now accepts `onDelete: () => void`; renders a Trash2 Delete button beside Re-parse.

---

- [ ] **Step 1: Replace RunHeader tests**

Replace the full contents of `frontend/src/components/parse-runs/RunHeader.test.tsx`.
All existing `render` calls gain `onDelete={vi.fn()}` (now a required prop), and a new test covers the delete button:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RunHeader } from './RunHeader'
import type { ParseRunListItem } from '@/types/cdm'

const baseRun: ParseRunListItem = {
  id: 'run-1',
  sourceDocumentId: 'src-1',
  parser: 'llamaparse',
  parserVersion: 'v1',
  representationKind: 'vector_light',
  status: 'succeeded',
  startedAt: '2026-04-25T10:00:00Z',
  finishedAt: '2026-04-25T10:00:04Z',
  durationMs: 4200,
  inputTokens: 100,
  outputTokens: 200,
  cost: { total: 0.012 },
  warnings: [],
  failedPages: [],
  providerRefs: { llamaparse_job_id: 'job-1' },
  error: null,
  config: { tier: 'agentic' },
  createdAt: '2026-04-25T10:00:00Z',
}

describe('RunHeader', () => {
  it('renders parser, status, and duration', () => {
    render(<RunHeader run={baseRun} onReparse={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText(/llamaparse/i)).toBeInTheDocument()
    expect(screen.getByText(/succeeded/i)).toBeInTheDocument()
    expect(screen.getByText(/4\.2s|4200/)).toBeInTheDocument()
  })

  it('exposes config JSON when expanded', async () => {
    render(<RunHeader run={baseRun} onReparse={vi.fn()} onDelete={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /config/i }))
    expect(screen.getByText(/"tier": "agentic"/)).toBeInTheDocument()
  })

  it('triggers onReparse when the re-parse button is clicked', async () => {
    const onReparse = vi.fn()
    render(<RunHeader run={baseRun} onReparse={onReparse} onDelete={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /re-parse/i }))
    expect(onReparse).toHaveBeenCalled()
  })

  it('shows error text for failed runs', () => {
    render(
      <RunHeader
        run={{ ...baseRun, status: 'failed', error: 'sdk down' }}
        onReparse={vi.fn()}
        onDelete={vi.fn()}
      />
    )
    expect(screen.getByText(/sdk down/)).toBeInTheDocument()
  })

  it('triggers onDelete when the delete button is clicked', async () => {
    const onDelete = vi.fn()
    render(<RunHeader run={baseRun} onReparse={vi.fn()} onDelete={onDelete} />)
    await userEvent.click(screen.getByRole('button', { name: /delete run/i }))
    expect(onDelete).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run RunHeader tests to confirm new test fails**

```
npx --prefix frontend vitest run src/components/parse-runs/RunHeader.test.tsx
```

Expected: first 4 tests PASS, new test FAILS — "delete run" button not found.

- [ ] **Step 3: Update RunHeader component**

Replace `frontend/src/components/parse-runs/RunHeader.tsx` with:

```tsx
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { ParseRunListItem } from '@/types/cdm'
import { ChevronDown, RefreshCw, Trash2 } from 'lucide-react'

interface RunHeaderProps {
  run: ParseRunListItem
  onReparse: () => void
  onDelete: () => void
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function statusVariant(
  status: ParseRunListItem['status']
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'succeeded':
      return 'default'
    case 'failed':
      return 'destructive'
    case 'partial':
      return 'secondary'
    default:
      return 'outline'
  }
}

export function RunHeader({ run, onReparse, onDelete }: RunHeaderProps) {
  const [configOpen, setConfigOpen] = useState(false)
  return (
    <div className="border-b bg-background sticky top-0 z-10">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        <span className="text-sm font-medium">
          {run.parser}
          {run.parserVersion && (
            <span className="text-muted-foreground">@{run.parserVersion}</span>
          )}
        </span>
        <span className="text-xs text-muted-foreground">
          {run.representationKind}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatDuration(run.durationMs)}
        </span>
        {(run.inputTokens !== null || run.outputTokens !== null) && (
          <span className="text-xs text-muted-foreground">
            tokens: {run.inputTokens ?? '—'} / {run.outputTokens ?? '—'}
          </span>
        )}
        {Object.keys(run.cost).length > 0 && (
          <span className="text-xs text-muted-foreground">
            cost: {JSON.stringify(run.cost)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={onReparse}>
            <RefreshCw className="h-3 w-3 mr-1" /> Re-parse
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={onDelete}
            aria-label="Delete run"
          >
            <Trash2 className="h-3 w-3 mr-1" /> Delete
          </Button>
        </div>
      </div>
      {run.error && (
        <div className="px-4 py-2 text-xs text-destructive border-t bg-destructive/5">
          {run.error}
        </div>
      )}
      <Collapsible open={configOpen} onOpenChange={setConfigOpen}>
        <CollapsibleTrigger asChild>
          <button className="w-full text-left px-4 py-1 text-xs text-muted-foreground hover:bg-muted/40 flex items-center gap-1">
            <ChevronDown
              className={`h-3 w-3 transition-transform ${
                configOpen ? '' : '-rotate-90'
              }`}
            />
            Config
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <pre className="px-4 pb-3 text-xs font-mono whitespace-pre-wrap text-muted-foreground">
            {JSON.stringify(run.config, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
```

- [ ] **Step 4: Run RunHeader tests**

```
npx --prefix frontend vitest run src/components/parse-runs/RunHeader.test.tsx
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Wire `ParseRunDeleteDialog` into ParseRunDetailPage**

In `frontend/src/pages/ParseRunDetailPage.tsx`:

Add the import at the top with other component imports:
```tsx
import { ParseRunDeleteDialog } from '@/components/parse-runs/ParseRunDeleteDialog'
```

Add state after the existing `useState` declarations (around line 27):
```tsx
const [deleteOpen, setDeleteOpen] = useState(false)
```

Update the `<RunHeader>` JSX to pass `onDelete`:
```tsx
// Before:
<RunHeader run={run} onReparse={() => setReparseOpen(true)} />

// After:
<RunHeader
  run={run}
  onReparse={() => setReparseOpen(true)}
  onDelete={() => setDeleteOpen(true)}
/>
```

Add the dialog just before the closing `</div>` of the page (after `<ReParseDialog ...>`):
```tsx
{runId && (
  <ParseRunDeleteDialog
    open={deleteOpen}
    onOpenChange={setDeleteOpen}
    runId={runId}
    onDeleted={() => navigate('/documents')}
  />
)}
```

- [ ] **Step 6: Lint**

```
npm run --prefix frontend lint
```

Expected: no errors.

- [ ] **Step 7: Run full frontend test suite**

```
npx --prefix frontend vitest run
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```
git add frontend/src/components/parse-runs/RunHeader.tsx frontend/src/components/parse-runs/RunHeader.test.tsx frontend/src/pages/ParseRunDetailPage.tsx
git commit -m "feat(parse-runs): add delete button to RunHeader and ParseRunDetailPage"
```
