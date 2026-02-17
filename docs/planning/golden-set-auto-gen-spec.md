# RAG Admin — Automatic Golden Set Generation

**Feature Specification: Product Requirements + Technical Reference**

| | |
|---|---|
| Status | Draft |
| Version | 1.0 |
| Date | February 2025 |
| Scope | Retrieval evaluation golden set auto-generation |
| Depends on | Project, Document, Index features |
| Anticipates | Answer evaluation (Phase 2) |

---

## 1. Overview

This specification defines how RAG Admin automatically generates golden sets for retrieval evaluation. A golden set contains query-relevance pairs that serve as ground truth: for each query, which document pages contain the answer. Auto-generation uses an LLM to read project documents and produce these pairs, which the user then reviews and curates before saving.

The feature addresses a key adoption barrier: manually creating golden sets is tedious, requires domain expertise, and discourages iterative evaluation. Auto-generation bootstraps a starting dataset that users refine, accelerating the path from document upload to measurable retrieval quality.

> **🔮 Answer Evaluation Consideration**
>
> The golden set data model, generation prompts, and review workflow are designed to accommodate answer evaluation in Phase 2. Where this influences a design decision, it is called out in a box like this one. The goal is to avoid rework while keeping the retrieval scope simple and self-contained.

---

## 2. Goals and Non-Goals

### 2.1 Goals

- Enable users to generate an initial golden set from project documents in under 2 minutes
- Provide a review-and-curate workflow that ensures human validation of every entry
- Support configurable generation (documents, queries per doc, question types, LLM provider)
- Produce golden sets at page-level granularity that work across indexes for cross-index comparison
- Design data models that extend naturally to answer evaluation without schema migration

### 2.2 Non-Goals (This Phase)

- Generating reference answers (Phase 2 — answer evaluation)
- Graded relevance scoring (binary relevant/not-relevant is sufficient for now)
- Auto-evaluation of generated quality (user review is the quality gate)
- Chunk-level golden sets (page-level is the target granularity)
- Import from external evaluation frameworks (RAGAS, LlamaIndex datasets)

---

## 3. Data Model

The data model is the foundation that must get right. It needs to support retrieval evaluation now and answer evaluation later without migration.

### 3.1 Golden Set

| Field | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| project_id | UUID (FK) | Owning project. Golden sets are project-scoped, not index-scoped. |
| name | string | User-provided name |
| description | string (nullable) | Optional description of dataset purpose |
| created_by | UUID (FK) | User who created the set |
| generation_config | JSONB (nullable) | Snapshot of auto-gen config if applicable (see 3.3) |
| status | enum | `draft` \| `ready` \| `archived` |
| created_at / updated_at | timestamp | Standard audit fields |

### 3.2 Golden Set Entry

| Field | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| golden_set_id | UUID (FK) | Parent golden set |
| query | text | The evaluation query |
| relevant_sources | JSONB | Array of `{doc_id, source_ref: {type, value}}` |
| source_method | enum | `manual` \| `auto_generated` \| `imported` |
| review_status | enum | `pending` \| `accepted` \| `rejected` \| `edited` |
| **reference_answer** (nullable) | text (nullable) | **Phase 2:** Expected answer text. Null for retrieval-only entries. |
| **answer_metadata** (nullable) | JSONB (nullable) | **Phase 2:** Evaluation criteria, rubric, key claims to verify. |
| created_at / updated_at | timestamp | Standard audit fields |

> **⚠️ Why relevant_sources uses source_ref**
>
> The source_ref structure `{type: "page", value: "45"}` is extensible to other document types without schema changes. For PDFs (our current scope), type is always `"page"`. Future types include `"section"`, `"line_range"`, `"timestamp"`. See the data source mapping table in the project documentation.

**relevant_sources JSONB structure:**

```json
[
  { "doc_id": "uuid", "source_ref": { "type": "page", "value": "45" } },
  { "doc_id": "uuid", "source_ref": { "type": "page", "value": "23" } }
]
```

