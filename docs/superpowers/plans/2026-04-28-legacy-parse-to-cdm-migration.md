# Legacy Parse → CDM Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the legacy `parse_results` path and route all three parsers (liteparse, llamaparse, landing_ai) exclusively through the CDM pipeline.

**Architecture:** Add a `LiteParseAdapter` + `run_liteparse` runner that wraps the existing `LlamaIndexExtractor`, wire it into `ParsingService`, then remove the `_CDM_PARSER_TYPES` gate so every upload and re-parse uses `process_cdm_parsing`. Delete the legacy `ParseService`, `ParseResultRepository`, `ParseResult` model, and `parse_results` router, then drop the `parse_results` table in a migration. Mirror the rename on the frontend (`simple` → `liteparse`) and replace the legacy `useParseResults`/`ParseResultViewer` pair with the CDM hooks already in place.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, React 18, TypeScript, Vitest, Pytest

---

## File Map

### Create
- `backend/app/cdm/adapters/liteparse.py` — `LiteParseAdapter`
- `backend/app/services/parsing/liteparse_runner.py` — `run_liteparse`
- `backend/tests/cdm/adapters/test_liteparse_adapter.py`
- `backend/tests/services/parsing/test_liteparse_runner.py`
- `backend/alembic/versions/<hash>_drop_parse_results_table.py`

### Modify
- `backend/app/services/parsing/errors.py` — add `LiteParseRunError`
- `backend/app/services/parsing/parsing_service.py` — add `LITEPARSE` to `_RUNNERS`
- `backend/app/dependencies/documents.py` — add `LITEPARSE` client to `get_parsing_service`, remove `USE_CDM_PARSER` guard
- `backend/app/services/document_service.py` — delete `process_document_extraction`; remove `document_extractor` from `DocumentService.__init__`; add `get_document_extractor()` inline in `process_cdm_parsing` clients dict
- `backend/app/routers/documents.py` — remove `_CDM_PARSER_TYPES` gate; always CDM; rename `simple` → `liteparse`; add `POST /{document_id}/parse-runs` reparse endpoint; strip legacy imports
- `backend/app/main.py` — remove `parse_results` router import and `include_router`
- `backend/app/models/__init__.py` — remove `ParseResult`, `ParseResultStatus`
- `backend/app/config.py` — remove `USE_CDM_PARSER`
- `frontend/src/components/documents/ParseMethodSelector.tsx` — rename `simple` → `liteparse`
- `frontend/src/api/parseRuns.ts` — add `createParseRun`
- `frontend/src/api/parsing.ts` — remove `listParseResults`, `getParseResult`, `reparseDocument`
- `frontend/src/types/parsing.ts` — remove `ParseResult`, `ParseResultListItem`
- `frontend/src/pages/DocumentsPage.tsx` — remove `useParseResults`, `ParseResultViewer`; wire reparse to CDM
- `frontend/src/pages/ProjectDocumentsPage.tsx` — same changes as `DocumentsPage`
- `frontend/src/test/builders.ts` — remove `ParseResult` / `ParseResultListItem` builders

### Delete
- `backend/app/services/parse_service.py`
- `backend/app/repositories/parse_result_repository.py`
- `backend/app/models/parse_result.py`
- `backend/app/schemas/parse_result.py`
- `backend/app/adapters/parsing/llamaparse.py` (legacy adapter — distinct from `cdm/adapters/llamaparse.py`)
- `backend/app/adapters/parsing/registry.py`
- `backend/app/routers/parse_results.py`
- `backend/tests/repositories/test_parse_result_repository.py`
- `backend/tests/services/test_parse_service.py`
- `backend/tests/routers/test_parse_results.py`
- `backend/tests/adapters/test_llamaparse_adapter.py` (tests the legacy adapter)
- `frontend/src/hooks/useParseResults.ts`
- `frontend/src/hooks/useParseResults.test.ts`
- `frontend/src/components/documents/ParseResultViewer.tsx`
- `frontend/src/components/documents/ParseResultViewer.test.tsx`

---

## Task 1: Add `LiteParseRunError` to errors module

**Files:**
- Modify: `backend/app/services/parsing/errors.py`

- [ ] **Step 1: Add error class**

Open `backend/app/services/parsing/errors.py` and add after `LandingAIRunError`:

```python
class LiteParseRunError(ParseRunError):
    """Raised by liteparse_runner when local extraction fails."""
```

