# Classification Results Viewer — Design Spec

**Date:** 2026-05-05
**Status:** Approved for implementation

---

## 1. Problem & Use Case

After a classification run completes, the user needs to validate the results: did the LLM correctly identify all expected regions, and did it correctly leave out content that doesn't belong to any label? The current `ClassificationRunDetailPage` shows only aggregate metadata (region count, tokens, duration) and a flat list of region cards with label/page range/confidence. There is no way to read the actual block content — the text the LLM was looking at — without leaving the UI.

The results viewer fills this gap. It shows every block in the source document, grouped by the label it was assigned to (or "Unmatched" if none), with expandable text so the user can read the content and judge whether the classification was correct.

---

## 2. Approach

**Label-grouped block viewer with a new enrichment endpoint.**

The backend exposes `GET /classification-runs/{run_id}/blocks`, which stitches together the classification regions and the source ParsedDocument server-side, returning an annotated flat list of blocks. The frontend groups by label and renders collapsible sections with expandable block rows.

This is preferred over:
- **Client-side join**: requires a parsed document endpoint that returns full block content (does not exist; would be a large payload with client-side join logic)
- **Enriching the run detail response**: bloats `GET /classification-runs/{run_id}`; cannot include unmatched blocks without a structural change

---

## 3. Architecture

No new files are needed beyond the frontend component. The new endpoint is added to the existing classification router. The stitching logic is a method on `ClassificationRunRepository` — not a new service file.

```
GET /classification-runs/{run_id}/blocks
  ↓
classification router (existing file)
  ↓
ClassificationRunRepository.get_annotated_blocks(run_id)
  → fetch run → get parse_run_id
  → ParsedDocumentRepository.get_by_run(parse_run_id) → ParsedDocument
  → ClassificationRunRepository.get_regions(run_id) → regions
  → walk doc.blocks, annotate each with label or null
  → return ordered list
```

Frontend:

```
ClassificationRunDetailPage (existing)
  └─ ClassificationResultsViewer (new component)
       └─ ClassificationLabelSection (new component, one per label + Unmatched)
            └─ ClassificationBlockRow (new component, one per block)
```

The `ClassificationResultsViewer` fetches `/blocks` independently — the metadata header loads from the existing run fetch and is immediately visible; the viewer shows a skeleton while the blocks load.

---

## 4. API

### New endpoint

```
GET /api/classification-runs/{run_id}/blocks
```

**Auth:** current active user (same pattern as all classification endpoints)

**Response:** `list[AnnotatedBlockResponse]`

```json
[
  {
    "blockId": "b-001",
    "pageIndex": 44,
    "role": "heading",
    "text": "Consolidated Balance Sheet",
    "markdown": null,
    "label": "balance_sheet"
  },
  {
    "blockId": "b-002",
    "pageIndex": 44,
    "role": "paragraph",
    "text": "As at 31 December 2024...",
    "markdown": null,
    "label": "balance_sheet"
  },
  {
    "blockId": "b-003",
    "pageIndex": 48,
    "role": "paragraph",
    "text": "Notes to the financial statements...",
    "markdown": null,
    "label": null
  }
]
```

Fields:
- `blockId` — UUID string, matches block IDs in the ParsedDocument
- `pageIndex` — 0-indexed page number (display as `pageIndex + 1`)
- `role` — block role from CDM (heading, paragraph, table, figure, etc.)
- `text` — plain text content; always present
- `markdown` — markdown content; non-null for table blocks only
- `label` — the label this block was assigned to, or `null` if unmatched

Blocks are returned in document order (by page, then reading order within page). The endpoint returns 404 if the run is not found.

**Pydantic schema** (new, added to `app/schemas/classification.py`):

```python
class AnnotatedBlockResponse(BaseModel):
    blockId: str
    pageIndex: int
    role: str
    text: str
    markdown: str | None
    label: str | None
```

---

## 5. Backend Implementation

