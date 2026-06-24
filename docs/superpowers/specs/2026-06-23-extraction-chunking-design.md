# Extraction Chunking & Composable Pipeline — Design

**Date:** 2026-06-23
**Status:** Approved (design); pending implementation plan
**Related:** `backend/app/adapters/extraction/`, `backend/app/services/classification/` (chunking blueprint)

## Problem

Large-document LLM extraction fails in two ways:

1. **Response truncation** — output is cut at `max_tokens` (default 4096,
   `backend/app/adapters/extraction/llm.py`). The per-field `__source`
   augmentation (`augment_schema_with_sources`,
   `backend/app/adapters/extraction/llm_context.py`) roughly doubles output
   size, so multi-record extractions exhaust the budget mid-array and
   `json.loads` fails with a misleading "non-JSON response" error.
2. **Rate limiting** — the entire document markdown plus the doubled schema is
   sent in a single request, and there is no 429 handling anywhere in the
   Anthropic adapter (`backend/app/services/llm/anthropic_adapter.py`). Large
   input + output per call burns tokens-per-minute quota and any 429 bubbles up
   as a hard failure.

The fix is structural: chunk large documents into token-bounded pieces,
configurably degrade citation granularity so output fits, and introduce a
composable, UI-driven pipeline so future filters (classification, etc.) slot in
without modifying the extractor.

## Goals

- Chunk documents into token-bounded pieces and merge the results.
- Make citation granularity configurable, auto-selected by document size with
  manual override.
- Introduce a declarative, per-run **pipeline config** so preprocessing and
  chunking are composable stages, not logic baked into the extractor.
- Add 429 backoff, bounded concurrency, and truncation detection.
- Preserve exact current behavior when the new config is absent.

## Non-goals (this spec)

- `category_filter` (label-based page/block scoping from an upstream
  classification run) — only a defined, registered seam; wiring deferred to a
  follow-up spec.
- Cross-distant-page stitching / reconciliation passes. Within-chunk alignment
  of SKU ↔ specs ↔ price is the target; HITL handles the last mile.
- Saved/named pipeline presets — config is per-run only.
- Prompt caching.

## Pipeline topology

Parse, classify, and extract are three independent, persisted stages. Each
stage owns its own config; downstream stages reference upstream output by id.
`ParsedDocument` is produced once and is the source of truth across all stages.

```
Parser ──▶ parse_run + ParsedDocument (persisted, source of truth)
              │  parse config lives on the parse run
              ▼
Classifier ─▶ classification_run + regions  (persisted, reusable)
              │  classify config + labels live on the classification run;
              │  classification never mutates the ParsedDocument
              ▼
Extractor ──▶ extraction pipeline ──▶ result
              │  chunking + preprocess config lives on the extraction request
```

| Config | Lives on | Extraction references it via |
|---|---|---|
| Parse | the parse run (upstream) | `parseRunId` (exists) |
| Classify | the classification run (upstream, exists today) | `classificationRunId` (future — see `category_filter`) |
| Chunking + light preprocess | the extraction request | `chunking` / `preprocess` (this spec) |

Classification is **already** a first-class stage with its own runs, repository,
and persisted regions (`backend/app/routers/classification.py`,
`backend/app/services/classification/service.py`). This spec does **not** run
classification inside extraction; it consumes classification output via the
deferred `category_filter` stage (below).

## Pipeline config (request shape)

`RunExtractionRequest`
(`backend/app/schemas/extraction_result.py`) gains two optional fields.
Everything else is unchanged, so existing callers behave identically.

```jsonc
{
  "parseRunId": "...",
  "extractionSchemaId": "...",
  "extractionMethod": "llm",
  "llmConfig": { "...": "..." },

  "preprocess": [                      // NEW — ordered, optional
    { "stage": "block_filter",
      "config": { "drop": ["page_header", "page_footer", "page_number"] } }
  ],
  "chunking": {                        // NEW — optional
    "strategy": "token_budget_pages",  // or "none" (default)
    "config": { "maxInputTokens": 8000, "pageOverlap": 0, "dedupeKey": "sku" },
    "citationLevel": "auto"            // auto | full | page_only | off
  }
}
```

