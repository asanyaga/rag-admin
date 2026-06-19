# Index Detail Page — Edit UI Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Index Detail page so users can see the full parse config, edit name/description regardless of index status (except while processing), and know when a re-index is needed.

**Architecture:** All changes are contained in `IndexDetailPage.tsx`. Task 1 fixes the status gate, renames the config button, and adds the `configDirty` warning banner. Task 2 replaces the flat 6-field config grid with a grouped 3-section layout showing all 13 `IndexConfig` fields. Tests live in `IndexDetailPage.test.tsx`; the mock is upgraded to `vi.fn()` in Task 1 so per-test overrides work cleanly.

**Tech Stack:** React 18, TypeScript, Vitest + Testing Library, Tailwind CSS, shadcn/ui.

## Global Constraints

- No new dependencies
- Follow existing Tailwind class patterns in `IndexDetailPage.tsx`
- `IndexUpdate` backend schema accepts only `name` and `description` — do not attempt to make config fields editable
- Tests run with: `cd frontend && npx vitest run src/pages/IndexDetailPage.test.tsx`

---

### Task 1: Fix status gate, rename button, add configDirty banner

All three changes live in `IndexDetailPage.tsx`. The test mock is also upgraded from arrow-function stubs to `vi.fn()` in this task so that Tasks 1 and 2 tests can override the mock per-test.

**Files:**
- Modify: `frontend/src/pages/IndexDetailPage.tsx:108` (`canEdit` definition)
- Modify: `frontend/src/pages/IndexDetailPage.tsx:367-378` (Settings button)
- Modify: `frontend/src/pages/IndexDetailPage.tsx:408-421` (processing/error banners — add configDirty banner after)
- Modify: `frontend/src/pages/IndexDetailPage.test.tsx` (upgrade mock + new tests)

**Interfaces:**
- Produces: `canEdit = index?.status !== 'processing'` — available for Task 2 tests to rely on
- Produces: `vi.fn()` mock setup via `beforeEach` — all subsequent test tasks build on this

- [ ] **Step 1: Upgrade the test mock to vi.fn() and add complete config fields to mockIndex**

Replace the `vi.mock('@/hooks/useIndexes', ...)` block and add a module-level `beforeEach` in `frontend/src/pages/IndexDetailPage.test.tsx`. Also add the missing `IndexConfig` fields (`splitHeadingLevel`, `maxSectionChars`, `groupByHeading`, `maxBlocksPerChunk`, `blockRoleFilter`) to `mockIndex` so future tests don't get `undefined` for those values.

Replace the hoisted `mockIndex.config` object (around line 12) with:
```tsx
config: {
  sourceRepresentation: 'full_text' as const,
  parser: 'llamaparse',
  parseConfigHash: 'abc123def456',
  chunkingStrategy: 'recursive_character' as const,
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters' as const,
  splitHeadingLevel: 2,
  maxSectionChars: 10000,
  groupByHeading: true,
  maxBlocksPerChunk: 10,
  blockRoleFilter: null,
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
  embeddingDimensions: null,
},
```

Add these imports after the existing imports at the top of the file:
```tsx
import { useIndexDetail, useIndexes } from '@/hooks/useIndexes'
```

Replace the `vi.mock('@/hooks/useIndexes', ...)` block (lines 59-73) with:
```tsx
vi.mock('@/hooks/useIndexes', () => ({
  useIndexDetail: vi.fn(),
  useIndexes: vi.fn(),
}))
```

Add a module-level `beforeEach` directly after that mock block (before the `vi.mock('@/api/indexes', ...)` line):
```tsx
beforeEach(() => {
  vi.mocked(useIndexDetail).mockReturnValue({
    index: mockIndex,
    chunks: null,
    isLoading: false,
    error: null,
    fetchIndex: vi.fn().mockResolvedValue(undefined),
    fetchChunks: vi.fn().mockResolvedValue(undefined),
    getChunk: vi.fn(),
  })
  vi.mocked(useIndexes).mockReturnValue({
    updateIndex: vi.fn(),
    processIndex: vi.fn(),
  })
})
```

- [ ] **Step 2: Write failing tests for Task 1 behaviours**

Add a new `describe` block at the end of `frontend/src/pages/IndexDetailPage.test.tsx`:

```tsx
describe('IndexDetailPage — status gate and config button', () => {
  it('shows the name edit button when index is ready', async () => {
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    // Hover is not easily simulated — the pencil is hidden via group-hover.
    // Assert canEdit path: description placeholder should be present (only rendered when canEdit).
    expect(screen.getByText('Add a description...')).toBeInTheDocument()
  })

  it('does not show the description placeholder when index is processing', async () => {
    vi.mocked(useIndexDetail).mockReturnValue({
      index: { ...mockIndex, status: 'processing' },
      chunks: null,
      isLoading: false,
      error: null,
      fetchIndex: vi.fn().mockResolvedValue(undefined),
      fetchChunks: vi.fn().mockResolvedValue(undefined),
      getChunk: vi.fn(),
    })
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(screen.queryByText('Add a description...')).not.toBeInTheDocument()
  })

  it('renders a "Config" button, not "Settings"', async () => {
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(screen.getByRole('button', { name: /config/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^settings$/i })).not.toBeInTheDocument()
  })

  it('shows a configDirty warning when configDirty is true', async () => {
    vi.mocked(useIndexDetail).mockReturnValue({
      index: { ...mockIndex, configDirty: true },
      chunks: null,
      isLoading: false,
      error: null,
      fetchIndex: vi.fn().mockResolvedValue(undefined),
      fetchChunks: vi.fn().mockResolvedValue(undefined),
      getChunk: vi.fn(),
    })
    renderPage()
    await waitFor(() =>
      expect(
        screen.getByText(/document set has changed since last index build/i),
      ).toBeInTheDocument(),
    )
  })

  it('does not show configDirty warning when configDirty is false', async () => {
    renderPage()
    await waitFor(() => screen.getByText('My Index'))
    expect(
      screen.queryByText(/document set has changed since last index build/i),
    ).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run tests — confirm new tests fail**

```bash
cd frontend && npx vitest run src/pages/IndexDetailPage.test.tsx
```

Expected: the 5 new tests fail (3 pass for existing tests, 5 new fail). Specifically:
- "renders a Config button, not Settings" fails because the button says "Settings"
- "does not show description placeholder when processing" fails because `canEdit` only allows `created`
- "shows a description placeholder when ready" fails for the same reason
- The configDirty tests fail because no banner exists yet

- [ ] **Step 4: Change `canEdit` to allow all statuses except processing**

In `frontend/src/pages/IndexDetailPage.tsx`, find line 108:
```tsx
const canEdit = index?.status === 'created'
```
Replace with:
```tsx
const canEdit = index?.status !== 'processing'
```

- [ ] **Step 5: Rename the "Settings" button to "Config"**

In `frontend/src/pages/IndexDetailPage.tsx`, find the Settings toggle button (lines ~367-378). Change the label:
```tsx
<button
  onClick={() => setShowConfig(!showConfig)}
  className={cn(
    'flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors',
    showConfig
      ? 'bg-muted border text-foreground'
      : 'border text-muted-foreground hover:bg-muted/50'
  )}
>
  <Settings className="h-4 w-4" /> Config
</button>
```

- [ ] **Step 6: Add the configDirty warning banner**

In `frontend/src/pages/IndexDetailPage.tsx`, after the error message block (after the `index.status === 'failed'` div, around line 421), add:

```tsx
{/* configDirty warning */}
{index.configDirty && (
  <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-700 dark:bg-amber-950/30 dark:border-amber-900 dark:text-amber-400 flex items-center gap-2">
    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
    Document set has changed since last index build — re-index to apply.
  </div>
)}
```

`AlertTriangle` is already imported at the top of the file.

- [ ] **Step 7: Run tests — all pass**

```bash
cd frontend && npx vitest run src/pages/IndexDetailPage.test.tsx
```

Expected: all tests pass, including the 5 new ones.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/IndexDetailPage.tsx frontend/src/pages/IndexDetailPage.test.tsx
git commit -m "feat(indexes): fix edit status gate, rename Config button, surface configDirty"
```

---

### Task 2: Full config panel with grouped sections

Replace the flat `configItems` array and its grid with three labelled sections (Source, Chunking, Embedding) that expose all `IndexConfig` fields. Block-specific fields (`groupByHeading`, `maxBlocksPerChunk`, `blockRoleFilter`) render conditionally when the chunking strategy is `block` or `classified_block`.

