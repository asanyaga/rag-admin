# Chunking Strategy Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `full_markdown` source representation and `markdown_heading` chunking strategy from the index pipeline, retaining `full_text` (naive path) and `block` (semantic CDM path).

**Architecture:** `full_markdown` + `markdown_heading` is removed at every layer — schema validation, source resolution, chunking dispatch, frontend UI, and tests. The CDM `ParsedDocument.full_markdown` field and all parser adapters are untouched; only the *indexing/chunking* pipeline loses the markdown path. `full_text` + text splitters and `block` + block strategy remain as the two valid index configurations.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, React 18, TypeScript, Vitest

**Spec:** `docs/superpowers/specs/2026-05-30-chunking-strategy-simplification-design.md`

---

## File Map

| Action | File |
|---|---|
| Modify | `backend/app/schemas/index.py` |
| Modify | `backend/app/services/source_resolution_service.py` |
| Modify | `backend/app/services/chunking_dispatcher.py` |
| Modify | `backend/app/services/index_processing_service.py` |
| **Delete** | `backend/app/services/markdown_chunking_service.py` |
| Modify | `backend/tests/schemas/test_index_config_schema.py` |
| **Delete** | `backend/tests/services/test_markdown_chunking_service.py` |
| Modify | `backend/tests/services/test_chunking_dispatcher.py` |
| Modify | `backend/tests/routers/test_preview_chunks_router.py` |
| Modify | `frontend/src/types/index.ts` |
| Modify | `frontend/src/lib/parsed-documents.ts` |
| Modify | `frontend/src/pages/CreateIndexPage.tsx` |
| Modify | `frontend/src/components/indexes/CitationFooter.tsx` |
| Modify | `frontend/src/pages/IndexDetailPage.test.tsx` |
| Modify | `frontend/src/components/indexes/CitationFooter.test.tsx` |
| Modify | `frontend/src/components/indexes/ParsedDocumentPicker.test.tsx` |

---

## Task 1: IndexConfig schema — remove full_markdown and markdown fields

**Files:**
- Modify: `backend/app/schemas/index.py`
- Modify: `backend/tests/schemas/test_index_config_schema.py`

- [ ] **Step 1: Write a failing test asserting full_markdown is rejected**

Add this test to `backend/tests/schemas/test_index_config_schema.py` after the existing `test_index_config_rejects_legacy_raw_text` test:

```python
def test_index_config_rejects_full_markdown():
    with pytest.raises(PydanticValidationError, match="source_representation"):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
        ))
```

- [ ] **Step 2: Run the test to confirm it fails**

```
uv run --directory backend python -m pytest tests/schemas/test_index_config_schema.py::test_index_config_rejects_full_markdown -v
```

Expected: `FAILED` — `PydanticValidationError` is not raised because `full_markdown` is currently valid.

- [ ] **Step 3: Remove full_markdown, markdown_heading, and markdown config fields from IndexConfig**

In `backend/app/schemas/index.py`, make these three changes:

**Change 1** — `source_representation` field:
```python
# Before
source_representation: Literal["full_text", "full_markdown", "block"] = Field(
    default="full_text", alias="sourceRepresentation"
)

# After
source_representation: Literal["full_text", "block"] = Field(
    default="full_text", alias="sourceRepresentation"
)
```

**Change 2** — `chunking_strategy` field:
```python
# Before
chunking_strategy: Literal[
    "fixed_size",
    "recursive_character",
    "markdown_heading",
    "block",
    "classified_block",
] = Field(
    default="recursive_character",
    alias="chunkingStrategy",
    description="How documents are split into chunks",
)

# After
chunking_strategy: Literal[
    "fixed_size",
    "recursive_character",
    "block",
    "classified_block",
] = Field(
    default="recursive_character",
    alias="chunkingStrategy",
    description="How documents are split into chunks",
)
```

**Change 3** — Remove markdown config fields (delete these two lines entirely):
```python
# Delete these two lines:
split_heading_level: int = Field(default=2, ge=1, le=3, alias="splitHeadingLevel")
max_section_chars: int = Field(default=4000, ge=500, le=16000, alias="maxSectionChars")
```