- [ ] **Step 2: Run existing error tests to verify no regression**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_errors.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/parsing/errors.py
git commit -m "feat(cdm): add LiteParseRunError to parsing errors"
```

---

## Task 2: LiteParseAdapter — TDD

**Files:**
- Create: `backend/app/cdm/adapters/liteparse.py`
- Create: `backend/tests/cdm/adapters/test_liteparse_adapter.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/cdm/adapters/test_liteparse_adapter.py`:

```python
import pytest
from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.liteparse import LiteParseAdapter
from app.cdm.models import BlockRole, ParserKind


SOURCE_META = SourceMeta(
    source_document_id="src-1",
    parse_run_id="run-1",
    filename="test.pdf",
    sha256="a" * 64,
)

TWO_PAGE_RAW = {
    "text": "[Page 1]\nhello world\n\n[Page 2]\nfoo bar",
    "page_count": 2,
    "page_boundaries": [
        {"page": 1, "start_char": 0, "end_char": 20},
        {"page": 2, "start_char": 22, "end_char": 40},
    ],
}


def test_adapter_parser_kind():
    assert LiteParseAdapter.parser == ParserKind.LITEPARSE


def test_two_pages_produces_two_pages_and_two_blocks():
    doc = LiteParseAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.page_count == 2
    assert len(doc.pages) == 2
    assert len(doc.blocks) == 2


def test_block_role_is_paragraph():
    doc = LiteParseAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert all(b.role == BlockRole.PARAGRAPH for b in doc.blocks)


def test_block_ids_are_unique_and_referenced_by_pages():
    doc = LiteParseAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    block_ids = {b.id for b in doc.blocks}
    assert len(block_ids) == 2
    for page in doc.pages:
        assert len(page.block_ids) == 1
        assert page.block_ids[0] in block_ids


def test_page_indices_are_zero_based():
    doc = LiteParseAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.pages[0].index == 0
    assert doc.pages[1].index == 1


def test_full_text_preserved():
    doc = LiteParseAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.full_text == TWO_PAGE_RAW["text"]


def test_source_and_run_ids_wired():
    doc = LiteParseAdapter().adapt(TWO_PAGE_RAW, SOURCE_META)
    assert doc.source_document_id == "src-1"
    assert doc.parse_run_id == "run-1"
    assert doc.source_filename == "test.pdf"


def test_fallback_when_no_page_boundaries():
    raw = {"text": "some text", "page_count": 1, "page_boundaries": []}
    doc = LiteParseAdapter().adapt(raw, SOURCE_META)
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert len(doc.blocks) == 1
    assert doc.blocks[0].text == "some text"


def test_empty_raw_produces_single_empty_page():
    doc = LiteParseAdapter().adapt({}, SOURCE_META)
    assert doc.page_count == 1
    assert len(doc.pages) == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/cdm/adapters/test_liteparse_adapter.py -v -o "addopts="
```

Expected: `ModuleNotFoundError` or `ImportError` — the module does not exist yet.

- [ ] **Step 3: Implement LiteParseAdapter**

Create `backend/app/cdm/adapters/liteparse.py`:

```python
"""LiteParseAdapter — maps LlamaIndexExtractor output to CDM."""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import Block, BlockRole, Page, ParsedDocument, ParserKind


class LiteParseAdapter:
    parser: ClassVar[ParserKind] = ParserKind.LITEPARSE

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        """Convert LlamaIndexExtractor result dict to CDM ParsedDocument.

        Expected keys in raw:
          text (str): full extracted text
          page_count (int): number of pages
          page_boundaries (list[dict]): each dict has page, start_char, end_char
        """
        full_text: str = raw.get("text") or ""
        page_boundaries: list = raw.get("page_boundaries") or []

        pages: list[Page] = []
        blocks: list[Block] = []

        for pb in page_boundaries:
            page_number: int = pb.get("page", 1)
            page_index = page_number - 1
            start_char: int = pb.get("start_char", 0)
            end_char: int = pb.get("end_char", len(full_text))
            page_text = full_text[start_char:end_char].strip()

            block_id = f"{source_meta.source_document_id}:p{page_index}:b0"
            blocks.append(Block(
                id=block_id,
                role=BlockRole.PARAGRAPH,
                native_type="text",
                text=page_text,
                page_index=page_index,
            ))
            pages.append(Page(index=page_index, block_ids=[block_id]))

        if not pages:
            block_id = f"{source_meta.source_document_id}:p0:b0"
            blocks = [Block(
                id=block_id,
                role=BlockRole.PARAGRAPH,
                native_type="text",
                text=full_text.strip(),
                page_index=0,
            )]
            pages = [Page(index=0, block_ids=[block_id])]

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=blocks,
            full_text=full_text or None,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/cdm/adapters/test_liteparse_adapter.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/liteparse.py backend/tests/cdm/adapters/test_liteparse_adapter.py
