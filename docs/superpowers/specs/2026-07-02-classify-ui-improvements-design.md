# Design Spec: Classify UI Improvements

**Date:** 2026-07-02  
**Status:** Awaiting user review  
**Related:** `docs/superpowers/specs/2026-07-02-classify-ui-improvements-proposed-changes.md`

---

## Scope

Two screens receive changes:

1. **Classify results display** (`ClassificationRunDetailPage`) — three improvements
2. **New classification run form** (`NewClassificationRunPage`) — two improvements

Full run details (LLM request/response traces, per-batch inputs/outputs) are explicitly out of scope.

---

## A — Classify Results Display

### A1: Document Name in Header

**Goal:** make it immediately clear which document this run is for.

**Change:** add `documentTitle` after the status badge in the page header.

```
← Back  [completed]  My Document.pdf  ollama_local/qwen2.5:7b  2h ago  3 labels  12 regions  4.2s  [Re-run]
```

The document name is rendered in `text-sm font-medium` and truncated with `truncate` if the header is tight. It lives between the status badge and the model summary.

**Backend:** `ClassificationRunResponse` gains a `documentTitle: str` field. The repository's `get(run_id)` method joins the `documents` table (or calls a simple `SELECT name FROM documents WHERE id = ?`) and includes the name in the response schema. No new endpoint needed.

---

### A2: Run Config Summary — Collapsible Section in Right Panel

**Goal:** let the user inspect what config was used without cluttering the results view.

**Placement:** collapsible section at the top of the right panel (w-80), above `ClassificationResultsViewer`. Collapsed by default.

**Trigger:** a single row `▶ Run config` (using `ChevronRight` / `ChevronDown`). Clicking expands it.

**Expanded content — two groups:**

**Classification run**
| Field | Example |
|-------|---------|
| Classifier | LLM |
| Labels | `[Introduction]` `[Methodology]` `[Conclusion]` |
| Batch size | 10 pages |
| Batch overlap | 3 pages |

**LLM classification** *(only when `classifierType === 'llm'`)*
| Field | Example |
|-------|---------|
| Provider / Model | `ollama_local / qwen2.5:7b` |
| Temperature | 0.0 |
| System prompt | First ~2 lines, truncated; "Show full" link expands inline |

Labels are shown as small `Badge variant="secondary"` chips. The system prompt expansion is inline (no modal) using a `Collapsible`.

**Component:** `ClassificationRunConfigPanel` (new component in `components/classification/`). Receives the full `ClassificationRun` object as its only prop.

---

### A3: Right Panel Hierarchy — Label → Page → Block

**Goal:** the primary mental model for classification results is sections of a document. The page level is the natural summary unit; blocks are secondary detail.

**Before:**
```
▼ Introduction  [8]         Pages 1–4
    [p.1] paragraph  "This report covers..."
    [p.1] heading    "Executive Summary"
    [p.2] paragraph  "The findings show..."
```

**After:**
```
▼ Introduction  [8 blocks]  Pages 1–4
  ▶ Page 1  [3 blocks]
  ▶ Page 2  [2 blocks]
  ▶ Page 3  [2 blocks]
  ▶ Page 4  [1 block]
```

Clicking a page row expands it:
```
▼ Introduction  [8 blocks]  Pages 1–4
  ▼ Page 1  [3 blocks]
      paragraph  "This report covers..."
      heading    "Executive Summary"
      paragraph  "Background context..."
  ▶ Page 2  [2 blocks]
```

**Default states:**
- Label sections: open (unchanged from current behaviour)
- Page groups: **closed** — the summary of interest is at the page level
- Block rows: no change (click to expand markdown content, click selects block in PDF)

**Component changes:**

`ClassificationLabelSection` — groups its `blocks` array by `pageIndex` (ascending) before rendering. Replaces the current `blocks.map(ClassificationBlockRow)` with `pageGroups.map(ClassificationPageGroup)`.

`ClassificationPageGroup` *(new, `components/classification/ClassificationPageGroup.tsx`)* — collapsible row:
- Header: `▶ Page N  [k blocks]` — uses `ChevronRight`/`ChevronDown`, `Badge variant="secondary"` for count
- Closed by default (`useState(false)`)
- Content: `ClassificationBlockRow` for each block in the group
- Passes through `selectedBlockId` and `onBlockSelect`

`ClassificationBlockRow` — remove the `p.N` page badge (now redundant at the group level). Keep role badge and text.

---

## B — New Classification Run Form

### B1: Batch Settings Move to Classification Card

**Goal:** the "LLM configuration" card should contain only LLM concerns.

**Before — "LLM configuration" card contains:**
- System prompt
- Provider / Model
- Temperature
- Batch size / Batch overlap (collapsible)