**Change 4** — Simplify `validate_representation_and_strategy`:
```python
# Before
@model_validator(mode="after")
def validate_representation_and_strategy(self) -> "IndexConfig":
    rep = self.source_representation
    strategy = self.chunking_strategy

    text_strategies = {"fixed_size", "recursive_character"}
    allowed: dict[str, set[str]] = {
        "full_text": text_strategies,
        "full_markdown": {"markdown_heading"},
        "block": {"block", "classified_block"},
    }
    if strategy not in allowed.get(rep, set()):
        raise ValueError(
            f"chunking_strategy='{strategy}' is not compatible with "
            f"source_representation='{rep}'. "
            f"Allowed: {sorted(allowed[rep])}"
        )
    return self

# After
@model_validator(mode="after")
def validate_representation_and_strategy(self) -> "IndexConfig":
    rep = self.source_representation
    strategy = self.chunking_strategy

    text_strategies = {"fixed_size", "recursive_character"}
    allowed: dict[str, set[str]] = {
        "full_text": text_strategies,
        "block": {"block", "classified_block"},
    }
    if strategy not in allowed.get(rep, set()):
        raise ValueError(
            f"chunking_strategy='{strategy}' is not compatible with "
            f"source_representation='{rep}'. "
            f"Allowed: {sorted(allowed[rep])}"
        )
    return self
```

- [ ] **Step 4: Run the new test to confirm it now passes**

```
uv run --directory backend python -m pytest tests/schemas/test_index_config_schema.py::test_index_config_rejects_full_markdown -v
```

Expected: `PASSED`

- [ ] **Step 5: Delete the now-dead markdown schema tests**

Remove these four test functions from `backend/tests/schemas/test_index_config_schema.py`:

- `test_index_config_full_markdown_requires_markdown_strategy` (lines 40–45)
- `test_index_config_markdown_heading_defaults` (lines 72–78)
- `test_index_config_split_heading_level_range` (lines 81–93)
- `test_index_config_max_section_chars_range` (lines 96–108)

- [ ] **Step 6: Run the full schema test file to confirm no regressions**

```
uv run --directory backend python -m pytest tests/schemas/test_index_config_schema.py -v
```

Expected: all remaining tests `PASSED`

- [ ] **Step 7: Commit**

```
git add backend/app/schemas/index.py backend/tests/schemas/test_index_config_schema.py
git commit -m "feat(schema): remove full_markdown source representation and markdown_heading strategy"
```

---

## Task 2: Remove full_markdown from SourceResolutionService

**Files:**
- Modify: `backend/app/services/source_resolution_service.py`

- [ ] **Step 1: Remove the full_markdown branch from SourceResolutionService**

In `backend/app/services/source_resolution_service.py`:

**Change 1** — Update the `SourceRepresentation` type alias:
```python
# Before
SourceRepresentation = Literal["full_text", "full_markdown", "block"]

# After
SourceRepresentation = Literal["full_text", "block"]
```

**Change 2** — Delete the `full_markdown` resolution branch from `resolve()`:
```python
# Remove this entire block from resolve():
if source_representation == "full_markdown":
    if parsed_doc.full_markdown is None:
        raise ValidationError(
            f"Parsed document {parsed_document_id} has no full_markdown. "
            "Re-parse with a configuration that outputs markdown."
        )
    return TextSource(
        text=parsed_doc.full_markdown,
        page_boundaries=_extract_page_boundaries(content),
    )
```

The `_extract_page_boundaries` function and `TextSource.page_boundaries` field are **not** removed — they are still used by the `full_text` path.

- [ ] **Step 2: Run the source resolution tests**

```
uv run --directory backend python -m pytest tests/ -k "source_resolution" -v
```

Expected: all `PASSED` (or no test found — check for source resolution tests with `find backend/tests -name "*source_resol*"` if unsure)

- [ ] **Step 3: Commit**

```
git add backend/app/services/source_resolution_service.py
git commit -m "refactor(source-resolution): remove full_markdown resolution path"
```

---

## Task 3: Remove full_markdown from ChunkingDispatcher; delete MarkdownChunkingService

