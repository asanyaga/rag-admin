# Design Spec: Classify UI Improvements

**Date:** 2026-07-02  
**Status:** Awaiting user review  
**Related:** `docs/superpowers/specs/2026-07-02-classify-ui-improvements-proposed-changes.md`

---

## Scope

Two screens receive changes:

1. **Classify results display** (`ClassificationRunDetailPage`) — three improvements
2. **New classification run form** (`NewClassificationRunPage`) — two improvements

Out of scope: full run detail traces (LLM request/response per batch), persistent prompt templates, `PromptConfigEditor` refactors.

---

## A — Classify Results Display

### A1: Document Name in Header

**Goal:** make it immediately clear which document this run is for.

**Change:** add the document name in the page header after the status badge.

```
← Back  [completed]  My Document.pdf  ollama_local/qwen2.5:7b  2h ago  3 labels  12 regions  4.2s  [Re-run]
```

**Frontend-only approach — no backend schema change.**  
Document title is passed as `location.state.documentTitle` when navigating to `/classify/{runId}`. The detail page reads it from state: `(location.state as { documentTitle?: string } | null)?.documentTitle`. When a run is opened from `ClassificationRunHistory`, the history component passes the document name in the navigation state. Direct URL access shows no title (graceful degradation; acceptable for a technical audience).

`ClassificationRunHistory` already receives a `documentTitle` or has access to the document context — the navigation call adds `{ state: { documentTitle } }`.

---

### A2: Run Config Summary — Collapsible Section in Right Panel

**Goal:** let the user inspect what config was used without cluttering the results view.

**Placement:** collapsible section at the top of the right panel (`w-80`), above `ClassificationResultsViewer`. Collapsed by default.

**Trigger:** a single row `▶ Run config` (`ChevronRight` / `ChevronDown`). Clicking expands inline.

**Expanded content — two groups:**

**Classification run**
| Field | Example |
|-------|---------|
| Classifier | LLM |
| Labels | `[Introduction]` `[Methodology]` `[Conclusion]` |
| Batch size / Overlap | 10 / 3 pages |

**LLM classification** *(only when `classifierType === 'llm'`)*
| Field | Example |
|-------|---------|
| Provider / Model | `ollama_local / qwen2.5:7b` |
| Temperature | 0.0 |
| System prompt | First ~2 lines, truncated; "Show full" link expands inline |

Labels are `Badge variant="secondary"` chips. System prompt expansion is inline via `Collapsible`.

**Component:** `ClassificationRunConfigPanel` (new, `components/classification/ClassificationRunConfigPanel.tsx`). Receives the full `ClassificationRun` as its only prop.

---

### A3: Right Panel Hierarchy — Label → Page → Block

**Goal:** the page level is the primary unit of interest for classification results; blocks are secondary detail.

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

Clicking a page row expands it to reveal blocks:
```
▼ Introduction  [8 blocks]  Pages 1–4
  ▼ Page 1  [3 blocks]
      paragraph  "This report covers..."
      heading    "Executive Summary"
      paragraph  "Background context..."
  ▶ Page 2  [2 blocks]
```

**Default states:**
- Label sections: **open** (unchanged)
- Page groups: **closed** — user sees pages at a glance and drills in on demand

**Component changes:**

`ClassificationLabelSection` — groups its `blocks` by `pageIndex` (ascending) before rendering; replaces `blocks.map(ClassificationBlockRow)` with `pageGroups.map(ClassificationPageGroup)`.

`ClassificationPageGroup` *(new, `components/classification/ClassificationPageGroup.tsx`)* — collapsible row:
- Header: `▶ Page N  [k blocks]` using `ChevronRight`/`ChevronDown` and a secondary badge for count
- **Closed by default** (`useState(false)`)
- Expands to render `ClassificationBlockRow` for each block
- Passes through `selectedBlockId` and `onBlockSelect`

`ClassificationBlockRow` — remove the `p.N` page badge (redundant now). Keep role badge and text.

---

## B — New Classification Run Form

### B1: Batch Settings Move to Classification Card

**Goal:** "LLM configuration" card contains only LLM concerns; batch settings are classification run parameters.

**Before — "LLM configuration" card:** system prompt, provider/model, temperature, batch size/overlap (collapsible).

**After — "Classification" card gains:** batch size and batch overlap shown as a two-field row below the classifier selector, visible when `classifierType === 'llm'`. No longer collapsible (they are first-class parameters).

**After — "LLM configuration" card contains:** system prompt area (see B2) + `PromptConfigEditor` for provider/model/temperature/thinking.

---

