# Landing AI CDM Adapter — Design

> **Status**: Approved. Implementation plan to follow.
> **Date**: 2026-04-27
> **References**: [`docs/planning/cdm_architecture.md`](../../planning/cdm_architecture.md) §5, [`docs/specs/cdm_v1.md`](../../specs/cdm_v1.md)

---

## 1. Goals

1. Implement a `LandingAIAdapter` that maps `ParseResponse` output to `ParsedDocument`.
2. Implement `run_landingai` runner using the async `parse_jobs` API (no 100-page sync limit).
3. Decouple `ParsingService` from LlamaParse — make it parser-agnostic via a dispatch table.
4. Introduce a `ParseRunError` base class so the service catches all runner errors uniformly.
5. Ship structural invariant tests and a snapshot backed by a real API call against `cleanshelf-12-4-26.jpg`.

---

## 2. Files Changed / Created

| File | Action |
|---|---|
| `backend/app/cdm/adapters/landing_ai.py` | **create** |
| `backend/app/services/parsing/landingai_runner.py` | **create** |
| `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.json` | **create** (real API fixture) |
| `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.expected.json` | **create** (snapshot) |
| `backend/tests/cdm/test_landing_ai_adapter.py` | **create** |
| `backend/app/services/parsing/errors.py` | **modify** — add `ParseRunError` base, `LandingAIRunError` |
| `backend/app/services/parsing/parsing_service.py` | **modify** — decouple, dispatch table |
| `backend/app/core/config.py` | **modify** — add `VISION_AGENT_API_KEY` |
| `backend/pyproject.toml` | **modify** — add `landingai-ade` dep |

---

## 3. Adapter Design (`landing_ai.py`)

Stateless class, follows `ParserAdapter` protocol. Input is `ParseResponse.model_dump()`.

### 3.1 Chunk type → BlockRole

| chunk type | BlockRole | notes |
|---|---|---|
| `text` | `PARAGRAPH` | |
| `table` | `TABLE` | builds `Table` with `Cell` list |
| `figure` | `FIGURE` | |
| `logo` | `FIGURE` | `native_type="logo"` |
| `attestation` | `OTHER` | `native_type="attestation"` |
| `scan_code` | `FIGURE` | `native_type="scan_code"` |
| `marginalia` | `MARGINALIA` | |

### 3.2 BBox

Identity conversion — `left→x0, top→y0, right→x1, bottom→y1`. Already normalised 0–1. `source_space="fraction"`, `source_coords=(left, top, right, bottom)`.

### 3.3 Page indexing

Landing AI is already 0-indexed. No conversion required.

### 3.4 Block IDs

Reuse the chunk UUID directly (`chunk["id"]`). Stable and unique within a response.

### 3.5 Grounding dict

`response["grounding"]` is a `Dict[str, Any]` keyed by chunk UUID or cell ID.

- **Chunk entries** (`type` in `{"chunkText","chunkTable","chunkFigure","chunkLogo",...}`):
  `confidence` → `Block.quality.confidence`; `low_confidence_spans` → `Block.quality.low_confidence_spans`.
- **Cell entries** (`type == "tableCell"`):
  `position.{row, col, rowspan, colspan}` → `Cell` fields; `confidence` → `Cell.quality.confidence`;
  bounding box (if present) → `Cell.bbox`.

### 3.6 Table parsing

For `TABLE` blocks, parse the HTML in `chunk["markdown"]` using `html.parser` (stdlib). Extract rows → cells → text. Cross-reference grounding dict for per-cell `row/col/rowspan/colspan/confidence`. Preserve verbatim HTML on `Table.html`; chunk markdown on `Table.markdown`.

### 3.7 Pages

Constructed by grouping chunks on `chunk["grounding"]["page"]`. `Page.width/height` left `None` (Landing AI does not expose page dimensions).

### 3.8 Document-level fields

