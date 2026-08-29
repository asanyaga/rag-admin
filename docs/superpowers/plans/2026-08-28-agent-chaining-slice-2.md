# Agent Chaining — Slice 2 (Frontend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface Definition-2 chaining in the UI — a TypeScript graph validator mirroring the backend, a source-aware generic run form, and composer per-node unmet-input warnings with a gated Run.

**Architecture:** A shared `lib/agentGraph.ts` provides `validateGraph` (reachable-predecessor, mirror of the backend `validate_graph`) and `deriveRunFormFields` (source-aware). `AgentRunForm` uses them to render the right pickers and gate Run; `AgentComposer`/`ComposerNode` use `validateGraph` to badge nodes with missing inputs.

**Tech Stack:** React 18 + TypeScript, @xyflow/react, shadcn/ui, vitest.

**Spec:** [docs/superpowers/specs/2026-08-28-agent-chaining-design.md](../specs/2026-08-28-agent-chaining-design.md) §4
**Issue:** https://github.com/asanyaga/rag-admin/issues/194
**Branch:** `feat/agent-chaining` (same as Slice 1)

## Global Constraints

- Frontend tests: `cd frontend && npx vitest run <path>`; build: `cd frontend && npm run build`.
- The TS `validateGraph` MUST mirror the backend `backend/app/services/agent/validation.py` rule: a node input with `source === 'upstream'` is unmet if its key is not produced by a **reachable predecessor** (transitive). `form`/`either` inputs are never reported unmet. Ignore `__start__`/`__end__` edge endpoints.
- Do not touch backend files.
- Reuse existing hooks/pickers (`useDocuments`, `useExtractionSchemas`, `useSourceDocuments`) — do not build new data layers.

---

### Task 1: Shared `agentGraph` util + `source` on the type

**Files:**
- Modify: `frontend/src/types/agent.ts` (`AgentToolRuntimeInput`)
- Create: `frontend/src/lib/agentGraph.ts`
- Create: `frontend/src/lib/agentGraph.test.ts`

**Interfaces:**
- Produces: `AgentToolRuntimeInput` gains `source: string`.
- Produces: `interface GraphNode { id: string; tool: string }`, `interface GraphEdge { source: string; target: string }`, `interface UnmetInput { nodeId: string; key: string }`.
- Produces: `validateGraph(nodes: GraphNode[], edges: GraphEdge[], tools: AgentTool[]): UnmetInput[]`.
- Produces: `deriveRunFormFields(nodes: GraphNode[], tools: AgentTool[]): AgentToolRuntimeInput[]` — inputs with `source !== 'upstream'` whose key is not produced by any used node, deduped by key.

- [ ] **Step 1: Add `source` to the type**

`types/agent.ts`:

```ts
export interface AgentToolRuntimeInput {
  key: string
  label: string
  widget: string
  source: string
}
```

(Existing fixtures/usages that build `AgentToolRuntimeInput` without `source` will fail typecheck — fix them to include `source: 'form'` where they appear in tests; production reads it from the API which now returns it.)

- [ ] **Step 2: Write the failing test**

`lib/agentGraph.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { validateGraph, deriveRunFormFields } from './agentGraph'
import type { AgentTool } from '@/types/agent'

const tool = (slug: string, runtimeInputs: AgentTool['runtimeInputs'], outputs: string[]): AgentTool => ({
  slug, name: slug, category: 'x', description: '', runtimeInputs, outputs,
  configSchema: {}, configPanel: null,
})

const TOOLS: AgentTool[] = [
  tool('llamaextract',
    [{ key: 'document_id', label: 'Document', widget: 'document_picker', source: 'form' },
     { key: 'extraction_schema_id', label: 'Schema', widget: 'extraction_schema_picker', source: 'form' }],
    ['extracted_data']),
  tool('human-review',
    [{ key: 'extracted_data', label: 'Extracted data', widget: 'pipeline', source: 'upstream' }],
    ['review_action', 'reviewed_data']),
  tool('export',
    [{ key: 'extracted_data', label: 'Extracted data', widget: 'pipeline', source: 'upstream' }],
    ['exported', 'rows_exported']),
]

describe('validateGraph', () => {
  it('valid extract->review->export has no unmet', () => {
    const nodes = [{ id: 'e', tool: 'llamaextract' }, { id: 'r', tool: 'human-review' }, { id: 'x', tool: 'export' }]
    const edges = [{ source: 'e', target: 'r' }, { source: 'r', target: 'x' }]
    expect(validateGraph(nodes, edges, TOOLS)).toEqual([])
  })

  it('lone export has unmet extracted_data', () => {
    expect(validateGraph([{ id: 'x', tool: 'export' }], [], TOOLS))
      .toEqual([{ nodeId: 'x', key: 'extracted_data' }])
  })

  it('producer after consumer does not satisfy', () => {
    const nodes = [{ id: 'x', tool: 'export' }, { id: 'e', tool: 'llamaextract' }]
    const edges = [{ source: 'x', target: 'e' }] // export before extract
    expect(validateGraph(nodes, edges, TOOLS)).toContainEqual({ nodeId: 'x', key: 'extracted_data' })
  })
})

describe('deriveRunFormFields', () => {
  it('extract chain prompts document + schema only (not extracted_data)', () => {
    const nodes = [{ id: 'e', tool: 'llamaextract' }, { id: 'r', tool: 'human-review' }, { id: 'x', tool: 'export' }]
    const keys = deriveRunFormFields(nodes, TOOLS).map((f) => f.key)
    expect(keys).toEqual(['document_id', 'extraction_schema_id'])
  })
})
```