When `chunking` is absent or `strategy: "none"` and the resolved citation level
is `full`, behavior is byte-identical to today's single-shot path.

The two new registries (chunking strategies, preprocess stages) each expose a
`config_schema` exactly like the existing extractor registry
(`backend/app/adapters/extraction/registry.py`), so the UI renders a form per
selected stage/strategy.

## Components

Each unit has one purpose, a defined interface, and is independently testable.

### `PipelineExtractor` — `backend/app/adapters/extraction/pipeline.py`
Implements the existing `DataExtractor` port and wraps an inner extractor.
Per `extract()` call it runs: **preprocess → chunk → inner.extract per chunk →
merge**. Because it satisfies the same port, `process_extraction` and the
background task in `backend/app/routers/extraction.py` are untouched — the
router constructs a `PipelineExtractor` (wrapping the existing `LLMExtractor`)
when `chunking`/`preprocess` are present, and a bare `LLMExtractor` otherwise.

### `chunking/` package — `backend/app/adapters/extraction/chunking/`
- `base.py` — `ChunkStrategy` protocol with
  `split(parsed_doc, schema, config) -> list[DocumentChunk]`, plus the
  `DocumentChunk` type (below).
- `token_budget.py` — the `token_budget_pages` strategy (below).
- `registry.py` — named strategies + `config_schema`, mirroring the extractor
  registry. Entries at ship: `none`, `token_budget_pages`.

### `merge.py` — `backend/app/adapters/extraction/chunking/merge.py`
Schema-guided merge of per-chunk `ExtractionOutput`s into one (below).

### `citation_policy.py` — `backend/app/adapters/extraction/chunking/citation_policy.py`
Resolves `auto`, degrades the augmented schema, and post-filters `__source`
fields (below).

### `preprocess/` package — `backend/app/adapters/extraction/preprocess/`
- `base.py` — stage protocol `apply(parsed_doc, config) -> ParsedDocument`,
  plus a registry with `config_schema`.
- `block_filter.py` — shipped stage; drops blocks by type/role.
- `category_filter` — **seam only** (deferred to a follow-up spec). Registered
  name with documented interface and `config_schema`, raising
  `NotImplementedError`. When built, it will read an upstream
  `classificationRunId`'s persisted regions and scope the `ParsedDocument` to
  pages/blocks whose label is in the configured categories (e.g.
  `["spec", "price list"]`), returning a derived `ParsedDocument` before
  chunking. Classification itself is **not** run here — it is a separate
  upstream stage that already exists. Defining the seam now lets the UI list it
  as "coming soon" and reserves the `classificationRunId` request field without
  backend rework.

## DocumentChunk — a derived, non-destructive view

`ParsedDocument` is the source of truth across all pipelines and is **never
mutated or replaced**. It is a frozen Pydantic model (`backend/app/cdm/models.py`,
`extra="forbid"`); the CDM already provides lineage fields for exactly this
purpose:

```python
# models.py
derived_from: Optional[str] = None   # source parse_run_id
derivation:  Optional[str] = None    # e.g. "chunk:pages=1-3"
```

A chunk is therefore a **derived `ParsedDocument`**, not a new stripped-down
type:

```python
class DocumentChunk(BaseModel):
    document: ParsedDocument   # derived: subset of pages+blocks, lineage set
    chunk_index: int           # deterministic merge ordering
    page_indices: list[int]    # source page indices, for citation re-pathing
```

The splitter builds each `document` via `source.model_copy(update={...})`,
selecting the subset of `pages`/`blocks` for the chunk's page range,
recomputing `page_count`, and setting `derived_from` / `derivation`. The
original instance is untouched (frozen), and chunks are transient,
extraction-time inputs — never persisted as the canonical document.

Consequences:

- The **inner extractor needs no changes**: `LLMExtractor.extract()` receives a
  `ParsedDocument` and runs `build_extraction_context()` as today — it simply
  sees a smaller document.
- **Preprocess filters** follow the same rule: `block_filter` returns a new
  derived `ParsedDocument` with fewer blocks, never mutating its input.
- Every chunk is traceable to its source via `derived_from`.

## Chunking: `token_budget_pages`

