# Classify UI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the classify results display (doc name in header, collapsible run-config panel, label→page→block hierarchy) and the new classification run form (batch settings moved to Classification card, system prompt pre-populated with editable instruction + read-only required format section).

**Architecture:** Mostly frontend changes. Two backend changes in Task 1: split `_DEFAULT_SYSTEM_PROMPT` into `_DEFAULT_INSTRUCTION` + `_REQUIRED_FORMAT` in a new constants module, update `LLMClassifier` to always append the required format, and expose a `GET /classification-runs/system-prompt-config` endpoint the frontend fetches once on the new-run page. All other changes are React components and page modifications.

**Tech Stack:** Python 3.12 / FastAPI / pytest (backend); React 18 / TypeScript / shadcn/ui / Tailwind / vitest (frontend); axios via `apiClient` in `frontend/src/api/`

## Global Constraints

- `PromptConfigEditor` (`frontend/src/components/shared/PromptConfigEditor.tsx`) must **not be modified** — it is used as-is.
- New frontend components live in `frontend/src/components/classification/`.
- Backend auth pattern: every route handler takes `current_user: User = Depends(get_current_active_user)`.
- Static route `/system-prompt-config` must be declared **before** the parameterized `/{run_id}` route in `runs_router` — FastAPI matches in declaration order and `/{run_id}` uses `UUID` type validation which would 422 otherwise.
- Run commands from the repo root using absolute paths or `--directory` flags per CLAUDE.md. Never `cd X && Y`.
- Backend tests: `uv run python -m pytest -o "addopts=" <path> -v` from `backend/`.
- Frontend tests: `npx vitest run` from `frontend/`.

---

## Setup

- [ ] **Create feature branch**

```
git checkout -b feat/classify-ui-improvements
```

- [ ] **Pre-implementation gate (per CLAUDE.md):** Before writing any code, create a GitHub issue with the acceptance criteria below and confirm with the user.

Acceptance criteria for the issue:
1. Classify results header shows document name (from nav state)
2. Right panel has a collapsible "Run config" section (collapsed by default) showing classifier type, labels, batch settings, LLM provider/model/temp, system prompt
3. Right panel label sections show page groups (closed by default); clicking a page expands its blocks; block rows no longer show a page badge
4. New run form: batch size and overlap are in the Classification card (not LLM config card)
5. New run form: LLM config system prompt textarea is pre-populated with the default instruction from the backend
6. New run form: a read-only "Required output format" section appears below `PromptConfigEditor` showing the JSON contract
7. Backend: `GET /classification-runs/system-prompt-config` returns `{ instruction, required_format }`
8. Backend: `LLMClassifier` always appends the required format when a custom instruction is provided

---

## File Map

| File | Action |
|------|--------|
| `backend/app/services/classification/prompt_constants.py` | **Create** — `_DEFAULT_INSTRUCTION`, `_REQUIRED_FORMAT`, `DEFAULT_SYSTEM_PROMPT` |
| `backend/app/services/classification/llm_classifier.py` | **Modify** — import from constants; append `_REQUIRED_FORMAT` when custom instruction given |
| `backend/app/routers/classification.py` | **Modify** — add `GET /system-prompt-config` before `/{run_id}` |
| `frontend/src/api/classification.ts` | **Modify** — add `getClassificationSystemPromptConfig()` |
| `frontend/src/pages/ClassificationPage.tsx` | **Modify** — pass `documentTitle` in nav state when opening a run |
| `frontend/src/pages/ClassificationRunDetailPage.tsx` | **Modify** — read title from state; add `ClassificationRunConfigPanel`; pass title in rerun nav |
| `frontend/src/components/classification/ClassificationRunConfigPanel.tsx` | **Create** — collapsible config summary |
| `frontend/src/components/classification/ClassificationPageGroup.tsx` | **Create** — page-level collapsible group |
| `frontend/src/components/classification/ClassificationLabelSection.tsx` | **Modify** — group blocks by page; render `ClassificationPageGroup` |
| `frontend/src/components/classification/ClassificationBlockRow.tsx` | **Modify** — remove `p.N` page badge |
| `frontend/src/pages/NewClassificationRunPage.tsx` | **Modify** — move batch settings; fetch prompt config; render required format section |

