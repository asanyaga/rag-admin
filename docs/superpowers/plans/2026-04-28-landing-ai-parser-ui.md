# Landing AI Parser UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Landing AI as a selectable parser in upload and re-parse flows, introduce a `PARSER_REGISTRY` in `ParseMethodSelector` so future parsers require only a new config component + one registry entry, and fix the backend CDM gate so `landing_ai` routes through `process_cdm_parsing`.

**Architecture:** Two backend routers (`documents.py`, `parse_results.py`) need their CDM gate and validation extended to accept `landing_ai`. On the frontend, `ParseMethodSelector` is refactored around a `PARSER_REGISTRY` constant; LlamaParse config is extracted into `LlamaParseConfig.tsx` and a new `LandingAIConfig.tsx` is created. Three callers (`DocumentUploadZone`, `BulkUploadQueue`, `ReParseDialog`) have a hard-coded `parserType === 'llamaparse'` guard on config passing that must be generalised.

**Tech Stack:** Python 3.12 / FastAPI (backend), React 18 / TypeScript / shadcn/ui / Vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-04-28-landing-ai-parser-ui-design.md`

---

## File Map

| File | Action |
|---|---|
| `backend/app/routers/documents.py` | Modify — CDM gate, parser validation, parser key injection |
| `backend/app/routers/parse_results.py` | Modify — CDM gate, parser validation, parser key injection |
| `frontend/src/types/parsing.ts` | Modify — add `model?: string` to `ParseConfig` |
| `frontend/src/components/documents/parser-configs/LlamaParseConfig.tsx` | Create — extracted from `ParseMethodSelector` |
| `frontend/src/components/documents/parser-configs/LandingAIConfig.tsx` | Create — model dropdown |
| `frontend/src/components/documents/ParseMethodSelector.tsx` | Rewrite — registry-driven |
| `frontend/src/components/documents/DocumentUploadZone.tsx` | Modify — generalise config guard + reset |
| `frontend/src/components/documents/BulkUploadQueue.tsx` | Modify — generalise config guard + reset |
| `frontend/src/components/documents/ReParseDialog.tsx` | Modify — generalise config guard + updated default state |

---

## Task 1: Fix `documents.py` — CDM gate, validation, parser key injection

**Files:**
- Modify: `backend/app/routers/documents.py`

The single-upload route (line ~107) and bulk-upload route (line ~234) each have:
```python
use_cdm = settings.USE_CDM_PARSER and parser_type == "llamaparse"
```
Both need `landing_ai` added. The bulk route also validates parser type upfront via `get_parser()` (lines ~237–244), which will reject `landing_ai` (it is not in the legacy registry). Both CDM branches also need `parse_cfg["parser"] = parser_type` injected so `parse_and_persist` dispatches to the right runner.

- [ ] **Step 1: Add module-level constant after the existing imports**

Find the imports block at the top of `backend/app/routers/documents.py`. Add this constant after the last import and before the router definition:

```python
_CDM_PARSER_TYPES = frozenset({"llamaparse", "landing_ai"})
```

- [ ] **Step 2: Fix single-upload CDM gate (line ~107)**

Find:
```python
        use_cdm = settings.USE_CDM_PARSER and parser_type == "llamaparse"
```
Replace with:
```python
        use_cdm = settings.USE_CDM_PARSER and parser_type in _CDM_PARSER_TYPES
