# Landing AI CDM Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Landing AI ADE adapter for the CDM, decouple `ParsingService` from LlamaParse, and ship structural invariant tests backed by a real API fixture.

**Architecture:** A `LandingAIAdapter` maps `ParseResponse` dicts to `ParsedDocument` following the same `ParserAdapter` protocol as `LlamaParseAdapter`. A `run_landingai` runner always uses the async `parse_jobs` API (no 100-page sync limit), polling internally so callers see the same `(ParseRun, ParsedDocument)` signature. `ParsingService` is decoupled by replacing the `llamaparse_client` constructor arg with a `clients: Dict[ParserKind, Any]` dict and reading `parser` from the `config` dict to dispatch to the correct runner.

**Tech Stack:** Python 3.12, FastAPI (async), Pydantic v2, `landingai-ade` SDK, `html.parser` (stdlib), `asyncio.to_thread`, `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-04-27-landing-ai-cdm-adapter-design.md`

---

## File Map

| File | Action |
|---|---|
| `backend/pyproject.toml` | add `landingai-ade` dep |
| `backend/app/config.py` | add `VISION_AGENT_API_KEY` |
| `backend/app/cdm/models.py` | add `parser_extras` to `ParsedDocument` |
| `backend/app/services/parsing/errors.py` | add `ParseRunError` base + `LandingAIRunError` |
| `backend/app/services/parsing/parsing_service.py` | decouple: `clients` dict, dispatch by config |
| `backend/app/dependencies/documents.py` | add `get_landingai_client()`, update `get_parsing_service` |
| `backend/app/services/document_service.py` | update `ParsingService(...)` call |
| `backend/app/cdm/adapters/landing_ai.py` | **create** |
| `backend/app/services/parsing/landingai_runner.py` | **create** |
| `backend/scripts/generate_landingai_fixture.py` | **create** (one-off, not shipped) |
| `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.json` | **create** (real API output) |
| `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.expected.json` | **create** (snapshot) |
| `backend/tests/cdm/test_landing_ai_adapter.py` | **create** |
| `backend/tests/services/parsing/test_parsing_service.py` | update `_make_service` + call sites |

---

## Task 1: Add `landingai-ade` dependency and config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add dep to pyproject.toml**

In the `# Document Processing` block in `backend/pyproject.toml`, add after the `"llama-cloud>=1.0.0"` line:

```toml
    "landingai-ade>=0.3.3",     # Landing AI ADE document parsing
```

- [ ] **Step 2: Add VISION_AGENT_API_KEY to config.py**

In `backend/app/config.py`, after the `# LlamaParse / LlamaCloud` block:

```python
    # Landing AI ADE
    VISION_AGENT_API_KEY: str = ""
```

- [ ] **Step 3: Install the dependency**

```bash
uv sync --directory backend
```

Expected: resolves successfully with `landingai-ade` in the lockfile.

- [ ] **Step 4: Verify import works**

```bash
uv run --directory backend python -c "from landingai_ade import LandingAIADE; print('ok')"
```

Expected: prints `ok` with no import errors.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py
git commit -m "chore(cdm): add landingai-ade dep and VISION_AGENT_API_KEY config"
```

---

## Task 2: Add `parser_extras` to `ParsedDocument`

`ParsedDocument` currently has no `parser_extras` field, but `Block` and `Page` both do. The Landing AI adapter needs to store `splits` here.

**Files:**
- Modify: `backend/app/cdm/models.py:139-154`
- Modify: `backend/tests/cdm/test_models.py`

- [ ] **Step 1: Add the field to ParsedDocument**

In `backend/app/cdm/models.py`, update the `ParsedDocument` class:

```python
class ParsedDocument(_Frozen):
    id: str
    source_document_id: str
    parse_run_id: str
    source_filename: Optional[str] = None
    page_count: int
    pages: List[Page]
    blocks: List[Block]
    full_text: Optional[str] = None
    full_markdown: Optional[str] = None
    labels: List[Label] = []
    derived_from: Optional[str] = None
    derivation: Optional[str] = None
    parser_extras: Dict[str, Any] = {}
    schema_version: str = "1.0"
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
uv run --directory backend python -m pytest tests/cdm/ -o "addopts=" -v
```

Expected: all pass. The new field has a default so old round-trips still work.

- [ ] **Step 3: Commit**

```bash
git add backend/app/cdm/models.py
git commit -m "feat(cdm): add parser_extras field to ParsedDocument"
```

---

## Task 3: Refactor error hierarchy

Extract a `ParseRunError` base class so `ParsingService` can catch all runner errors uniformly without importing each error type.

**Files:**
- Modify: `backend/app/services/parsing/errors.py`

- [ ] **Step 1: Write failing test for the new hierarchy**

In `backend/tests/services/parsing/test_errors.py` (create file):

```python
from app.cdm.source import ParseRun, ParseRunStatus, ParserKind
from app.services.parsing.errors import LandingAIRunError, LlamaParseRunError, ParseRunError
from datetime import datetime, timezone


def _dummy_run() -> ParseRun:
    return ParseRun(
        id="run-1",
        source_document_id="src-1",
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        status=ParseRunStatus.FAILED,
        started_at=datetime.now(timezone.utc),
    )


def test_llamaparse_error_is_parse_run_error():
    err = LlamaParseRunError("boom", run=_dummy_run())
    assert isinstance(err, ParseRunError)
    assert err.run.status == ParseRunStatus.FAILED


def test_landingai_error_is_parse_run_error():
    err = LandingAIRunError("boom", run=_dummy_run())
    assert isinstance(err, ParseRunError)
    assert err.run.status == ParseRunStatus.FAILED
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_errors.py -o "addopts=" -v
```

Expected: FAIL — `ParseRunError` and `LandingAIRunError` don't exist yet.

- [ ] **Step 3: Update errors.py**

Replace `backend/app/services/parsing/errors.py` with:

```python
from __future__ import annotations