**Files:**
- Modify: `backend/app/services/chunking_dispatcher.py`
- Delete: `backend/app/services/markdown_chunking_service.py`
- Delete: `backend/tests/services/test_markdown_chunking_service.py`
- Modify: `backend/tests/services/test_chunking_dispatcher.py`

- [ ] **Step 1: Delete the markdown chunking service and its tests**

```
rm backend/app/services/markdown_chunking_service.py
rm backend/tests/services/test_markdown_chunking_service.py
```

- [ ] **Step 2: Remove MarkdownChunkingService from ChunkingDispatcher**

Replace the entire contents of `backend/app/services/chunking_dispatcher.py` with:

```python
"""Dispatch a resolved ChunkSource + IndexConfig to the right chunker."""
from app.schemas.index import IndexConfig
from app.services.block_chunking_service import (
    BlockChunkingService,
    get_block_chunking_service,
)
from app.services.chunking_service import (
    ChunkResult,
    ChunkingService,
    get_chunking_service,
)
from app.services.source_resolution_service import (
    BlocksSource,
    ChunkSource,
    TextSource,
)


class ChunkingDispatcher:
    """Routes a `ChunkSource` to the right chunker based on the config."""

    def __init__(
        self,
        chunking_service: ChunkingService | None = None,
        block_chunking_service: BlockChunkingService | None = None,
    ) -> None:
        self.chunking_service = chunking_service or get_chunking_service()
        self.block_chunking_service = (
            block_chunking_service or get_block_chunking_service()
        )

    def dispatch(
        self,
        *,
        source: ChunkSource,
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if isinstance(source, TextSource):
            return self.chunking_service.chunk_text(
                text=source.text,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
                page_boundaries=source.page_boundaries or None,
            )
        if isinstance(source, BlocksSource):
            if config.chunking_strategy == "classified_block":
                raise NotImplementedError(
                    "classified_block chunking requires a classification run "
                    "and is not yet implemented"
                )
            return self.block_chunking_service.chunk_blocks(
                blocks=source.blocks,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
            )
        raise TypeError(f"Unsupported ChunkSource type: {type(source).__name__}")
```

- [ ] **Step 3: Delete the full_markdown dispatcher test**

In `backend/tests/services/test_chunking_dispatcher.py`, delete the function `test_dispatch_text_source_full_markdown_routes_to_markdown_service` (the one that creates a `TextSource` with markdown text and a `full_markdown` / `markdown_heading` config).

- [ ] **Step 4: Run the remaining dispatcher tests**

```
uv run --directory backend python -m pytest tests/services/test_chunking_dispatcher.py -v
```

Expected: all remaining tests `PASSED`. The deleted test no longer appears.

- [ ] **Step 5: Commit**

```
git add backend/app/services/chunking_dispatcher.py backend/tests/services/test_chunking_dispatcher.py
git rm backend/app/services/markdown_chunking_service.py
git rm backend/tests/services/test_markdown_chunking_service.py
git commit -m "refactor(chunking): remove MarkdownChunkingService and full_markdown dispatch path"
```

---

## Task 4: Update IndexProcessingService and preview chunks router test

**Files:**
- Modify: `backend/app/services/index_processing_service.py`
- Modify: `backend/tests/routers/test_preview_chunks_router.py`

- [ ] **Step 1: Update the source representation guard in IndexProcessingService**

In `backend/app/services/index_processing_service.py`, find the condition (around line 175):

```python
# Before
if config.source_representation in ("full_text", "full_markdown", "block"):

# After
if config.source_representation in ("full_text", "block"):
```

- [ ] **Step 2: Convert the full_markdown preview test to assert 422**

In `backend/tests/routers/test_preview_chunks_router.py`:

**Change 1** — Delete the `_full_markdown_config()` helper function (lines 124–136).

**Change 2** — Replace `test_preview_chunks_with_parsed_document_id_full_markdown` with a test that asserts `full_markdown` config is rejected:

