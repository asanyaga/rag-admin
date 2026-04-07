# Extraction Evaluation — Feature Spec

## RAG Admin Feature: Extraction Eval

**Status:** Draft
**Author:** Asa
**Date:** 2026-03-19
**Parent spec:** `spec-intelligent-parsing-v4.md` (Sections 5–9, Tasks 5/6/8/9)
**Scope:** Ground truth management + evaluation engine + labeling UI + eval dashboard

---

## 1. Problem Statement

RAG Admin can now extract structured data from documents (via LlamaExtract), but there is no way to measure extraction quality. Without ground truth and automated scoring, we cannot:

- Know if extraction results are correct before using them downstream
- Compare extraction methods (LLM vs vendor-bundled) or configurations
- Detect regressions when schemas or parsers change
- Quantify improvement from better parsing (e.g., agentic vs fast tier)

### What This Feature Delivers

1. **Ground truth sets** — collections of documents with human-labeled expected extraction output
2. **Evaluation engine** — automated scoring of extraction results against ground truth (field-level + line items)
3. **Ground truth labeling UI** — document preview + structured editor for creating/editing ground truth
4. **Evaluation dashboard** — aggregate and per-document scoring with field-level breakdown

---

## 2. Conceptual Model

```
ExtractionSchema (user-defined, already exists)
    │
    ├── ExtractionGroundTruthSet (collection scoped to a schema)
    │       │
    │       └── ExtractionGroundTruthItem (per-document expected output)
    │               document_id → documents.id
    │               expected_data: { "vendor_name": "Naivas", "total": 175.00, ... }
    │
    ├── ExtractionResult (already exists — actual extraction output)
    │       document_id → documents.id
    │       structured_data: { "vendor_name": "Naivas Ltd", "total": 175.00, ... }
    │
    └── ExtractionEvalRun (compares results against ground truth)
            │
            └── ExtractionEvalResult (per-document scoring)
                    field_scores: { "vendor_name": { "exact": false, "fuzzy": 0.88 }, ... }
                    line_items_score: { "precision": 0.8, "recall": 1.0, "f1": 0.89 }
                    overall_score: 0.82
```

### Key Relationships

- A **ground truth set** is scoped to one `ExtractionSchema` and one `Project`
- A **ground truth item** pairs a document with its expected structured output for that schema
- An **eval run** takes a ground truth set and a set of extraction results, scores each document, and aggregates
- An **eval result** stores per-document and per-field scoring

---

## 3. Database Schema (All Additive)

### 3.1 `extraction_ground_truth_sets` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects.id | CASCADE delete |
| extraction_schema_id | UUID FK → extraction_schemas.id | CASCADE delete |
| name | String(255) | e.g., "Kenyan Receipts v1" |
| description | Text | Optional |
| created_by | UUID FK → users.id | |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

Index: `(project_id)`, Unique: `(project_id, name)`

### 3.2 `extraction_ground_truth_items` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| ground_truth_set_id | UUID FK → extraction_ground_truth_sets.id | CASCADE delete |
| document_id | UUID FK → documents.id | CASCADE delete |
| expected_data | JSON | Expected structured output (matches schema) |
| annotations | JSON | `{ "quality": "clean", "difficulty": "easy", "language": "en", "notes": "..." }` |
| created_by | UUID FK → users.id | |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

Unique constraint: `(ground_truth_set_id, document_id)`

### 3.3 `extraction_eval_runs` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects.id | CASCADE delete |
| ground_truth_set_id | UUID FK → extraction_ground_truth_sets.id | CASCADE delete |
| name | String(255) | Auto-generated or user-provided |
| config | JSON | `{ "extraction_method": "vendor_bundled", "fuzzy_threshold": 85, "numeric_tolerance": 0.01 }` |
| status | Enum | pending / running / completed / failed |
| metrics | JSON | Aggregate scores (populated on completion) |
| error_message | Text | If failed |
| items_completed | Integer | Progress tracking |
| items_total | Integer | Total items to evaluate |
| created_by | UUID FK → users.id | |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

Index: `(project_id)`, `(ground_truth_set_id)`

