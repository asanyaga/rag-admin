# Chunk Details Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface full per-chunk LLM prompts, responses, extracted data, and usage stats in a list+detail panel inside `ExtractionResultViewer` for chunked extraction runs.

**Architecture:** Backend zips per-chunk `ExtractionOutput` with `DocumentChunk` metadata in `merge_outputs`, writing a `chunks` array into the merged `extractionMetadata` JSONB field. Frontend adds a `ChunkDetailsPanel` inner component to `ExtractionResultViewer` that renders a two-column layout — scrollable chunk list on the left, full detail pane on the right — collapsed by default, only shown when `chunks` data is present.

**Tech Stack:** Python 3.12, FastAPI backend; React 18, TypeScript, shadcn/ui, Tailwind CSS frontend; Vitest + Testing Library.

## Global Constraints

- No new API endpoints, no DB migrations — all data stored in existing `extractionMetadata` JSONB column.
- Per-chunk dict uses camelCase top-level keys (`chunkIndex`, `pageIndices`, `promptMessages`, `providerResponseRaw`, `structuredData`, `latencyMs`); `usage` keeps snake_case sub-keys (`prompt_tokens`, `completion_tokens`, `total_tokens`) to match the existing top-level `usage` convention.
- Page indices in `pageIndices` are 0-based (CDM convention); UI displays them 1-based (`pageIndices[0] + 1`).
- Chunk list labels: "Chunk N" (1-based: `chunkIndex + 1`); page badge "pp. X–Y" omitted when `pageIndices` is empty.
- `merge_outputs` signature change is backward-compatible: `chunks` param defaults to `None`; existing call-sites and tests that omit it are unaffected.
- `UserMessageDisplay` and `parseUserContent` from `ExtractionResultViewer.tsx` are reused in `ChunkDetailsPanel` — do not duplicate.
- `FormattedJson` imported from `@/components/shared/FormattedJson`.
- `cn` imported from `@/lib/utils` for conditional class merging.
- Run backend tests: `uv run --directory backend python -m pytest tests/adapters/extraction/chunking/test_merge.py -v`
- Run frontend tests: `npx vitest run --reporter verbose src/components/extraction/ExtractionResultViewer.test.tsx` (from `frontend/`)
- Run frontend lint: `npm run lint` (from `frontend/`)

---

### Task 1: Backend — store per-chunk summaries in extractionMetadata

**Files:**
- Modify: `backend/app/adapters/extraction/chunking/merge.py`
- Modify: `backend/app/adapters/extraction/pipeline.py`
- Test: `backend/tests/adapters/extraction/chunking/test_merge.py`

**Interfaces:**
- Produces: `merge_outputs(..., chunks: list | None = None)` — when `chunks` is provided, merged `extractionMetadata` gains a `chunks` key containing a list of per-chunk dicts.
- Per-chunk dict shape (consumed by Task 2):
  ```python
  {
      "chunkIndex": int,          # 0-based
      "pageIndices": list[int],   # 0-based page numbers
      "promptMessages": list | None,
      "providerResponseRaw": dict | None,
      "structuredData": dict | None,
      "usage": dict | None,       # {"prompt_tokens", "completion_tokens", "total_tokens"}
      "latencyMs": int | None,
  }
  ```

- [ ] **Step 1: Write failing tests for merge_outputs with chunks**

Add to `backend/tests/adapters/extraction/chunking/test_merge.py`:

```python
from dataclasses import dataclass


@dataclass
class _FakeChunk:
    chunk_index: int
    page_indices: list


def _out_full(data, prompt_messages=None, provider_response=None, latency_ms=500):
    return ExtractionOutput(
        structured_data=data,
        source_parse_run_id=_RUN,
        citations=[],
        provider_response_raw=provider_response or {"raw": "ok"},
        extraction_metadata={
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "prompt_messages": prompt_messages or [{"role": "system", "content": "sys"}],
            "latency_ms": latency_ms,
            "model": "claude-opus-4-7",
            "provider": "anthropic",
        },
    )


def test_chunks_array_populated_when_chunks_param_provided():
    c0 = _FakeChunk(chunk_index=0, page_indices=[0, 1])
    c1 = _FakeChunk(chunk_index=1, page_indices=[2])
    o0 = _out_full({"sku": "A"}, latency_ms=1000)
    o1 = _out_full({"sku": "B"}, latency_ms=2000)

    merged = merge_outputs([o0, o1], _SCHEMA, dedupe_key=None, chunks=[c0, c1])

    assert "chunks" in merged.extraction_metadata
    chunks = merged.extraction_metadata["chunks"]
    assert len(chunks) == 2

    assert chunks[0]["chunkIndex"] == 0
    assert chunks[0]["pageIndices"] == [0, 1]
    assert chunks[0]["latencyMs"] == 1000
    assert chunks[0]["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert chunks[0]["structuredData"] == {"sku": "A"}
    assert chunks[0]["providerResponseRaw"] == {"raw": "ok"}
    assert chunks[0]["promptMessages"] == [{"role": "system", "content": "sys"}]

    assert chunks[1]["chunkIndex"] == 1
    assert chunks[1]["pageIndices"] == [2]
    assert chunks[1]["latencyMs"] == 2000


def test_chunks_key_absent_when_chunks_param_not_provided():
    merged = merge_outputs([_out({})], _SCHEMA, dedupe_key=None)
    assert "chunks" not in merged.extraction_metadata


def test_chunks_key_absent_when_chunks_param_is_none():
    merged = merge_outputs([_out({})], _SCHEMA, dedupe_key=None, chunks=None)
    assert "chunks" not in merged.extraction_metadata
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/adapters/extraction/chunking/test_merge.py::test_chunks_array_populated_when_chunks_param_provided -v
```

Expected: FAIL — `merge_outputs() got an unexpected keyword argument 'chunks'`

- [ ] **Step 3: Implement merge_outputs changes**

In `backend/app/adapters/extraction/chunking/merge.py`, update the function signature and add the chunks block after `metadata` is built:

```python
def merge_outputs(
    outputs: list[ExtractionOutput],
    schema: dict[str, Any],
    dedupe_key: str | None,
    chunks: list | None = None,
) -> ExtractionOutput:
```

After the existing lines that build `metadata` (after the `if scalar_conflicts:` block and the existing model/provider/latency propagation), add:

```python
    if chunks is not None:
        metadata["chunks"] = [
            {
                "chunkIndex": chunk.chunk_index,
                "pageIndices": chunk.page_indices,
                "promptMessages": (out.extraction_metadata or {}).get("prompt_messages"),
                "providerResponseRaw": out.provider_response_raw,
                "structuredData": out.structured_data,
                "usage": (out.extraction_metadata or {}).get("usage"),
                "latencyMs": (out.extraction_metadata or {}).get("latency_ms"),
            }
            for chunk, out in zip(chunks, outputs)
        ]
```

- [ ] **Step 4: Update pipeline.py to pass chunks**

In `backend/app/adapters/extraction/pipeline.py`, find the final `return merge_outputs(...)` call (the one inside the multi-chunk path, currently on the last line of the `extract` method):

```python
        dedupe_key = self._chunking.get("config", {}).get("dedupeKey")
        return merge_outputs(list(results), schema, dedupe_key)
```

Change to:

```python
        dedupe_key = self._chunking.get("config", {}).get("dedupeKey")
        return merge_outputs(list(results), schema, dedupe_key, chunks=chunks)
```

`chunks` here is the `list[DocumentChunk]` already in scope from line 75 (`chunks = strategy.split(...)`).

- [ ] **Step 5: Run all merge tests to confirm pass**

```
uv run --directory backend python -m pytest tests/adapters/extraction/chunking/test_merge.py -v
```

Expected: All 13 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/adapters/extraction/chunking/merge.py backend/app/adapters/extraction/pipeline.py backend/tests/adapters/extraction/chunking/test_merge.py
git commit -m "feat(extraction): store per-chunk prompt, response, and usage in extractionMetadata.chunks"
```

---

### Task 2: Frontend — Chunk Details panel in ExtractionResultViewer

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`