> **🔮 Answer Eval: reference_answer and answer_metadata**
>
> These nullable fields cost nothing now but avoid a migration later. When answer evaluation is added, the same golden set entry gains a reference_answer column. answer_metadata supports structured rubrics: key claims that must appear, required specificity level, acceptable answer formats. This means a single golden set can serve both retrieval and answer evaluation.

### 3.3 Generation Config (JSONB)

Stored on the golden set as an immutable snapshot of how it was generated. Enables reproducibility and serves as audit trail.

| Field | Type | Description |
|---|---|---|
| document_ids | UUID[] | Which project documents were used |
| llm_provider | string | Provider identifier (e.g., `anthropic`, `openai`, `ollama`) |
| llm_model | string | Model identifier (e.g., `claude-sonnet-4-20250514`) |
| queries_per_document | integer | Target queries per document |
| question_types | string[] | `factual` \| `comparison` \| `summarization` |
| **generate_reference_answers** (future) | boolean | **Phase 2:** Whether to also generate reference answers |
| temperature | float | LLM temperature used |
| prompt_version | string | Version tag for the generation prompt template |

---

## 4. Generation Pipeline

The generation pipeline processes documents through the configured LLM to produce query-relevance pairs. Processing is asynchronous, consistent with how document indexing already works in RAG Admin.

### 4.1 Pipeline Steps

| Step | Action | Details |
|---|---|---|
| 1. Validate | Pre-flight checks | Verify selected documents exist, have page metadata, user has valid API key for chosen provider |
| 2. Extract | Build page context | For each selected document, extract text content per page. Group into page windows (see 4.2). |
| 3. Generate | LLM call per window | Send page content + generation prompt to LLM. Parse structured response. |
| 4. Deduplicate | Remove near-duplicates | Compare generated queries using embedding similarity. Flag pairs above 0.92 cosine threshold. |
| 5. Store | Persist with pending status | Save all entries with review_status = `pending`. Trigger notification to user. |

### 4.2 Page Windowing Strategy

Sending entire documents to the LLM in a single call wastes context and produces lower-quality questions. Instead, the pipeline processes documents in overlapping page windows.

- **Window size:** 5 pages (configurable). Balances context richness against generation focus.
- **Overlap:** 1 page. Prevents questions about content split across window boundaries.
- **Example:** 86-page document with 5-page windows and 1-page overlap = 22 windows.

Each window produces queries that reference specific pages within that window. The LLM must cite which page(s) within the window contain the answer.

> **⚠️ Why not send the full document?**
>
> Full-document prompts produce generic questions ("What is this document about?"). Page windows force the LLM to engage with specific content, producing more targeted queries that are actually useful for retrieval evaluation. This also controls cost — smaller inputs = fewer tokens = lower API spend per generation run.

### 4.3 Generation Prompt Design

The generation prompt is the most critical component. It must produce queries that are realistic (matching how users actually search), diverse (covering different question types), and precisely attributed (citing exact pages).

**Prompt template structure:**

- **System:** Role definition, output format specification (JSON), quality criteria
- **Context:** Document metadata (title, type) + page content for the current window
- **Task:** Generate N queries of specified types, with page-level attribution
- **Constraints:** Each query must be answerable from the provided pages. No questions requiring external knowledge. Each page citation must be justified.

**Required output format (per query):**

```json
{
  "query": "What was the year-over-year revenue growth in 2024?",
  "question_type": "factual",
  "relevant_pages": [45],
  "reasoning": "Page 45 contains the revenue comparison table for 2023-2025"
}
```

The `reasoning` field is not stored in the golden set but is displayed during the review workflow to help the user validate relevance attributions.