```

- [ ] **Step 3: Inject parser key in single-upload CDM branch (line ~124)**

Find the single-upload CDM branch (starts with `if use_cdm and document.source_document_id is not None:`). Inside it, find:
```python
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            background_tasks.add_task(
```
Add one line between them:
```python
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            parse_cfg["parser"] = parser_type
            background_tasks.add_task(
```

- [ ] **Step 4: Fix bulk-upload CDM gate (line ~234)**

Find:
```python
    use_cdm = settings.USE_CDM_PARSER and parser_type == "llamaparse"
```
Replace with:
```python
    use_cdm = settings.USE_CDM_PARSER and parser_type in _CDM_PARSER_TYPES
```

- [ ] **Step 5: Fix bulk-upload parser validation (lines ~237–244)**

Find:
```python
    # Validate parser type upfront
    parser = None
    if parser_type != "simple":
        parser = get_parser(parser_type)
        if parser is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {parser_type}",
            )
```
Replace with:
```python
    # Validate parser type upfront
    # CDM parser types bypass the legacy registry — they are handled by process_cdm_parsing.
    parser = None
    if parser_type != "simple" and parser_type not in _CDM_PARSER_TYPES:
        parser = get_parser(parser_type)
        if parser is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {parser_type}",
            )
```

- [ ] **Step 6: Inject parser key in bulk-upload CDM branch (line ~269)**

Find the per-document CDM branch in the bulk route (inside the `for item in results:` loop):
```python
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            background_tasks.add_task(
```
Add one line between them:
```python
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            parse_cfg["parser"] = parser_type
            background_tasks.add_task(
```

- [ ] **Step 7: Run backend tests**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/documents.py
git commit -m "fix(routers): extend CDM gate and parser validation to support landing_ai"
```

---

## Task 2: Fix `parse_results.py` — CDM gate, validation, parser key injection

**Files:**
- Modify: `backend/app/routers/parse_results.py`

The re-parse route (line ~96) has `body.parser_type == "llamaparse"` as the CDM gate. The validation at lines ~69–74 calls `get_parser()` before reaching that gate, so `landing_ai` is rejected immediately. The CDM branch also needs `parse_cfg["parser"]` injected.

- [ ] **Step 1: Add module-level constant**

Find the imports block at the top of `backend/app/routers/parse_results.py`. Add after the last import:

```python
_CDM_PARSER_TYPES = frozenset({"llamaparse", "landing_ai"})
```

- [ ] **Step 2: Fix parser validation (lines ~69–74)**

Find:
```python
        parser = get_parser(body.parser_type)
        if parser is None and body.parser_type != "simple":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {body.parser_type}",
            )
```
Replace with:
```python
        parser = get_parser(body.parser_type)
        if parser is None and body.parser_type not in ("simple", *_CDM_PARSER_TYPES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {body.parser_type}",
            )
```

- [ ] **Step 3: Fix re-parse CDM gate (line ~96)**

Find:
```python
        use_cdm = (
            settings.USE_CDM_PARSER
            and body.parser_type == "llamaparse"
            and document is not None
            and document.source_document_id is not None
        )
```
Replace with:
```python
        use_cdm = (
            settings.USE_CDM_PARSER
            and body.parser_type in _CDM_PARSER_TYPES
            and document is not None
            and document.source_document_id is not None
        )
```

- [ ] **Step 4: Inject parser key in re-parse CDM branch (line ~112)**

Find inside the `if use_cdm:` block:
```python
            parse_cfg = {k: v for k, v in cfg.items() if k != "representation_kind"}
            background_tasks.add_task(
```
Add one line between them:
```python
            parse_cfg = {k: v for k, v in cfg.items() if k != "representation_kind"}
            parse_cfg["parser"] = body.parser_type
            background_tasks.add_task(
```

- [ ] **Step 5: Run backend tests**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/parse_results.py
git commit -m "fix(routers): extend re-parse CDM gate and validation to support landing_ai"
```

---

## Task 3: Update `ParseConfig` type

**Files:**
- Modify: `frontend/src/types/parsing.ts`

- [ ] **Step 1: Add `model` field to ParseConfig**

Open `frontend/src/types/parsing.ts`. Find:
```ts
export type ParseConfig = {
  tier?: string
  expand?: string[]
  [key: string]: unknown
}
```
Replace with:
```ts
export type ParseConfig = {
  tier?: string
  expand?: string[]
  model?: string
  [key: string]: unknown
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/parsing.ts
git commit -m "feat(types): add model field to ParseConfig for Landing AI"
```

---

## Task 4: Create `LlamaParseConfig` component

Extract the existing LlamaParse config block from `ParseMethodSelector.tsx` into its own file. No behaviour change.

**Files:**
- Create: `frontend/src/components/documents/parser-configs/LlamaParseConfig.tsx`
- Create: `frontend/src/components/documents/parser-configs/LlamaParseConfig.test.tsx`

- [ ] **Step 1: Create the test file**

Create `frontend/src/components/documents/parser-configs/LlamaParseConfig.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LlamaParseConfig } from './LlamaParseConfig'

const defaultConfig = { tier: 'agentic', expand: ['markdown', 'text', 'items'] }

describe('LlamaParseConfig', () => {
  it('renders tier select with current value', () => {
    render(<LlamaParseConfig config={defaultConfig} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders all three output checkboxes', () => {
    render(<LlamaParseConfig config={defaultConfig} onChange={vi.fn()} />)
    expect(screen.getByLabelText(/text \(always included\)/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/markdown/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/structured items/i)).toBeInTheDocument()
  })

  it('calls onChange with updated expand when markdown is unchecked', async () => {
    const onChange = vi.fn()
    render(<LlamaParseConfig config={defaultConfig} onChange={onChange} />)
    await userEvent.click(screen.getByLabelText(/markdown/i))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ expand: expect.not.arrayContaining(['markdown']) })
    )
  })

  it('disables markdown and items when fast tier is selected', async () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <LlamaParseConfig config={{ tier: 'fast', expand: ['text'] }} onChange={onChange} />
    )
    rerender(
      <LlamaParseConfig config={{ tier: 'fast', expand: ['text'] }} onChange={onChange} />
    )
    const markdownCheckbox = screen.getByLabelText(/markdown/i)
    expect(markdownCheckbox).toBeDisabled()
  })
})
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
npx vitest run --reporter=verbose frontend/src/components/documents/parser-configs/LlamaParseConfig.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create the component**