---

## Task 1: Backend — Prompt Constants + System Prompt Endpoint

**Files:**
- Create: `backend/app/services/classification/prompt_constants.py`
- Modify: `backend/app/services/classification/llm_classifier.py`
- Modify: `backend/app/routers/classification.py`
- Modify: `frontend/src/api/classification.ts`
- Test: `backend/tests/services/classification/test_llm_classifier_prompt.py`

**Interfaces:**
- Produces: `_DEFAULT_INSTRUCTION: str`, `_REQUIRED_FORMAT: str`, `DEFAULT_SYSTEM_PROMPT: str` (importable from `prompt_constants`)
- Produces: `GET /classification-runs/system-prompt-config` → `{ "instruction": str, "required_format": str }`
- Produces: `getClassificationSystemPromptConfig(): Promise<{ instruction: string; requiredFormat: string }>`

- [ ] **Step 1.1: Create `prompt_constants.py`**

```python
# backend/app/services/classification/prompt_constants.py

_DEFAULT_INSTRUCTION = """\
You are a document classifier. Analyze the document pages provided and determine which labels apply to each page.

For each label, classify each page as:
- "start": this page begins a section matching this label
- "continue": this page continues a section from a previous page
- "none": this page does not contain this label\
"""

_REQUIRED_FORMAT = """\
Return ONLY valid JSON in this exact format:
{
  "pages": [
    {"page": <page_index>, "labels": {"<label>": "start"|"continue"|"none", ...}},
    ...
  ]
}

Include every page index present in the document content.\
"""

DEFAULT_SYSTEM_PROMPT = _DEFAULT_INSTRUCTION + "\n\n" + _REQUIRED_FORMAT
```

- [ ] **Step 1.2: Write failing tests for `LLMClassifier` prompt assembly**

```python
# backend/tests/services/classification/test_llm_classifier_prompt.py
import pytest
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.prompt_constants import (
    _REQUIRED_FORMAT,
    DEFAULT_SYSTEM_PROMPT,
)


def _make_classifier(system_prompt=None):
    return LLMClassifier(
        adapter=None,  # not used in prompt-assembly tests
        provider="ollama_local",
        model="test-model",
        system_prompt=system_prompt,
    )


def test_default_prompt_used_when_no_system_prompt():
    c = _make_classifier()
    assert c.system_prompt == DEFAULT_SYSTEM_PROMPT


def test_custom_instruction_gets_required_format_appended():
    custom = "You are a specialized classifier."
    c = _make_classifier(system_prompt=custom)
    assert c.system_prompt == custom + "\n\n" + _REQUIRED_FORMAT


def test_required_format_not_duplicated_in_default():
    c = _make_classifier()
    # default prompt already contains required format exactly once
    assert c.system_prompt.count("Return ONLY valid JSON") == 1
```

- [ ] **Step 1.3: Run tests — confirm they fail**

```
uv run python -m pytest -o "addopts=" backend/tests/services/classification/test_llm_classifier_prompt.py -v
```
Expected: FAIL (import errors until `prompt_constants` is created; then assertion errors until classifier is updated)

- [ ] **Step 1.4: Update `llm_classifier.py` to import from constants and update constructor**

Replace the inline `_DEFAULT_SYSTEM_PROMPT` constant and the `__init__` assignment. The full diff is:

```python
# backend/app/services/classification/llm_classifier.py
# --- REMOVE these lines (the old inline constant) ---
# _DEFAULT_SYSTEM_PROMPT = """\
# You are a document classifier...
# ...
# Include every page index present in the document content.\
# """

# --- ADD import at top (after existing imports) ---
from app.services.classification.prompt_constants import (
    DEFAULT_SYSTEM_PROMPT as _DEFAULT_SYSTEM_PROMPT,
    _REQUIRED_FORMAT,
)

# --- UPDATE the constructor body (replace the single assignment line) ---
# OLD:
#   self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
# NEW:
        if system_prompt:
            self.system_prompt = system_prompt + "\n\n" + _REQUIRED_FORMAT
        else:
            self.system_prompt = _DEFAULT_SYSTEM_PROMPT
```

Full updated `__init__` signature and body for clarity:

```python
    def __init__(
        self,
        adapter: LLMPort,
        provider: str,
        model: str,
        batch_size: int = 10,
        batch_overlap: int = 3,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self.adapter = adapter
        self.provider = provider
        self.model = model
        self.batch_size = batch_size
        self.batch_overlap = batch_overlap
        if system_prompt:
            self.system_prompt = system_prompt + "\n\n" + _REQUIRED_FORMAT
        else:
            self.system_prompt = _DEFAULT_SYSTEM_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens
```

- [ ] **Step 1.5: Run tests — confirm they pass**

```
uv run python -m pytest -o "addopts=" backend/tests/services/classification/test_llm_classifier_prompt.py -v
```
Expected: 3 PASSED

- [ ] **Step 1.6: Add `GET /system-prompt-config` endpoint to `classification.py` router**

Insert the new route **before** the existing `@runs_router.get("/{run_id}", ...)` handler (currently line 202). Add the import at the top of the file alongside the existing `from app.services.classification...` imports:

```python
# Add to existing imports block in backend/app/routers/classification.py:
from app.services.classification.prompt_constants import (
    _DEFAULT_INSTRUCTION,
    _REQUIRED_FORMAT,
)
```

Insert before `@runs_router.get("/{run_id}", ...)`:

```python
@runs_router.get("/system-prompt-config")
async def get_classification_system_prompt_config(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return {
        "instruction": _DEFAULT_INSTRUCTION,
        "required_format": _REQUIRED_FORMAT,
    }
```

- [ ] **Step 1.7: Add `getClassificationSystemPromptConfig` to `frontend/src/api/classification.ts`**

Append to the end of the file:

```typescript
export async function getClassificationSystemPromptConfig(): Promise<{
  instruction: string
  requiredFormat: string
}> {
  const response = await apiClient.get<{ instruction: string; required_format: string }>(
    '/classification-runs/system-prompt-config',
  )
  return {
    instruction: response.data.instruction,
    requiredFormat: response.data.required_format,
  }
}
```

- [ ] **Step 1.8: Start the backend and verify the endpoint manually**

```
uv run --directory backend uvicorn app.main:app --reload
```

In a second terminal:
```
curl -s http://localhost:8000/api/classification-runs/system-prompt-config -H "Authorization: Bearer <token>" | python -m json.tool
```
Expected: JSON with `instruction` and `required_format` keys containing the prompt text.

- [ ] **Step 1.9: Commit**

```
git add backend/app/services/classification/prompt_constants.py \
        backend/app/services/classification/llm_classifier.py \
        backend/app/routers/classification.py \
        frontend/src/api/classification.ts \
        backend/tests/services/classification/test_llm_classifier_prompt.py
git commit -m "feat(classify): expose prompt constants via API; LLMClassifier always appends required format"
```

---

## Task 2: Results Display — Document Name in Header (A1)

**Files:**
- Modify: `frontend/src/pages/ClassificationPage.tsx` (lines 170–171)
- Modify: `frontend/src/pages/ClassificationRunDetailPage.tsx` (lines 2, 81–91, 108–112)

**Interfaces:**
- Consumes: `selectedDocument` (already in scope in `ClassificationPage`)
- Produces: `location.state.documentTitle: string | undefined` passed to `/classify/{runId}`

- [ ] **Step 2.1: Pass `documentTitle` in nav state when opening a run from `ClassificationPage.tsx`**