- [ ] **Step 3: Run — verify fail**

Run: `cd frontend && npx vitest run src/lib/agentGraph.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement `agentGraph.ts`**

```ts
import type { AgentTool, AgentToolRuntimeInput, AgentDefinitionData } from '@/types/agent'

export interface GraphNode { id: string; tool: string }
export interface GraphEdge { source: string; target: string }
export interface UnmetInput { nodeId: string; key: string }

const SYNTHETIC = new Set(['__start__', '__end__'])

function reachablePredecessors(nodeId: string, preds: Map<string, Set<string>>): Set<string> {
  const seen = new Set<string>()
  const stack = [...(preds.get(nodeId) ?? [])]
  while (stack.length) {
    const p = stack.pop() as string
    if (seen.has(p)) continue
    seen.add(p)
    for (const q of preds.get(p) ?? []) stack.push(q)
  }
  return seen
}

/** Mirror of backend validate_graph: an `upstream` input is unmet unless a
 *  reachable predecessor produces its key. */
export function validateGraph(nodes: GraphNode[], edges: GraphEdge[], tools: AgentTool[]): UnmetInput[] {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const preds = new Map<string, Set<string>>(nodes.map((n) => [n.id, new Set<string>()]))
  for (const e of edges) {
    if (SYNTHETIC.has(e.source) || SYNTHETIC.has(e.target)) continue
    if (!preds.has(e.target)) preds.set(e.target, new Set())
    preds.get(e.target)!.add(e.source)
  }
  const outputsOf = (id: string): Set<string> => {
    const n = nodes.find((x) => x.id === id)
    const t = n && bySlug.get(n.tool)
    return new Set(t ? t.outputs : [])
  }
  const unmet: UnmetInput[] = []
  for (const n of nodes) {
    const t = bySlug.get(n.tool)
    if (!t) continue
    const upstreamKeys = new Set<string>()
    for (const p of reachablePredecessors(n.id, preds))
      for (const k of outputsOf(p)) upstreamKeys.add(k)
    for (const f of t.runtimeInputs)
      if (f.source === 'upstream' && !upstreamKeys.has(f.key))
        unmet.push({ nodeId: n.id, key: f.key })
  }
  return unmet
}

/** Run-form fields = form/either inputs not produced by any used node, deduped. */
export function deriveRunFormFields(nodes: GraphNode[], tools: AgentTool[]): AgentToolRuntimeInput[] {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const used = nodes.map((n) => bySlug.get(n.tool)).filter(Boolean) as AgentTool[]
  const produced = new Set(used.flatMap((t) => t.outputs))
  const seen = new Set<string>()
  const fields: AgentToolRuntimeInput[] = []
  for (const t of used)
    for (const f of t.runtimeInputs)
      if (f.source !== 'upstream' && !produced.has(f.key) && !seen.has(f.key)) {
        seen.add(f.key); fields.push(f)
      }
  return fields
}
```

(`AgentDefinitionData` import is used by consumers; `deriveRunFormFields` takes the `nodes` array — callers pass `definition.nodes`.)

- [ ] **Step 5: Run — verify pass; typecheck**

Run: `cd frontend && npx vitest run src/lib/agentGraph.test.ts && npm run build`
Expected: tests PASS; build clean (fix any fixture missing `source`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/agent.ts frontend/src/lib/agentGraph.ts frontend/src/lib/agentGraph.test.ts
git commit -m "feat(agent): TS validateGraph + source-aware run-form derivation (mirror backend)"
```

