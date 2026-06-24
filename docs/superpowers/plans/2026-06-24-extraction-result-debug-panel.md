# Extraction Result Debug Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace two raw-JSON collapsibles in `ExtractionResultViewer` with three structured debug panels (Run Config, Prompt, LLM Response) and a shared `FormattedJson` syntax-coloured renderer.

**Architecture:** New `FormattedJson` shared component does syntax colouring via regex (no external deps). `ExtractionResultViewer` gains three `Collapsible` panels that read from `result.extractionMetadata` and `result.config`; chunked runs show muted placeholders for absent fields.

**Tech Stack:** React 18, TypeScript, shadcn/ui (`Tabs`, `Separator`, `Collapsible`, `Card`), Tailwind CSS, Vitest + Testing Library.

## Global Constraints

- No new API fields, no backend changes — frontend only.
- All JSON values rendered via `FormattedJson`; no raw `JSON.stringify` in `<pre>` blocks visible to users.
- All new behaviour must be covered by unit tests.
- `shadcn/ui` components used for all UI; `tabs.tsx` and `separator.tsx` already installed at `frontend/src/components/ui/`.
- Run tests with: `npx vitest run --reporter verbose <file>` from `frontend/` directory (absolute path: `C:\Repos\rag-admin\frontend`).
- Lint with: `npm run lint` from `frontend/` directory.

---

### Task 1: FormattedJson shared component

**Files:**
- Create: `frontend/src/components/shared/FormattedJson.tsx`
- Create: `frontend/src/components/shared/FormattedJson.test.tsx`

**Interfaces:**
- Produces: `FormattedJson({ value: unknown; maxHeight?: string }): JSX.Element` — exported named export used by Task 2.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/shared/FormattedJson.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FormattedJson } from './FormattedJson'