from app.cdm.source import ParseRun


class ParseRunError(RuntimeError):
    """Base for all runner errors. Carries the unpersisted failed ParseRun."""
    def __init__(self, message: str, *, run: ParseRun) -> None:
        super().__init__(message)
        self.run = run


class LlamaParseRunError(ParseRunError):
    """Raised by llamaparse_runner when the SDK call fails."""


class LandingAIRunError(ParseRunError):
    """Raised by landingai_runner when the SDK call or polling fails."""


class ParseFailedError(RuntimeError):
    """Domain error raised by ParsingService to callers (routers) after
    a failed ParseRun has been persisted."""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_errors.py -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 5: Verify existing tests still pass**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v
```

Expected: all pass — `LlamaParseRunError` still exists, just now inherits from `ParseRunError`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parsing/errors.py backend/tests/services/parsing/test_errors.py
git commit -m "refactor(parsing): extract ParseRunError base class, add LandingAIRunError"
```

---

## Task 4: Decouple ParsingService from LlamaParse

Replace the hard-coded `llamaparse_client` constructor arg with a `clients: Dict[ParserKind, Any]` dict. Read `parser` from `config.get("parser", "llamaparse")` inside `parse_and_persist` to select the runner. Update all call sites and tests.

**Files:**
- Modify: `backend/app/services/parsing/parsing_service.py`
- Modify: `backend/app/dependencies/documents.py`
- Modify: `backend/app/services/document_service.py:569-574`
- Modify: `backend/tests/services/parsing/test_parsing_service.py`

- [ ] **Step 1: Update _make_service in test_parsing_service.py**

Find the `_make_service` helper (currently line ~130) and update it:

```python
def _make_service(repos, client) -> ParsingService:
    src_repo, run_repo, doc_repo = repos
    storage = AsyncMock()
    storage.save.return_value = "local://stored.pdf"
    return ParsingService(
        source_doc_repo=src_repo,
        parse_run_repo=run_repo,
        parsed_doc_repo=doc_repo,
        storage=storage,
        clients={ParserKind.LLAMAPARSE: client},
    )
```