Find line 170 in `ClassificationPage.tsx`:
```typescript
// OLD:
onSelectRun={(runId) => navigate(`/classify/${runId}`)}
// NEW:
onSelectRun={(runId) => navigate(`/classify/${runId}`, {
  state: { documentTitle: selectedDocument?.title },
})}
```

- [ ] **Step 2.2: Read title from location state and display it in `ClassificationRunDetailPage.tsx`**

Add `useLocation` to the react-router-dom import (line 2):
```typescript
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom'
```

Add after the `navigate` declaration (after line 29):
```typescript
const location = useLocation()
const documentTitle = (location.state as { documentTitle?: string } | null)?.documentTitle
```

- [ ] **Step 2.3: Show `documentTitle` in the header and pass it through on re-run**

In the header section (around line 108), insert the document title span after the status badge:

```tsx
<div className="flex items-center gap-3 flex-1 min-w-0">
  <ClassificationRunStatusBadge status={run.status} />
  {documentTitle && (
    <span className="text-sm font-medium truncate max-w-[200px]">{documentTitle}</span>
  )}
  <span className="text-sm text-muted-foreground truncate">{modelSummary}</span>
  <span className="text-xs text-muted-foreground shrink-0">
    {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
  </span>
  <div className="flex gap-3 text-xs text-muted-foreground ml-auto shrink-0">
    <span>
      <span className="font-medium text-foreground">{run.labelsRequested.length}</span> labels
    </span>
    <span>
      <span className="font-medium text-foreground">{run.regions.length}</span> regions
    </span>
    {run.durationMs !== null && (
      <span>
        <span className="font-medium text-foreground">{(run.durationMs / 1000).toFixed(1)}s</span>
      </span>
    )}
  </div>
</div>
```

Update `handleRerun` to forward the title (replace existing `handleRerun` function):
```typescript
const handleRerun = () => {
  navigate(`/classify/new?documentId=${run.documentId}`, {
    state: {
      documentTitle,
      defaults: {
        labels: run.labelsRequested,
        classifierType: run.classifierType,
        classifierConfig: run.classifierConfig,
      },
    },
  })
}
```

- [ ] **Step 2.4: Verify manually**

Start the frontend: `npm run dev --prefix frontend`  
Open the Classify page, select a document, click a run. The header should show the document name. Click "Re-run" — the new run page should show the document title.

- [ ] **Step 2.5: Commit**

```
git add frontend/src/pages/ClassificationPage.tsx \
        frontend/src/pages/ClassificationRunDetailPage.tsx
git commit -m "feat(classify): display document name in results header"
```

---

## Task 3: Results Display — Run Config Panel (A2)

**Files:**
- Create: `frontend/src/components/classification/ClassificationRunConfigPanel.tsx`
- Modify: `frontend/src/pages/ClassificationRunDetailPage.tsx`

**Interfaces:**
- Consumes: `ClassificationRun` from `@/types/classification`
- Produces: `<ClassificationRunConfigPanel run={run} />` (rendered at top of right panel, before status-dependent content)

- [ ] **Step 3.1: Create `ClassificationRunConfigPanel.tsx`**