---

### Task 2: `AgentRunForm` — source-aware derivation, pickers, Run gate

**Files:**
- Modify: `frontend/src/components/agent/AgentRunForm.tsx`
- Modify/extend: `frontend/src/components/agent/AgentRunForm.test.tsx`

**Interfaces:**
- Consumes: `deriveRunFormFields`, `validateGraph` (Task 1); `useDocuments()` → `{ documents }` (`DocumentListItem` has `id`, `title`, `status`); `useExtractionSchemas()` → `{ schemas }` (`id`, `name`); existing `useSourceDocuments()`.

- [ ] **Step 1: Write the failing tests**

Extend `AgentRunForm.test.tsx` (keep the existing parse case). Add mocks for the new hooks and cases:

```tsx
vi.mock('@/hooks/useDocuments', () => ({
  useDocuments: () => ({ documents: [{ id: 'doc-1', title: 'Invoice', status: 'ready' }], isLoading: false }),
}))
vi.mock('@/hooks/useExtractionSchemas', () => ({
  useExtractionSchemas: () => ({ schemas: [{ id: 'sch-1', name: 'Invoice schema' }], isLoading: false }),
}))
```

```tsx
const extractTools: AgentTool[] = [
  { slug: 'llamaextract', name: 'LlamaExtract', category: 'extraction', description: '',
    runtimeInputs: [
      { key: 'document_id', label: 'Document', widget: 'document_picker', source: 'form' },
      { key: 'extraction_schema_id', label: 'Schema', widget: 'extraction_schema_picker', source: 'form' }],
    outputs: ['extracted_data'], configSchema: {}, configPanel: null },
  { slug: 'export', name: 'Export', category: 'export', description: '',
    runtimeInputs: [{ key: 'extracted_data', label: 'Extracted data', widget: 'pipeline', source: 'upstream' }],
    outputs: ['exported'], configSchema: {}, configPanel: null },
]
const extractDef = { nodes: [
  { id: 'e', tool: 'llamaextract' }, { id: 'x', tool: 'export' }],
  edges: [{ source: 'e', target: 'x' }] }

it('prompts document + schema for an extract chain and starts a generic run', async () => {
  render(<AgentRunForm projectId="p1" definitionId="def-1" definition={extractDef}
                       tools={extractTools} onStarted={vi.fn()} />)
  await userEvent.selectOptions(await screen.findByLabelText(/document/i), 'doc-1')
  await userEvent.selectOptions(screen.getByLabelText(/schema/i), 'sch-1')
  await userEvent.click(screen.getByRole('button', { name: /run/i }))
  await waitFor(() => expect(startAgentRun).toHaveBeenCalledWith('p1', {
    agentDefinitionId: 'def-1',
    initialState: { document_id: 'doc-1', extraction_schema_id: 'sch-1' },
  }))
})

it('disables Run when the graph has an unmet upstream input', () => {
  const loneExport = { nodes: [{ id: 'x', tool: 'export' }], edges: [] }
  render(<AgentRunForm projectId="p1" definitionId="def-1" definition={loneExport}
                       tools={extractTools} onStarted={vi.fn()} />)
  expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  expect(screen.getByText(/needs .*extracted data/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run — verify fail**

Run: `cd frontend && npx vitest run src/components/agent/AgentRunForm.test.tsx`
Expected: FAIL — no document/schema pickers; Run not gated on graph validity.

- [ ] **Step 3: Implement**

Rewrite `AgentRunForm.tsx`: use the shared util, add pickers, gate Run. Key changes:

```tsx
import { deriveRunFormFields, validateGraph } from '@/lib/agentGraph'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
// ...existing imports (useSourceDocuments, startAgentRun, toast, Button, Label, Play)