### `ClassificationRunRepository.get_annotated_blocks`

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

    # Build block_id → label index from regions
    block_label: dict[str, str] = {}
    for region in regions:
        for block_id in region.block_ids:
            block_label[block_id] = region.label

    result = []
    for block in doc.blocks:
        result.append(AnnotatedBlock(
            block_id=str(block.id),
            page_index=block.page_index,
            role=block.role,
            text=block.text or "",
            markdown=block.markdown,
            label=block_label.get(str(block.id)),
        ))
    return result
```

`AnnotatedBlock` is a simple dataclass local to the repository (not a CDM type — it's a read model for this endpoint only).

### Router handler

Added to `runs_router` in `classification.py`:

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

---

## 6. Frontend

### New types (`types/classification.ts`)

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

### New API function (`api/classification.ts`)

```typescript
export async function getClassificationRunBlocks(runId: string): Promise<AnnotatedBlock[]> {
  const response = await apiClient.get<AnnotatedBlock[]>(`/classification-runs/${runId}/blocks`)
  return response.data
}
```

### New hook (`hooks/useClassificationRuns.ts`)

`useClassificationRunBlocks(runId)` — fetches once on mount (no polling needed; blocks don't change after a run completes). Returns `{ blocks, isLoading, error }`.

### New components

#### `ClassificationResultsViewer`

Props: `{ runId: string; labelsRequested: string[] }`

- Fetches blocks via `useClassificationRunBlocks`
- Groups blocks by label into a `Map<string | null, AnnotatedBlock[]>`
- Renders one `ClassificationLabelSection` per entry in `labelsRequested` order, then one for `null` (Unmatched) if any unmatched blocks exist
- Shows a skeleton (3 placeholder rows) while loading
- Shows an error alert on fetch failure

#### `ClassificationLabelSection`

Props: `{ label: string | null; blocks: AnnotatedBlock[] }`

- Collapsible section using shadcn `Collapsible`
- Header: label name (or "Unmatched" for null), block count, page range (`Pages X–Y` computed from min/max `pageIndex` in the block list)
- Labeled sections open by default; Unmatched collapsed by default
- Empty state: "No regions identified for this label" if `blocks.length === 0`

#### `ClassificationBlockRow`

Props: `{ block: AnnotatedBlock }`

- Row layout: `[p.N badge] [role badge] [text preview ...]  [▶]`
- Page badge: `p.{pageIndex + 1}`, muted variant
- Role badge: outline variant, role string as-is from CDM (heading, paragraph, table, etc.)
- Text preview: single line, truncated with ellipsis (`line-clamp-1`)
- Chevron right icon; clicking the row expands to show full content
- Expanded state: full `text` rendered in a `<pre>` block; if `markdown` is non-null, render the raw markdown string in a `<pre>` block instead (no markdown renderer needed — the table structure is readable as plain text)
- Toggle is local state (`useState`)

### Integration into `ClassificationRunDetailPage`

Replace the current `{run.status === 'completed' && <ClassificationRegionList .../>}` section with `ClassificationResultsViewer`. Pass `runId` and `run.labelsRequested`.

Keep the existing metadata header and stats grid unchanged. Keep the "running" pulse message and error alert unchanged.

---

## 7. File Map

| Layer | Change |
|---|---|
| Backend schema | Add `AnnotatedBlockResponse` to `app/schemas/classification.py` |
| Backend repository | Add `get_annotated_blocks` method to `ClassificationRunRepository` |
| Backend router | Add `GET /{run_id}/blocks` handler to `runs_router` in `classification.py` |
| Frontend types | Add `AnnotatedBlock` to `types/classification.ts` |
| Frontend API | Add `getClassificationRunBlocks` to `api/classification.ts` |
| Frontend hook | Add `useClassificationRunBlocks` to `hooks/useClassificationRuns.ts` |
| Frontend components | New: `ClassificationResultsViewer`, `ClassificationLabelSection`, `ClassificationBlockRow` in `components/classification/` |
| Frontend page | Update `ClassificationRunDetailPage` to use `ClassificationResultsViewer` |

---

## 8. Out of Scope

- Editing or correcting classifications in the viewer (human annotation)
- Filtering blocks by role within a section
- Searching block text
- Showing confidence/reasoning per block (those belong to the region, not the block)
- Document page image rendering