```tsx
// frontend/src/components/classification/ClassificationRunConfigPanel.tsx
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import type { ClassificationRun } from '@/types/classification'

interface Props {
  run: ClassificationRun
}

export function ClassificationRunConfigPanel({ run }: Props) {
  const [open, setOpen] = useState(false)
  const [promptExpanded, setPromptExpanded] = useState(false)

  const cfg = run.classifierConfig as Record<string, unknown>
  const llmCfg = (cfg.llm_config as Record<string, unknown> | undefined) ?? {}
  const isLlm = run.classifierType === 'llm'

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mb-3">
      <CollapsibleTrigger className="w-full flex items-center gap-2 py-2 px-1 text-xs text-muted-foreground hover:text-foreground">
        {open ? (
          <ChevronDown className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" />
        )}
        <span className="font-medium">Run config</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 pb-3 border-b mb-3">
        {/* Classification run */}
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Classification run
          </p>
          <div className="space-y-1 text-xs">
            <div className="flex gap-2">
              <span className="text-muted-foreground w-24 shrink-0">Classifier</span>
              <span>{run.classifierType}</span>
            </div>
            <div className="flex gap-2 items-start">
              <span className="text-muted-foreground w-24 shrink-0 mt-0.5">Labels</span>
              <div className="flex flex-wrap gap-1">
                {run.labelsRequested.map((l) => (
                  <Badge key={l} variant="secondary" className="text-xs font-normal">
                    {l}
                  </Badge>
                ))}
              </div>
            </div>
            {isLlm && (
              <>
                <div className="flex gap-2">
                  <span className="text-muted-foreground w-24 shrink-0">Batch size</span>
                  <span>{String(cfg.batch_size ?? '—')} pages</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-muted-foreground w-24 shrink-0">Batch overlap</span>
                  <span>{String(cfg.batch_overlap ?? '—')} pages</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* LLM classification */}
        {isLlm && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              LLM classification
            </p>
            <div className="space-y-1 text-xs">
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Provider</span>
                <span>{String(cfg.provider ?? '—')}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Model</span>
                <span>{String(cfg.model ?? '—')}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Temperature</span>
                <span>{String(llmCfg.temperature ?? '—')}</span>
              </div>
              {llmCfg.system_prompt && (
                <div className="flex gap-2 items-start">
                  <span className="text-muted-foreground w-24 shrink-0 mt-0.5">
                    System prompt
                  </span>
                  <Collapsible
                    open={promptExpanded}
                    onOpenChange={setPromptExpanded}
                    className="flex-1 min-w-0"
                  >
                    <CollapsibleTrigger asChild>
                      <button className="text-left w-full hover:text-foreground">
                        {promptExpanded ? (
                          <span className="text-xs underline text-muted-foreground">Hide</span>
                        ) : (
                          <span className="block text-muted-foreground line-clamp-2 break-words">
                            {String(llmCfg.system_prompt).slice(0, 100)}
                            {String(llmCfg.system_prompt).length > 100 ? '…' : ''}
                          </span>
                        )}
                      </button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <pre className="mt-1 text-xs whitespace-pre-wrap break-words bg-muted rounded p-2 font-mono">
                        {String(llmCfg.system_prompt)}
                      </pre>
                    </CollapsibleContent>
                  </Collapsible>
                </div>
              )}
            </div>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
```

- [ ] **Step 3.2: Wire `ClassificationRunConfigPanel` into `ClassificationRunDetailPage.tsx`**

Add the import near the other classification imports (after line 8):
```typescript
import { ClassificationRunConfigPanel } from '@/components/classification/ClassificationRunConfigPanel'
```

Replace the right panel `<div>` content (the `w-80` panel, around line 145):
```tsx
<div className="w-80 shrink-0 overflow-y-auto p-4">
  <ClassificationRunConfigPanel run={run} />
  {run.status === 'completed' ? (
    <ClassificationResultsViewer
      runId={run.id}
      labelsRequested={run.labelsRequested}
      selectedBlockId={selectedBlockId}
      onBlockSelect={setSelectedBlockId}
    />
  ) : run.status === 'running' ? (
    <p className="text-sm text-muted-foreground animate-pulse">Classification in progress…</p>
  ) : run.error ? (
    <Alert variant="destructive">
      <AlertDescription>{run.error}</AlertDescription>
    </Alert>
  ) : null}
</div>
```

Note: the config panel is rendered outside the status condition so it's visible in all run states.

- [ ] **Step 3.3: Verify manually**

Open a completed classification run. The right panel should show a collapsed "Run config" row at the top. Expanding it shows labels, classifier type, batch settings, and LLM provider/model/temperature. System prompt row only appears if a custom prompt was saved.

- [ ] **Step 3.4: Commit**

```
git add frontend/src/components/classification/ClassificationRunConfigPanel.tsx \
        frontend/src/pages/ClassificationRunDetailPage.tsx
git commit -m "feat(classify): add collapsible run config panel in results right panel"
```