> **🔮 Answer Eval: Extending the Generation Prompt**
>
> When answer evaluation is added, the prompt gains additional output fields:
>
> ```json
> {
>   "reference_answer": "Revenue grew 22.6% YoY from $3.1B to $3.8B",
>   "key_claims": ["22.6% growth", "$3.1B to $3.8B", "year-over-year"]
> }
> ```
>
> The `key_claims` array feeds into faithfulness evaluation later. By versioning the prompt template (`prompt_version` in generation_config), existing golden sets are unaffected when the prompt evolves. Users can re-generate with the new prompt to add reference answers to an existing set.

---

## 5. Review and Curation Workflow

Every auto-generated entry must be reviewed before it becomes part of the active golden set. This is a deliberate design choice: the review process builds user intuition about what makes good evaluation queries and ensures the golden set reflects genuine information needs rather than LLM artifacts.

### 5.1 Review States

| State | Meaning | User Action |
|---|---|---|
| pending | Freshly generated, awaiting review | Must be accepted, edited, or rejected |
| accepted | Approved as-is for use in evaluation | Can be re-edited or rejected later |
| edited | Modified by user (query text or page attribution changed) | Tracked as user-modified for quality analysis |
| rejected | Not suitable for evaluation | Excluded from the active golden set. Retained for audit. |

### 5.2 Review UX Flow

- **Entry list with status filtering:** Cards showing Total / Accepted / Pending / Rejected counts, doubling as filter toggles
- **Per-entry actions:** Accept (checkmark), Edit (pencil), Reject (X). Inline editing for query text.
- **Page attribution editing:** Click to open the PDF viewer at the cited page. Add or remove page references.
- **Bulk actions:** Accept All Pending for fast approval. No bulk reject (intentional — rejections should be deliberate).
- **Save gate:** Cannot save until all entries are accepted, edited, or rejected. Pending count displayed prominently.

### 5.3 Quality Signals During Review

The review UI surfaces signals that help users identify low-quality entries:

- **LLM reasoning:** Displayed alongside each entry. If the reasoning is vague ("this page discusses the topic"), the query may be too generic.
- **Duplicate warning:** Entries flagged by the deduplication step (>0.92 cosine similarity) show a visual indicator and link to the similar entry.
- **Question type badge:** Helps users ensure coverage across factual, comparison, and summarization types.
- **Page count heuristic:** Entries citing many pages (>3) may indicate overly broad questions. Highlighted for attention.

---

## 6. Architecture and Integration

### 6.1 System Flow

The generation pipeline integrates with existing RAG Admin infrastructure:

| Component | Role | Existing / New |
|---|---|---|
| LLM Abstraction Layer | Route generation requests to configured provider (Anthropic, OpenAI, Ollama) | Existing — reuse BYOK provider layer |
| Document Store | Provide page-level text extraction for generation context | Existing — requires page text access |
| Async Task Runner | Execute generation pipeline as background task with progress tracking | Existing — reuse document processing infrastructure |
| Golden Set Service | Orchestrate generation, deduplication, storage, and review state machine | **New** — core business logic for this feature |
| Embedding Service | Compute query embeddings for deduplication similarity check | Existing — reuse index embedding pipeline |
| Evaluation Engine | Consume golden sets to run retrieval evaluations against indexes | **New** — but separate from generation |

### 6.2 API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/projects/{id}/golden-sets` | Create golden set (manual, import, or auto-generate) |
| POST | `/projects/{id}/golden-sets/generate` | Trigger auto-generation (returns task_id) |
| GET | `/tasks/{task_id}` | Poll generation progress (reuse existing task infrastructure) |
| GET | `/golden-sets/{id}/entries` | List entries with status filter, pagination |
| PATCH | `/golden-sets/{id}/entries/{entry_id}` | Update entry (review status, query text, page attribution) |
| POST | `/golden-sets/{id}/entries/bulk-accept` | Accept all pending entries |
| POST | `/golden-sets/{id}/entries` | Add manual entry to existing golden set |
| POST | `/golden-sets/{id}/import` | Import entries from CSV/JSON |
| DELETE | `/golden-sets/{id}/entries/{entry_id}` | Hard delete (only for rejected entries) |