```python
@pytest.mark.asyncio
async def test_preview_chunks_rejects_full_markdown_config(
    client: AsyncClient, test_db: AsyncSession
):
    """Submitting full_markdown source representation returns 422."""
    token = await _signup(client, "preview_reject_markdown@example.com")
    user = await _user_by_email(test_db, "preview_reject_markdown@example.com")
    project = await _make_project(test_db, user)

    _doc, pdoc = await _seed_run_with_pdoc(
        test_db,
        user=user,
        project=project,
        sha="a" * 64,
        full_markdown="# Heading\n\nSome content.",
    )
    assert pdoc is not None

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={
            "parsedDocumentId": str(pdoc.parse_run_id),
            "config": {
                "parser": "llamaparse",
                "parseConfigHash": "h" * 64,
                "sourceRepresentation": "full_markdown",
                "chunkingStrategy": "markdown_heading",
                "chunkSize": 512,
                "chunkOverlap": 0,
                "splitHeadingLevel": 2,
                "maxSectionChars": 4000,
                "embeddingProvider": "openai",
                "embeddingModel": "text-embedding-3-small",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
```

**Change 3** — Update `test_preview_chunks_parsed_document_outside_project_returns_404` to use `_full_text_config()` instead of `_full_markdown_config()`. Find the two occurrences of `_full_markdown_config()` in that test and replace with `_full_text_config()`.

- [ ] **Step 3: Run the updated router tests**

```
uv run --directory backend python -m pytest tests/routers/test_preview_chunks_router.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 4: Run the full backend test suite to confirm no regressions**

```
uv run --directory backend python -m pytest -o "addopts=" -x -q
```

Expected: all tests pass. If any fail, investigate before proceeding.

- [ ] **Step 5: Commit**

```
git add backend/app/services/index_processing_service.py backend/tests/routers/test_preview_chunks_router.py
git commit -m "refactor(processing): remove full_markdown from index processing service and preview test"
```

---

## Task 5: Frontend — TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/parsed-documents.ts`

- [ ] **Step 1: Update SourceRepresentation and ChunkingStrategy types**

In `frontend/src/types/index.ts`:

**Change 1** — `SourceRepresentation`:
```typescript
// Before
export type SourceRepresentation = 'full_text' | 'full_markdown' | 'block'

// After
export type SourceRepresentation = 'full_text' | 'block'
```

**Change 2** — `ChunkingStrategy`:
```typescript
// Before
export type ChunkingStrategy =
  | 'fixed_size'
  | 'recursive_character'
  | 'markdown_heading'
  | 'block'
  | 'classified_block'

// After
export type ChunkingStrategy =
  | 'fixed_size'
  | 'recursive_character'
  | 'block'
  | 'classified_block'
```

**Change 3** — `ChunkCitation.sourceType`:
```typescript
// Before
sourceType: 'raw_text' | 'full_text' | 'full_markdown' | 'block'

// After
sourceType: 'raw_text' | 'full_text' | 'block'
```

- [ ] **Step 2: Update the parsed-documents API helper type**

In `frontend/src/lib/parsed-documents.ts`:

```typescript
// Before
representation?: 'full_text' | 'full_markdown' | 'block'

// After
representation?: 'full_text' | 'block'
```

- [ ] **Step 3: Run lint only (do not build yet)**

```
npm run --prefix frontend lint
```

Expected: lint passes. The TypeScript build will fail at this point because `CitationFooter.tsx` still compares `sourceType === 'full_markdown'` against the narrowed union, and `IndexDetailPage.test.tsx` still passes `'full_markdown'` as a `SourceRepresentation`. Both are fixed in Task 7.

- [ ] **Step 4: Commit**

```
git add frontend/src/types/index.ts frontend/src/lib/parsed-documents.ts
git commit -m "refactor(types): remove full_markdown from SourceRepresentation, ChunkingStrategy, ChunkCitation"
```

---

## Task 6: Frontend — CreateIndexPage.tsx

**Files:**
- Modify: `frontend/src/pages/CreateIndexPage.tsx`

- [ ] **Step 1: Remove full_markdown from handleSourceRepresentationChange**

Find `handleSourceRepresentationChange` (around line 124):

```typescript
// Before
const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_markdown') updateConfig('chunkingStrategy', 'markdown_heading')
    else if (value === 'full_text') updateConfig('chunkingStrategy', 'recursive_character')
    else if (value === 'block') updateConfig('chunkingStrategy', 'block')
    setSelectedParsedDocIds([])
    setPreviewDocId(null)
}

// After
const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_text') updateConfig('chunkingStrategy', 'recursive_character')
    else if (value === 'block') updateConfig('chunkingStrategy', 'block')
    setSelectedParsedDocIds([])
    setPreviewDocId(null)
}
```