- [ ] **Step 2: Run existing parsing service tests to see what breaks**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_parsing_service.py -o "addopts=" -v
```

Expected: FAIL on constructor signature (still uses `llamaparse_client`).

- [ ] **Step 3: Update parsing_service.py**

Replace `backend/app/services/parsing/parsing_service.py` with:

```python
"""ParsingService — orchestrates source-document dedup, parse-run reuse, and persistence."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict
from uuid import UUID

from app.cdm.models import ParsedDocument as ParsedDocumentCDM, ParserKind
from app.cdm.source import (
    ParseRun as ParseRunCDM,
    ParseRunStatus,
    SourceDocument as SourceDocumentCDM,
)
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.source_document import SourceDocument as SourceDocumentORM
from app.ports.storage import StorageService
from app.repositories.parse_run_repository import ParseRunCreate, ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentCreate, ParsedDocumentRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.services.parsing.errors import ParseFailedError, ParseRunError
from app.services.parsing.llamaparse_runner import run_llamaparse


_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
}


def _compute_config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _run_orm_to_cdm(orm: ParseRunORM) -> ParseRunCDM:
    return ParseRunCDM(
        id=str(orm.id),
        source_document_id=str(orm.source_document_id),
        parser=ParserKind(orm.parser),
        parser_version=orm.parser_version,
        representation_kind=orm.representation_kind,
        config=orm.config or {},
        status=ParseRunStatus(orm.status),
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        duration_ms=orm.duration_ms,
        cost=orm.cost or {},
        input_tokens=orm.input_tokens,
        output_tokens=orm.output_tokens,
        warnings=orm.warnings or [],
        failed_pages=orm.failed_pages or [],
        provider_refs=orm.provider_refs or {},
        error=orm.error,
    )


def _doc_orm_to_cdm(orm: ParsedDocumentORM) -> ParsedDocumentCDM:
    return ParsedDocumentCDM.model_validate(orm.content)


def _source_orm_to_cdm(orm: SourceDocumentORM) -> SourceDocumentCDM:
    return SourceDocumentCDM(
        id=str(orm.id),
        sha256=orm.sha256,
        filename=orm.filename,
        mime_type=orm.mime_type,
        byte_size=orm.byte_size,
        storage_uri=orm.storage_uri,
        created_at=orm.created_at,
    )


class ParsingService:
    def __init__(
        self,
        source_doc_repo: SourceDocumentRepository,
        parse_run_repo: ParseRunRepository,
        parsed_doc_repo: ParsedDocumentRepository,
        storage: StorageService,
        clients: Dict[ParserKind, Any],
    ) -> None:
        self._source_doc_repo = source_doc_repo
        self._parse_run_repo = parse_run_repo
        self._parsed_doc_repo = parsed_doc_repo
        self._storage = storage
        self._clients = clients

    async def ensure_source_document(
        self,
        *,
        bytes_: bytes,
        filename: str,
        mime_type: str,
    ) -> SourceDocumentCDM:
        """Store bytes (idempotent on sha256) and return a CDM SourceDocument."""
        from app.utils.file_validation import compute_checksum
        sha256 = compute_checksum(bytes_)
        storage_uri = await self._storage.save(bytes_, f"uploads/{sha256}/{filename}")
        orm, _ = await self._source_doc_repo.get_or_create_by_sha256(
            sha256=sha256,
            storage_uri=storage_uri,
            filename=filename,
            mime_type=mime_type,
            byte_size=len(bytes_),
        )
        return _source_orm_to_cdm(orm)

    async def parse_and_persist(
        self,
        *,
        source: SourceDocumentCDM,
        file_path: str,
        representation_kind: str,
        config: dict[str, Any],
        project_id: UUID,
    ) -> tuple[ParseRunCDM, ParsedDocumentCDM | None]:
        """Run parse with same-project reuse. Persists success, partial, and failure runs.

        The parser is read from ``config["parser"]`` (default: ``"llamaparse"``).
        Returns (run, parsed_doc-or-None).
          - parsed_doc is not None when run.status is SUCCEEDED or PARTIAL.
          - parsed_doc is None when run.status is FAILED.
        Raises ParseFailedError on terminal failure after the failed ParseRun is persisted.
        """
        parser = ParserKind(config.get("parser", ParserKind.LLAMAPARSE.value))
        config_hash = _compute_config_hash(config)
        source_uuid = UUID(source.id)

        existing = await self._parse_run_repo.get_latest_for_project(
            source_document_id=source_uuid,
            representation_kind=representation_kind,
            config_hash=config_hash,
            project_id=project_id,
        )
        if existing is not None:
            cdm_run = _run_orm_to_cdm(existing)
            if existing.status in ("succeeded", "partial"):
                doc_orm = await self._parsed_doc_repo.get_by_run(existing.id)
                return cdm_run, _doc_orm_to_cdm(doc_orm) if doc_orm else None
            return cdm_run, None

        runner = _RUNNERS.get(parser)
        if runner is None:
            raise ValueError(f"No runner registered for parser: {parser}")
        client = self._clients.get(parser)

        try:
            cdm_run, cdm_doc = await runner(
                source=source,
                file_path=file_path,
                representation_kind=representation_kind,
                config=config,
                client=client,
            )
        except ParseRunError as err:
            await self._persist_run(err.run, config_hash, source_uuid)
            raise ParseFailedError(str(err)) from err

        orm_run = await self._persist_run(cdm_run, config_hash, source_uuid)
        orm_doc = await self._parsed_doc_repo.create(ParsedDocumentCreate(
            parse_run_id=orm_run.id,
            source_document_id=source_uuid,
            full_text=cdm_doc.full_text,
            full_markdown=cdm_doc.full_markdown,
            page_count=cdm_doc.page_count,
            block_count=len(cdm_doc.blocks),
            content=cdm_doc.model_dump(),
        ))
        return _run_orm_to_cdm(orm_run), _doc_orm_to_cdm(orm_doc)

    async def _persist_run(
        self,
        cdm_run: ParseRunCDM,
        config_hash: str,
        source_uuid: UUID,
    ) -> ParseRunORM:
        return await self._parse_run_repo.create(ParseRunCreate(
            id=UUID(cdm_run.id),
            source_document_id=source_uuid,
            parser=cdm_run.parser.value,
            parser_version=cdm_run.parser_version,
            representation_kind=cdm_run.representation_kind,
            config=dict(cdm_run.config),
            config_hash=config_hash,
            status=cdm_run.status.value,
            started_at=cdm_run.started_at,
            finished_at=cdm_run.finished_at,
            duration_ms=cdm_run.duration_ms,
            cost=dict(cdm_run.cost),
            input_tokens=cdm_run.input_tokens,
            output_tokens=cdm_run.output_tokens,
            warnings=list(cdm_run.warnings),
            failed_pages=list(cdm_run.failed_pages),
            provider_refs=dict(cdm_run.provider_refs),
            raw_payload=cdm_run.raw_payload,
            error=cdm_run.error,
        ))
```

- [ ] **Step 4: Update dependencies/documents.py**

Replace `backend/app/dependencies/documents.py` with:

```python
"""Dependencies for document-related operations."""
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llamaindex import LlamaIndexExtractor
from app.adapters.storage import LocalStorageService
from app.cdm.models import ParserKind
from app.config import settings
from app.ports import DocumentExtractor, StorageService
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.services.parsing.parsing_service import ParsingService


@lru_cache()
def get_storage_service() -> StorageService:
    return LocalStorageService(base_path=settings.DOCUMENT_STORAGE_PATH)


@lru_cache()
def get_document_extractor() -> DocumentExtractor:
    return LlamaIndexExtractor()


def get_llamaparse_client() -> Any:
    from llama_cloud import AsyncLlamaCloud
    if settings.LLAMA_CLOUD_KEY:
        return AsyncLlamaCloud(api_key=settings.LLAMA_CLOUD_KEY)
    return None


def get_landingai_client() -> Any:
    from landingai_ade import LandingAIADE
    if settings.VISION_AGENT_API_KEY:
        return LandingAIADE(api_key=settings.VISION_AGENT_API_KEY)
    return None


def get_parsing_service(db: AsyncSession) -> ParsingService:
    return ParsingService(
        source_doc_repo=SourceDocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        storage=get_storage_service(),
        clients={
            ParserKind.LLAMAPARSE: get_llamaparse_client(),
            ParserKind.LANDING_AI: get_landingai_client(),
        },
    )
```

- [ ] **Step 5: Update document_service.py**

Find the `ParsingService(...)` call in `backend/app/services/document_service.py` (around line 569) and replace:

```python
    service = ParsingService(
        source_doc_repo=source_doc_repo,
        parse_run_repo=parse_run_repo,
        parsed_doc_repo=parsed_doc_repo,
        storage=storage_service,
        clients={
            ParserKind.LLAMAPARSE: llamaparse_client,
        },
    )
```

Also add the import at the top of the function or at the module level where `ParserKind` is used:

```python
from app.cdm.models import ParserKind
```

(Check if it's already imported; if `ParserKind` is already imported at the top of document_service.py, skip this.)

- [ ] **Step 6: Run tests to verify**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_parsing_service.py -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 7: Run full test suite**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/parsing/parsing_service.py \
        backend/app/dependencies/documents.py \
        backend/app/services/document_service.py \
        backend/tests/services/parsing/test_parsing_service.py
git commit -m "refactor(parsing): decouple ParsingService from LlamaParse, dispatch by config"
```

---

## Task 5: Implement LandingAIAdapter

**Files:**
- Create: `backend/app/cdm/adapters/landing_ai.py`
- Create: `backend/tests/cdm/test_landing_ai_adapter.py`

- [ ] **Step 1: Write failing tests with a synthetic fixture**

Create `backend/tests/cdm/test_landing_ai_adapter.py`:

```python
"""Unit tests for LandingAIAdapter using a hand-crafted minimal fixture."""
from __future__ import annotations

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.landing_ai import LandingAIAdapter
from app.cdm.models import BlockRole, ParsedDocument, ParserKind


SOURCE_DOC_ID = "src-0000"
PARSE_RUN_ID = "run-0000"

_META = SourceMeta(
    source_document_id=SOURCE_DOC_ID,
    parse_run_id=PARSE_RUN_ID,
    filename="test.jpg",
    sha256="a" * 64,
)

MINIMAL_RAW = {
    "chunks": [
        {
            "id": "chunk-uuid-1",
            "type": "text",
            "markdown": "Hello world.",
            "grounding": {
                "page": 0,
                "box": {"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.2},
            },
        },
        {
            "id": "chunk-uuid-2",
            "type": "table",
            "markdown": (
                "<table id='page-0'>"
                "<tr><th id='r0c0'>Name</th><th id='r0c1'>Value</th></tr>"
                "<tr><td id='r1c0'>Alpha</td><td id='r1c1'>1</td></tr>"
                "</table>"
            ),
            "grounding": {
                "page": 0,
                "box": {"left": 0.1, "top": 0.3, "right": 0.9, "bottom": 0.8},
            },
        },
    ],
    "markdown": "Hello world.\n\n<!-- PAGE BREAK -->\n",
    "metadata": {
        "filename": "test.jpg",
        "page_count": 1,
        "duration_ms": 800,
        "credit_usage": 0.5,
        "job_id": "job-abc",
        "version": "dpt-2-latest",
        "failed_pages": [],
    },
    "splits": [{"class_": "full", "pages": [0]}],
    "grounding": {
        "chunk-uuid-1": {
            "type": "chunkText",
            "confidence": 0.97,
            "low_confidence_spans": [],
        },
        "chunk-uuid-2": {
            "type": "chunkTable",
            "confidence": 0.92,
            "low_confidence_spans": [],
        },
        "r0c0": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 0, "col": 0, "rowspan": 1, "colspan": 1}, "confidence": 0.95},
        "r0c1": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 0, "col": 1, "rowspan": 1, "colspan": 1}, "confidence": 0.94},
        "r1c0": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 1, "col": 0, "rowspan": 1, "colspan": 1}, "confidence": 0.93},
        "r1c1": {"type": "tableCell", "position": {"chunk_id": "chunk-uuid-2", "row": 1, "col": 1, "rowspan": 1, "colspan": 1}, "confidence": 0.91},
    },
}


@pytest.fixture
def doc() -> ParsedDocument:
    return LandingAIAdapter().adapt(MINIMAL_RAW, _META)


def test_ids_are_deterministic(doc):
    # IDs must use source_doc_id:pN:bN scheme, not provider UUIDs
    for block in doc.blocks:
        assert block.id.startswith(SOURCE_DOC_ID)


def test_provider_uuid_in_extras(doc):
    assert doc.blocks[0].parser_extras["landing_ai_chunk_id"] == "chunk-uuid-1"


def test_page_indexing_zero_based(doc):
    for block in doc.blocks:
        assert block.page_index == 0


def test_bbox_normalized(doc):
    for block in doc.blocks:
        if block.bbox:
            assert 0.0 <= block.bbox.x0 <= block.bbox.x1 <= 1.0
            assert 0.0 <= block.bbox.y0 <= block.bbox.y1 <= 1.0


def test_block_roles(doc):
    roles = {b.role for b in doc.blocks}
    assert BlockRole.PARAGRAPH in roles
    assert BlockRole.TABLE in roles


def test_table_cells_parsed(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    assert table_block.table is not None
    assert len(table_block.table.cells) == 4
    texts = {c.text for c in table_block.table.cells}
    assert "Name" in texts
    assert "Alpha" in texts


def test_table_cell_header_flag(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    headers = [c for c in table_block.table.cells if c.is_header]
    assert len(headers) == 2


def test_table_html_preserved(doc):
    table_block = next(b for b in doc.blocks if b.role == BlockRole.TABLE)
    assert table_block.table.html is not None
    assert "<table" in table_block.table.html


def test_quality_from_grounding(doc):
    text_block = next(b for b in doc.blocks if b.role == BlockRole.PARAGRAPH)
    assert text_block.quality is not None
    assert text_block.quality.confidence == pytest.approx(0.97)


def test_full_markdown_populated(doc):
    assert doc.full_markdown is not None
    assert len(doc.full_markdown) > 0


def test_splits_in_parser_extras(doc):
    assert "landing_ai_splits" in doc.parser_extras


def test_page_count(doc):
    assert doc.page_count == 1
    assert len(doc.pages) == 1


def test_page_block_ids_consistent(doc):
    all_block_ids = {b.id for b in doc.blocks}
    for page in doc.pages:
        for bid in page.block_ids:
            assert bid in all_block_ids


def test_source_ids_wired(doc):
    assert doc.source_document_id == SOURCE_DOC_ID
    assert doc.parse_run_id == PARSE_RUN_ID


def test_round_trip(doc):
    assert ParsedDocument.model_validate_json(doc.model_dump_json()) == doc
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_adapter.py -o "addopts=" -v
```

Expected: FAIL — `app.cdm.adapters.landing_ai` doesn't exist yet.

- [ ] **Step 3: Create the adapter**

Create `backend/app/cdm/adapters/landing_ai.py`:

```python
"""Landing AI ADE adapter — maps ParseResponse output to CDM.