Reuses the page grouping in `build_extraction_context`
(`backend/app/adapters/extraction/llm_context.py`) and the batching spirit of
classification's `build_batches`
(`backend/app/services/classification/serializer.py`).

Algorithm:
1. Estimate tokens per page (character-count / 4 heuristic; the divisor is a
   tunable constant).
2. Pack whole pages into a chunk until adding the next page would exceed
   `maxInputTokens`; never split a page.
3. Emit a `DocumentChunk`; repeat.
4. Optional `pageOverlap` repeats the last N pages of a chunk at the start of
   the next.

A document that fits within `maxInputTokens` yields exactly one chunk →
identical to single-shot extraction.

## Merge semantics

Walks the **original** (pre-augmentation) schema to merge per-chunk outputs:

- **Array fields** → concatenate across chunks in page order. Dedupe when a
  `dedupeKey` is configured in `chunking.config` (e.g. `sku`) *or* on
  exact-record equality (handles overlap duplicates).
- **Scalar / nested-object fields** → first non-null wins, chunks ordered by
  their first page. When two chunks return *differing* non-null values for the
  same scalar, keep the first and record `{path, kept, discarded, chunkPages}`
  in `extractionMetadata.scalarConflicts` (no silent data loss).
- **Citations** → unioned; field paths re-indexed to the merged array
  positions.
- **Metadata** → per-chunk usage/latency summed; `chunkCount` and per-chunk
  `stopReason` recorded.

## Citation granularity

Three levels, applied by `citation_policy`:

- **`full`** — current behavior: per-field `{page_index, block_id}`.
- **`page_only`** — per-field `page_index`; `block_id` removed from the
  augmented schema and stripped from output.
- **`off`** — no `__source` augmentation at all.

`auto` resolves by estimated document tokens: below a threshold → `full`; at or
above → `page_only`. **`auto` never selects `off`** — provenance is only fully
discarded by explicit override. Thresholds live in one constants module for
easy tuning. Default when `chunking` is absent: `full` (today's behavior).

## Execution, rate limits, truncation

- **Bounded concurrency** — chunks run through an `asyncio.Semaphore` (default
  3, configurable). Required so chunking does not worsen rate limiting.
- **429 backoff** — the per-chunk LLM call is wrapped in exponential backoff
  honoring `retry-after`, addressing the missing resilience in
  `backend/app/services/llm/anthropic_adapter.py`.
- **Truncation detection** — `stop_reason` is threaded from the Anthropic
  response through `CompletionResult` (`backend/app/services/llm/types.py`) as
  an additive optional field. A chunk that stops on `max_tokens` produces a
  precise error ("chunk pages 4–6 truncated; lower maxInputTokens or raise
  maxTokens") instead of the current misleading "non-JSON response".

## Error handling

A failed or truncated chunk marks the whole extraction result `FAILED` with a
message naming the chunk and its page range — HITL must know coverage is
incomplete; partial output is never reported as success. `LLMConnectionError`
continues to map to `ExtractionError` as today.

## Testing

- **`token_budget` splitter:** budget boundaries, single-chunk passthrough,
  overlap, never-split-a-page.
- **`merge`:** array concat + dedupe (by key and by exact equality), scalar
  first-non-null coalescing, `scalarConflicts` recording, citation re-pathing.
- **`citation_policy`:** schema/output shape per level; `auto` threshold
  resolution.
- **`block_filter`:** drops targeted block types, preserves reading order.
- **`PipelineExtractor`:** end-to-end with a fake inner extractor (no real
  LLM) — `none` strategy reproduces current output; multi-chunk merges
  correctly; a truncated chunk yields `FAILED`.

## Backward compatibility

No migration. Absent `chunking`/`preprocess` → byte-identical to current
behavior. Registry additions are additive. `CompletionResult.stop_reason` is an
additive optional field.

## Future work (out of scope)

- `category_filter` preprocess stage (own spec) — add `classificationRunId` to
  the extraction request and scope pages/blocks by the existing classification
  module's persisted regions (`backend/app/services/classification/`).
- Saved pipeline presets/profiles.
- Prompt caching for repeated passes over the same document.
- Auto-retry of a truncated chunk with a smaller budget.