export function AgentRunForm({ projectId, definitionId, definition, tools, onStarted }: Props) {
  const fields = useMemo(() => deriveRunFormFields(definition.nodes, tools), [definition, tools])
  const unmet = useMemo(
    () => validateGraph(definition.nodes, definition.edges ?? [], tools),
    [definition, tools])
  const { sourceDocuments } = useSourceDocuments()
  const { documents } = useDocuments()
  const { schemas } = useExtractionSchemas()
  const readyDocuments = documents.filter((d) => d.status === 'ready')
  const [values, setValues] = useState<Record<string, string>>({})
  const [isStarting, setStarting] = useState(false)

  const graphValid = unmet.length === 0
  const ready = graphValid && fields.every((f) => values[f.key])

  const set = (key: string, v: string) => setValues((prev) => ({ ...prev, [key]: v }))

  const handleRun = async () => { /* unchanged: startAgentRun + toast on error */ }

  return (
    <div className="space-y-3">
      {!graphValid && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          This agent can't run yet: {unmet.map((u) => `node "${u.nodeId}" needs ${labelFor(u, tools)}`).join('; ')}.
        </div>
      )}
      {fields.map((f) => (
        <div key={f.key} className="space-y-1.5">
          <Label htmlFor={f.key} className="text-xs">{f.label}</Label>
          {renderPicker(f, { sourceDocuments, readyDocuments, schemas }, values[f.key] ?? '', (v) => set(f.key, v))}
        </div>
      ))}
      <Button size="sm" disabled={!ready || isStarting} onClick={handleRun}>
        <Play className="h-4 w-4 mr-1.5" />{isStarting ? 'Starting...' : 'Run'}
      </Button>
    </div>
  )
}
```

Add `labelFor(u, tools)` (find the tool of `u.nodeId`'s node → its runtimeInput with `key===u.key` → `.label`, fallback to `u.key`) and `renderPicker(field, data, value, onChange)` that switches on `field.widget`:
- `source_document_picker` → select over `sourceDocuments` (`sd.filename ?? sd.id`), option "Select a document...".
- `document_picker` → select over `readyDocuments` (`doc.title`), `aria-label={field.label}`.
- `extraction_schema_picker` → select over `schemas` (`s.name`), `aria-label={field.label}`.
- default → the existing "Unsupported input" span.

Each `<select>` carries `id={field.key}` and `aria-label={field.label}`.

- [ ] **Step 4: Run — verify pass; build**

Run: `cd frontend && npx vitest run src/components/agent/AgentRunForm.test.tsx && npm run build`
Expected: PASS + clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/agent/AgentRunForm.tsx frontend/src/components/agent/AgentRunForm.test.tsx
git commit -m "feat(agent): source-aware run form with document/schema pickers + Run gate"
```

---

### Task 3: Composer per-node unmet-input warnings

**Files:**
- Modify: `frontend/src/components/agent/composer/ComposerNode.tsx`
- Modify: `frontend/src/components/agent/composer/AgentComposer.tsx`
- Create: `frontend/src/components/agent/composer/ComposerNode.test.tsx`

**Interfaces:**
- Consumes: `validateGraph` (Task 1).
- Produces: `ComposerNodeData` gains `unmetInputs?: string[]` (human labels); `ComposerNode` renders a warning badge when non-empty. `AgentComposer` computes `validateGraph` over the canvas and injects per-node labels.

- [ ] **Step 1: Write the failing test**

`ComposerNode.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { ReactFlowProvider } from '@xyflow/react'
import { describe, it, expect } from 'vitest'
import { ComposerNode } from './ComposerNode'

function renderNode(data: Record<string, unknown>) {
  return render(
    <ReactFlowProvider>
      <ComposerNode id="n1" data={data as never} selected={false} />
    </ReactFlowProvider>
  )
}

it('shows an unmet-input warning when the node has missing inputs', () => {
  renderNode({ label: 'Export', toolSlug: 'export', category: 'export', config: {},
               unmetInputs: ['Extracted data'] })
  expect(screen.getByText(/extracted data/i)).toBeInTheDocument()
})

it('shows no warning when inputs are satisfied', () => {
  renderNode({ label: 'Export', toolSlug: 'export', category: 'export', config: {}, unmetInputs: [] })
  expect(screen.queryByText(/needs/i)).not.toBeInTheDocument()
})
```

(If `ComposerNode` needs handles outside a provider it may warn; the `ReactFlowProvider` wrapper prevents that. If it still errors, render without the provider and assert only on the badge text — adjust to what the component requires.)

- [ ] **Step 2: Run — verify fail**

Run: `cd frontend && npx vitest run src/components/agent/composer/ComposerNode.test.tsx`
Expected: FAIL — no badge rendered.