Input is ParseResponse.model_dump(mode="json") — a plain dict with top-level
keys: chunks, markdown, metadata, splits, grounding.
"""
from __future__ import annotations

import uuid
from html.parser import HTMLParser
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import (
    BBox,
    Block,
    BlockRole,
    Cell,
    Page,
    ParsedDocument,
    ParserKind,
    Quality,
    Table,
)


_ROLE_MAP: Dict[str, BlockRole] = {
    "text":        BlockRole.PARAGRAPH,
    "table":       BlockRole.TABLE,
    "figure":      BlockRole.FIGURE,
    "logo":        BlockRole.FIGURE,
    "attestation": BlockRole.OTHER,
    "scan_code":   BlockRole.FIGURE,
    "marginalia":  BlockRole.MARGINALIA,
}


def _map_role(chunk_type: str) -> BlockRole:
    return _ROLE_MAP.get(chunk_type, BlockRole.OTHER)


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


def _make_bbox(box: Dict[str, Any]) -> Optional[BBox]:
    if not box:
        return None
    l = float(box.get("left", 0.0))
    t = float(box.get("top", 0.0))
    r = float(box.get("right", 1.0))
    b = float(box.get("bottom", 1.0))
    return BBox(x0=l, y0=t, x1=r, y1=b, source_space="fraction", source_coords=(l, t, r, b))


# ---------------------------------------------------------------------------
# HTML table parser
# ---------------------------------------------------------------------------

class _TableHTMLParser(HTMLParser):
    """Extract rows × cells from an HTML table string."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: List[List[Dict[str, Any]]] = []
        self._cur_row: Optional[List[Dict[str, Any]]] = None
        self._cur_cell: Optional[Dict[str, Any]] = None
        self._text_buf: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        adict = dict(attrs)
        if tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            self._cur_cell = {
                "id": adict.get("id"),
                "is_header": tag == "th",
                "rowspan": int(adict.get("rowspan", 1)),
                "colspan": int(adict.get("colspan", 1)),
            }
            self._text_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cur_cell is not None:
            self._cur_cell["text"] = "".join(self._text_buf).strip()
            if self._cur_row is not None:
                self._cur_row.append(self._cur_cell)
            self._cur_cell = None
        elif tag == "tr" and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None

    def handle_data(self, data: str) -> None:
        if self._cur_cell is not None:
            self._text_buf.append(data)