**After — "Classification" card gains:**
- Batch size (shown inline when `classifierType === 'llm'`, below the classifier selector)
- Batch overlap (same row as batch size)

**After — "LLM configuration" card contains:**
- System prompt (new `ClassificationSystemPromptEditor` — see B2)
- Provider / Model
- Temperature / Max tokens

The batch settings are no longer wrapped in a collapsible — they are a straightforward two-field row inside the Classification card since they are always relevant for LLM runs.

---

### B2: System Prompt — Editable + Read-Only Split

**Goal:** users can see and customise what the classifier is instructed to do, without accidentally breaking the JSON output contract that the app depends on.

**Component:** `ClassificationSystemPromptEditor` (new, `components/classification/ClassificationSystemPromptEditor.tsx`)

Replaces the generic system prompt `Textarea` in `PromptConfigEditor` when used in the classification run form. `PromptConfigEditor` is passed a `hideSystemPrompt` prop (or the classification form simply doesn't use `PromptConfigEditor`'s system prompt field and renders `ClassificationSystemPromptEditor` above it instead).

**UI layout:**

```
System prompt
┌──────────────────────────────────────────────────────┐
│ You are a document classifier. Analyze the document  │
│ pages provided and determine which labels apply to   │  ← editable Textarea
│ each page.                                           │
│                                                      │
│ For each label, classify each page as:               │
│ - "start": this page begins a section matching...    │
│ - "continue": this page continues a section...       │
│ - "none": this page does not contain this label      │
└──────────────────────────────────────────────────────┘
                                         [Reset to default]

Required output format · read-only
┌──────────────────────────────────────────────────────┐
│ Return ONLY valid JSON in this exact format:         │
│ {                                                    │  ← read-only pre/code block
│   "pages": [                                         │     bg-muted, text-muted-foreground
│     {"page": <page_index>, "labels": {              │     cursor-not-allowed
│       "<label>": "start"|"continue"|"none", ...}}   │
│   ]                                                  │
│ }                                                    │
│ Include every page index in the document content.    │
└──────────────────────────────────────────────────────┘
ⓘ The app parses this JSON structure from the model response.
```

**Props:**
```typescript
interface ClassificationSystemPromptEditorProps {
  value: string | undefined   // the editable instruction portion; undefined = use default
  onChange: (value: string | undefined) => void
  disabled?: boolean
}
```

**Default instruction text** (shown in the textarea when `value` is `undefined`):
```
You are a document classifier. Analyze the document pages provided and determine which labels apply to each page.

For each label, classify each page as:
- "start": this page begins a section matching this label
- "continue": this page continues a section from a previous page
- "none": this page does not contain this label
```

"Reset to default" link: sets `value` back to `undefined`, restoring the textarea to the default text.

**What is submitted:** `promptConfig.systemPrompt` receives the editable portion only (`undefined` if the user hasn't changed the default, or their custom text). The backend handles appending the required format section.

**Data model — backend changes:**

`llm_classifier.py` — split `_DEFAULT_SYSTEM_PROMPT`:
```python
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

_DEFAULT_SYSTEM_PROMPT = _DEFAULT_INSTRUCTION + "\n\n" + _REQUIRED_FORMAT
```

The constructor logic changes:
```python
# Before
self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

# After
if system_prompt:
    self.system_prompt = system_prompt + "\n\n" + _REQUIRED_FORMAT
else:
    self.system_prompt = _DEFAULT_SYSTEM_PROMPT
```

This means:
- `system_prompt = null` → full default (backward compatible with existing runs)
- `system_prompt = <user text>` → user text + required format

Per-run customization only. Persistent prompt templates are out of scope for this sprint.

---

## Component Summary

| Component | File | Type |
|-----------|------|------|
| `ClassificationRunConfigPanel` | `components/classification/ClassificationRunConfigPanel.tsx` | New |
| `ClassificationPageGroup` | `components/classification/ClassificationPageGroup.tsx` | New |
| `ClassificationSystemPromptEditor` | `components/classification/ClassificationSystemPromptEditor.tsx` | New |
| `ClassificationRunDetailPage` | `pages/ClassificationRunDetailPage.tsx` | Modified |
| `ClassificationLabelSection` | `components/classification/ClassificationLabelSection.tsx` | Modified |
| `ClassificationBlockRow` | `components/classification/ClassificationBlockRow.tsx` | Modified |
| `NewClassificationRunPage` | `pages/NewClassificationRunPage.tsx` | Modified |

## Backend Summary

| File | Change |
|------|--------|
| `schemas/classification.py` | Add `documentTitle: str` to `ClassificationRunResponse` |
| `repositories/classification_run_repository.py` | Join documents in `get(run_id)` to populate `documentTitle` |
| `services/classification/llm_classifier.py` | Split prompt constant; always append `_REQUIRED_FORMAT` |