- [ ] **Step 3: Implement the badge**

`ComposerNode.tsx` — add to `ComposerNodeData`:

```ts
  unmetInputs?: string[]
```

Render below the toolSlug line, inside the node div:

```tsx
{data.unmetInputs && data.unmetInputs.length > 0 && (
  <div className="mt-1 flex items-start gap-1 text-[10px] text-amber-700">
    <TriangleAlert className="h-3 w-3 shrink-0 mt-px" />
    <span>Needs: {data.unmetInputs.join(', ')}</span>
  </div>
)}
```

(import `TriangleAlert` from `lucide-react`.)

- [ ] **Step 4: Wire `AgentComposer`**

In `AgentComposer.tsx`, compute unmet per node and inject into node data alongside the existing `onRemove`/`onSelect` injection:

```tsx
import { validateGraph } from '@/lib/agentGraph'
// ...
const unmetByNode = useMemo(() => {
  const gnodes = nodes.map((n) => ({ id: n.id, tool: n.data.toolSlug as string }))
  const gedges = edges.map((e) => ({ source: e.source, target: e.target }))
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const map: Record<string, string[]> = {}
  for (const u of validateGraph(gnodes, gedges, tools)) {
    const tool = bySlug.get(nodes.find((n) => n.id === u.nodeId)?.data.toolSlug as string)
    const label = tool?.runtimeInputs.find((f) => f.key === u.key)?.label ?? u.key
    ;(map[u.nodeId] ??= []).push(label)
  }
  return map
}, [nodes, edges, tools])
```

Then in the `nodesWithCallbacks` memo, add `unmetInputs: unmetByNode[n.id] ?? []` into each node's `data`. Save remains unaffected (no gating on Save).

- [ ] **Step 5: Run — verify pass; build**

Run: `cd frontend && npx vitest run src/components/agent/composer && npm run build`
Expected: PASS + clean build.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/agent/composer/ComposerNode.tsx frontend/src/components/agent/composer/AgentComposer.tsx frontend/src/components/agent/composer/ComposerNode.test.tsx
git commit -m "feat(agent): composer per-node unmet-input warnings from validateGraph"
```

---

### Task 4: Full frontend regression + manual verification notes

**Files:** none (verification only).

- [ ] **Step 1: Frontend suite + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: all PASS; build clean. Fix any fixture that builds `AgentToolRuntimeInput` without `source` or `AgentTool` without the new field.

- [ ] **Step 2: Manual verification pointer (for the user)**

Not automated. In the composer: build `extract → review → export`. Before wiring, `review`/`export` nodes show "Needs: Extracted data"; once `extract` feeds them, the warnings clear. Save works throughout. On the runs page, the run form asks only for a **Document** + **Extraction schema**; Run is disabled (with a reason) for an incomplete graph and enabled when valid + filled. Running reaches review (`waiting_for_input`); approving resumes to export. (Requires a LlamaExtract-capable setup.)

- [ ] **Step 3: Comment on issue #194** with the automated result and what's left to the user's manual E2E.

---

## Self-Review

**Spec coverage:** §4 composer UX + §3 run-form derivation → Tasks 2 (run form) + 3 (composer). AC1 (TS validateGraph reachable-predecessor, mirror) → Task 1. AC2 (source on type + source-aware derivation) → Task 1 (+ Task 2 uses it). AC3 (document/schema pickers + Run gate) → Task 2. AC4 (composer warnings, Save unaffected) → Task 3. AC5 (suite + build green) → Task 4.

**Placeholder scan:** none — every code step has real content. Task 2 Step 3 factors `renderPicker`/`labelFor` as named helpers with explicit per-widget behavior (not "handle the widgets"). Task 3 Step 1 notes the ReactFlowProvider fallback if the component requires it — a concrete confirmation, not an open decision.

**Type consistency:** `AgentToolRuntimeInput.source` (Task 1) is read by `validateGraph`/`deriveRunFormFields` (Task 1), `AgentRunForm` (Task 2), and `AgentComposer` (Task 3). `GraphNode {id,tool}` / `GraphEdge {source,target}` / `UnmetInput {nodeId,key}` shapes are consistent across the util, the run form, and the composer wiring. Widget strings (`document_picker`, `extraction_schema_picker`, `source_document_picker`) match the backend `FieldSpec.widget` values from Slice 1.