### 3.4 `extraction_eval_results` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| eval_run_id | UUID FK → extraction_eval_runs.id | CASCADE delete |
| extraction_result_id | UUID FK → extraction_results.id | CASCADE delete |
| ground_truth_item_id | UUID FK → extraction_ground_truth_items.id | CASCADE delete |
| overall_score | Float | Weighted composite 0–1 |
| field_scores | JSON | Per-field: `{ "vendor_name": { "exact": true, "fuzzy_score": 1.0, "score": 1.0 } }` |
| line_items_score | JSON | `{ "precision": 0.8, "recall": 1.0, "f1": 0.89, "matched": 4, "predicted": 5, "expected": 4 }` |
| evaluation_metadata | JSON | Metric versions, weights used, timing |
| created_at | DateTime(tz) | |

Unique constraint: `(eval_run_id, ground_truth_item_id)`

---

## 4. Evaluation Engine (Pure Computation)

The engine scores `extraction_result.structured_data` against `ground_truth_item.expected_data`. It is a pure function with no DB or API dependencies.

### 4.1 Field-Level Metrics

| Metric | What It Measures | Implementation |
|--------|-----------------|----------------|
| **Exact match** | Field value identical? | `str(predicted).strip().lower() == str(expected).strip().lower()` |
| **Fuzzy match** | Close but not exact? | `rapidfuzz.fuzz.ratio(predicted, expected) / 100` — score 0–1 |
| **Numeric match** | Money amounts correct? | `abs(float(predicted) - float(expected)) <= tolerance` (default ±0.01) |
| **Date match** | Date correct? | Parse both to date, compare equality |
| **Null handling** | Missing vs present? | If both null → score 1.0; if one null → score 0.0 |

Each field gets a composite `score` (0–1) based on its type:
- String fields: fuzzy score (exact match = 1.0)
- Numeric fields: 1.0 if within tolerance, 0.0 otherwise
- Date fields: 1.0 if equal after normalization, 0.0 otherwise

### 4.2 Line Items F1 (Hungarian Algorithm)

For schemas with `line_items` arrays:

1. **Cost function** for each (predicted, expected) pair:
   ```
   cost = 0.6 * (1 - fuzz.ratio(pred.description, exp.description) / 100)
        + 0.4 * (0 if abs(pred.total - exp.total) <= 0.01 else 1)
   ```
2. Pairs with `cost > 0.5` are treated as unmatched
3. `scipy.optimize.linear_sum_assignment` on cost matrix → optimal assignment
4. F1 from matched/unmatched:
   - `precision = matched / predicted_count`
   - `recall = matched / expected_count`
   - `f1 = 2 * precision * recall / (precision + recall)`

### 4.3 Overall Document Score

Weighted composite (configurable in eval run config, defaults below):

| Component | Weight | Source |
|-----------|--------|--------|
| Field exact match rate | 30% | Fraction of fields with exact match |
| Field fuzzy score avg | 20% | Average fuzzy score across string fields |
| Numeric accuracy | 25% | Fraction of numeric fields within tolerance |
| Line items F1 | 25% | F1 from Hungarian matching (0 if no line_items in schema) |

When the schema has no `line_items`, weights redistribute: 40% exact, 25% fuzzy, 35% numeric.

### 4.4 Aggregate Metrics (Per Eval Run)

Stored in `extraction_eval_runs.metrics`:

```json
{
  "overall_score_mean": 0.82,
  "overall_score_median": 0.85,
  "field_accuracy": {
    "vendor_name": { "exact_match_rate": 0.80, "avg_fuzzy": 0.92 },
    "total": { "exact_match_rate": 0.93 },
    "date": { "exact_match_rate": 0.87 }
  },
  "line_items_f1_mean": 0.78,
  "documents_evaluated": 15,
  "documents_perfect": 8
}
```

---

## 5. API Endpoints

### 5.1 Ground Truth Sets