### 6.3 Async Processing Model

Generation is an async task following the same pattern as document indexing:

- **Task creation:** POST /generate returns immediately with a task_id and 202 Accepted
- **Progress tracking:** GET /tasks/{id} returns status (`queued` | `processing` | `completed` | `failed`), progress percentage, and partial results count
- **Cancellation:** DELETE /tasks/{id} stops processing. Already-generated entries are preserved with pending status.
- **Error handling:** Per-window failures are logged but don't fail the entire task. Partial results are saved. Final status includes success/failure count per window.

> **⚠️ Rate Limiting Consideration**
>
> LLM API calls are rate-limited by provider. The generation pipeline must respect these limits. Implementation should use a simple sequential-with-delay approach rather than parallel calls. For a typical generation run (2 documents, 5 queries each, ~20 windows), this completes in 1-3 minutes, which is acceptable for the async model. The user sees progress updates as each window completes.

---

## 7. Answer Evaluation: Forward-Looking Design Decisions

This section documents specific architectural choices made in this spec that are influenced by the upcoming answer evaluation feature. These are not implementation requirements for the current phase but explain why certain abstractions exist.

### 7.1 Data Model Extensibility

| Decision | Rationale | Cost Now |
|---|---|---|
| `reference_answer` nullable column on golden_set_entry | Avoids ALTER TABLE migration when answer eval launches. A single golden set entry can serve both retrieval and answer evaluation. | Negligible — null column |
| `answer_metadata` JSONB nullable column | Supports structured evaluation criteria (key claims, rubrics, completeness checklist) without rigid schema | Negligible — null column |
| `generation_config` includes `generate_reference_answers` flag | Enables a single generation run to produce both queries and answers when answer eval is active | One boolean field |
| `prompt_version` in generation_config | Allows prompt evolution without invalidating existing golden sets. Users can re-generate with new prompts. | One string field |
| `source_method` tracks origin of each entry | When answer eval introduces LLM-generated reference answers, distinguishing auto vs. manual origins matters for quality calibration | Enum field |

### 7.2 Generation Pipeline Extensibility

The page-windowing generation pipeline is designed to extend naturally:

- **Same windows, richer output:** Answer generation uses the same page windows. The prompt simply requests additional output fields (reference_answer, key_claims). No pipeline restructuring needed.
- **Separate generation modes:** Users should be able to generate queries first (retrieval eval), validate retrieval quality, then generate reference answers for the validated queries. This two-phase workflow is more valuable than generating everything at once.
- **Backfill capability:** The API should support adding reference answers to existing golden set entries. This means answer generation is a PATCH operation on entries, not a new creation flow.

### 7.3 Review Workflow Extensibility

The review workflow expands for answer evaluation:

| Aspect | Retrieval Eval (Now) | Answer Eval (Phase 2) |
|---|---|---|
| What user reviews | Query + page attributions | Query + pages + reference answer + key claims |
| Quality signals | Reasoning, duplicates, page count | Answer completeness, claim specificity, answer length |
| Edit capabilities | Query text, page references | Query, pages, answer text, claims |
| Review required? | Yes — mandatory before save | Yes — same gate. Answer quality is more subjective, so review is even more important. |

### 7.4 Evaluation Engine Separation

A critical architectural boundary: the golden set generation service and the evaluation execution engine are separate services with a clean interface between them.

- **Generation service:** Produces golden sets. Knows about documents, LLMs, and page content.
- **Evaluation engine:** Consumes golden sets. Knows about indexes, retrieval, and metrics.
- **Interface:** The golden set is the contract. Generation produces it, evaluation consumes it.

This separation matters because answer evaluation introduces a third consumer: the answer generation and evaluation pipeline, which needs the golden set's queries and reference answers but not the retrieval results. Keeping the golden set as a standalone, well-defined data contract makes this clean.

---

## 8. Error Handling and Edge Cases