Create `frontend/src/components/documents/parser-configs/LlamaParseConfig.tsx`:

```tsx
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'

interface LlamaParseConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
}

const TIERS = [
  { value: 'fast', label: 'Fast (1 credit/page)', supportsMarkdown: false },
  { value: 'cost_effective', label: 'Cost Effective (3 credits/page)', supportsMarkdown: true },
  { value: 'agentic', label: 'Agentic (10 credits/page)', supportsMarkdown: true },
  { value: 'agentic_plus', label: 'Agentic Plus (45 credits/page)', supportsMarkdown: true },
]

export function LlamaParseConfig({ config, onChange, disabled = false }: LlamaParseConfigProps) {
  const tier = config.tier || 'agentic'
  const expand = config.expand || ['markdown', 'text', 'items']
  const currentTier = TIERS.find((t) => t.value === tier)
  const supportsMarkdown = currentTier?.supportsMarkdown ?? true

  const handleTierChange = (newTier: string) => {
    const tierInfo = TIERS.find((t) => t.value === newTier)
    let newExpand = [...expand]
    if (!tierInfo?.supportsMarkdown) {
      newExpand = newExpand.filter((e) => e === 'text')
      if (!newExpand.includes('text')) newExpand.push('text')
    }
    onChange({ ...config, tier: newTier, expand: newExpand })
  }

  const handleExpandToggle = (option: string, checked: boolean) => {
    let newExpand = [...expand]
    if (checked) {
      newExpand.push(option)
    } else {
      newExpand = newExpand.filter((e) => e !== option)
    }
    if (!newExpand.includes('text')) newExpand.push('text')
    onChange({ ...config, expand: newExpand })
  }

  return (
    <>
      <div className="space-y-2">
        <Label>Tier</Label>
        <Select value={tier} onValueChange={handleTierChange} disabled={disabled}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIERS.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Output Options</Label>
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <Checkbox id="expand-text" checked disabled />
            <Label htmlFor="expand-text" className="text-sm font-normal">
              Text (always included)
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="expand-markdown"
              checked={expand.includes('markdown')}
              onCheckedChange={(checked) => handleExpandToggle('markdown', !!checked)}
              disabled={disabled || !supportsMarkdown}
            />
            <Label htmlFor="expand-markdown" className="text-sm font-normal">
              Markdown{!supportsMarkdown && ' (not available on fast tier)'}
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="expand-items"
              checked={expand.includes('items')}
              onCheckedChange={(checked) => handleExpandToggle('items', !!checked)}
              disabled={disabled || !supportsMarkdown}
            />
            <Label htmlFor="expand-items" className="text-sm font-normal">
              Structured Items{!supportsMarkdown && ' (not available on fast tier)'}
            </Label>
          </div>
        </div>
      </div>
    </>
  )
}
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
npx vitest run --reporter=verbose frontend/src/components/documents/parser-configs/LlamaParseConfig.test.tsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/documents/parser-configs/
git commit -m "feat(ui): extract LlamaParseConfig component"
```