- [ ] **Step 2: Clean up hasFullMarkdown usage and the unavailable-markdown warning in handleParserFamilyChange**

In `handleParserFamilyChange` (around line 133), make these changes:

**Change 1** — Remove `hasMarkdown` variable and stop passing it to `setSelectedFamily`:
```typescript
// Before
const hasMarkdown = opt?.hasFullMarkdown ?? false
setSelectedFamily({ ...f, hasFullMarkdown: hasMarkdown })

// After
setSelectedFamily({ ...f })
```

**Change 2** — Remove the three-line `full_markdown` downgrade block:
```typescript
// Remove this block entirely:
if (config.sourceRepresentation === 'full_markdown' && !hasMarkdown) {
    updateConfig('sourceRepresentation', 'full_text')
    updateConfig('chunkingStrategy', 'recursive_character')
}
```

**Change 3** — Remove `hasFullMarkdown` from the local `SelectedFamily` interface (around line 43):
```typescript
// Before
interface SelectedFamily {
  parser: string
  parseConfigHash: string
  hasFullMarkdown: boolean
}

// After
interface SelectedFamily {
  parser: string
  parseConfigHash: string
}
```

- [ ] **Step 3: Remove the full_markdown ToggleGroupItem from the source representation selector**

Find the ToggleGroup for source representation (around line 323). Remove the middle item:

```tsx
// Remove this ToggleGroupItem entirely:
<ToggleGroupItem
  value="full_markdown"
  aria-label="Full Markdown"
  disabled={!selectedFamily?.hasFullMarkdown}
>
  Full Markdown
</ToggleGroupItem>
```

- [ ] **Step 4: Remove the full_markdown chunking config panel**

Find the three-branch conditional starting at `{config.sourceRepresentation === 'full_markdown' ? (` (around line 387). 

Replace the entire three-branch conditional with the two-branch version:

```tsx
// Before
{config.sourceRepresentation === 'full_markdown' ? (
  <>
    <div className="space-y-2">
      <Label>Heading split level</Label>
      <ToggleGroup
        type="single"
        value={String(config.splitHeadingLevel ?? 2)}
        onValueChange={(v) => v && updateConfig('splitHeadingLevel', parseInt(v))}
        className="justify-start"
      >
        <ToggleGroupItem value="1">H1 only</ToggleGroupItem>
        <ToggleGroupItem value="2">H1 + H2</ToggleGroupItem>
        <ToggleGroupItem value="3">H1 + H2 + H3</ToggleGroupItem>
      </ToggleGroup>
    </div>
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Max section size</Label>
        <span className="text-sm text-muted-foreground">
          {(config.maxSectionChars ?? 4000).toLocaleString()} chars
        </span>
      </div>
      <Slider
        min={500} max={16000} step={500}
        value={[config.maxSectionChars ?? 4000]}
        onValueChange={([v]) => updateConfig('maxSectionChars', v)}
      />
      <p className="text-xs text-muted-foreground">
        Sections larger than this are split further.
      </p>
    </div>
  </>
) : config.sourceRepresentation === 'block' ? (
  <BlockConfigPanel config={config} onUpdate={updateConfig} />
) : (
  /* full_text panel — chunk size / overlap / strategy inputs */
  ...
)}

// After — remove the full_markdown branch, keep the other two:
{config.sourceRepresentation === 'block' ? (
  <BlockConfigPanel config={config} onUpdate={updateConfig} />
) : (
  /* full_text panel — chunk size / overlap / strategy inputs (unchanged) */
  ...
)}
```

Keep everything inside the `block` branch and the `else` (full_text) branch exactly as-is; only remove the `full_markdown ? ... :` leading branch.

- [ ] **Step 5: Remove the "Full Markdown is unavailable" warning paragraph**

In `CreateIndexPage.tsx`, find and delete this block (just after the ToggleGroup for source representation, around line 345):

```tsx
{!selectedFamily?.hasFullMarkdown && (
  <p className="text-sm text-muted-foreground">
    Full Markdown is unavailable — the selected parse-config family does not produce markdown output.
  </p>
)}
```