def _parse_table(
    html_str: str,
    grounding_dict: Dict[str, Any],
) -> Optional[Table]:
    if not html_str or "<table" not in html_str.lower():
        return None
    parser = _TableHTMLParser()
    try:
        parser.feed(html_str)
    except Exception:
        return None
    if not parser.rows:
        return None

    cells: List[Cell] = []
    max_col = 0

    for row_idx, row in enumerate(parser.rows):
        col_idx = 0
        for cell_data in row:
            cell_id = cell_data.get("id")
            rowspan = cell_data["rowspan"]
            colspan = cell_data["colspan"]

            cell_quality: Optional[Quality] = None
            cell_bbox: Optional[BBox] = None

            ge = grounding_dict.get(cell_id) if cell_id else None
            if ge:
                conf = ge.get("confidence")
                if conf is not None:
                    cell_quality = Quality(confidence=float(conf))
                box = ge.get("box")
                if box:
                    cell_bbox = _make_bbox(box)

            cells.append(Cell(
                row=row_idx,
                col=col_idx,
                rowspan=rowspan,
                colspan=colspan,
                text=cell_data["text"],
                bbox=cell_bbox,
                quality=cell_quality,
                is_header=cell_data["is_header"],
            ))
            max_col = max(max_col, col_idx + colspan - 1)
            col_idx += colspan

    return Table(
        rows=len(parser.rows),
        cols=max_col + 1,
        cells=cells,
        html=html_str,
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class LandingAIAdapter:
    parser: ClassVar[ParserKind] = ParserKind.LANDING_AI

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        chunks: List[Dict[str, Any]] = raw.get("chunks") or []
        grounding_dict: Dict[str, Any] = raw.get("grounding") or {}

        pages_map: Dict[int, List[str]] = {}
        ro_by_page: Dict[int, int] = {}
        all_blocks: List[Block] = []

        for chunk in chunks:
            chunk_id = str(chunk.get("id", ""))
            chunk_type = str(chunk.get("type", "other"))
            chunk_grounding = chunk.get("grounding") or {}
            page_index = int(chunk_grounding.get("page", 0))

            ro = ro_by_page.get(page_index, 0)
            block_id = _mint_block_id(source_meta.source_document_id, page_index, ro)
            ro_by_page[page_index] = ro + 1

            role = _map_role(chunk_type)
            bbox = _make_bbox(chunk_grounding.get("box") or {})

            # Quality from grounding dict
            quality: Optional[Quality] = None
            ge = grounding_dict.get(chunk_id) or {}
            if ge:
                conf = ge.get("confidence")
                lcs = ge.get("low_confidence_spans") or []
                if conf is not None or lcs:
                    quality = Quality(
                        confidence=float(conf) if conf is not None else None,
                        low_confidence_spans=[(s[0], s[1]) for s in lcs] if lcs else [],
                    )

            chunk_md: Optional[str] = chunk.get("markdown") or None

            # Build Table for table chunks
            table: Optional[Table] = None
            text = ""
            if role == BlockRole.TABLE and chunk_md:
                table = _parse_table(chunk_md, grounding_dict)
                if table:
                    text = " | ".join(c.text for c in table.cells if c.text)
            else:
                text = chunk_md or ""

            block = Block(
                id=block_id,
                role=role,
                native_type=chunk_type,
                text=text,
                markdown=chunk_md,
                page_index=page_index,
                bbox=bbox,
                reading_order=ro,
                quality=quality,
                table=table,
                parser_extras={"landing_ai_chunk_id": chunk_id},
            )
            all_blocks.append(block)
            pages_map.setdefault(page_index, []).append(block_id)

        page_count = (max(pages_map.keys()) + 1) if pages_map else 0
        pages = [
            Page(index=pi, block_ids=pages_map.get(pi, []))
            for pi in range(page_count)
        ]

        full_markdown = raw.get("markdown") or (
            "\n\n".join(b.markdown for b in all_blocks if b.markdown) or None
        )
        full_text = "\n\n".join(b.text for b in all_blocks if b.text) or None

        doc_extras: Dict[str, Any] = {}
        if raw.get("splits"):
            doc_extras["landing_ai_splits"] = raw["splits"]

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=page_count,
            pages=pages,
            blocks=all_blocks,
            full_text=full_text,
            full_markdown=full_markdown,
            parser_extras=doc_extras,
        )