### B2: System Prompt — Full Prompt Visibility with Required Section

**Goal:** surface the complete prompt that goes to the LLM. The editable instruction portion and the required output format are shown together. The required portion is visually marked as app-controlled and not editable.

**Approach:** `PromptConfigEditor` is used **unchanged** for all LLM config fields (system prompt textarea, provider, model, temperature, thinking, advanced). The system prompt textarea in `PromptConfigEditor` is pre-populated with the **instruction portion** of the default prompt (fetched from the backend).

A **read-only format section** is rendered below `PromptConfigEditor` in the LLM config card — outside the component. It shows the required output format with a clear label, explaining what the app always expects:

```
┌─ LLM configuration ───────────────────────────────────────────┐
│                                                               │
│  System Prompt                                                │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ You are a document classifier. Analyze the document   │   │  ← PromptConfigEditor
│  │ pages provided and determine which labels apply...    │   │     (unchanged)
│  │ For each label, classify each page as:                │   │
│  │ - "start": this page begins a section...              │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
│  Provider: ollama_local ▼    Model: qwen2.5:7b               │
│  Temperature: 0.0 ─────────────────────────────────────      │
│  Thinking / Reasoning  ○                                     │
│  ▸ Advanced                                                   │
│                                                               │
│  ─────────────────────────────────────────────────────────   │  ← separator
│                                                               │
│  Required output format · always appended by the app         │  ← new read-only
│  ┌───────────────────────────────────────────────────────┐   │     section, outside
│  │ Return ONLY valid JSON in this exact format:          │   │     PromptConfigEditor
│  │ {                                                     │   │
│  │   "pages": [                                          │   │
│  │     {"page": <page_index>, "labels": {               │   │
│  │       "<label>": "start"|"continue"|"none", ...}}    │   │
│  │   ]                                                   │   │
│  │ }                                                     │   │
│  │ Include every page index present in the document.     │   │
│  └───────────────────────────────────────────────────────┘   │
│  ⓘ The app parses this JSON to build classification regions. │
└───────────────────────────────────────────────────────────────┘
```

The read-only section uses a `bg-muted` code block (`<pre>`) with `cursor-default select-text`. Its label and the info note below it make it clear this is generated by the app.

**What `PromptConfigEditor` receives for system prompt:** the instruction portion only (`value.systemPrompt`). When the user hasn't changed it, this is pre-populated with `_DEFAULT_INSTRUCTION` text fetched from the backend (not left as an empty placeholder). When submitting, `promptConfig.systemPrompt` carries the instruction text (or is `undefined` if the user cleared it back to empty).

**Backend changes (two):**

**1. New endpoint — expose prompt constants:**
```
GET /api/classification/system-prompt-config
→ { "instruction": "...", "required_format": "..." }
```
Frontend fetches this once on mount of `NewClassificationRunPage` to populate the system prompt textarea default and render the read-only section.

**2. `llm_classifier.py` — always append required format:**

Split `_DEFAULT_SYSTEM_PROMPT`:
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

Constructor logic:
```python
# system_prompt here is the instruction portion only
if system_prompt:
    self.system_prompt = system_prompt + "\n\n" + _REQUIRED_FORMAT
else:
    self.system_prompt = _DEFAULT_SYSTEM_PROMPT   # backward compatible with existing runs (null)
```

Existing runs with `system_prompt = null` continue to use the full default unchanged.

---

## Component / File Summary

| Component | File | Type |
|-----------|------|------|
| `ClassificationRunConfigPanel` | `components/classification/ClassificationRunConfigPanel.tsx` | New |
| `ClassificationPageGroup` | `components/classification/ClassificationPageGroup.tsx` | New |
| `ClassificationRunDetailPage` | `pages/ClassificationRunDetailPage.tsx` | Modified |
| `ClassificationRunHistory` | `components/classification/ClassificationRunHistory.tsx` | Modified (pass doc title in nav state) |
| `ClassificationLabelSection` | `components/classification/ClassificationLabelSection.tsx` | Modified |
| `ClassificationBlockRow` | `components/classification/ClassificationBlockRow.tsx` | Modified |
| `NewClassificationRunPage` | `pages/NewClassificationRunPage.tsx` | Modified |
| `PromptConfigEditor` | `components/shared/PromptConfigEditor.tsx` | **Unchanged** |

| Backend File | Change |
|-------------|--------|
| `routers/classification.py` | Add `GET /classification/system-prompt-config` endpoint |
| `services/classification/llm_classifier.py` | Split prompt constant; append `_REQUIRED_FORMAT` when custom instruction provided |