- [ ] **Step 6: Run lint**

```
npm run --prefix frontend lint
```

Expected: no errors related to `full_markdown`, `splitHeadingLevel`, `maxSectionChars`, or `hasFullMarkdown` in CreateIndexPage.

- [ ] **Step 7: Commit**

```
git add frontend/src/pages/CreateIndexPage.tsx
git commit -m "feat(ui): remove full_markdown source representation from index creation form"
```

---

## Task 7: Frontend — CitationFooter + all frontend tests

**Files:**
- Modify: `frontend/src/components/indexes/CitationFooter.tsx`
- Modify: `frontend/src/components/indexes/CitationFooter.test.tsx`
- Modify: `frontend/src/pages/IndexDetailPage.test.tsx`
- Modify: `frontend/src/components/indexes/ParsedDocumentPicker.test.tsx`

- [ ] **Step 1: Remove the full_markdown heading breadcrumb from CitationFooter**

In `frontend/src/components/indexes/CitationFooter.tsx`, delete lines 39–48:

```tsx
// Remove this block entirely:
{citation.sourceType === 'full_markdown' && citation.headingPath && citation.headingPath.length > 0 && (
  <span className="flex items-center gap-1">
    {citation.headingPath.map((h, i) => (
      <span key={i} className="flex items-center gap-1">
        {i > 0 && <span className="text-zinc-300">›</span>}
        <span>{h}</span>
      </span>
    ))}
  </span>
)}
```

- [ ] **Step 2: Remove the full_markdown test case from CitationFooter.test.tsx**

In `frontend/src/components/indexes/CitationFooter.test.tsx`, delete the entire `it('renders heading breadcrumb for markdown citations', ...)` test (lines 33–50).

- [ ] **Step 3: Update IndexDetailPage.test.tsx**

In `frontend/src/pages/IndexDetailPage.test.tsx`, find the fixture using `sourceRepresentation: 'full_markdown'` and `chunkingStrategy: 'markdown_heading'` and update it:

```typescript
// Before
config: {
  sourceRepresentation: 'full_markdown',
  ...
  chunkingStrategy: 'markdown_heading',
  ...
}

// After
config: {
  sourceRepresentation: 'full_text',
  ...
  chunkingStrategy: 'recursive_character',
  ...
}
```

- [ ] **Step 4: Update ParsedDocumentPicker.test.tsx**

In `frontend/src/components/indexes/ParsedDocumentPicker.test.tsx`, find all three occurrences of `representation: 'full_markdown'` and replace with `representation: 'block'`:

```typescript
// Before (three occurrences)
representation: 'full_markdown' as const,
// and
representation: 'full_markdown',

// After
representation: 'block' as const,
// and
representation: 'block',
```

- [ ] **Step 5: Run the frontend test suite**

```
npx --prefix frontend vitest run
```

Expected: all tests pass. The deleted `full_markdown` citation test no longer appears.

- [ ] **Step 6: Run the full frontend build**

```
npm run --prefix frontend build
```

Expected: build succeeds with no type errors.

- [ ] **Step 7: Commit**

```
git add frontend/src/components/indexes/CitationFooter.tsx frontend/src/components/indexes/CitationFooter.test.tsx frontend/src/pages/IndexDetailPage.test.tsx frontend/src/components/indexes/ParsedDocumentPicker.test.tsx
git commit -m "feat(ui): remove full_markdown citation display and update frontend tests"
```

---

## Final Verification

- [ ] **Run the complete backend test suite**

```
uv run --directory backend python -m pytest -o "addopts=" -q
```

Expected: all tests pass, no references to `full_markdown` remain in chunking/indexing paths.

- [ ] **Run the complete frontend test suite and build**

```
npx --prefix frontend vitest run && npm run --prefix frontend build
```

Expected: all Vitest tests pass, TypeScript build succeeds.

- [ ] **Verify full_markdown is no longer accepted by the API**

Confirm with a quick manual test or by checking the schema test `test_index_config_rejects_full_markdown` passes: submitting `sourceRepresentation: full_markdown` to any index endpoint returns `422 Unprocessable Entity`.