**Interfaces:**
- Consumes from Task 1: `extractionMetadata.chunks` array with shape described above.
- Consumes from existing code: `UserMessageDisplay`, `parseUserContent`, `FormattedJson`, `ConfigRow` — all defined earlier in `ExtractionResultViewer.tsx`; do not duplicate.
- `cn` from `@/lib/utils`.
- shadcn Badge from `@/components/ui/badge` (already imported).

- [ ] **Step 1: Write failing tests**

Add the following to `frontend/src/components/extraction/ExtractionResultViewer.test.tsx` (after the existing `buildChunkedResult` helper, before the existing `describe` block):

```tsx
function buildChunkedResultWithDetails(
  overrides: Partial<ExtractionResult> = {}
): ExtractionResult {
  return buildResult({
    extractionMethod: 'llm',
    extractionMetadata: {
      chunkCount: 2,
      usage: { total_tokens: 6400 },
      model: 'claude-opus-4-7',
      provider: 'anthropic',
      latency_ms: 2700,
      chunks: [
        {
          chunkIndex: 0,
          pageIndices: [0, 1, 2],
          promptMessages: [
            { role: 'system', content: 'Shared system prompt.' },
            {
              role: 'user',
              content:
                'Extract.\n<schema>{"type":"object"}</schema>\n<document>Page 1 content</document>',
            },
          ],
          providerResponseRaw: { id: 'r1', answer: 'chunk-1-response' },
          structuredData: { invoice: 'INV-001' },
          usage: { prompt_tokens: 3000, completion_tokens: 500, total_tokens: 3500 },
          latencyMs: 1500,
        },
        {
          chunkIndex: 1,
          pageIndices: [3, 4],
          promptMessages: [
            { role: 'system', content: 'Shared system prompt.' },
            {
              role: 'user',
              content:
                'Extract.\n<schema>{"type":"object"}</schema>\n<document>Page 4 content</document>',
            },
          ],
          providerResponseRaw: { id: 'r2', answer: 'chunk-2-response' },
          structuredData: { invoice: 'INV-002' },
          usage: { prompt_tokens: 2500, completion_tokens: 400, total_tokens: 2900 },
          latencyMs: 1200,
        },
      ],
    },
    providerResponseRaw: null,
    ...overrides,
  })
}
```

Add a new `describe` block at the end of the test file:

```tsx
describe('Chunk Details panel', () => {
  it('is hidden when extractionMetadata has no chunks array', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.queryByText('Chunk Details')).not.toBeInTheDocument()
  })

  it('shows chunk list with page range badges', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText('Chunk 1')).toBeInTheDocument()
    expect(screen.getByText('pp. 1–3')).toBeInTheDocument()
    expect(screen.getByText('Chunk 2')).toBeInTheDocument()
    expect(screen.getByText('pp. 4–5')).toBeInTheDocument()
  })

  it('shows system prompt with shared-across-chunks note by default', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText('Shared system prompt.')).toBeInTheDocument()
    expect(screen.getByText(/identical across all chunks/i)).toBeInTheDocument()
  })

  it('shows pre-merge note in extracted section', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText(/pre-merge/i)).toBeInTheDocument()
    expect(screen.getByText(/conflict resolution and deduplication/i)).toBeInTheDocument()
  })

  it('shows first chunk document content by default', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    expect(screen.getByText('Page 1 content')).toBeInTheDocument()
  })

  it('switches detail pane when second chunk row is clicked', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    const chunkButtons = screen.getAllByRole('button')
    const chunk2Btn = chunkButtons.find((b) => b.textContent?.includes('Chunk 2'))!
    await user.click(chunk2Btn)
    expect(screen.getByText('Page 4 content')).toBeInTheDocument()
  })

  it('shows token counts for selected chunk', async () => {
    const user = userEvent.setup()
    render(<ExtractionResultViewer result={buildChunkedResultWithDetails()} />)
    await user.click(screen.getByRole('button', { name: /chunk details/i }))
    // Chunk 1 total tokens = 3,500
    expect(screen.getByText('3,500')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```