```

- [ ] **Step 4: Run tests**

```bash
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_adapter.py -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/landing_ai.py backend/tests/cdm/test_landing_ai_adapter.py
git commit -m "feat(cdm): implement LandingAIAdapter"
```

---

## Task 6: Implement `landingai_runner.py`

**Files:**
- Create: `backend/app/services/parsing/landingai_runner.py`
- Create: `backend/tests/services/parsing/test_landingai_runner.py`

- [ ] **Step 1: Write failing tests with mock client**

Create `backend/tests/services/parsing/test_landingai_runner.py`:

```python
"""Tests for run_landingai using a mock SDK client."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.errors import LandingAIRunError
from app.services.parsing.landingai_runner import run_landingai


def _source() -> SourceDocument:
    return SourceDocument(
        id=str(uuid4()),
        sha256="b" * 64,
        filename="test.jpg",
        storage_uri="local://test.jpg",
        created_at=datetime.now(timezone.utc),
    )


def _completed_response(source_id: str) -> Any:
    """Simulate a completed parse_jobs.get() response."""
    raw = {
        "chunks": [
            {
                "id": "chunk-1",
                "type": "text",
                "markdown": "Hello",
                "grounding": {"page": 0, "box": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.1}},
            }
        ],
        "markdown": "Hello",
        "metadata": {
            "filename": "test.jpg",
            "page_count": 1,
            "duration_ms": 500,
            "credit_usage": 0.5,
            "job_id": "job-xyz",
            "version": "dpt-2-latest",
            "failed_pages": [],
        },
        "splits": [],
        "grounding": {
            "chunk-1": {"type": "chunkText", "confidence": 0.9, "low_confidence_spans": []},
        },
    }
    data = MagicMock()
    data.model_dump = MagicMock(return_value=raw)
    return SimpleNamespace(status="completed", data=data)


def _make_client(source_id: str, fail: bool = False) -> Any:
    job = SimpleNamespace(job_id="job-xyz")
    if fail:
        poll_response = SimpleNamespace(status="failed", data=None)
    else:
        poll_response = _completed_response(source_id)
    client = MagicMock()
    client.parse_jobs.create.return_value = job
    client.parse_jobs.get.return_value = poll_response
    return client


@pytest.mark.asyncio
async def test_run_landingai_success(tmp_path):
    src = _source()
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff")  # minimal JPEG header
    client = _make_client(src.id)

    run, doc = await run_landingai(
        source=src,
        file_path=str(f),
        representation_kind="extract_rich",
        config={"model": "dpt-2-latest"},
        client=client,
    )

    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.parser == ParserKind.LANDING_AI
    assert run.provider_refs.get("landingai_job_id") == "job-xyz"
    assert run.parser_version == "dpt-2-latest"
    assert run.cost.get("credits") == pytest.approx(0.5)
    assert doc is not None
    assert doc.source_document_id == src.id
    assert doc.page_count == 1


@pytest.mark.asyncio
async def test_run_landingai_failure_raises_error(tmp_path):
    src = _source()
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff")
    client = _make_client(src.id, fail=True)

    with pytest.raises(LandingAIRunError) as exc_info:
        await run_landingai(
            source=src,
            file_path=str(f),
            representation_kind="extract_rich",
            config={"model": "dpt-2-latest"},
            client=client,
        )

    err = exc_info.value
    assert err.run.status == ParseRunStatus.FAILED
    assert err.run.parser == ParserKind.LANDING_AI


@pytest.mark.asyncio
async def test_run_landingai_timeout_raises_error(tmp_path):
    src = _source()
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff")

    # Client always returns "running" — will time out immediately with poll_timeout_s=0
    job = SimpleNamespace(job_id="job-xyz")
    running_response = SimpleNamespace(status="running", data=None)
    client = MagicMock()
    client.parse_jobs.create.return_value = job
    client.parse_jobs.get.return_value = running_response

    with pytest.raises(LandingAIRunError) as exc_info:
        await run_landingai(
            source=src,
            file_path=str(f),
            representation_kind="extract_rich",
            config={"model": "dpt-2-latest", "poll_timeout_s": 0, "poll_interval_s": 0.01},
            client=client,
        )

    assert exc_info.value.run.status == ParseRunStatus.FAILED
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_landingai_runner.py -o "addopts=" -v
```

Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Create the runner**

Create `backend/app/services/parsing/landingai_runner.py`:

```python
"""Drives Landing AI ADE end-to-end: parse_jobs API → ParseRun + ParsedDocument.

Always uses the async parse_jobs path (supports documents of any size).
SDK calls are sync; wrapped in asyncio.to_thread to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.landing_ai import LandingAIAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import LandingAIRunError