---

## Task 5: Create `LandingAIConfig` component

**Files:**
- Create: `frontend/src/components/documents/parser-configs/LandingAIConfig.tsx`
- Create: `frontend/src/components/documents/parser-configs/LandingAIConfig.test.tsx`

- [ ] **Step 1: Create the test file**

Create `frontend/src/components/documents/parser-configs/LandingAIConfig.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LandingAIConfig } from './LandingAIConfig'

describe('LandingAIConfig', () => {
  it('renders model select', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders model label', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} />)
    expect(screen.getByText('Model')).toBeInTheDocument()
  })

  it('renders description text', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} />)
    expect(screen.getByText(/vision-based document parsing model/i)).toBeInTheDocument()
  })

  it('defaults to dpt-2-latest when model not set', () => {
    render(<LandingAIConfig config={{}} onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('disables select when disabled prop is true', () => {
    render(<LandingAIConfig config={{ model: 'dpt-2-latest' }} onChange={vi.fn()} disabled />)
    expect(screen.getByRole('combobox')).toBeDisabled()
  })
})
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
npx vitest run --reporter=verbose frontend/src/components/documents/parser-configs/LandingAIConfig.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create the component**

Create `frontend/src/components/documents/parser-configs/LandingAIConfig.tsx`:

```tsx
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'

interface LandingAIConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
}

const MODELS = [{ value: 'dpt-2-latest', label: 'dpt-2-latest' }]