npx vitest run --reporter verbose src/components/extraction/ExtractionResultViewer.test.tsx
```

Expected: 6 new tests FAIL — "Chunk Details" not found.

- [ ] **Step 3: Add ChunkDetail interface and ChunkDetailsPanel to ExtractionResultViewer.tsx**

Add the `cn` import and `ChunkDetail` interface, then the `ChunkDetailsPanel` component. Place these immediately after the `NotAvailableChunked` component definition (before `UserMessageDisplay`).

**Add to imports at top of file:**
```tsx
import { cn } from '@/lib/utils'
```

**Add after `NotAvailableChunked` component:**

```tsx
interface ChunkDetail {
  chunkIndex: number
  pageIndices: number[]
  promptMessages: Array<{ role: string; content: string }> | null
  providerResponseRaw: Record<string, unknown> | null
  structuredData: Record<string, unknown> | null
  usage: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  } | null
  latencyMs: number | null
}

function ChunkDetailsPanel({ chunks }: { chunks: ChunkDetail[] }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const chunk = chunks[selectedIndex]
  const systemContent = chunk.promptMessages?.[0]?.content ?? null
  const userMessage = chunk.promptMessages?.[1] ?? null

  return (
    <div className="grid grid-cols-[16rem_1fr] divide-x overflow-hidden">
      {/* Chunk list */}
      <div className="overflow-y-auto max-h-[32rem]">
        {chunks.map((c, i) => {
          const pages = c.pageIndices
          const pageLabel =
            pages.length > 0
              ? `pp. ${pages[0] + 1}–${pages[pages.length - 1] + 1}`
              : null
          const tokens = c.usage?.total_tokens?.toLocaleString() ?? '—'
          const latency =
            c.latencyMs != null ? `${c.latencyMs.toLocaleString()} ms` : '—'
          return (
            <button
              key={i}
              onClick={() => setSelectedIndex(i)}
              className={cn(
                'w-full text-left px-4 py-3 border-b last:border-b-0 hover:bg-muted/50 transition-colors',
                selectedIndex === i && 'bg-muted border-l-2 border-l-primary'
              )}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">
                  Chunk {c.chunkIndex + 1}
                </span>
                {pageLabel && (
                  <Badge variant="outline" className="text-xs font-normal">
                    {pageLabel}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {tokens} tokens · {latency}
              </p>
            </button>
          )
        })}
      </div>

      {/* Detail pane */}
      <div className="overflow-y-auto max-h-[32rem] px-4 py-3 space-y-4">
        {/* System */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-xs font-semibold text-muted-foreground">System</p>
            <span className="text-xs text-muted-foreground italic">
              · identical across all chunks
            </span>
          </div>
          <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-48 whitespace-pre-wrap">
            {systemContent ?? '—'}
          </pre>
        </div>

        {/* User */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-1">User</p>
          {userMessage ? (
            <UserMessageDisplay content={userMessage.content} />
          ) : (
            <p className="text-sm text-muted-foreground italic">—</p>
          )}
        </div>

        {/* LLM Response */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-1">
            LLM Response
          </p>
          {chunk.providerResponseRaw ? (
            <FormattedJson value={chunk.providerResponseRaw} maxHeight="20rem" />
          ) : (
            <p className="text-sm text-muted-foreground italic">
              No response recorded for this chunk.
            </p>
          )}
        </div>

        {/* Extracted (pre-merge) */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-0.5">
            Extracted{' '}
            <span className="font-normal italic">(pre-merge)</span>
          </p>
          <p className="text-xs text-muted-foreground mb-1">
            Raw output before conflict resolution and deduplication.
          </p>
          <FormattedJson value={chunk.structuredData ?? {}} maxHeight="16rem" />
        </div>

        {/* Usage */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2">Usage</p>
          <div className="grid grid-cols-4 gap-3">
            {(
              [
                ['Prompt tokens', chunk.usage?.prompt_tokens],
                ['Completion tokens', chunk.usage?.completion_tokens],
                ['Total tokens', chunk.usage?.total_tokens],
                ['Latency', chunk.latencyMs != null ? `${chunk.latencyMs.toLocaleString()} ms` : null],
              ] as [string, number | string | null | undefined][]
            ).map(([label, val]) => (
              <div key={label}>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-sm">
                  {val != null
                    ? typeof val === 'number'
                      ? val.toLocaleString()
                      : val
                    : '—'}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
```

Note: `useState` is already imported via React in the file. If not, add `import { useState } from 'react'`.

- [ ] **Step 4: Add Chunk Details collapsible to ExtractionResultViewer render**

In the `ExtractionResultViewer` component, after casting `meta` and `cfg`, add:

```tsx
const chunks = (meta?.chunks ?? null) as ChunkDetail[] | null
```

Then add the Chunk Details panel as the last item in the returned `<div className="space-y-4">`, after the LLM Response panel:

```tsx
{/* ── Chunk Details panel (chunked runs only) ────────────────────── */}
{chunks && chunks.length > 0 && (
  <Collapsible>
    <CollapsibleTrigger asChild>
      <Button variant="outline" size="sm" className="w-full justify-between">
        <span>Chunk Details</span>
        <ChevronDown className="h-4 w-4" />
      </Button>
    </CollapsibleTrigger>
    <CollapsibleContent>
      <Card className="mt-2 overflow-hidden">
        <ChunkDetailsPanel chunks={chunks} />
      </Card>
    </CollapsibleContent>
  </Collapsible>
)}
```

- [ ] **Step 5: Run targeted tests**

```
npx vitest run --reporter verbose src/components/extraction/ExtractionResultViewer.test.tsx
```

Expected: All 25 tests PASS (19 existing + 6 new).

- [ ] **Step 6: Run full frontend test suite**

```
npx vitest run --reporter verbose
```

Expected: All tests PASS; no regressions.

- [ ] **Step 7: Run lint**

```
npm run lint
```

Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/extraction/ExtractionResultViewer.tsx frontend/src/components/extraction/ExtractionResultViewer.test.tsx
git commit -m "feat(extraction-ui): add Chunk Details panel with list+detail view for per-chunk prompts, responses, and usage"
```

---

## Self-Review vs Spec

**Spec coverage:**

| Requirement | Task |
|---|---|
| `extractionMetadata.chunks` populated with `chunkIndex`, `pageIndices`, `promptMessages`, `providerResponseRaw`, `structuredData`, `usage`, `latencyMs` | Task 1 |
| `merge_outputs` backward-compatible (`chunks` defaults to `None`) | Task 1 — optional param, existing tests pass |
| `pipeline.py` passes `chunks=chunks` to `merge_outputs` at multi-chunk call-site | Task 1 Step 4 |
| Panel hidden when no chunks | Task 2 test + `chunks && chunks.length > 0` guard |
| Chunk list shows page ranges (1-based, badge omitted when empty) | Task 2 `ChunkDetailsPanel` |
| Chunk list shows formatted tokens + latency | Task 2 `ChunkDetailsPanel` |
| Selecting chunk updates detail pane | Task 2 `useState(selectedIndex)` |
| System prompt + "identical across all chunks" note | Task 2 |
| User message parsed (instruction/schema/document) via `UserMessageDisplay` | Task 2 — reuses existing helper |
| LLM Response via `FormattedJson` | Task 2 |
| Extracted (pre-merge) via `FormattedJson` + note | Task 2 |
| Usage 4-cell grid (prompt/completion/total/latency) | Task 2 |
| `parseUserContent` reused, not duplicated | Task 2 — `UserMessageDisplay` component call |
| All new behaviour covered by unit tests | Tasks 1 + 2 |
| No regressions | Task 2 Step 6 full suite |

**Placeholder scan:** No TBDs, no "implement later". All code blocks are complete.

**Type consistency:** `ChunkDetail.usage` uses `prompt_tokens` / `completion_tokens` / `total_tokens` (snake_case), matching the backend output from `extraction_metadata.get("usage")`. `ChunkDetail.latencyMs` (camelCase) matches `"latencyMs"` key written by `merge_outputs`. Consistent throughout Tasks 1 and 2.