async def run_landingai(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    """Submit a Landing AI parse job, poll to completion, and adapt to CDM.

    Raises LandingAIRunError (carrying the failed ParseRun) on SDK failure,
    job failure, or timeout.
    """
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    model = config.get("model", "dpt-2-latest")
    poll_interval: float = float(config.get("poll_interval_s", 5))
    poll_timeout: float = float(config.get("poll_timeout_s", 600))

    def _create_job() -> Any:
        return client.parse_jobs.create(document=Path(file_path), model=model)

    def _get_job(job_id: str) -> Any:
        return client.parse_jobs.get(job_id)

    try:
        job = await asyncio.to_thread(_create_job)
        job_id: str = job.job_id

        elapsed = 0.0
        response = None
        while elapsed < poll_timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            response = await asyncio.to_thread(_get_job, job_id)
            if response.status == "completed":
                break
            if response.status == "failed":
                raise RuntimeError(f"Landing AI job {job_id} reported status=failed")
        else:
            raise TimeoutError(
                f"Landing AI job {job_id} did not complete within {poll_timeout}s"
            )

    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        provider_refs = {"landingai_job_id": job_id} if "job_id" in dir() else {}  # type: ignore[name-defined]
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LANDING_AI,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            provider_refs=provider_refs,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise LandingAIRunError(f"Landing AI run failed: {exc}", run=failed) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    raw = response.data.model_dump(mode="json")
    meta: Dict[str, Any] = raw.get("metadata") or {}

    # Use API-reported duration if available; fall back to wall-clock
    api_duration_ms = meta.get("duration_ms") or duration_ms

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LANDING_AI,
        parser_version=meta.get("version"),
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=api_duration_ms,
        cost={"credits": meta["credit_usage"]} if meta.get("credit_usage") is not None else {},
        failed_pages=list(meta.get("failed_pages") or []),
        provider_refs={"landingai_job_id": job_id},
        raw_payload=raw,
    )

    adapter = LandingAIAdapter()
    doc = adapter.adapt(raw, SourceMeta(
        source_document_id=source.id,
        parse_run_id=run.id,
        filename=source.filename,
        sha256=source.sha256,
    ))
    return run, doc
```

- [ ] **Step 4: Run tests**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_landingai_runner.py -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/landingai_runner.py \
        backend/tests/services/parsing/test_landingai_runner.py
git commit -m "feat(cdm): implement landingai_runner with async parse_jobs polling"
```

---

## Task 7: Wire the Landing AI runner into the dispatch table

**Files:**
- Modify: `backend/app/services/parsing/parsing_service.py` (top of file — `_RUNNERS` dict)

- [ ] **Step 1: Update _RUNNERS in parsing_service.py**

At the top of `backend/app/services/parsing/parsing_service.py`, update `_RUNNERS`:

```python
from app.services.parsing.landingai_runner import run_landingai
from app.services.parsing.llamaparse_runner import run_llamaparse

_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
}
```

- [ ] **Step 2: Run full test suite**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/parsing/parsing_service.py
git commit -m "feat(cdm): register landingai_runner in ParsingService dispatch table"
```

---

## Task 8: Generate real fixture from Landing AI API

**Files:**
- Create: `backend/scripts/generate_landingai_fixture.py` (run once, not committed to main)
- Create: `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.json`

- [ ] **Step 1: Ensure the eval/fixtures directory exists**

```bash
mkdir -p backend/app/cdm/eval/fixtures
touch backend/app/cdm/eval/__init__.py
touch backend/app/cdm/eval/fixtures/.gitkeep
```

- [ ] **Step 2: Create the fixture generation script**

Create `backend/scripts/generate_landingai_fixture.py`:

```python
#!/usr/bin/env python3
"""One-off script: call Landing AI parse_jobs with cleanshelf image, save fixture JSON.

Usage:
    VISION_AGENT_API_KEY=<key> uv run --directory backend python scripts/generate_landingai_fixture.py
"""
import json
import os
import time
from pathlib import Path

from landingai_ade import LandingAIADE

API_KEY = os.environ["VISION_AGENT_API_KEY"]
DOCUMENT = Path(__file__).parent.parent.parent / "_scratch" / "cleanshelf-12-4-26.jpg"
OUTPUT = Path(__file__).parent.parent / "app" / "cdm" / "eval" / "fixtures" / "landing_ai_cleanshelf.json"