```
POST   /api/v1/projects/{project_id}/extraction-ground-truth-sets
       Body: { "extraction_schema_id": "uuid", "name": "...", "description": "..." }
       Returns: 201, GroundTruthSetResponse

GET    /api/v1/projects/{project_id}/extraction-ground-truth-sets
       Query: ?extraction_schema_id=uuid (optional filter)
       Returns: List of ground truth sets

GET    /api/v1/extraction-ground-truth-sets/{set_id}
       Returns: Set with item count, schema info

PUT    /api/v1/extraction-ground-truth-sets/{set_id}
       Body: { "name": "...", "description": "..." }

DELETE /api/v1/extraction-ground-truth-sets/{set_id}
```

### 5.2 Ground Truth Items

```
POST   /api/v1/extraction-ground-truth-sets/{set_id}/items
       Body: { "document_id": "uuid", "expected_data": {...}, "annotations": {...} }
       Returns: 201, GroundTruthItemResponse

POST   /api/v1/extraction-ground-truth-sets/{set_id}/items/bulk
       Body: { "items": [ { "document_id": "uuid", "expected_data": {...} }, ... ] }
       Returns: 201, { "created": N, "errors": [...] }

GET    /api/v1/extraction-ground-truth-sets/{set_id}/items
       Returns: List of items with document info

GET    /api/v1/extraction-ground-truth-items/{item_id}

PUT    /api/v1/extraction-ground-truth-items/{item_id}
       Body: { "expected_data": {...}, "annotations": {...} }

DELETE /api/v1/extraction-ground-truth-items/{item_id}
```

### 5.3 Extraction Eval Runs

```
POST   /api/v1/projects/{project_id}/extraction-eval-runs
       Body: {
         "ground_truth_set_id": "uuid",
         "name": "Receipt eval - agentic tier" (optional, auto-generated if omitted),
         "config": {
           "fuzzy_threshold": 85,
           "numeric_tolerance": 0.01,
           "weights": { "exact": 0.3, "fuzzy": 0.2, "numeric": 0.25, "line_items": 0.25 }
         }
       }
       Returns: 202 Accepted, { "eval_run_id": "uuid" }
       Note: The engine finds the most recent completed ExtractionResult for each
             (document_id, extraction_schema_id) pair in the ground truth set.

GET    /api/v1/projects/{project_id}/extraction-eval-runs
       Query: ?ground_truth_set_id=uuid (optional)
       Returns: List of eval runs with status and aggregate metrics

GET    /api/v1/extraction-eval-runs/{run_id}
       Returns: Full run with aggregate metrics

DELETE /api/v1/extraction-eval-runs/{run_id}
```

### 5.4 Extraction Eval Results

```
GET    /api/v1/extraction-eval-runs/{run_id}/results
       Query: ?sort_by=overall_score&order=asc (for finding worst performers)
       Returns: Per-document results with field scores

GET    /api/v1/extraction-eval-results/{result_id}
       Returns: Full result with field-level breakdown
```

---

## 6. Frontend

### 6.1 Ground Truth Labeling Page

**Route:** `/projects/:projectId/extraction-ground-truth`

**Set list view:**
- Table of ground truth sets: name, schema, item count, created date
- Create button → dialog: select schema, enter name/description
- Click set → set detail

**Set detail view:**
- Header: set name, schema name, item count
- Documents table: document title, labeling status (labeled/unlabeled), last updated
- Add documents button → select from project documents
- Click document row → labeling editor

**Labeling editor (two-panel layout):**
```
┌─────────────────────────────┬──────────────────────────────┐
│  Document Preview            │  Expected Output Editor       │
│                              │                               │
│  [PDF/Image viewer]          │  Schema: Receipt v1           │
│  or                          │                               │
│  [Extracted text]            │  vendor_name: [Naivas     ]   │
│                              │  date:        [2025-11-15 ]   │
│                              │  total:       [175.00     ]   │
│                              │  payment:     [M-Pesa     ]   │
│                              │                               │
│                              │  Line Items:                  │
│                              │  ┌─────────────────────────┐  │
│                              │  │ Bread White 400g  65.00 │  │
│                              │  │ [+ Add line item]       │  │
│                              │  └─────────────────────────┘  │
│                              │                               │
│                              │  Annotations:                 │
│                              │  Quality: [clean ▼]           │
│                              │  Difficulty: [easy ▼]         │
│                              │  Notes: [                  ]  │
│                              │                               │
│                              │  [Save] [← Prev] [Next →]    │
└─────────────────────────────┴──────────────────────────────┘
```