**Files:**
- Modify: `frontend/src/pages/IndexDetailPage.tsx:265-272` (remove `configItems` array)
- Modify: `frontend/src/pages/IndexDetailPage.tsx:424-435` (replace config drawer JSX)
- Modify: `frontend/src/pages/IndexDetailPage.test.tsx` (new describe block)

**Interfaces:**
- Consumes: `vi.fn()` mock setup from Task 1 (required for per-test overrides)
- Consumes: `showConfig` state already on the component — no changes to toggle logic
- Produces: visible text labels `Source`, `Chunking`, `Embedding` in the expanded config panel

- [ ] **Step 1: Write failing tests for the full config panel**

Add a new `describe` block at the end of `frontend/src/pages/IndexDetailPage.test.tsx`:

```tsx
describe('IndexDetailPage — full config panel', () => {
  it('shows Source, Chunking, Embedding section headings when Config is toggled', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.getByText('Chunking')).toBeInTheDocument()
    expect(screen.getByText('Embedding')).toBeInTheDocument()
  })

  it('shows parser, parse config hash (first 8 chars), and representation in Source section', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.getByText('llamaparse')).toBeInTheDocument()
    // parseConfigHash 'abc123def456' truncated to 'abc123de'
    expect(screen.getByText('abc123de')).toBeInTheDocument()
    expect(screen.getByText('full_text')).toBeInTheDocument()
  })

  it('shows chunking strategy, chunk size with unit, and overlap with unit', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.getByText('recursive_character')).toBeInTheDocument()
    expect(screen.getByText('512 characters')).toBeInTheDocument()
    expect(screen.getByText('50 characters')).toBeInTheDocument()
  })

  it('shows embedding provider, model, and dimensions in Embedding section', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.getByText('openai')).toBeInTheDocument()
    expect(screen.getByText('text-embedding-3-small')).toBeInTheDocument()
    // embeddingDimensions is null → shows 'Auto'
    expect(screen.getByText('Auto')).toBeInTheDocument()
  })

  it('shows block-specific fields for block chunking strategy', async () => {
    const user = userEvent.setup()
    vi.mocked(useIndexDetail).mockReturnValue({
      index: {
        ...mockIndex,
        config: {
          ...mockIndex.config,
          sourceRepresentation: 'block' as const,
          chunkingStrategy: 'block' as const,
          groupByHeading: true,
          maxBlocksPerChunk: 5,
          blockRoleFilter: ['paragraph', 'heading'],
        },
      },
      chunks: null,
      isLoading: false,
      error: null,
      fetchIndex: vi.fn().mockResolvedValue(undefined),
      fetchChunks: vi.fn().mockResolvedValue(undefined),
      getChunk: vi.fn(),
    })
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.getByText('Yes')).toBeInTheDocument()         // groupByHeading
    expect(screen.getByText('5')).toBeInTheDocument()           // maxBlocksPerChunk
    expect(screen.getByText('paragraph, heading')).toBeInTheDocument() // blockRoleFilter
  })

  it('shows "all" for role filter when blockRoleFilter is null', async () => {
    const user = userEvent.setup()
    vi.mocked(useIndexDetail).mockReturnValue({
      index: {
        ...mockIndex,
        config: {
          ...mockIndex.config,
          sourceRepresentation: 'block' as const,
          chunkingStrategy: 'classified_block' as const,
          groupByHeading: false,
          maxBlocksPerChunk: 10,
          blockRoleFilter: null,
        },
      },
      chunks: null,
      isLoading: false,
      error: null,
      fetchIndex: vi.fn().mockResolvedValue(undefined),
      fetchChunks: vi.fn().mockResolvedValue(undefined),
      getChunk: vi.fn(),
    })
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.getByText('all')).toBeInTheDocument()
  })

  it('does not show block-specific fields for recursive_character strategy', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('My Index'))

    await user.click(screen.getByRole('button', { name: /config/i }))

    expect(screen.queryByText('Group by heading')).not.toBeInTheDocument()
    expect(screen.queryByText('Max blocks/chunk')).not.toBeInTheDocument()
    expect(screen.queryByText('Role filter')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests — confirm new tests fail**

```bash
cd frontend && npx vitest run src/pages/IndexDetailPage.test.tsx
```

Expected: 7 new tests fail. Existing tests still pass.

- [ ] **Step 3: Remove the configItems array**

In `frontend/src/pages/IndexDetailPage.tsx`, delete lines 265-272 (the `configItems` constant):
```tsx
// DELETE this entire block:
const configItems = [
  { label: 'Chunking Strategy', value: index.config.chunkingStrategy },
  { label: 'Chunk Size', value: `${index.config.chunkSize} ${index.config.chunkUnit}` },
  { label: 'Chunk Overlap', value: `${index.config.chunkOverlap} ${index.config.chunkUnit}` },
  { label: 'Embedding Provider', value: index.config.embeddingProvider },
  { label: 'Embedding Model', value: index.config.embeddingModel },
  { label: 'Dimensions', value: index.config.embeddingDimensions ?? 'Auto' },
]
```

- [ ] **Step 4: Replace the config drawer JSX with the grouped layout**

In `frontend/src/pages/IndexDetailPage.tsx`, find the Config Drawer block (lines ~424-435):
```tsx
{/* Config Drawer */}
{showConfig && (
  <div className="mt-4 pt-4 border-t grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
    {configItems.map((item) => (
      <div key={item.label}>
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
          {item.label}
        </div>
        <div className="text-sm font-mono text-foreground">{item.value}</div>
      </div>
    ))}
  </div>
)}
```

Replace it with:
```tsx
{/* Config Panel */}
{showConfig && (
  <div className="mt-4 pt-4 border-t space-y-4">
    {/* Source */}
    <div>
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
        Source
      </p>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Parser</p>
          <p className="text-sm font-mono text-foreground">{index.config.parser ?? '—'}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Parse Config</p>
          <p
            className="text-sm font-mono text-foreground"
            title={index.config.parseConfigHash ?? undefined}
          >
            {index.config.parseConfigHash?.slice(0, 8) ?? '—'}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Representation</p>
          <p className="text-sm font-mono text-foreground">
            {index.config.sourceRepresentation}
          </p>
        </div>
      </div>
    </div>

    {/* Chunking */}
    <div>
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
        Chunking
      </p>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Strategy</p>
          <p className="text-sm font-mono text-foreground">{index.config.chunkingStrategy}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Chunk Size</p>
          <p className="text-sm font-mono text-foreground">
            {index.config.chunkSize} {index.config.chunkUnit}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Overlap</p>
          <p className="text-sm font-mono text-foreground">
            {index.config.chunkOverlap} {index.config.chunkUnit}
          </p>
        </div>
        {(index.config.chunkingStrategy === 'block' ||
          index.config.chunkingStrategy === 'classified_block') && (
          <>
            <div>
              <p className="text-[10px] text-muted-foreground mb-0.5">Group by heading</p>
              <p className="text-sm font-mono text-foreground">
                {index.config.groupByHeading ? 'Yes' : 'No'}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground mb-0.5">Max blocks/chunk</p>
              <p className="text-sm font-mono text-foreground">
                {index.config.maxBlocksPerChunk}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground mb-0.5">Role filter</p>
              <p className="text-sm font-mono text-foreground">
                {index.config.blockRoleFilter?.join(', ') ?? 'all'}
              </p>
            </div>
          </>
        )}
      </div>
    </div>

    {/* Embedding */}
    <div>
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
        Embedding
      </p>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Provider</p>
          <p className="text-sm font-mono text-foreground">{index.config.embeddingProvider}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Model</p>
          <p className="text-sm font-mono text-foreground">{index.config.embeddingModel}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground mb-0.5">Dimensions</p>
          <p className="text-sm font-mono text-foreground">
            {index.config.embeddingDimensions ?? 'Auto'}
          </p>
        </div>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 5: Run tests — all pass**

```bash
cd frontend && npx vitest run src/pages/IndexDetailPage.test.tsx
```

Expected: all tests pass including the 7 new config panel tests.

- [ ] **Step 6: Run lint and type-check**

```bash
cd frontend && npm run lint && npm run build
```

Expected: no errors. TypeScript will catch any prop mismatches from the refactored config drawer.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/IndexDetailPage.tsx frontend/src/pages/IndexDetailPage.test.tsx
git commit -m "feat(indexes): expand config panel to show all IndexConfig fields in grouped sections"
```