---

## Task 4: Results Display — Page Group Hierarchy (A3)

**Files:**
- Create: `frontend/src/components/classification/ClassificationPageGroup.tsx`
- Modify: `frontend/src/components/classification/ClassificationLabelSection.tsx`
- Modify: `frontend/src/components/classification/ClassificationBlockRow.tsx`

**Interfaces:**
- Produces: `<ClassificationPageGroup pageIndex={n} blocks={[...]} selectedBlockId={...} onBlockSelect={...} />`
- Consumes from `ClassificationLabelSection`: same `blocks: AnnotatedBlock[]` prop; groups by `block.pageIndex`

- [ ] **Step 4.1: Create `ClassificationPageGroup.tsx`**

```tsx
// frontend/src/components/classification/ClassificationPageGroup.tsx
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ClassificationBlockRow } from './ClassificationBlockRow'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  pageIndex: number
  blocks: AnnotatedBlock[]
  selectedBlockId?: string | null
  onBlockSelect?: (blockId: string) => void
}

export function ClassificationPageGroup({ pageIndex, blocks, selectedBlockId, onBlockSelect }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-muted/30 text-left">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          )}
          <span className="text-muted-foreground">Page {pageIndex + 1}</span>
          <Badge variant="secondary" className="font-mono text-xs">
            {blocks.length}
          </Badge>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-1 pb-1 px-2">
        {blocks.map((block) => (
          <ClassificationBlockRow
            key={block.blockId}
            block={block}
            isSelected={selectedBlockId === block.blockId}
            onSelect={onBlockSelect}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}
```

- [ ] **Step 4.2: Update `ClassificationLabelSection.tsx` to group blocks by page**

Replace the full file:

```tsx
// frontend/src/components/classification/ClassificationLabelSection.tsx
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ClassificationPageGroup } from './ClassificationPageGroup'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  label: string | null
  blocks: AnnotatedBlock[]
  selectedBlockId?: string | null
  onBlockSelect?: (blockId: string) => void
}

function pageRange(blocks: AnnotatedBlock[]): string {
  if (blocks.length === 0) return ''
  const pages = blocks.map((b) => b.pageIndex)
  const min = Math.min(...pages) + 1
  const max = Math.max(...pages) + 1
  return min === max ? `Page ${min}` : `Pages ${min}–${max}`
}

export function ClassificationLabelSection({ label, blocks, selectedBlockId, onBlockSelect }: Props) {
  const displayName = label ?? 'Unmatched'
  const [open, setOpen] = useState(label !== null)

  const pageGroups = Array.from(
    blocks.reduce((map, block) => {
      const key = block.pageIndex
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(block)
      return map
    }, new Map<number, AnnotatedBlock[]>()),
  ).sort(([a], [b]) => a - b)

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
      <CollapsibleContent className="mt-1 space-y-0.5">
        {blocks.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 py-2">
            No regions identified for this label.
          </p>
        ) : (
          pageGroups.map(([pageIndex, pageBlocks]) => (
            <ClassificationPageGroup
              key={pageIndex}
              pageIndex={pageIndex}
              blocks={pageBlocks}
              selectedBlockId={selectedBlockId}
              onBlockSelect={onBlockSelect}
            />
          ))
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
```

- [ ] **Step 4.3: Remove the page badge from `ClassificationBlockRow.tsx`**

Replace the full file (removing `Badge` for `p.N`, keeping role badge):