**Implementation:**
- Left panel: reuse existing document preview (extracted text viewer or PDF embed)
- Right panel: dynamic form generated from ExtractionSchema fields
  - String fields → text input
  - Number fields → number input
  - Date fields → date picker
  - Array fields (line_items) → repeatable row group with add/remove
- JSON toggle: switch between form editor and raw JSON editor
- Navigation: prev/next buttons to move through documents in the set
- Auto-save or explicit save with validation against schema

### 6.2 Evaluation Dashboard Page

**Route:** `/projects/:projectId/extraction-evaluation`

**Run creation panel:**
- Select ground truth set (dropdown)
- Optional: custom name, config overrides (fuzzy threshold, weights)
- "Run Evaluation" button → POST, then poll for completion

**Aggregate metrics cards:**
```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Overall Score│ │ Field Match  │ │ Line Items   │ │ Documents    │
│    0.82      │ │    87%       │ │  F1: 0.78    │ │  15 / 15     │
│              │ │              │ │              │ │  8 perfect   │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

**Per-field accuracy breakdown:**
- Bar chart or table showing accuracy per field (vendor_name: 80%, total: 93%, date: 87%)
- Color-coded: green ≥90%, yellow ≥70%, red <70%

**Per-document results table:**
```
┌──────────────────────────┬───────┬─────────┬──────────┬──────────┐
│ Document                 │ Score │ Fields  │ Line F1  │ Status   │
├──────────────────────────┼───────┼─────────┼──────────┼──────────┤
│ receipt-naivas.pdf       │ 0.95  │ 4/4     │ 1.00     │ ✓        │
│ receipt-carrefour.pdf    │ 0.72  │ 3/4     │ 0.67     │ ⚠        │
│ receipt-java-house.pdf   │ 0.45  │ 2/4     │ 0.33     │ ✗        │
└──────────────────────────┴───────┴─────────┴──────────┴──────────┘
```

**Row expansion → field-level breakdown:**
```
  vendor_name:  Expected "Naivas Supermarket"  Got "Naivas Ltd"     fuzzy: 0.76  ✗
  date:         Expected "2025-11-15"          Got "2025-11-15"     exact: ✓
  total:        Expected 175.00                Got 175.00           exact: ✓
  payment:      Expected "M-Pesa"              Got "Mpesa"          fuzzy: 0.91  ✓
```

**Eval run history:**
- List of past runs with date, score, ground truth set used
- Click to view full results

### 6.3 Navigation

Add to sidebar under Extraction section:
```
Extraction
  ├── Schemas        (existing)
  ├── Ground Truth   (new)
  └── Evaluation     (new)
