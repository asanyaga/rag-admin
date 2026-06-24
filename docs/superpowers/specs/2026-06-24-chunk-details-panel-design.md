# Chunk Details Panel — Design

**Date:** 2026-06-24
**Status:** Draft
**Related files:** `backend/app/adapters/extraction/pipeline.py`,
`backend/app/adapters/extraction/chunking/merge.py`,
`frontend/src/components/extraction/ExtractionResultViewer.tsx`

## Problem

For chunked LLM extraction runs the debug panels in `ExtractionResultViewer` show
only aggregate information — total tokens, chunk count, merged structured data — and
placeholder messages for prompt and LLM response. There is no way to inspect what
was sent to the model for each individual chunk or what it returned, making it
impractical to diagnose extraction quality or prompt behaviour in a multi-chunk run.

## Goals

- Surface all per-chunk information (prompts, LLM responses, pre-merge extracted
  data, token usage, latency) in a structured, scannable panel.
- Use a list + detail layout: chunk selector on the left, full detail on the right,
  so depth of information does not compete with navigation for vertical space.
- No new API endpoints, no database migrations — store per-chunk summaries inside the
  existing `extractionMetadata` JSONB column.
- Backend change is additive: existing non-chunked and chunked runs without the new
  field degrade gracefully (panel hidden).

## Non-goals

- Streaming or live per-chunk updates during an in-progress extraction.
- Diff / comparison across chunks (e.g., "what changed between chunk 1 and 2").
- Editing or re-running individual chunks.

---

## Data model

### Backend: `extractionMetadata.chunks`

`pipeline.py` currently discards per-chunk `ExtractionOutput` after merging. After
the `asyncio.gather`, zip `results: list[ExtractionOutput]` with
`chunks: list[DocumentChunk]` (which carry `page_indices`) before calling
`merge_outputs`.

`merge_outputs` gains an optional `chunks` parameter and adds a `chunks` key to the
merged metadata dict:

```python
metadata["chunks"] = [
    {
        "chunkIndex": chunk.chunk_index,          # int, 0-based
        "pageIndices": chunk.page_indices,        # list[int]
        "promptMessages": out.extraction_metadata.get("prompt_messages", []),
        "providerResponseRaw": out.provider_response_raw,
        "structuredData": out.structured_data,
        "usage": out.extraction_metadata.get("usage"),
        "latencyMs": out.extraction_metadata.get("latency_ms"),
    }
    for chunk, out in zip(chunks, results)
]
```

Key naming uses camelCase to match the existing `extractionMetadata` convention
(`chunkCount`, `latencyMs`, etc.).

`merge_outputs` signature change:

```python
def merge_outputs(
    outputs: list[ExtractionOutput],
    schema: dict[str, Any],
    dedupe_key: str | None,
    chunks: list | None = None,      # list[DocumentChunk] | None
) -> ExtractionOutput:
```

`chunks` is optional (defaults to `None`) so existing call-sites and tests that pass
only `outputs` continue to work unchanged.

`pipeline.py` call-site:

```python
return merge_outputs(list(results), schema, dedupe_key, chunks=chunks)
```

where `chunks` is the `list[DocumentChunk]` returned by `strategy.split(...)`.

---

## UI design

### Placement

A new "Chunk Details" `Collapsible` panel rendered below the existing three panels
(Run Config, Prompt, LLM Response), collapsed by default. Only rendered when
`meta?.chunks` exists and has length > 0.

```
[ Run Config ▾ ]
[ Prompt ▾ ]
[ LLM Response ▾ ]          ← hidden for chunked runs (no providerResponseRaw)
[ Chunk Details ▾ ]         ← new; chunked runs only
```

The existing panels are unchanged. The Chunk Details panel is purely additive.

### Layout: list + detail

When opened, the panel body is a two-column CSS grid:

```
┌─────────────────────┬────────────────────────────────────────────┐
│  Chunk list (16rem) │  Detail pane (flex 1)                      │
│  ─────────────────  │  ──────────────────────────────────────── │
│  ● Chunk 1          │  System ────────────────────────────────── │
│    pp. 1–3          │  <pre> system prompt (shared across chunks)│
│    4,542 tok · 1.2s │                                            │
│                     │  User ──────────────────────────────────── │
│  ○ Chunk 2          │  Instruction / Schema (FormattedJson) /    │
│    pp. 4–7          │  Document sections                         │
│    3,901 tok · 1.0s │                                            │
│                     │  LLM Response ──────────────────────────── │
│  ○ Chunk 3          │  FormattedJson of providerResponseRaw      │
│    pp. 8–10         │                                            │
│    4,100 tok · 1.1s │  Extracted (pre-merge) ─────────────────── │
│                     │  FormattedJson of structuredData           │
│                     │                                            │
│                     │  Usage ────────────────────────────────────│
│                     │  Prompt · Completion · Total · Latency     │
└─────────────────────┴────────────────────────────────────────────┘
```

**Chunk list (left column, `w-64`, `overflow-y-auto`, sticky within panel):**

Each row is a button:
- First line: `Chunk N` (semibold, 1-based display: `chunkIndex + 1`) + page-range
  badge (`pp. 1–3`, 1-based: `pageIndices[0] + 1`–`pageIndices[last] + 1`).
  Badge omitted when `pageIndices` is empty.
- Second line: `4,542 tokens · 1.2 s` (muted, small). Latency formatted as
  `toLocaleString() + ' ms'`; missing values show `—`.
- Selected row: `bg-muted` background, left border accent

State: `selectedChunkIndex: number` (React `useState`, initialised to `0`).

**Detail pane (right column, `flex-1`, `overflow-y-auto`, `pl-4`):**

Vertically stacked, labelled sections (no sub-tabs — show everything at once):

1. **System** — `<pre>` of `chunk.promptMessages[0].content`; muted footnote
   *"Identical across all chunks"*. `max-h-48`, `overflow-y-auto`.

2. **User** — parsed via the existing `parseUserContent` helper (reused from the
   Prompt panel):
   - **Instruction** — plain `<pre>`
   - **Schema** — `<FormattedJson>` (`max-h-48`)
   - **Document** — plain `<pre>`, `max-h-48`, `overflow-y-auto`
   - Falls back to full-content `<pre>` if tags absent.

3. **LLM Response** — `<FormattedJson value={chunk.providerResponseRaw} maxHeight="20rem" />`
   If null: muted italics *"No response recorded for this chunk."*

4. **Extracted (pre-merge)** — `<FormattedJson value={chunk.structuredData} maxHeight="16rem" />`
   Label includes a note: *"Raw output before conflict resolution and deduplication."*

5. **Usage** — four-cell inline grid:
   - Prompt tokens / Completion tokens / Total tokens / Latency
   - Values formatted with `toLocaleString()` / `ms` suffix. Missing values show `—`.

---

## Component changes

| File | Change |
|---|---|
| `backend/app/adapters/extraction/pipeline.py` | Pass `chunks` list to `merge_outputs` at the chunked call-site. |
| `backend/app/adapters/extraction/chunking/merge.py` | Add optional `chunks` param; build `metadata["chunks"]` when provided. |
| `backend/tests/adapters/extraction/chunking/test_merge.py` | Add: chunks array populated with correct fields when `chunks` param passed; existing tests unaffected. |
| `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Add `ChunkDetailsPanel` inner component and render it below LLM Response when `meta?.chunks` present. |
| `frontend/src/components/extraction/ExtractionResultViewer.test.tsx` | Add: panel hidden when no chunks; chunk list renders correct labels; selecting a chunk updates detail pane; system prompt shows shared note. |

No changes to `ExtractionResult` type, API layer, or database schema.

---

## Acceptance criteria

- [ ] For a completed chunked LLM run, `extractionMetadata.chunks` contains one entry
  per chunk with `chunkIndex`, `pageIndices`, `promptMessages`, `providerResponseRaw`,
  `structuredData`, `usage`, and `latencyMs`.
- [ ] Chunk Details panel is hidden for non-chunked runs and for runs where
  `extractionMetadata.chunks` is absent.
- [ ] Chunk list shows correct page ranges and formatted token/latency counts for
  each chunk.
- [ ] Selecting a chunk updates the detail pane to show that chunk's system prompt,
  parsed user message, LLM response, pre-merge extracted data, and usage.
- [ ] System prompt section carries the *"Identical across all chunks"* note.
- [ ] Extracted pre-merge section carries the *"Raw output before conflict resolution
  and deduplication"* note.
- [ ] `parseUserContent` helper is reused; no duplication.
- [ ] Existing non-chunked run tests are unaffected.
- [ ] All new behaviour is covered by unit tests.