```tsx
// frontend/src/components/classification/ClassificationBlockRow.tsx
import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  block: AnnotatedBlock
  isSelected?: boolean
  onSelect?: (blockId: string) => void
}

export function ClassificationBlockRow({ block, isSelected, onSelect }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`border rounded-md overflow-hidden ${isSelected ? 'border-primary ring-1 ring-primary' : ''}`}
    >
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 text-left"
        onClick={() => {
          setExpanded((v) => !v)
          onSelect?.(block.blockId)
        }}
      >
        <Badge variant="outline" className="shrink-0 text-xs">
          {block.role}
        </Badge>
        <span className="flex-1 truncate text-muted-foreground line-clamp-1">{block.text}</span>
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

- [ ] **Step 4.4: Run frontend lint and build**

```
npx --prefix frontend tsc --noEmit
npm run lint --prefix frontend
```
Expected: no errors.

- [ ] **Step 4.5: Verify manually**

Open a completed run. The right panel should show: `▼ LabelName [N blocks]  Pages X–Y` → inside, `▶ Page 1 [k]`, `▶ Page 2 [k]`, etc. (all closed). Click a page row — it expands to show block rows without the `p.N` badge. Clicking a block still highlights it in the PDF.

- [ ] **Step 4.6: Commit**

```
git add frontend/src/components/classification/ClassificationPageGroup.tsx \
        frontend/src/components/classification/ClassificationLabelSection.tsx \
        frontend/src/components/classification/ClassificationBlockRow.tsx
git commit -m "feat(classify): add label -> page -> block hierarchy in results panel"
```

---

## Task 5: New Run Form — Batch Settings + System Prompt (B1 + B2)

**Files:**
- Modify: `frontend/src/pages/NewClassificationRunPage.tsx`

**Interfaces:**
- Consumes: `getClassificationSystemPromptConfig()` from `@/api/classification`
- Produces: batch settings in Classification card; required format section below `PromptConfigEditor` in LLM card

- [ ] **Step 5.1: Update imports in `NewClassificationRunPage.tsx`**

Remove `Collapsible`, `CollapsibleContent`, `CollapsibleTrigger` and `ChevronDown` from the import list (no longer needed in this file after this task). Add `getClassificationSystemPromptConfig` to the api import.

```typescript
// REMOVE these imports:
// import { ChevronDown } from 'lucide-react'
// import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

// UPDATE the classification API import:
import { createClassificationRun, getClassificationSystemPromptConfig } from '@/api/classification'
```

The `ChevronLeft` icon import stays (used for the Back button).

- [ ] **Step 5.2: Add `systemPromptConfig` state and fetch effect**

Add after the existing `useState` declarations (after line 75 in the original file):

```typescript
const [systemPromptConfig, setSystemPromptConfig] = useState<{
  instruction: string
  requiredFormat: string
} | null>(null)
```

Add a new `useEffect` after the existing parse-seed effect:

```typescript
useEffect(() => {
  getClassificationSystemPromptConfig()
    .then(setSystemPromptConfig)
    .catch(() => {
      // silently degrade — required format section simply won't render
    })
}, [])
```

- [ ] **Step 5.3: Pre-populate system prompt from fetched config**

Add another `useEffect` after the one from step 5.2:

```typescript
useEffect(() => {
  if (!systemPromptConfig) return
  setPromptConfig((prev) => {
    if (prev.systemPrompt !== undefined) return prev // already set from re-run defaults
    return { ...prev, systemPrompt: systemPromptConfig.instruction }
  })
}, [systemPromptConfig])
```

- [ ] **Step 5.4: Move batch settings into the Classification card**

Replace the entire Classification card JSX (the `{/* Section 2: Classification */}` block) with:

```tsx
{/* Section 2: Classification */}
<Card>
  <CardHeader>
    <CardTitle className="text-base">Classification</CardTitle>
  </CardHeader>
  <CardContent className="space-y-4">
    <ClassificationConfig
      defaultValues={{
        labels: classifyConfig.labels,
        classifierType: classifyConfig.classifierType,
      }}
      onChange={setClassifyConfig}
    />
    {classifyConfig.classifierType === 'llamaindex_split' && (
      <p className="text-sm text-muted-foreground">
        LlamaIndex split classifier is not yet implemented. Select LLM classifier to proceed.
      </p>
    )}
    {isLlm && (
      <div className="grid grid-cols-2 gap-4 pt-2 border-t">
        <div className="space-y-2">
          <Label>Batch size (pages)</Label>
          <Input
            type="number"
            min={1}
            value={batchSize}
            onChange={(e) => setBatchSize(Number(e.target.value))}
            disabled={isSubmitting}
          />
        </div>
        <div className="space-y-2">
          <Label>Batch overlap (pages)</Label>
          <Input
            type="number"
            min={0}
            value={batchOverlap}
            onChange={(e) => setBatchOverlap(Number(e.target.value))}
            disabled={isSubmitting}
          />
        </div>
      </div>
    )}
  </CardContent>