```

---

## 7. Implementation Tasks

### Task 1: Database Models + Migration (~2h)

**Files to create:**
```
backend/app/models/extraction_ground_truth.py    # ExtractionGroundTruthSet + ExtractionGroundTruthItem
backend/app/models/extraction_eval.py            # ExtractionEvalRun + ExtractionEvalResult
backend/alembic/versions/XXXXX_add_extraction_eval_tables.py
```

**Files to modify:**
```
backend/app/models/__init__.py                   # Register new models
```

Follow patterns from: `models/golden_set.py`, `models/eval_run.py`

### Task 2: Ground Truth Repository + Service + API (~3h)

**Files to create:**
```
backend/app/repositories/extraction_ground_truth_repository.py
backend/app/services/extraction_ground_truth_service.py
backend/app/routers/extraction_ground_truth.py
backend/app/schemas/extraction_ground_truth.py   # Pydantic request/response schemas
```

Follow patterns from: `repositories/golden_set_repository.py`, `services/golden_set_service.py`, `routers/golden_sets.py`

### Task 3: Evaluation Engine (Pure Computation) (~3h)

**Files to create:**
```
backend/app/services/extraction_eval/__init__.py
backend/app/services/extraction_eval/engine.py           # score_document(), score_field(), score_line_items()
backend/app/services/extraction_eval/field_matchers.py   # exact_match, fuzzy_match, numeric_match, date_match
backend/app/services/extraction_eval/line_item_matcher.py # Hungarian algorithm matching
```

**Dependencies to add:** `rapidfuzz`, `scipy`

**Unit tests:** `backend/tests/services/test_extraction_eval_engine.py` — test scoring with known inputs/outputs

### Task 4: Eval Run Repository + Service + API (~3h)

**Files to create:**
```
backend/app/repositories/extraction_eval_repository.py
backend/app/services/extraction_eval/service.py          # Orchestrate eval runs, background task
backend/app/routers/extraction_eval.py
backend/app/schemas/extraction_eval.py                   # Pydantic request/response schemas
```

**Files to modify:**
```
backend/app/main.py                                      # Register new routers
```

### Task 5: Frontend — Ground Truth Labeling UI (~4h)

**Files to create:**
```
frontend/src/types/extractionGroundTruth.ts
frontend/src/api/extractionGroundTruth.ts
frontend/src/hooks/useExtractionGroundTruth.ts
frontend/src/pages/ExtractionGroundTruthPage.tsx
frontend/src/components/extraction-ground-truth/GroundTruthSetList.tsx
frontend/src/components/extraction-ground-truth/GroundTruthSetDetail.tsx
frontend/src/components/extraction-ground-truth/GroundTruthEditor.tsx
frontend/src/components/extraction-ground-truth/DynamicFieldForm.tsx  # Schema-driven form
```

### Task 6: Frontend — Evaluation Dashboard (~3h)

**Files to create:**
```
frontend/src/types/extractionEval.ts
frontend/src/api/extractionEval.ts
frontend/src/hooks/useExtractionEval.ts
frontend/src/pages/ExtractionEvaluationPage.tsx
frontend/src/components/extraction-eval/EvalRunConfig.tsx
frontend/src/components/extraction-eval/AggregateMetrics.tsx
frontend/src/components/extraction-eval/DocumentResultsTable.tsx
frontend/src/components/extraction-eval/FieldBreakdownView.tsx
```

**Files to modify:**
```
frontend/src/config/navigation.ts                        # Add Ground Truth + Evaluation nav items
frontend/src/App.tsx                                     # Add routes
```

---

## 8. What This Spec Does NOT Change

| Existing Component | Status |
|--------------------|--------|
| `extraction_schemas` table + CRUD | **Unchanged** |
| `extraction_results` table + service | **Unchanged** (eval reads these, doesn't modify) |
| `ExtractionSchema` model | **Unchanged** |
| `ExtractionResult` model | **Unchanged** |
| Existing retrieval eval (`golden_sets`, `eval_runs`) | **Unchanged** |
| Document upload/parsing pipeline | **Unchanged** |

---

## 9. Dependencies

**Backend (new):**
- `rapidfuzz` — fuzzy string matching for field comparison
- `scipy` — `linear_sum_assignment` for Hungarian algorithm line item matching

**Frontend (new):**
- No new dependencies expected (shadcn/ui components sufficient)

---

## 10. Initial Ground Truth: Kenyan Receipts

Start with 15 Kenyan receipts using the existing receipt schema. Ground truth created via bulk API import, then verified/edited in the labeling UI.

Receipt categories: supermarket (Naivas, Carrefour), restaurant (Java House), fuel station, pharmacy, hardware store.

Annotations include: quality (clean/faded/crumpled), difficulty (easy/medium/hard), is_scanned, language.

---

## 11. Definition of Done

- [ ] Ground truth CRUD API working (sets + items, including bulk import)
- [ ] Evaluation engine computing field-level + line-item metrics correctly
- [ ] Eval run API: create, execute in background, return aggregate + per-document results
- [ ] Ground truth labeling UI: two-panel editor with schema-driven form
- [ ] Evaluation dashboard: aggregate cards, per-field breakdown, per-document table with row expansion
- [ ] Navigation updated with Ground Truth + Evaluation entries
- [ ] 15 Kenyan receipts labeled and first eval run completed
- [ ] Unit tests for evaluation engine (field matchers + line item matching)