- `full_markdown`: use `response["markdown"]` directly (complete string with `<!-- PAGE BREAK -->` separators).
- `full_text`: join `block.text` for all blocks.
- `ParsedDocument.parser_extras["landing_ai_splits"]`: verbatim copy of `response["splits"]`.

---

## 4. Runner Design (`landingai_runner.py`)

**Always uses `parse_jobs`** (async path, supports up to 1000 pages / 1 GB).

```python
async def run_landingai(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]: ...
```

### Flow

1. `client.parse_jobs.create(document=Path(file_path), model=config.get("model", "dpt-2-latest"))` → `job_id`
2. Store `job_id` in `provider_refs` immediately.
3. Poll `client.parse_jobs.get(job_id)` every `config.get("poll_interval_s", 5)` seconds via `asyncio.sleep`.
4. Timeout after `config.get("poll_timeout_s", 600)` seconds (10 min default).
5. On `status == "completed"`: build `ParseRun(SUCCEEDED)` from `response.data.metadata`, adapt via `LandingAIAdapter`.
6. On `status == "failed"` or timeout: raise `LandingAIRunError(run=failed_run)`.

### ParseRun fields from metadata

| Landing AI field | ParseRun field |
|---|---|
| `metadata.duration_ms` | `duration_ms` |
| `metadata.credit_usage` | `cost["credits"]` |
| `metadata.job_id` | `provider_refs["landingai_job_id"]` |
| `metadata.failed_pages` | `failed_pages` |
| `metadata.version` | `parser_version` |
| `metadata.page_count` | (inferred from `pages` list) |

---

## 5. ParsingService Decoupling

### Constructor

```python
# Before
def __init__(self, ..., llamaparse_client: Any)

# After
def __init__(self, ..., clients: Dict[ParserKind, Any])
```

### Dispatch table

```python
_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
}
```

### `parse_and_persist` signature change

Adds `parser: ParserKind` parameter. Looks up `_RUNNERS[parser]` and `self._clients[parser]`.

### Error handling

Catches `ParseRunError` (base) instead of `LlamaParseRunError`.

---

## 6. Error Hierarchy

```python
# errors.py

class ParseRunError(RuntimeError):
    """Base for all runner errors. Carries the unpersisted failed ParseRun."""
    def __init__(self, message: str, *, run: ParseRun):
        super().__init__(message)
        self.run = run

class LlamaParseRunError(ParseRunError): ...
class LandingAIRunError(ParseRunError): ...
```

---

## 7. Config

Add to `app/core/config.py`:

```python
VISION_AGENT_API_KEY: str = ""
```

The `LandingAIADE` client is initialised with `api_key=settings.VISION_AGENT_API_KEY` at app startup (same location as the LlamaParse client).

---

## 8. Eval + Tests

### Fixture generation

One-off script (or manual call) using `VISION_AGENT_API_KEY` against `_scratch/cleanshelf-12-4-26.jpg` via `parse_jobs`. Raw `ParseResponse.model_dump()` saved to:

```
backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.json
```

### Structural invariant tests (`tests/cdm/test_landing_ai_adapter.py`)

Run offline against fixture JSON. Assert:
- `page_count == len(pages)`
- Every `block.page_index` in `[0, page_count)`
- Every `bbox` has `0 ≤ x0 ≤ x1 ≤ 1` and `0 ≤ y0 ≤ y1 ≤ 1`
- Every block has non-empty `role` and `native_type`
- Every `Page.block_ids` references existing blocks
- `full_markdown` non-empty
- Round-trip: `ParsedDocument.model_validate_json(doc.model_dump_json()) == doc`

### Snapshot

`backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.expected.json` committed alongside fixture. Diff on subsequent adapter changes is intentional.

---

## 9. Call-site Impact

`parse_and_persist` gains a required `parser: ParserKind` param. All callers (routers that invoke `ParsingService`) must be updated to pass the parser explicitly. Search for `parse_and_persist(` to find all call sites before implementation.