</Card>
```

- [ ] **Step 5.5: Update LLM configuration card — remove batch settings, add required format section**

Replace the entire `{/* Section 3: LLM configuration */}` block with:

```tsx
{/* Section 3: LLM configuration (only when LLM classifier selected) */}
{isLlm && (
  <Card>
    <CardHeader>
      <CardTitle className="text-base">LLM configuration</CardTitle>
    </CardHeader>
    <CardContent className="space-y-6">
      <PromptConfigEditor
        value={promptConfig}
        onChange={setPromptConfig}
        capabilities={{ thinking: true }}
      />
      {systemPromptConfig && (
        <div className="border-t pt-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Required output format · always appended by the app
          </p>
          <pre className="text-xs bg-muted rounded-md p-3 font-mono text-muted-foreground whitespace-pre-wrap break-words cursor-default select-text">
            {systemPromptConfig.requiredFormat}
          </pre>
          <p className="text-xs text-muted-foreground">
            ⓘ The app parses this JSON structure from the model response to build classification regions.
          </p>
        </div>
      )}
    </CardContent>
  </Card>
)}
```

- [ ] **Step 5.6: Run TypeScript check and lint**

```
npx --prefix frontend tsc --noEmit
npm run lint --prefix frontend
```
Expected: no errors.

- [ ] **Step 5.7: Verify manually**

Navigate to `/classify/new?documentId=<id>`.
- Classification card should now show batch size / overlap fields (when LLM selected), after the labels section.
- LLM configuration card should show `PromptConfigEditor` with the system prompt textarea pre-populated with the default instruction text.
- Below the `PromptConfigEditor`, a "Required output format · always appended by the app" section should show the JSON format block.
- The batch settings Collapsible should be gone from the LLM card.
- Re-running an existing run should pre-fill the instruction textarea with whatever was saved in `classifierConfig.llm_config.system_prompt`.

- [ ] **Step 5.8: Commit**

```
git add frontend/src/pages/NewClassificationRunPage.tsx
git commit -m "feat(classify): move batch settings to classification card; show system prompt with required format"
```

---

## Final Steps

- [ ] **Run frontend build to catch any remaining type errors**

```
npm run build --prefix frontend
```
Expected: builds without errors.

- [ ] **Create PR**

```
gh pr create --title "feat: classify UI improvements — doc name, config panel, page hierarchy, prompt editor" \
  --body "$(cat <<'EOF'
## Summary
- Results display: document name in header (via nav state), collapsible run config panel, label→page→block hierarchy in right panel
- New run form: batch settings moved to Classification card, system prompt pre-populated from backend and shown alongside read-only required output format section

## Spec
docs/superpowers/specs/2026-07-02-classify-ui-improvements-design.md

## Test plan
- [ ] Open a classification run from the Classify page — header shows document name
- [ ] Re-run a run — new run page receives document title in header
- [ ] Expand "Run config" panel in results — shows labels, classifier, batch settings, LLM params
- [ ] Results panel shows label → collapsed page groups → blocks on expand
- [ ] Click a block within an expanded page group — highlights in PDF
- [ ] New run form: Classification card shows batch size/overlap when LLM selected
- [ ] New run form: LLM config card shows pre-populated system prompt textarea
- [ ] New run form: required output format section visible below PromptConfigEditor
- [ ] Re-run an existing run with custom prompt — instruction portion pre-fills in textarea

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