git commit -m "feat(cdm): add LiteParseAdapter for local text extraction"
```

---

## Task 3: LiteParse runner — TDD

**Files:**
- Create: `backend/app/services/parsing/liteparse_runner.py`
- Create: `backend/tests/services/parsing/test_liteparse_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/parsing/test_liteparse_runner.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.ports.document_processing import ExtractionResult
from app.services.parsing.errors import LiteParseRunError
from app.services.parsing.liteparse_runner import run_liteparse


def _make_source() -> SourceDocument:
    return SourceDocument(
        id="src-1",
        sha256="a" * 64,
        filename="test.pdf",
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )


def _make_extractor(text: str = "hello", page_count: int = 1) -> AsyncMock:
    result = ExtractionResult(
        text=text,
        page_count=page_count,
        metadata={},
        page_boundaries=[{"page": 1, "start_char": 0, "end_char": len(text)}],
    )
    mock = AsyncMock()
    mock.extract = AsyncMock(return_value=result)
    return mock


@pytest.mark.asyncio
async def test_success_returns_run_and_doc():
    client = _make_extractor("hello world")
    run, doc = await run_liteparse(
        source=_make_source(),
        file_path="/tmp/test.pdf",
        representation_kind="extract_rich",
        config={"parser": "liteparse"},
        client=client,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.parser == ParserKind.LITEPARSE
    assert doc.full_text == "hello world"
    assert doc.page_count == 1


@pytest.mark.asyncio
async def test_extractor_called_with_file_path_and_mime_type():
    client = _make_extractor()
    source = _make_source()
    await run_liteparse(
        source=source,
        file_path="/tmp/doc.pdf",
        representation_kind="extract_rich",
        config={"parser": "liteparse"},
        client=client,
    )
    client.extract.assert_awaited_once_with("/tmp/doc.pdf", "application/pdf")


@pytest.mark.asyncio
async def test_extractor_failure_raises_liteparse_run_error():
    client = AsyncMock()
    client.extract = AsyncMock(side_effect=IOError("file not found"))
    with pytest.raises(LiteParseRunError) as exc_info:
        await run_liteparse(
            source=_make_source(),
            file_path="/tmp/missing.pdf",
            representation_kind="extract_rich",
            config={"parser": "liteparse"},
            client=client,
        )
    assert exc_info.value.run.status == ParseRunStatus.FAILED
    assert "file not found" in exc_info.value.run.error


@pytest.mark.asyncio
async def test_run_id_propagated_when_provided():
    client = _make_extractor()
    run, _ = await run_liteparse(
        source=_make_source(),
        file_path="/tmp/test.pdf",
        representation_kind="extract_rich",
        config={"parser": "liteparse"},
        client=client,
        parse_run_id="fixed-run-id",
    )
    assert run.id == "fixed-run-id"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_liteparse_runner.py -v -o "addopts="
```

Expected: `ModuleNotFoundError` — the runner does not exist yet.

- [ ] **Step 3: Implement the runner**

Create `backend/app/services/parsing/liteparse_runner.py`:

```python
"""Drives LiteParse end-to-end: LlamaIndexExtractor → ParseRun + ParsedDocument."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.liteparse import LiteParseAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import LiteParseRunError


async def run_liteparse(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,  # DocumentExtractor (LlamaIndexExtractor)
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    """Extract text locally via LlamaIndexExtractor and adapt to CDM.

    Raises LiteParseRunError (carries failed ParseRun) on extraction failure.
    """
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    try:
        extraction = await client.extract(file_path, source.mime_type)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LITEPARSE,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise LiteParseRunError(f"LiteParse failed: {exc}", run=failed) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LITEPARSE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )

    raw = {
        "text": extraction.text,
        "page_count": extraction.page_count,
        "page_boundaries": extraction.page_boundaries,
    }
    adapter = LiteParseAdapter()
    doc = adapter.adapt(raw, SourceMeta(
        source_document_id=source.id,
        parse_run_id=run.id,
        filename=source.filename,
        sha256=source.sha256,
    ))
    return run, doc
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/services/parsing/test_liteparse_runner.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/liteparse_runner.py backend/tests/services/parsing/test_liteparse_runner.py backend/app/services/parsing/errors.py
git commit -m "feat(cdm): add liteparse runner and LiteParseRunError"
```

---

## Task 4: Wire liteparse into ParsingService and dependencies

**Files:**
- Modify: `backend/app/services/parsing/parsing_service.py`
- Modify: `backend/app/dependencies/documents.py`
- Modify: `backend/app/services/document_service.py`

- [ ] **Step 1: Add liteparse to `_RUNNERS` in `parsing_service.py`**

In `backend/app/services/parsing/parsing_service.py`, update the imports and `_RUNNERS` dict:

```python
# Add to imports (after existing runner imports on line 24):
from app.services.parsing.liteparse_runner import run_liteparse

# Update _RUNNERS dict (lines 27-30):
_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
    ParserKind.LITEPARSE: run_liteparse,
}
```

- [ ] **Step 2: Add liteparse client to `get_parsing_service` in `dependencies/documents.py`**

In `backend/app/dependencies/documents.py`, update `get_parsing_service` to include the liteparse client (the local extractor, no API key needed):

```python
def get_parsing_service(db: AsyncSession) -> ParsingService:
    return ParsingService(
        source_doc_repo=SourceDocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        storage=get_storage_service(),
        clients={
            ParserKind.LLAMAPARSE: get_llamaparse_client(),
            ParserKind.LANDING_AI: get_landingai_client(),
            ParserKind.LITEPARSE: get_document_extractor(),
        },
    )
```

- [ ] **Step 3: Add liteparse client to `process_cdm_parsing` in `document_service.py`**

In `backend/app/services/document_service.py`, update the `service = ParsingService(...)` block inside `process_cdm_parsing` (around line 571). Add `LITEPARSE` to the clients dict:

```python
    from app.cdm.models import ParserKind
    from app.cdm.source import SourceDocument as SourceDocumentCDM
    from app.services.parsing.errors import ParseFailedError
    from app.services.parsing.parsing_service import ParsingService
    from app.dependencies.documents import get_document_extractor  # add this import

    # ... existing source_orm and doc fetching code ...

    service = ParsingService(
        source_doc_repo=source_doc_repo,
        parse_run_repo=parse_run_repo,
        parsed_doc_repo=parsed_doc_repo,
        storage=storage_service,
        clients={
            ParserKind.LLAMAPARSE: llamaparse_client,
            ParserKind.LANDING_AI: landingai_client,
            ParserKind.LITEPARSE: get_document_extractor(),
        },
    )
```

- [ ] **Step 4: Run the parsing service tests to verify wiring**

```bash
uv run --directory backend python -m pytest tests/services/parsing/ -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/parsing_service.py backend/app/dependencies/documents.py backend/app/services/document_service.py
git commit -m "feat(cdm): wire liteparse runner into ParsingService and process_cdm_parsing"
```

---

## Task 5: Add CDM reparse endpoint

**Files:**
- Modify: `backend/app/routers/documents.py`

This adds `POST /documents/{document_id}/parse-runs` so all parsers can be triggered via CDM. The legacy `POST /documents/{id}/parse` endpoint (in `parse_results.py`) will be deleted in Task 7.

- [ ] **Step 1: Add the request schema and endpoint to `documents.py`**

Near the top of `backend/app/routers/documents.py`, after the existing imports, add the schema. Then at the end of the file (after `list_document_parse_runs`), add the endpoint:

```python
# Add to imports section (near top of file, after other pydantic imports):
from pydantic import BaseModel as PydanticBaseModel

# Add schema near top of file (after imports):
class _ParseRunCreateRequest(PydanticBaseModel):
    parser_type: str = "liteparse"
    config: dict | None = None


# Add endpoint after list_document_parse_runs:
@router.post(
    "/{document_id}/parse-runs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a new CDM parse run for a document",
)
async def create_document_parse_run(
    document_id: UUID,
    body: _ParseRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    """Dispatch a new CDM parse run for an existing document."""
    from app.dependencies.documents import get_llamaparse_client, get_landingai_client
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.document_service import process_cdm_parsing

    document_repo = DocumentRepository(db)
    document = await document_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    if document.source_document_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no source_document_id; upload must be re-done via CDM path",
        )

    cfg = body.config or {}
    representation_kind = cfg.get("representation_kind", "extract_rich")
    parse_cfg = {k: v for k, v in cfg.items() if k != "representation_kind"}
    parse_cfg["parser"] = body.parser_type

    background_tasks.add_task(
        process_cdm_parsing,
        document_id=document_id,
        source_document_id=document.source_document_id,
        project_id=document.project_id,
        representation_kind=representation_kind,
        config=parse_cfg,
        document_repo=DocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        source_doc_repo=SourceDocumentRepository(db),
        storage_service=storage_service,
        llamaparse_client=get_llamaparse_client(),
        landingai_client=get_landingai_client(),
    )
    return {"status": "accepted"}
```

- [ ] **Step 2: Run existing CDM router tests to verify no breakage**

```bash
uv run --directory backend python -m pytest tests/routers/test_documents_cdm_router.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/documents.py
git commit -m "feat(cdm): add POST /documents/{id}/parse-runs reparse endpoint"
```

---

## Task 6: Simplify upload router — always CDM, rename simple → liteparse

**Files:**
- Modify: `backend/app/routers/documents.py`

Remove the `_CDM_PARSER_TYPES` gate, always route through CDM, and rename `simple` → `liteparse` in the parser type string throughout the router. Also remove the legacy path code blocks in both `upload_document` and `bulk_upload_documents`.

- [ ] **Step 1: Remove `document_extractor` from `DocumentService.__init__` first**

`get_document_service` (updated in Step 4) will no longer pass `document_extractor` to `DocumentService`. Make the constructor match before touching the router.

In `backend/app/services/document_service.py`, change `__init__` (around line 51) to:

```python
def __init__(
    self,
    document_repo: DocumentRepository,
    project_repo: ProjectRepository,
    storage_service: StorageService,
    parsing_service: ParsingService | None = None,
) -> None:
    self.document_repo = document_repo
    self.project_repo = project_repo
    self.storage_service = storage_service
    self.parsing_service = parsing_service
```

Remove the `DocumentExtractor` import from `app.ports` in `document_service.py` at the same time (line 18 — keep `StorageService`). Do **not** yet delete `process_document_extraction`; that goes in Task 7.

- [ ] **Step 2: Update `upload_document` in `documents.py`**

Replace the entire routing block (lines ~100–182 in `upload_document`) with the CDM-only path. The new version:

```python
    try:
        config_dict = None
        if parse_config:
            try:
                config_dict = json.loads(parse_config)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON in parse_config")

        file_content = await file.read()
        filename = file.filename or "upload.pdf"
        document = await document_service.initiate_upload(
            user_id=current_user.id,
            project_id=project_id,
            file_content=file_content,
            filename=filename,
            title=title,
            description=description,
            folder_id=folder_id,
            use_cdm=True,
        )

        if document.source_document_id is not None:
            representation_kind = (config_dict or {}).get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            parse_cfg["parser"] = parser_type
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document.id,
                source_document_id=document.source_document_id,
                project_id=project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=DocumentRepository(db),
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
                landingai_client=get_landingai_client(),
            )
        else:
            logger.error(
                "document.source_document_id is None after CDM upload for document %s",
                document.id,
            )

        return document

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
```

Also update the Form default in the function signature: `parser_type: str = Form("liteparse", ...)`.

- [ ] **Step 3: Update `bulk_upload_documents` in `documents.py`**

Replace the per-document background task dispatch block (lines ~265–323) with the CDM-only path:

```python
    use_cdm = True

    # Read all file contents
    file_data: list[tuple[bytes, str]] = []
    for f in files:
        content = await f.read()
        file_data.append((content, f.filename or "upload.pdf"))

    results: list[BulkUploadItemResult] = await document_service.initiate_bulk_upload(
        user_id=current_user.id,
        project_id=project_id,
        files=file_data,
        use_cdm=use_cdm,
    )

    for item in results:
        if item.document is None or not item.is_new:
            continue
        document_id = item.document.id

        if item.document.source_document_id is not None:
            representation_kind = (config_dict or {}).get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            parse_cfg["parser"] = parser_type
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document_id,
                source_document_id=item.document.source_document_id,
                project_id=project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=DocumentRepository(db),
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
                landingai_client=get_landingai_client(),
            )
        else:
            logger.error(
                "source_document_id is None after CDM bulk upload for document %s",
                document_id,
            )
```

Also update the Form default: `parser_type: str = Form("liteparse", ...)`.

- [ ] **Step 4: Remove legacy imports from `documents.py`**

Remove these lines from the imports at the top of `documents.py`:

```python
# Remove these imports:
from app.repositories.parse_result_repository import ParseResultRepository
from app.services.parse_service import ParseService, process_document_parsing
from app.adapters.parsing.registry import get_parser
```

Remove `_CDM_PARSER_TYPES = frozenset(...)` constant (line 43).

Remove `from app.services.document_service import ... BulkUploadItemResult` — keep `BulkUploadItemResult` import but remove `process_document_extraction` if it was in that import.

Also remove the `settings.USE_CDM_PARSER` guard in `get_document_service` — always create `parsing_service`:

```python
def get_document_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> DocumentService:
    from app.dependencies.documents import get_parsing_service
    document_repo = DocumentRepository(db)
    project_repo = ProjectRepository(db)
    parsing_service = get_parsing_service(db)
    return DocumentService(
        document_repo=document_repo,
        project_repo=project_repo,
        storage_service=storage_service,
        parsing_service=parsing_service,
    )
```

- [ ] **Step 5: Run CDM router tests**

```bash
uv run --directory backend python -m pytest tests/routers/test_documents_cdm_router.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/documents.py backend/app/services/document_service.py
git commit -m "refactor(router): remove _CDM_PARSER_TYPES gate, always CDM, simple→liteparse"
```

---

## Task 7: Delete legacy backend code and clean up DocumentService

**Files:**
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/config.py`
- Delete: `backend/app/services/parse_service.py`
- Delete: `backend/app/repositories/parse_result_repository.py`
- Delete: `backend/app/models/parse_result.py`
- Delete: `backend/app/schemas/parse_result.py`
- Delete: `backend/app/adapters/parsing/llamaparse.py`
- Delete: `backend/app/adapters/parsing/registry.py`
- Delete: `backend/app/routers/parse_results.py`
- Delete: `backend/tests/repositories/test_parse_result_repository.py`
- Delete: `backend/tests/services/test_parse_service.py`
- Delete: `backend/tests/routers/test_parse_results.py`
- Delete: `backend/tests/adapters/test_llamaparse_adapter.py`

- [ ] **Step 1: Delete `process_document_extraction` from `document_service.py`**

In `backend/app/services/document_service.py`, delete the entire `process_document_extraction` function (around lines 446–510). The `DocumentService.__init__` cleanup was already done in Task 6 Step 1.

- [ ] **Step 2: Remove `parse_results` router from `main.py`**

In `backend/app/main.py`, remove `parse_results` from the import line (line 7) and remove `app.include_router(parse_results.router, ...)` (line 164).

- [ ] **Step 3: Remove `ParseResult` from `models/__init__.py`**

In `backend/app/models/__init__.py`:
- Remove line: `from app.models.parse_result import ParseResult, ParseResultStatus`
- Remove `"ParseResult"` and `"ParseResultStatus"` from `__all__`

- [ ] **Step 4: Remove `USE_CDM_PARSER` from `config.py`**

In `backend/app/config.py`, remove the line:
```python
USE_CDM_PARSER: bool = True
```

Also remove any `settings.USE_CDM_PARSER` references that remain (check with `grep -rn USE_CDM_PARSER backend/`).

- [ ] **Step 5: Delete legacy files**

```bash
rm backend/app/services/parse_service.py
rm backend/app/repositories/parse_result_repository.py
rm backend/app/models/parse_result.py
rm backend/app/schemas/parse_result.py
rm backend/app/adapters/parsing/llamaparse.py
rm backend/app/adapters/parsing/registry.py
rm backend/app/routers/parse_results.py
rm backend/tests/repositories/test_parse_result_repository.py
rm backend/tests/services/test_parse_service.py
rm backend/tests/routers/test_parse_results.py
rm backend/tests/adapters/test_llamaparse_adapter.py
```

- [ ] **Step 6: Run full backend test suite to verify**

```bash
uv run --directory backend python -m pytest -v -o "addopts=" --ignore=tests/services/parsing/test_parsing_service.py
```

(The parsing_service test may exercise CDM reuse paths; if it needs updating, fix import errors.)

Expected: no `ImportError` from deleted modules; existing CDM tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(backend): delete legacy parse path (ParseService, parse_results, registry)"
```

---

## Task 8: Alembic migration — drop parse_results table

**Files:**
- Create: `backend/alembic/versions/<hash>_drop_parse_results_table.py`

- [ ] **Step 1: Generate the migration**

```bash
uv run --directory backend alembic revision --autogenerate -m "drop_parse_results_table"
```

This will create a new file in `backend/alembic/versions/`. The autogenerate output may not be perfect; verify and edit it in the next step.

- [ ] **Step 2: Verify and fix the migration file**

Open the generated file. Ensure the `upgrade` function drops the table and the `downgrade` function recreates it. The final content should match this structure:

```python
"""drop parse_results table

Revision ID: <generated_hash>
Revises: adec07f4ba7c
Create Date: ...
"""
from __future__ import annotations
from typing import Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "<generated_hash>"
down_revision: Union[str, None] = "adec07f4ba7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("parse_results")


def downgrade() -> None:
    op.create_table(
        "parse_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("parser_type", sa.String(), nullable=False),
        sa.Column("fidelity", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column("pages", sa.JSON(), nullable=True),
        sa.Column("document_structure", sa.JSON(), nullable=True),
        sa.Column("diagnostics", sa.JSON(), nullable=True),
        sa.Column("metadata_", sa.JSON(), nullable=True),
        sa.Column("parser_config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
```

- [ ] **Step 3: Run the migration**

```bash
uv run --directory backend alembic upgrade head
```

Expected: migration completes without error.

- [ ] **Step 4: Verify table is gone**

```bash
uv run --directory backend python -c "
import asyncio
from app.database import get_engine
from sqlalchemy import text, inspect

async def check():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT to_regclass('public.parse_results')\"))
        print('parse_results exists:', result.scalar())

asyncio.run(check())
"
```

Expected: `parse_results exists: None`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): drop parse_results table"
```

---

## Task 9: Frontend — rename simple → liteparse in ParseMethodSelector

**Files:**
- Modify: `frontend/src/components/documents/ParseMethodSelector.tsx`
- Test: `frontend/src/components/documents/ParseMethodSelector.test.tsx`

- [ ] **Step 1: Run existing ParseMethodSelector tests first**

```bash
npx --prefix frontend vitest run src/components/documents/ParseMethodSelector.test.tsx
```

Expected: all PASS (baseline).

- [ ] **Step 2: Update `PARSER_REGISTRY` in `ParseMethodSelector.tsx`**

Replace the `simple` entry key with `liteparse`:

```tsx
const PARSER_REGISTRY: Record<string, ParserMeta> = {
  liteparse: {
    label: 'LiteParse (local)',
    description: 'Fast local text extraction. Works best on clean text-based PDFs.',
    defaultConfig: {},
  },
  llamaparse: {
    label: 'LlamaParse',
    description: 'Intelligent parsing. Handles complex layouts, tables, scanned documents.',
    defaultConfig: { tier: 'agentic', expand: ['markdown', 'text', 'items'] },
  },
  landing_ai: {
    label: 'Landing AI',
    description: 'Vision-based parsing. Best for images, shelf photos, and complex visual layouts.',
    defaultConfig: { model: 'dpt-2-latest' },
  },
}
```

- [ ] **Step 3: Update tests in `ParseMethodSelector.test.tsx`**

Find any test that references `'simple'` as a parser type value and change it to `'liteparse'`. Also update any label checks from `'Simple (local)'` to `'LiteParse (local)'`.

- [ ] **Step 4: Run tests**

```bash
npx --prefix frontend vitest run src/components/documents/ParseMethodSelector.test.tsx
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/documents/ParseMethodSelector.tsx frontend/src/components/documents/ParseMethodSelector.test.tsx
git commit -m "feat(ui): rename simple parser to liteparse in ParseMethodSelector"
```

---

## Task 10: Frontend — wire reparse to CDM API

**Files:**
- Modify: `frontend/src/api/parseRuns.ts`
- Modify: `frontend/src/pages/DocumentsPage.tsx`
- Modify: `frontend/src/pages/ProjectDocumentsPage.tsx`

- [ ] **Step 1: Add `createParseRun` to `api/parseRuns.ts`**

Open `frontend/src/api/parseRuns.ts` and add:

```typescript
import type { ParseConfig } from '@/types/parsing'

export async function createParseRun(
  documentId: string,
  parserType: string,
  config?: ParseConfig
): Promise<void> {
  await apiClient.post(
    `/documents/${documentId}/parse-runs`,
    { parser_type: parserType, config: config ?? null }
  )
}
```

- [ ] **Step 2: Update `DocumentsPage.tsx`**

In `frontend/src/pages/DocumentsPage.tsx`:

1. Remove the `useParseResults` import (line 28) and the call (line 64): `const { parseResults, reparseDocument } = useParseResults(viewDocumentId)`.

2. Add an import for `createParseRun`:
```tsx
import { createParseRun } from '@/api/parseRuns'
```

3. Replace the `handleReparse` function to call the CDM API directly:
```tsx
const handleReparse = async (parserType: string, config?: ParseConfig) => {
  if (!viewDocumentId) return
  try {
    await createParseRun(viewDocumentId, parserType, config)
    toast.success('Re-parse started', {
      description: 'Parsing is in progress',
    })
  } catch (err) {
    toast.error('Re-parse failed', {
      description: err instanceof Error ? err.message : 'An error occurred',
    })
    throw err
  }
}
```

4. Remove the `ParseResultViewer` import (line 18) and its usage (lines 384–386):
```tsx
// Remove:
import { ParseResultViewer } from '@/components/documents/ParseResultViewer'
// Remove:
{viewDocumentId && parseResults.length > 0 && (
  <ParseResultViewer documentId={viewDocumentId} />
)}
```

- [ ] **Step 3: Apply the same changes to `ProjectDocumentsPage.tsx`**

Same four changes as Step 2 applied to `frontend/src/pages/ProjectDocumentsPage.tsx`:
- Remove `useParseResults` import and call
- Add `createParseRun` import
- Replace `handleReparse` to use `createParseRun`
- Remove `ParseResultViewer` import and usage

- [ ] **Step 4: Run frontend build to catch type errors**

```bash
npm --prefix frontend run build 2>&1 | grep -E "error|Error" | head -20
```

Expected: no TypeScript errors relating to the changed files.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/parseRuns.ts frontend/src/pages/DocumentsPage.tsx frontend/src/pages/ProjectDocumentsPage.tsx
git commit -m "feat(ui): wire document reparse to CDM parse-runs endpoint"
```

---

## Task 11: Frontend — delete legacy parse UI and clean up types

**Files:**
- Delete: `frontend/src/hooks/useParseResults.ts`
- Delete: `frontend/src/hooks/useParseResults.test.ts`
- Delete: `frontend/src/components/documents/ParseResultViewer.tsx`
- Delete: `frontend/src/components/documents/ParseResultViewer.test.tsx`
- Modify: `frontend/src/api/parsing.ts`
- Modify: `frontend/src/types/parsing.ts`
- Modify: `frontend/src/test/builders.ts`

- [ ] **Step 1: Delete legacy UI files**

```bash
rm frontend/src/hooks/useParseResults.ts
rm frontend/src/hooks/useParseResults.test.ts
rm frontend/src/components/documents/ParseResultViewer.tsx
rm frontend/src/components/documents/ParseResultViewer.test.tsx
```

- [ ] **Step 2: Trim `api/parsing.ts`**

Replace the contents of `frontend/src/api/parsing.ts` with only the parsers list endpoint (the only one still used):

```typescript
import apiClient from './client'
import type { ParserInfo } from '@/types/parsing'

export async function getAvailableParsers(): Promise<ParserInfo[]> {
  const response = await apiClient.get<ParserInfo[]>('/parsers')
  return response.data
}
```

- [ ] **Step 3: Trim `types/parsing.ts`**

Replace contents with only the types still in use:

```typescript
export interface ParserInfo {
  parserType: string
  name: string
  description: string
  supportedFileTypes: string[]
  configSchema: Record<string, unknown> | null
}

export type ParseConfig = {
  tier?: string
  expand?: string[]
  model?: string
  [key: string]: unknown
}
```

- [ ] **Step 4: Remove legacy builders from `test/builders.ts`**

In `frontend/src/test/builders.ts`, remove:
- The `ParseResult` import from `@/types/parsing`
- The `ParseResultListItem` import from `@/types/parsing`
- The `buildParseResult(...)` function
- The `buildParseResultListItem(...)` function
- The `buildParserInfo(...)` function (the `/parsers` endpoint is not tested via mock currently)

Check for any test files importing `buildParseResult` or `buildParseResultListItem`:

```bash
grep -rn "buildParseResult\|buildParserInfo" frontend/src --include="*.ts" --include="*.tsx"
```

Remove those usages from any test files found.

- [ ] **Step 5: Run full frontend test suite**

```bash
npx --prefix frontend vitest run
```

Expected: all PASS. No references to deleted files.

- [ ] **Step 6: Run frontend build**

```bash
npm --prefix frontend run build 2>&1 | tail -5
```

Expected: build succeeds with no errors.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(ui): delete legacy ParseResultViewer and useParseResults hook"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
uv run --directory backend python -m pytest -v -o "addopts="
```

Expected: all PASS. No imports of deleted modules.

- [ ] **Step 2: Run full frontend test suite**

```bash
npx --prefix frontend vitest run
```

Expected: all PASS.

- [ ] **Step 3: Run frontend lint**

```bash
npm --prefix frontend run lint
```

Expected: no errors.

- [ ] **Step 4: Verify `parse_results` endpoint returns 404**

The legacy endpoint is gone; confirm it returns 404:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/v1/documents/<any-doc-id>/parse-results \
  -H "Authorization: Bearer <token>"
```

Expected: `404` (route no longer registered).

- [ ] **Step 5: Confirm `parse_results` table is absent**

```bash
docker exec -it <postgres-container> psql -U <user> -d <db> \
  -c "\dt" | grep parse
```

Expected: `parse_runs` and `parsed_documents` visible; `parse_results` absent.

- [ ] **Step 6: Final commit (if any straggler changes)**

```bash
git status
# commit any remaining untracked changes
```