describe('FormattedJson', () => {
  it('renders JSON string keys and values', () => {
    const { container } = render(<FormattedJson value={{ name: 'Alice' }} />)
    // "name" as key and "Alice" as string value should appear in the pre
    expect(container.querySelector('pre')).toHaveTextContent('"name"')
    expect(container.querySelector('pre')).toHaveTextContent('"Alice"')
  })

  it('renders JSON number values', () => {
    render(<FormattedJson value={{ count: 42 }} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders JSON boolean values', () => {
    render(<FormattedJson value={{ active: true, disabled: false }} />)
    expect(screen.getByText('true')).toBeInTheDocument()
    expect(screen.getByText('false')).toBeInTheDocument()
  })

  it('renders null JSON value as literal text', () => {
    render(<FormattedJson value={{ x: null }} />)
    expect(screen.getByText('null')).toBeInTheDocument()
  })

  it('applies maxHeight style to pre element', () => {
    const { container } = render(<FormattedJson value={{ x: 1 }} maxHeight="10rem" />)
    expect(container.querySelector('pre')?.style.maxHeight).toBe('10rem')
  })

  it('uses default maxHeight of 24rem when prop omitted', () => {
    const { container } = render(<FormattedJson value={{ x: 1 }} />)
    expect(container.querySelector('pre')?.style.maxHeight).toBe('24rem')
  })

  it('handles null value prop gracefully without crashing', () => {
    const { container } = render(<FormattedJson value={null} />)
    expect(container.querySelector('pre')).toBeInTheDocument()
  })

  it('handles undefined value prop gracefully without crashing', () => {
    const { container } = render(<FormattedJson value={undefined} />)
    expect(container.querySelector('pre')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run --reporter verbose src/components/shared/FormattedJson.test.tsx
```

Expected: FAIL — "Cannot find module './FormattedJson'"

- [ ] **Step 3: Implement FormattedJson**

Create `frontend/src/components/shared/FormattedJson.tsx`:

```tsx
interface FormattedJsonProps {
  value: unknown
  maxHeight?: string
}

function highlight(json: string): React.ReactNode[] {
  // Groups: (1) quoted string + optional colon (key vs. value), (2) bool/null, (3) number
  const regex =
    /("(?:[^\\"]|\\.)*")(\s*:)?|(\btrue\b|\bfalse\b|\bnull\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g
  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(json)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(json.slice(lastIndex, match.index))
    }
    if (match[1] !== undefined) {
      const isKey = match[2] !== undefined
      nodes.push(
        <span
          key={match.index}
          className={
            isKey
              ? 'text-blue-700 dark:text-blue-400'
              : 'text-green-700 dark:text-green-400'
          }
        >
          {match[1]}
        </span>
      )
      if (match[2]) nodes.push(match[2])
    } else if (match[3] !== undefined) {
      nodes.push(
        <span key={match.index} className="text-amber-600 dark:text-amber-400">
          {match[3]}
        </span>
      )
    } else if (match[4] !== undefined) {
      nodes.push(
        <span key={match.index} className="text-amber-600 dark:text-amber-400">
          {match[4]}
        </span>
      )
    }
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < json.length) nodes.push(json.slice(lastIndex))
  return nodes
}

export function FormattedJson({ value, maxHeight = '24rem' }: FormattedJsonProps) {
  if (value === null || value === undefined) {
    return (
      <pre
        className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto text-muted-foreground"
        style={{ maxHeight }}
      >
        {String(value)}
      </pre>
    )
  }
  const json = JSON.stringify(value, null, 2)
  return (
    <pre
      className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto"
      style={{ maxHeight }}
    >
      {highlight(json)}
    </pre>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npx vitest run --reporter verbose src/components/shared/FormattedJson.test.tsx
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/shared/FormattedJson.tsx frontend/src/components/shared/FormattedJson.test.tsx
git commit -m "feat(extraction-ui): add FormattedJson syntax-coloured JSON renderer"
```

---

### Task 2: Replace ExtractionResultViewer debug panels

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`

**Interfaces:**
- Consumes: `FormattedJson({ value, maxHeight })` from Task 1.
- `ExtractionResult.extractionMetadata` cast as `{ model?, provider?, latency_ms?, usage?: { prompt_tokens?, completion_tokens?, total_tokens? }, chunkCount?, prompt_messages?: Array<{ role: string; content: string }> } | null`
- `ExtractionResult.config` cast as `{ structured_output_mode?, inject_block_ids?, chunking?: { strategy?, config?: Record<string, unknown>, citationLevel? } } | null`

- [ ] **Step 1: Write/update failing tests**

Replace the full content of `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExtractionResultViewer } from './ExtractionResultViewer'
import type { ExtractionResult } from '@/types/extraction'

function buildResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return {
    id: 'result-1',
    documentId: 'doc-1',
    extractionSchemaId: 'schema-1',
    schemaDefinitionSnapshot: {},
    extractionMethod: 'llamaextract',
    config: null,
    structuredData: { invoice_number: 'INV-001' },
    extractionMetadata: { latency_ms: 1234, file_id: 'f-abc' },
    citations: null,
    providerResponseRaw: null,
    sourceParseRunId: 'run-1',
    status: 'completed',
    statusMessage: null,
    startedAt: '2026-01-01T00:00:00Z',
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function buildLlmResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return buildResult({
    extractionMethod: 'llm',
    extractionMetadata: {
      model: 'claude-opus-4-7',
      provider: 'anthropic',
      latency_ms: 17794,
      usage: { prompt_tokens: 3712, completion_tokens: 1830, total_tokens: 5542 },
      prompt_messages: [
        { role: 'system', content: 'You are an extraction assistant.' },
        {
          role: 'user',
          content:
            'Extract the following.\n<schema>{"type":"object"}</schema>\n<document>Invoice #001</document>',
        },
      ],
    },
    config: {
      structured_output_mode: 'json_schema',
      inject_block_ids: false,
      chunking: { strategy: 'none', citationLevel: 'auto' },
    },
    providerResponseRaw: { id: 'msg_001', content: [{ type: 'text', text: '{}' }] },
    ...overrides,
  })
}

function buildChunkedResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return buildResult({
    extractionMethod: 'llm',
    extractionMetadata: {
      chunkCount: 3,
      usage: { total_tokens: 12000 },
      scalarConflicts: [],
      // no model, provider, latency_ms, prompt_messages
    },
    config: {
      structured_output_mode: 'json_schema',
      chunking: { strategy: 'token_budget_pages', config: { max_input_tokens: 4000 }, citationLevel: 'auto' },
    },
    providerResponseRaw: null,
    ...overrides,
  })
}

describe('ExtractionResultViewer', () => {
  // ── Run Config panel ──────────────────────────────────────────────────────
  it('shows Run Config panel for all results', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByText('Run Config')).toBeInTheDocument()
  })

  it('shows model and provider in Run Config for LLM results', () => {
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    expect(screen.getByText('claude-opus-4-7')).toBeInTheDocument()
    expect(screen.getByText('anthropic')).toBeInTheDocument()
  })

  it('shows formatted latency in Run Config for LLM results', () => {
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    expect(screen.getByText('17,794 ms')).toBeInTheDocument()
  })

  it('shows token counts in Run Config for LLM results', () => {
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    expect(screen.getByText('3,712')).toBeInTheDocument()
    expect(screen.getByText('1,830')).toBeInTheDocument()
    expect(screen.getByText('5,542')).toBeInTheDocument()
  })

  it('shows chunked run placeholder for model when model is absent', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.getAllByText('Not available for chunked runs').length).toBeGreaterThan(0)
  })

  it('shows chunk count in Run Config for chunked results', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows chunking strategy in Run Config settings', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.getByText('token_budget_pages')).toBeInTheDocument()
  })

  it('shows max input tokens when chunking strategy is not none', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.getByText('4,000')).toBeInTheDocument()
  })

  // ── Prompt panel ──────────────────────────────────────────────────────────
  it('shows Prompt panel for all results', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByText('Prompt')).toBeInTheDocument()
  })

  it('shows System and User tabs in Prompt panel for LLM results with prompt_messages', () => {
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    expect(screen.getByRole('tab', { name: 'System' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'User' })).toBeInTheDocument()
  })

  it('shows system prompt content in System tab', () => {
    render(<ExtractionResultViewer result={buildLlmResult()} />)
    expect(screen.getByText('You are an extraction assistant.')).toBeInTheDocument()
  })

  it('shows chunking unavailable message in Prompt panel for chunked results', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(
      screen.getByText(/Prompt not available.*chunking/i)
    ).toBeInTheDocument()
  })

  // ── LLM Response panel ────────────────────────────────────────────────────
  it('shows LLM Response panel when providerResponseRaw is present', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({ providerResponseRaw: { data: { invoice_number: 'INV-001' } } })}
      />
    )
    expect(screen.getByText('LLM Response')).toBeInTheDocument()
  })

  it('does not show LLM Response panel when providerResponseRaw is null', () => {
    render(<ExtractionResultViewer result={buildResult({ providerResponseRaw: null })} />)
    expect(screen.queryByText('LLM Response')).not.toBeInTheDocument()
  })

  it('does not show LLM Response panel for chunked runs', () => {
    render(<ExtractionResultViewer result={buildChunkedResult()} />)
    expect(screen.queryByText('LLM Response')).not.toBeInTheDocument()
  })

  it('shows Raw label when providerResponseRaw contains raw_content string', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({
          providerResponseRaw: { raw_content: 'this is not json' },
        })}
      />
    )
    expect(screen.getByText('Raw (non-JSON) response')).toBeInTheDocument()
    expect(screen.getByText('this is not json')).toBeInTheDocument()
  })

  // ── Legacy panel absence ──────────────────────────────────────────────────
  it('does not render old "Extraction Metadata" panel text', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.queryByText('Extraction Metadata')).not.toBeInTheDocument()
  })

  it('does not render old "Provider Response" panel text', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({ providerResponseRaw: { data: {} } })}
      />
    )
    expect(screen.queryByText('Provider Response')).not.toBeInTheDocument()
  })

  it('does not show old metadata label', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.queryByText(/citations \/ reasoning/i)).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run --reporter verbose src/components/extraction/ExtractionResultViewer.test.tsx
```

Expected: Many failures — "Run Config", "LLM Response" text not found; "Extraction Metadata"/"Provider Response" assertions now reversed.

- [ ] **Step 3: Implement the new ExtractionResultViewer**

Replace the full contents of `frontend/src/components/extraction/ExtractionResultViewer.tsx`:

```tsx
import type { ExtractionResult } from '@/types/extraction'
import { ChunkingSummary } from './ChunkingSummary'
import { FormattedJson } from '@/components/shared/FormattedJson'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { ChevronDown, Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface ExtractionResultViewerProps {
  result: ExtractionResult | null
  isLoading?: boolean
}

// ── Internal types for casting extractionMetadata and config ─────────────────

interface ExtractionMeta {
  model?: string
  provider?: string
  latency_ms?: number
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  }
  chunkCount?: number
  prompt_messages?: Array<{ role: string; content: string }>
}

interface ExtractionConfig {
  structured_output_mode?: string
  inject_block_ids?: boolean
  chunking?: {
    strategy?: string
    config?: Record<string, unknown>
    citationLevel?: string
  }
}

// ── Helper components ─────────────────────────────────────────────────────────

function StructuredDataDisplay({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data)

  return (
    <div className="space-y-4">
      {entries.map(([key, value]) => {
        if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
          return <ArrayTable key={key} label={key} items={value as Record<string, unknown>[]} />
        }

        if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
          return (
            <Collapsible key={key}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between px-3 py-2 h-auto">
                  <span className="font-medium text-sm">{formatLabel(key)}</span>
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pl-4 border-l-2 border-muted ml-3">
                <StructuredDataDisplay data={value as Record<string, unknown>} />
              </CollapsibleContent>
            </Collapsible>
          )
        }

        return (
          <div key={key} className="flex justify-between items-start py-1.5 px-3 rounded hover:bg-muted/50">
            <span className="text-sm text-muted-foreground">{formatLabel(key)}</span>
            <span className="text-sm text-right max-w-[60%]">{formatValue(value)}</span>
          </div>
        )
      })}
    </div>
  )
}

function ArrayTable({ label, items }: { label: string; items: Record<string, unknown>[] }) {
  if (items.length === 0) return null

  const columns = Object.keys(items[0])

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium px-3">{formatLabel(label)}</h4>
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-xs">
                  {formatLabel(col)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, i) => (
              <TableRow key={i}>
                {columns.map((col) => (
                  <TableCell key={col} className="text-sm">
                    {formatValue(item[col])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function ConfigRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[12rem_1fr] gap-4 py-0.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span>{value ?? '—'}</span>
    </div>
  )
}

function NotAvailableChunked() {
  return (
    <span className="text-muted-foreground italic text-xs">
      Not available for chunked runs
    </span>
  )
}

function UserMessageDisplay({ content }: { content: string }) {
  const parsed = parseUserContent(content)
  if (!parsed.schema) {
    return (
      <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-48 whitespace-pre-wrap">
        {content}
      </pre>
    )
  }
  let schemaJson: unknown
  try {
    schemaJson = JSON.parse(parsed.schema)
  } catch {
    schemaJson = parsed.schema
  }
  return (
    <div className="space-y-3">
      {parsed.instruction && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-1">Instruction</p>
          <pre className="text-xs font-mono bg-muted p-2 rounded border whitespace-pre-wrap">
            {parsed.instruction}
          </pre>
        </div>
      )}
      <div>
        <p className="text-xs font-semibold text-muted-foreground mb-1">Schema</p>
        <FormattedJson value={schemaJson} maxHeight="12rem" />
      </div>
      {parsed.document && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-1">Document</p>
          <pre className="text-xs font-mono bg-muted p-2 rounded border overflow-auto max-h-48 whitespace-pre-wrap">
            {parsed.document}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── Pure helpers ──────────────────────────────────────────────────────────────

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim()
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

interface ParsedUserContent {
  instruction: string
  schema: string | null
  document: string | null
}

function parseUserContent(content: string): ParsedUserContent {
  const schemaOpen = '<schema>'
  const schemaClose = '</schema>'
  const docOpen = '<document>'
  const docClose = '</document>'
  const s0 = content.indexOf(schemaOpen)
  const s1 = content.indexOf(schemaClose)
  const d0 = content.indexOf(docOpen)
  const d1 = content.indexOf(docClose)
  if (s0 === -1 || d0 === -1) {
    return { instruction: content, schema: null, document: null }
  }
  return {
    instruction: content.slice(0, s0).trim(),
    schema: content.slice(s0 + schemaOpen.length, s1).trim(),
    document: content.slice(d0 + docOpen.length, d1).trim(),
  }
}

// ── Main component ────────────────────────────────────────────────────────────

export function ExtractionResultViewer({
  result,
  isLoading,
}: ExtractionResultViewerProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!result) return null

  const meta = result.extractionMetadata as ExtractionMeta | null
  const cfg = result.config as ExtractionConfig | null
  const chunkingConfig = cfg?.chunking
  const promptMessages = meta?.prompt_messages
  const systemMessage = promptMessages?.[0]
  const userMessage = promptMessages?.[1]

  const hasProviderResponse =
    result.providerResponseRaw !== null &&
    result.providerResponseRaw !== undefined &&
    Object.keys(result.providerResponseRaw).length > 0
  const isRawContent =
    typeof result.providerResponseRaw?.['raw_content'] === 'string'

  const statusColor =
    result.status === 'completed'
      ? 'default'
      : result.status === 'pending'
        ? 'secondary'
        : 'destructive'

  return (
    <div className="space-y-4">
      <ChunkingSummary metadata={result.extractionMetadata} />

      {/* ── Result card ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Extraction Result</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={statusColor}>
                {result.status === 'pending' && (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                )}
                {result.status}
              </Badge>
              <Badge variant="outline">{result.extractionMethod}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {result.status === 'pending' && (
            <p className="text-sm text-muted-foreground">Extraction is in progress...</p>
          )}

          {result.status === 'failed' && (
            <div className="space-y-3">
              {result.statusMessage && (
                <p className="text-sm text-destructive">{result.statusMessage}</p>
              )}
              {isRawContent && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">LLM Response</p>
                  <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto whitespace-pre-wrap max-h-64">
                    {result.providerResponseRaw!['raw_content'] as string}
                  </pre>
                </div>
              )}
            </div>
          )}

          {result.status === 'completed' && result.structuredData && (
            <StructuredDataDisplay data={result.structuredData} />
          )}
        </CardContent>
      </Card>

      {/* ── Run Config panel ─────────────────────────────────────────────── */}
      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="w-full justify-between">
            <span>Run Config</span>
            <ChevronDown className="h-4 w-4" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Card className="mt-2">
            <CardContent className="pt-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Model
              </p>
              <div className="space-y-0.5">
                <ConfigRow
                  label="Model"
                  value={meta?.model ?? <NotAvailableChunked />}
                />
                <ConfigRow
                  label="Provider"
                  value={meta?.provider ?? <NotAvailableChunked />}
                />
                <ConfigRow
                  label="Latency"
                  value={
                    meta?.latency_ms !== undefined
                      ? `${meta.latency_ms.toLocaleString()} ms`
                      : <NotAvailableChunked />
                  }
                />
              </div>
              <Separator />
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Tokens
              </p>
              <div className="space-y-0.5">
                <ConfigRow
                  label="Prompt tokens"
                  value={meta?.usage?.prompt_tokens?.toLocaleString() ?? '—'}
                />
                <ConfigRow
                  label="Completion tokens"
                  value={meta?.usage?.completion_tokens?.toLocaleString() ?? '—'}
                />
                <ConfigRow
                  label="Total tokens"
                  value={meta?.usage?.total_tokens?.toLocaleString() ?? '—'}
                />
              </div>
              <Separator />
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Settings
              </p>
              <div className="space-y-0.5">
                <ConfigRow label="Extraction method" value={result.extractionMethod} />
                <ConfigRow
                  label="Structured output mode"
                  value={cfg?.structured_output_mode ?? '—'}
                />
                <ConfigRow
                  label="Inject block IDs"
                  value={
                    typeof cfg?.inject_block_ids === 'boolean'
                      ? cfg.inject_block_ids
                        ? 'Yes'
                        : 'No'
                      : '—'
                  }
                />
                <ConfigRow
                  label="Chunking strategy"
                  value={chunkingConfig?.strategy ?? '—'}
                />
                {chunkingConfig?.strategy && chunkingConfig.strategy !== 'none' && (
                  <ConfigRow
                    label="Max input tokens"
                    value={
                      (chunkingConfig.config?.['max_input_tokens'] as number | undefined)?.toLocaleString() ??
                      '—'
                    }
                  />
                )}
                <ConfigRow
                  label="Citation level"
                  value={chunkingConfig?.citationLevel ?? '—'}
                />
                {meta?.chunkCount !== undefined && (
                  <ConfigRow label="Chunk count" value={String(meta.chunkCount)} />
                )}
              </div>
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      {/* ── Prompt panel ─────────────────────────────────────────────────── */}
      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="w-full justify-between">
            <span>Prompt</span>
            <ChevronDown className="h-4 w-4" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Card className="mt-2">
            <CardContent className="pt-4">
              {!promptMessages ? (
                <p className="text-sm text-muted-foreground italic">
                  Prompt not available — this run used chunking. Individual chunk prompts
                  are not yet preserved.
                </p>
              ) : (
                <Tabs defaultValue="system">
                  <TabsList>
                    <TabsTrigger value="system">System</TabsTrigger>
                    <TabsTrigger value="user">User</TabsTrigger>
                  </TabsList>
                  <TabsContent value="system" className="mt-3">
                    <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-48 whitespace-pre-wrap">
                      {systemMessage?.content ?? '—'}
                    </pre>
                  </TabsContent>
                  <TabsContent value="user" className="mt-3">
                    {userMessage ? (
                      <UserMessageDisplay content={userMessage.content} />
                    ) : (
                      <p className="text-sm text-muted-foreground">—</p>
                    )}
                  </TabsContent>
                </Tabs>
              )}
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      {/* ── LLM Response panel (hidden for chunked/null) ──────────────────── */}
      {hasProviderResponse && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="outline" size="sm" className="w-full justify-between">
              <span>LLM Response</span>
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Card className="mt-2">
              <CardContent className="pt-4">
                {isRawContent ? (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Raw (non-JSON) response</p>
                    <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-96 whitespace-pre-wrap">
                      {result.providerResponseRaw!['raw_content'] as string}
                    </pre>
                  </div>
                ) : (
                  <FormattedJson value={result.providerResponseRaw} maxHeight="24rem" />
                )}
              </CardContent>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npx vitest run --reporter verbose src/components/extraction/ExtractionResultViewer.test.tsx
```

Expected: All tests PASS.

- [ ] **Step 5: Run full frontend test suite to catch regressions**

```bash
npx vitest run --reporter verbose
```

Expected: All tests PASS with no regressions.

- [ ] **Step 6: Run lint**

```bash
npm run lint
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/extraction/ExtractionResultViewer.tsx frontend/src/components/extraction/ExtractionResultViewer.test.tsx
git commit -m "feat(extraction-ui): replace raw JSON collapsibles with Run Config, Prompt, and LLM Response debug panels"
```

---

## Self-Review vs Spec

**Spec coverage check:**

| Requirement | Task |
|---|---|
| Run Config panel — model, provider, latency | Task 2 ConfigRow rows |
| Run Config — token counts | Task 2 Tokens section |
| Run Config — extraction settings (method, output mode, inject, chunking, citations) | Task 2 Settings section |
| Prompt panel — System/User tabs | Task 2 Tabs |
| Prompt User tab — parse instruction/schema/document sections | Task 2 `parseUserContent` + `UserMessageDisplay` |
| LLM Response — FormattedJson rendering | Task 2 LLM Response collapsible |
| LLM Response — raw_content fallback label | Task 2 `isRawContent` branch |
| LLM Response hidden when providerResponseRaw null | Task 2 `hasProviderResponse` guard |
| Chunked run placeholders (model/provider/latency) | Task 2 `NotAvailableChunked` |
| Chunked run — Prompt unavailable message | Task 2 `!promptMessages` branch |
| FormattedJson — syntax colouring (strings, keys, numbers, booleans) | Task 1 `highlight()` |
| FormattedJson — no external deps | Task 1 pure regex implementation |
| All JSON via FormattedJson; no raw JSON.stringify in pre | Tasks 1 + 2 |
| Unit tests for all new behaviour | Tasks 1 + 2 test files |
| No regressions in existing tests | Task 2 Step 5 full suite run |

**No gaps found.**

**Placeholder scan:** No TBDs, no "implement later", no incomplete steps.

**Type consistency:** `ExtractionMeta`, `ExtractionConfig` defined in Task 2 and used consistently throughout. `FormattedJson` props defined in Task 1, consumed in Task 2 with matching signature.