| Scenario | Handling |
|---|---|
| LLM returns malformed JSON | Retry once with stricter format instructions. If still malformed, skip window and log error. Report partial completion. |
| LLM cites pages outside the provided window | Filter out invalid page references. If no valid pages remain, discard the entry and log. |
| Document has no extractable text (scanned PDF without OCR) | Skip document with clear error message: "Document X has no extractable text. Run OCR first." |
| API key is invalid or rate-limited | Fail task immediately with clear error. Don't retry — user needs to fix their API key. |
| User cancels during generation | Save all entries generated so far with pending status. Mark task as cancelled. |
| Duplicate queries across windows (overlap produces same question) | Deduplication step catches these. Higher-similarity entry is auto-rejected with a note. |
| Very short documents (< 3 pages) | Use single window covering all pages. Adjust queries_per_document to match available content. |

---

## 9. Metrics and Observability

Track the following to understand feature usage and generation quality:

| Metric | Type | Purpose |
|---|---|---|
| generation_task_duration_seconds | Histogram | Pipeline performance. Alert if > 5 min for typical runs. |
| generation_entries_per_run | Histogram | Understanding typical golden set sizes |
| generation_entries_accepted_ratio | Gauge | Proxy for generation quality. If users reject > 50%, prompts need improvement. |
| generation_entries_edited_ratio | Gauge | Proxy for "almost right" quality. High edit rate suggests good concepts, wrong details. |
| generation_llm_errors_total | Counter | Provider reliability tracking |
| generation_dedup_filtered_total | Counter | How many duplicates the dedup step catches |
| review_time_to_complete_seconds | Histogram | How long users spend in review. Indicates UX friction. |

All metrics emit via OpenTelemetry, consistent with the existing observability approach. No backend-specific instrumentation.

---

## 10. Implementation Phases

### 10.1 Phase 1: Core Generation (This Spec)

- Database tables: `golden_sets`, `golden_set_entries` (with nullable answer eval columns)
- Generation pipeline: page windowing, LLM prompt, structured parsing, deduplication
- Async task integration: progress tracking, cancellation, error handling
- API endpoints: create, generate, list entries, update entry, bulk accept
- Review UI: status filtering, accept/edit/reject, bulk accept, save gate
- Configuration UI: document selection, LLM provider, queries per doc, question types

### 10.2 Phase 2: Answer Evaluation Extension

- Extended generation prompt: reference_answer + key_claims output
- Backfill API: add reference answers to existing entries
- Extended review UI: answer text editing, claim validation
- Answer evaluation engine: faithfulness scoring, relevance scoring, claim-level grounding
- Combined evaluation dashboard: retrieval metrics + answer metrics in single view

### 10.3 Phase 3: Advanced Generation

- Multi-hop question generation (queries requiring information from multiple documents)
- Adversarial query generation (questions designed to surface retrieval weaknesses)
- LLM-assisted review (second LLM validates the generated entries before human review)
- Golden set versioning (track changes to entries over time, diff between versions)

---

## 11. Open Questions

| Question | Options | Recommendation |
|---|---|---|
| Should rejected entries be hard-deleted or soft-deleted? | Hard delete saves storage. Soft delete enables analytics on rejection patterns. | Soft delete. The storage cost is trivial and rejection patterns inform prompt improvement. |
| Should generation support re-running for specific documents? | Full re-run only vs. incremental (add queries for new docs to existing set) | Support incremental. Users add documents over time. Re-generating everything wastes API cost and review effort. |
| How to handle very large documents (500+ pages)? | Process all pages vs. sample pages vs. let user select page ranges | Let user select page ranges as a generation config option. Large documents often have irrelevant sections (appendices, boilerplate). |
| Should the deduplication threshold (0.92) be configurable? | Fixed vs. user-configurable vs. auto-tuned | Fixed at 0.92 for now. Expose as advanced setting later if users request it. |

---

*— End of specification —*