export function LandingAIConfig({ config, onChange, disabled = false }: LandingAIConfigProps) {
  const model = config.model || 'dpt-2-latest'

  return (
    <div className="space-y-2">
      <Label>Model</Label>
      <Select
        value={model}
        onValueChange={(value) => onChange({ ...config, model: value })}
        disabled={disabled}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {MODELS.map((m) => (
            <SelectItem key={m.value} value={m.value}>
              {m.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">Vision-based document parsing model.</p>
    </div>
  )
}
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
npx vitest run --reporter=verbose frontend/src/components/documents/parser-configs/LandingAIConfig.test.tsx
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/documents/parser-configs/LandingAIConfig.tsx frontend/src/components/documents/parser-configs/LandingAIConfig.test.tsx
git commit -m "feat(ui): add LandingAIConfig component with model dropdown"
```

---

## Task 6: Rewrite `ParseMethodSelector`

Replace the hard-coded parser list and inline LlamaParse config block with a registry-driven approach. Switching parser type resets config to the new parser's defaults.

**Files:**
- Modify: `frontend/src/components/documents/ParseMethodSelector.tsx`

- [ ] **Step 1: Replace the entire file**

Overwrite `frontend/src/components/documents/ParseMethodSelector.tsx` with:

```tsx
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'
import { LandingAIConfig } from './parser-configs/LandingAIConfig'
import { LlamaParseConfig } from './parser-configs/LlamaParseConfig'

interface ParserMeta {
  label: string
  description: string
  defaultConfig: ParseConfig
}

const PARSER_REGISTRY: Record<string, ParserMeta> = {
  simple: {
    label: 'Simple (local)',
    description: 'Basic text extraction. Works on clean text-based PDFs.',
    defaultConfig: {},
  },
  llamaparse: {
    label: 'LlamaParse',
    description: 'Intelligent parsing. Handles complex layouts, tables, scanned documents.',
    defaultConfig: { tier: 'agentic', expand: ['markdown', 'text', 'items'] },
  },
  landing_ai: {
    label: 'Landing AI',
    description: 'Vision-based parsing. Best for images, shelf photos, and complex visual layouts.',
    defaultConfig: { model: 'dpt-2-latest' },
  },
}

interface ParseMethodSelectorProps {
  parserType: string
  config: ParseConfig
  onParserTypeChange: (type: string) => void
  onConfigChange: (config: ParseConfig) => void
  disabled?: boolean
}

export function ParseMethodSelector({
  parserType,
  config,
  onParserTypeChange,
  onConfigChange,
  disabled = false,
}: ParseMethodSelectorProps) {
  const handleParserChange = (newType: string) => {
    onParserTypeChange(newType)
    onConfigChange(PARSER_REGISTRY[newType]?.defaultConfig ?? {})
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Parse Method</Label>
        <Select value={parserType} onValueChange={handleParserChange} disabled={disabled}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(PARSER_REGISTRY).map(([value, meta]) => (
              <SelectItem key={value} value={value}>
                {meta.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {PARSER_REGISTRY[parserType]?.description}
        </p>
      </div>

      {parserType === 'llamaparse' && (
        <LlamaParseConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
      {parserType === 'landing_ai' && (
        <LandingAIConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
npm run build --prefix /home/asa/rag-admin/frontend 2>&1 | head -40
```

Expected: no TypeScript errors related to `ParseMethodSelector`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/ParseMethodSelector.tsx
git commit -m "refactor(ui): registry-driven ParseMethodSelector with LandingAI support"
```

---

## Task 7: Fix callers — `DocumentUploadZone`, `BulkUploadQueue`, `ReParseDialog`

Three components have a hard-coded `parserType === 'llamaparse' ? parseConfig : undefined` guard and stale default config state. Both need generalising: pass config for any non-simple parser; initialise config to `{}` for simple.

**Files:**
- Modify: `frontend/src/components/documents/DocumentUploadZone.tsx`
- Modify: `frontend/src/components/documents/BulkUploadQueue.tsx`
- Modify: `frontend/src/components/documents/ReParseDialog.tsx`

- [ ] **Step 1: Fix `DocumentUploadZone.tsx`**

Find (line ~39–43):
```ts
  const [parseConfig, setParseConfig] = useState<ParseConfig>({
    tier: 'agentic',
    expand: ['markdown', 'text'],
  })
```
Replace with:
```ts
  const [parseConfig, setParseConfig] = useState<ParseConfig>({})
```

Find (line ~140):
```ts
        parserType === 'llamaparse' ? parseConfig : undefined,
```
Replace with:
```ts
        parserType !== 'simple' ? parseConfig : undefined,
```

Find (line ~148):
```ts
      setParseConfig({ tier: 'agentic', expand: ['markdown', 'text'] })
```
Replace with:
```ts
      setParseConfig({})
```

- [ ] **Step 2: Fix `BulkUploadQueue.tsx`**

Find (line ~81–83):
```ts
  const [parseConfig, setParseConfig] = useState<ParseConfig>({
    tier: 'agentic',
    expand: ['markdown', 'text'],
  })
```
Replace with:
```ts
  const [parseConfig, setParseConfig] = useState<ParseConfig>({})
```

Find (line ~123):
```ts
        parseConfig: parserType === 'llamaparse' ? parseConfig : undefined,
```
Replace with:
```ts
        parseConfig: parserType !== 'simple' ? parseConfig : undefined,
```

- [ ] **Step 3: Fix `ReParseDialog.tsx`**

Find (line ~26–29):
```ts
  const [config, setConfig] = useState<ParseConfig>({
    tier: 'agentic',
    expand: ['markdown', 'text'],
  })
```
Replace with:
```ts
  const [config, setConfig] = useState<ParseConfig>({ tier: 'agentic', expand: ['markdown', 'text', 'items'] })
```

Find (line ~39):
```ts
        parserType === 'llamaparse' ? config : undefined
```
Replace with:
```ts
        parserType !== 'simple' ? config : undefined
```

- [ ] **Step 4: Run full frontend build**

```bash
npm run build --prefix /home/asa/rag-admin/frontend 2>&1 | head -60
```

Expected: clean build, no TypeScript errors.

- [ ] **Step 5: Run frontend tests**

```bash
npx vitest run --reporter=verbose --root /home/asa/rag-admin/frontend
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/DocumentUploadZone.tsx \
        frontend/src/components/documents/BulkUploadQueue.tsx \
        frontend/src/components/documents/ReParseDialog.tsx
git commit -m "fix(ui): generalise parser config guard in upload and re-parse flows"
```

---

## Task 8: Rebuild Docker image and manual verification

- [ ] **Step 1: Rebuild the backend container**

```bash
docker compose -f /home/asa/rag-admin/docker-compose.local.yml -p rag-admin up -d --build backend
```

Expected: container starts healthy.

- [ ] **Step 2: Manual — upload with Landing AI**

1. Open http://localhost in a browser
2. Navigate to any project → click **Upload Document**
3. Select an image file (JPEG or PNG)
4. In the **Parse Method** selector, choose **Landing AI**
5. Verify the **Model** dropdown appears showing `dpt-2-latest`
6. Verify the LlamaParse tier/output options are gone
7. Click **Upload Document**
8. Verify the document enters processing state

- [ ] **Step 3: Manual — verify config reset on parser switch**

1. In the upload dialog, select **LlamaParse** — verify Tier + Output Options appear
2. Switch to **Landing AI** — verify Tier/Output Options disappear, Model dropdown appears
3. Switch to **Simple** — verify no config section appears
4. Switch back to **LlamaParse** — verify tier defaults to `agentic`, all three output options are checked

- [ ] **Step 4: Manual — re-parse with Landing AI**

1. Open an existing document detail page
2. Click **Re-parse**
3. In the Re-parse dialog, choose **Landing AI**
4. Verify the Model dropdown appears
5. Click **Start Parse**
6. Verify the parse run appears in the parse runs timeline

---

## Self-Review

**Spec coverage:**
- §4.1 PARSER_REGISTRY with simple / llamaparse / landing_ai ✅ Task 6
- §4.1 Parser switch resets config to defaultConfig ✅ Task 6 (`handleParserChange`)
- §4.2 ParseMethodSelector driven by registry ✅ Task 6
- §4.3 LlamaParseConfig extracted, no behaviour change ✅ Task 4
- §4.4 LandingAIConfig model dropdown, description text ✅ Task 5
- §4.5 `model?: string` added to ParseConfig ✅ Task 3
- §5 Config passed for any non-simple parser ✅ Task 7
- §5 `parse_config` shape for landing_ai: `{"model":"dpt-2-latest"}` ✅ Tasks 5, 6, 7
- §6.1 CDM gate extended in documents.py (both routes) ✅ Task 1
- §6.1 CDM gate extended in parse_results.py ✅ Task 2
- §6.2 `parse_cfg["parser"] = parser_type` injected (all three call sites) ✅ Tasks 1, 2
- §6.3 Re-parse validation allows `landing_ai` ✅ Task 2
- §7 Extension pattern documented in spec (no code task needed) ✅ covered by registry pattern

**Placeholder scan:** None found.

**Type consistency:** `ParseConfig` with `model?: string` defined in Task 3, consumed in `LandingAIConfig` (Task 5) — consistent. `LlamaParseConfig` and `LandingAIConfig` both accept `{ config: ParseConfig, onChange: (config: ParseConfig) => void, disabled?: boolean }` — consistent with how `ParseMethodSelector` calls them in Task 6.
