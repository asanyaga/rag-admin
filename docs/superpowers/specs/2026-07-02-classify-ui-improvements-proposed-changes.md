# Proposed Changes: Classify UI Improvements

**Date:** 2026-07-02  
**Status:** Awaiting review

---

## Overview

Two deliverables: improvements to the **classify results display** (`ClassificationRunDetailPage`) and the **new classification run form** (`NewClassificationRunPage`). A third item (full run details with LLM request/response traces) is explicitly out of scope.

---

## Deliverable A — Classify Results Display

### A1: Document Name in Header

**Current:** header shows `status | model_summary | time_ago | labels/regions/duration | Re-run`

**Proposed:** add the document name prominently in the header:

```
← Back   [status]  My Document.pdf  ollama_local / qwen2.5:7b  2 hours ago  3 labels  12 regions  4.2s  [Re-run]
```

**Implementation:** the `ClassificationRunResponse` already has `documentId` but not the title. The backend will join with the `documents` table and add a `documentTitle: str` field to the response. No extra frontend fetch needed.

---

### A2: Run Config Parameters in Right Panel

**Current:** right panel shows only the results viewer (no config summary).

**Proposed:** a collapsible "Run config" section at the top of the right panel, collapsed by default (expandable with a chevron). Split into two conceptual groups:

**Classification run parameters:**
- Labels (rendered as badges)
- Classifier type (e.g., "LLM")
- Batch size / Batch overlap (e.g., 10 / 3)

**LLM classification parameters** *(only shown when `classifierType === 'llm'`)*:
- Provider / Model
- Temperature
- System prompt (truncated to ~2 lines; click to expand full text)

This respects the conceptual separation: LLM config belongs to the LLM classification strategy, not the classification run itself.

---

### A3: Right Panel Hierarchy: Label → Page → Block

**Current structure (flat blocks under label):**
```
▼ Introduction  [8 blocks]                Pages 1–4
    [p.1] paragraph  "This report covers..."
    [p.1] heading    "Executive Summary"
    [p.2] paragraph  "The findings show..."
    ...
```

**Proposed structure (blocks grouped by page):**
```
▼ Introduction  [8 blocks]                Pages 1–4
  ▼ Page 1  [3 blocks]
      paragraph  "This report covers..."
      heading    "Executive Summary"
      paragraph  "Background context..."
  ▼ Page 2  [2 blocks]
      paragraph  "The findings show..."
      table      "Figure 1: Results"
  ...
```

Changes:
- `ClassificationLabelSection` groups its blocks by `pageIndex` before rendering
- New `ClassificationPageGroup` component: collapsible row showing page number + block count; expands to show blocks
- `ClassificationBlockRow` drops the `p.N` page badge (now redundant since it lives in the group header); keeps the role badge and text
- Page groups default to open (consistent with current label section default)

---

## Deliverable B — New Classification Run Form

### B1: Batch Settings Move to Classification Card

**Current:** the "LLM configuration" card contains provider, model, temperature, system prompt **and** batch size / batch overlap.

**Proposed:** batch size and batch overlap move to the "Classification" card (they are classification run parameters, not LLM parameters). The "LLM configuration" card becomes strictly provider / model / temperature / system prompt.

```
┌─ Classification ──────────────────────────────┐
│  Labels: [Introduction] [Methodology] [+]     │
│  Classifier: LLM ▼                            │
│  Batch size: 10    Batch overlap: 3           │  ← moved here
└───────────────────────────────────────────────┘

┌─ LLM configuration ───────────────────────────┐  (only when classifierType=llm)
│  System prompt  [editable portion]            │
│  ─────────────────────────────────────────── │
│  Required format (read-only)                  │
│  Provider: ollama_local ▼   Model: qwen2.5:7b │
│  Temperature: 0.0 ────────────────────────    │
└───────────────────────────────────────────────┘
```

---

### B2: System Prompt — Editable + Read-Only Split

**Current:** a single textarea with placeholder "Leave empty to use the default system prompt…" — the default prompt is never shown to the user.

**Proposed:** replace with a `ClassificationSystemPromptEditor` component that shows the prompt in two clearly separated sections:

**Section 1 — Editable instructions** (textarea):
- Defaults to the instructional portion of the backend's `_DEFAULT_SYSTEM_PROMPT`:
  ```
  You are a document classifier. Analyze the document pages provided
  and determine which labels apply to each page.
  
  For each label, classify each page as:
  - "start": this page begins a section matching this label
  - "continue": this page continues a section from a previous page
  - "none": this page does not contain this label
  ```
- User can freely edit this. An "Reset to default" link restores the above text.

**Section 2 — Required output format** (read-only code block, visually distinct):
- Labelled "Required by app · read-only":
  ```
  Return ONLY valid JSON in this exact format:
  {
    "pages": [
      {"page": <page_index>, "labels": {"<label>": "start"|"continue"|"none", ...}},
      ...
    ]
  }
  
  Include every page index present in the document content.
  ```
- The app parses this JSON structure from the LLM response; changing it would break classification.

**Data model approach:**  
The `system_prompt` field stored in `classifierConfig.llm_config` will contain **only the editable instruction portion** (or `null` for default). The backend LLM classifier always appends the required format section before sending to the LLM. This means:
- Stored `system_prompt` is clean and only captures what the user customised
- Re-runs restore the editable portion correctly without needing to parse a concatenated string
- The format constraint lives in one place (the backend) and cannot be accidentally omitted
- **Backend change required:** split `_DEFAULT_SYSTEM_PROMPT` into `_DEFAULT_INSTRUCTION` + `_REQUIRED_FORMAT`; always append `_REQUIRED_FORMAT` when calling the LLM

---

## Out of Scope

- **Full run details (LLM request/response traces):** showing the raw LLM messages sent per batch, full token-level inputs/outputs, and reasoning chains is not implemented and not part of this workstream.

---

## Summary of Changes by File

| Area | File(s) | Change |
|------|---------|--------|
| Results — header | `ClassificationRunDetailPage.tsx` | Add document name |
| Results — right panel | `ClassificationRunDetailPage.tsx` | Add collapsible run config section |
| Results — right panel | `ClassificationResultsViewer.tsx` | Pass through to section |
| Results — right panel | `ClassificationLabelSection.tsx` | Group blocks by page |
| Results — right panel | `ClassificationPageGroup.tsx` *(new)* | Page-level collapsible group |
| Results — right panel | `ClassificationBlockRow.tsx` | Remove page badge |
| New run — form | `NewClassificationRunPage.tsx` | Move batch settings to classification card |
| New run — system prompt | `ClassificationSystemPromptEditor.tsx` *(new)* | Editable + read-only split prompt UI |
| New run — form | `NewClassificationRunPage.tsx` | Use new prompt editor |
| Backend — response | `classification.py` (schema) | Add `documentTitle` to response |
| Backend — repository | `classification_run_repository.py` | Join documents table in `get()` |
| Backend — classifier | `llm_classifier.py` | Split default prompt; append format section always |