def main() -> None:
    client = LandingAIADE(api_key=API_KEY)

    print(f"Submitting {DOCUMENT.name} ...")
    job = client.parse_jobs.create(document=DOCUMENT, model="dpt-2-latest")
    job_id = job.job_id
    print(f"Job ID: {job_id}")

    while True:
        response = client.parse_jobs.get(job_id)
        print(f"  status={response.status}")
        if response.status == "completed":
            break
        if response.status == "failed":
            raise RuntimeError(f"Job {job_id} failed")
        time.sleep(5)

    raw = response.data.model_dump(mode="json")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {OUTPUT}")
    print(f"  chunks:    {len(raw.get('chunks', []))}")
    print(f"  pages:     {raw.get('metadata', {}).get('page_count')}")
    print(f"  credits:   {raw.get('metadata', {}).get('credit_usage')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the script**

Make sure `VISION_AGENT_API_KEY` is set (it's in `.env.local`):

```bash
export VISION_AGENT_API_KEY=$(grep VISION_AGENT_API_KEY /home/asa/rag-admin/.env.local | cut -d= -f2)
uv run --directory backend python scripts/generate_landingai_fixture.py
```

Expected output: prints job ID, polls until `status=completed`, reports chunk/page/credit counts, saves to `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.json`.

- [ ] **Step 4: Verify the fixture is well-formed**

```bash
uv run --directory backend python -c "
import json
from pathlib import Path
raw = json.loads(Path('app/cdm/eval/fixtures/landing_ai_cleanshelf.json').read_text())
print('chunks:', len(raw.get('chunks', [])))
print('pages:', raw.get('metadata', {}).get('page_count'))
print('grounding keys:', len(raw.get('grounding', {})))
print('splits:', len(raw.get('splits', [])))
" --directory backend
```

Expected: non-zero chunks and grounding keys.

- [ ] **Step 5: Commit the fixture**

```bash
git add backend/app/cdm/eval/ 
git commit -m "test(cdm): add Landing AI cleanshelf fixture from real API call"
```

---

## Task 9: Structural invariant tests and snapshot

**Files:**
- Create: `backend/tests/cdm/test_landing_ai_structural.py`
- Create: `backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.expected.json`

- [ ] **Step 1: Write structural invariant tests against real fixture**

Create `backend/tests/cdm/test_landing_ai_structural.py`:

```python
"""Structural invariant tests for LandingAIAdapter against the real cleanshelf fixture.

These tests run offline — the fixture is committed JSON, no API call required.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.landing_ai import LandingAIAdapter
from app.cdm.models import ParsedDocument

FIXTURE = Path(__file__).parent.parent.parent / "app" / "cdm" / "eval" / "fixtures" / "landing_ai_cleanshelf.json"
SNAPSHOT = FIXTURE.with_name("landing_ai_cleanshelf.expected.json")

_META = SourceMeta(
    source_document_id="structural-test-src",
    parse_run_id="structural-test-run",
    filename="cleanshelf-12-4-26.jpg",
    sha256="0" * 64,
)


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc(raw) -> ParsedDocument:
    return LandingAIAdapter().adapt(raw, _META)


def test_page_count_matches_pages(doc):
    assert doc.page_count == len(doc.pages)


def test_all_block_page_indexes_valid(doc):
    for block in doc.blocks:
        assert 0 <= block.page_index < doc.page_count, (
            f"Block {block.id} has page_index={block.page_index}, "
            f"page_count={doc.page_count}"
        )


def test_all_bboxes_normalized(doc):
    for block in doc.blocks:
        if block.bbox:
            assert 0.0 <= block.bbox.x0 <= block.bbox.x1 <= 1.0, f"x out of range: {block.bbox}"
            assert 0.0 <= block.bbox.y0 <= block.bbox.y1 <= 1.0, f"y out of range: {block.bbox}"
        if block.table:
            for cell in block.table.cells:
                if cell.bbox:
                    assert 0.0 <= cell.bbox.x0 <= cell.bbox.x1 <= 1.0
                    assert 0.0 <= cell.bbox.y0 <= cell.bbox.y1 <= 1.0


def test_all_blocks_have_role_and_native_type(doc):
    for block in doc.blocks:
        assert block.role is not None
        assert block.native_type


def test_page_block_ids_reference_existing_blocks(doc):
    all_ids = {b.id for b in doc.blocks}
    for page in doc.pages:
        for bid in page.block_ids:
            assert bid in all_ids, f"Page {page.index} references unknown block_id {bid}"


def test_full_markdown_non_empty(doc):
    assert doc.full_markdown and len(doc.full_markdown) > 0


def test_source_ids_wired(doc):
    assert doc.source_document_id == _META.source_document_id
    assert doc.parse_run_id == _META.parse_run_id


def test_round_trip(doc):
    serialised = doc.model_dump_json()
    restored = ParsedDocument.model_validate_json(serialised)
    assert restored == doc


def test_deterministic_block_ids(doc, raw):
    # IDs must NOT be the provider's UUIDs — they must use the minted scheme
    for block in doc.blocks:
        assert block.id.startswith(_META.source_document_id), (
            f"Block ID {block.id!r} does not start with source_document_id"
        )
        # Provider UUID should be in parser_extras, not the block ID
        assert "landing_ai_chunk_id" in block.parser_extras


def test_snapshot(doc):
    """Fail if adapter output changes unexpectedly. Update snapshot intentionally."""
    current = doc.model_dump_json(indent=2)
    if not SNAPSHOT.exists():
        SNAPSHOT.write_text(current, encoding="utf-8")
        pytest.skip("Snapshot created — run again to verify")
    expected = SNAPSHOT.read_text(encoding="utf-8")
    # Strip the top-level id (UUID) before comparing — it's random per run
    import json as _json
    cur_dict = _json.loads(current)
    exp_dict = _json.loads(expected)
    cur_dict.pop("id", None)
    exp_dict.pop("id", None)
    assert cur_dict == exp_dict, (
        "Adapter output changed. If intentional, delete the snapshot and re-run."
    )
```

- [ ] **Step 2: Run tests (first run creates snapshot)**

```bash
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_structural.py -o "addopts=" -v
```

Expected: most tests pass; `test_snapshot` skips with "Snapshot created".

- [ ] **Step 3: Run again to verify snapshot**

```bash
uv run --directory backend python -m pytest tests/cdm/test_landing_ai_structural.py -o "addopts=" -v
```

Expected: all pass including `test_snapshot`.

- [ ] **Step 4: Run full test suite**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/eval/fixtures/landing_ai_cleanshelf.expected.json \
        backend/tests/cdm/test_landing_ai_structural.py
git commit -m "test(cdm): structural invariant tests and snapshot for Landing AI adapter"
```

---

## Self-Review

**Spec coverage check:**
- §3.1 chunk→role mapping ✅ Task 5
- §3.2 BBox identity conversion ✅ Task 5
- §3.3 page indexing already 0-indexed ✅ Task 5
- §3.4 deterministic block IDs ✅ Task 5 (mints `{src}:p{n}:b{n}`, stores UUID in parser_extras)
- §3.5 grounding dict → quality + cell confidence ✅ Task 5
- §3.6 HTML table parsing ✅ Task 5
- §3.7 pages from chunk grouping ✅ Task 5
- §3.8 full_markdown from response, splits in parser_extras ✅ Task 5 (parser_extras added Task 2)
- §4 async runner with parse_jobs ✅ Task 6
- §4 poll timeout + interval from config ✅ Task 6
- §4 ParseRun fields from metadata ✅ Task 6
- §5 clients dict constructor ✅ Task 4
- §5 parser read from config ✅ Task 4
- §5 _RUNNERS dispatch table ✅ Task 7
- §6 ParseRunError base class ✅ Task 3
- §7 VISION_AGENT_API_KEY ✅ Task 1
- §8 real fixture from cleanshelf ✅ Task 8
- §8 structural invariants ✅ Task 9
- §8 snapshot ✅ Task 9
- §9 call-site impact (parse_and_persist callers) ✅ Task 4 (document_service.py updated)
