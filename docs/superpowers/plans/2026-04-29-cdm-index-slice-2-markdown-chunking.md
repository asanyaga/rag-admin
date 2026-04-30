# CDM Index Slice 2: Markdown Chunking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `MarkdownChunkingService` that splits `full_markdown` on heading boundaries with `heading_path` provenance, wire it into the processing pipeline, and expose heading split level / max section size controls in the index creation UI.

**Architecture:** New `MarkdownChunkingService` (pure, no DB deps) is injected into `IndexProcessingService` alongside the existing `ChunkingService`. The processing dispatch gains a `full_markdown` branch that fetches `ParsedDocument.full_markdown`, calls the new service, and stores chunks with `source_type = "full_markdown"` and `heading_path` in metadata. Frontend `IndexCreateDialog` gains a source representation selector and an adaptive panel that replaces text chunking controls with heading/section controls when `full_markdown` is selected.

**Tech Stack:** Python 3.12 · FastAPI · Pydantic v2 · langchain-text-splitters · tiktoken · React 18 · TypeScript · shadcn/ui (Slider, ToggleGroup, Select)

---

## File Map

| Action | Path | What changes |
|--------|------|-------------|
| Modify | `backend/app/schemas/index.py` | Add `split_heading_level`, `max_section_chars` to `IndexConfig` |
| Modify | `backend/tests/schemas/test_index_config_schema.py` | Tests for new fields |
| **Create** | `backend/app/services/markdown_chunking_service.py` | New service |
| **Create** | `backend/tests/services/test_markdown_chunking_service.py` | New test file |
| Modify | `backend/app/services/index_processing_service.py` | Add `full_markdown` dispatch branch; inject `MarkdownChunkingService` |
| Modify | `backend/tests/services/test_index_processing_cdm.py` | `full_markdown` processing tests |
| Modify | `frontend/src/types/index.ts` | Add `splitHeadingLevel`, `maxSectionChars` to `IndexConfig` |
| Modify | `frontend/src/components/indexes/IndexCreateDialog.tsx` | Source representation selector + adaptive markdown config panel |
| **Create** | `frontend/src/components/indexes/IndexCreateDialog.test.tsx` | Frontend UI tests |

---

## Task 1: Extend `IndexConfig` with markdown config fields

**Files:**
- Modify: `backend/app/schemas/index.py:40-48`
- Modify: `backend/tests/schemas/test_index_config_schema.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/schemas/test_index_config_schema.py`:

```python
def test_markdown_config_defaults():
    config = IndexConfig(
        source_representation="full_markdown",
        chunking_strategy="markdown_heading",
        parser="llamaparse",
    )
    assert config.split_heading_level == 2
    assert config.max_section_chars == 4000


def test_split_heading_level_range():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            split_heading_level=0,
        )
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            split_heading_level=4,
        )


def test_max_section_chars_range():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            max_section_chars=499,
        )
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_markdown",
            chunking_strategy="markdown_heading",
            parser="llamaparse",
            max_section_chars=16001,
        )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest -o "addopts=" \
  tests/schemas/test_index_config_schema.py::test_markdown_config_defaults \
  tests/schemas/test_index_config_schema.py::test_split_heading_level_range \
  tests/schemas/test_index_config_schema.py::test_max_section_chars_range -v
```

Expected: FAIL — `split_heading_level` and `max_section_chars` attributes don't exist.

- [ ] **Step 3: Add the fields to `IndexConfig`**

In `backend/app/schemas/index.py`, after the `chunk_unit` field (line 43), add a new section:

```python
    # Text-based config (fixed_size, recursive_character)
    chunk_size: int = Field(default=512, ge=100, le=8000, alias="chunkSize")
    chunk_overlap: int = Field(default=50, ge=0, alias="chunkOverlap")
    chunk_unit: Literal["tokens", "characters"] = Field(default="characters", alias="chunkUnit")

    # Markdown-based config (markdown_heading)
    split_heading_level: int = Field(default=2, ge=1, le=3, alias="splitHeadingLevel")
    max_section_chars: int = Field(default=4000, ge=500, le=16000, alias="maxSectionChars")

    # Embedding config (unchanged)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest -o "addopts=" \
  tests/schemas/test_index_config_schema.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/index.py backend/tests/schemas/test_index_config_schema.py
git commit -m "feat(index): add split_heading_level and max_section_chars to IndexConfig"
```

---

## Task 2: Implement `MarkdownChunkingService`

**Files:**
- Create: `backend/app/services/markdown_chunking_service.py`
- Create: `backend/tests/services/test_markdown_chunking_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_markdown_chunking_service.py`:

```python
import pytest
from app.schemas.index import IndexConfig
from app.services.markdown_chunking_service import MarkdownChunkingService


def _config(**kwargs) -> IndexConfig:
    defaults = dict(
        source_representation="full_markdown",
        chunking_strategy="markdown_heading",
        parser="llamaparse",
        split_heading_level=2,
        max_section_chars=4000,
    )
    defaults.update(kwargs)
    return IndexConfig(**defaults)


def test_markdown_chunking_splits_on_headings():
    svc = MarkdownChunkingService()
    md = "# Introduction\nThis is the intro.\n\n## Background\nSome background info."
    chunks = svc.chunk_markdown(md, _config())

    assert len(chunks) == 2
    assert "Introduction" in chunks[0].content
    assert "intro" in chunks[0].content
    assert "Background" in chunks[1].content
    assert "background info" in chunks[1].content


def test_markdown_chunking_heading_path():
    svc = MarkdownChunkingService()
    md = (
        "# Report\nOverview.\n\n"
        "## Financials\nFinancial data.\n\n"
        "## Operations\nOps data."
    )
    chunks = svc.chunk_markdown(md, _config())

    assert chunks[0].metadata["heading_path"] == ["Report"]
    assert chunks[1].metadata["heading_path"] == ["Report", "Financials"]
    assert chunks[2].metadata["heading_path"] == ["Report", "Operations"]
    for chunk in chunks:
        assert chunk.metadata["split_level"] == 2


def test_markdown_chunking_large_section_fallback():
    svc = MarkdownChunkingService()
    # Force fallback: max_section_chars=100, section is ~1000 chars
    large_body = ("word " * 50 + "\n") * 4  # ~1000 chars
    md = f"# Big Section\n{large_body}"
    chunks = svc.chunk_markdown(md, _config(max_section_chars=100))

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata["heading_path"] == ["Big Section"]
        assert len(chunk.content) <= 200  # each sub-chunk must be smaller than section


def test_markdown_chunking_no_headings():
    svc = MarkdownChunkingService()
    md = "Just some plain text.\n\nNo headings here."
    chunks = svc.chunk_markdown(md, _config())

    assert len(chunks) == 1
    assert chunks[0].metadata["heading_path"] == []
    assert "plain text" in chunks[0].content


def test_markdown_chunking_h1_only_split_level():
    """split_heading_level=1: only H1 creates section boundaries."""
    svc = MarkdownChunkingService()
    md = "# Top\nIntro.\n\n## Sub A\nContent A.\n\n## Sub B\nContent B."
    chunks = svc.chunk_markdown(md, _config(split_heading_level=1))

    # H2s do not split — entire document is one chunk
    assert len(chunks) == 1
    assert "Sub A" in chunks[0].content
    assert "Sub B" in chunks[0].content


def test_markdown_chunking_empty_document():
    svc = MarkdownChunkingService()
    chunks = svc.chunk_markdown("", _config())
    assert chunks == []


def test_markdown_chunking_metadata_fields():
    svc = MarkdownChunkingService()
    md = "# Section\nContent here."
    chunks = svc.chunk_markdown(
        md, _config(),
        source_document_id="doc-123",
        source_filename="report.pdf",
    )

    assert len(chunks) == 1
    meta = chunks[0].metadata
    assert meta["source_document_id"] == "doc-123"
    assert meta["source_filename"] == "report.pdf"
    assert "start_char" in meta
    assert "end_char" in meta
    assert meta["chunk_index"] == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest -o "addopts=" \
  tests/services/test_markdown_chunking_service.py -v
```

Expected: FAIL — `MarkdownChunkingService` module doesn't exist.

- [ ] **Step 3: Implement `MarkdownChunkingService`**

Create `backend/app/services/markdown_chunking_service.py`:

```python
"""Service for chunking markdown documents by heading structure."""
import re

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.schemas.index import IndexConfig
from app.services.chunking_service import ChunkResult


class MarkdownChunkingService:
    """Chunks markdown text on heading boundaries with recursive fallback.

    Sections exceeding max_section_chars are further split with
    RecursiveCharacterTextSplitter; sub-chunks inherit the heading path.
    """

    _HEADING = re.compile(r"^(#{1,6})\s+(.+)$")

    def __init__(self) -> None:
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    def chunk_markdown(
        self,
        markdown: str,
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if not markdown or not markdown.strip():
            return []

        sections = self._parse_sections(markdown, config.split_heading_level)
        results: list[ChunkResult] = []
        chunk_index = 0

        for section in sections:
            content: str = section["content"]
            heading_path: list[str] = section["heading_path"]
            section_start: int = section["start_char"]

            # Determine sub-chunks: single section or recursive fallback
            if len(content) <= config.max_section_chars:
                sub_chunks: list[tuple[str, int]] = [(content, 0)]
            else:
                splitter = RecursiveCharacterTextSplitter(
                    separators=["\n\n", "\n", ". ", " ", ""],
                    chunk_size=config.max_section_chars,
                    chunk_overlap=0,
                    length_function=len,
                )
                raw = splitter.split_text(content)
                pos = 0
                sub_chunks = []
                for sub in raw:
                    idx = content.find(sub, pos)
                    offset = idx if idx != -1 else pos
                    sub_chunks.append((sub, offset))
                    pos = max(pos, offset + 1)

            for sub_content, offset in sub_chunks:
                start_char = section_start + offset
                end_char = start_char + len(sub_content)
                metadata: dict = {
                    "chunk_index": chunk_index,
                    "start_char": start_char,
                    "end_char": end_char,
                    "heading_path": heading_path,
                    "split_level": config.split_heading_level,
                }
                if source_document_id:
                    metadata["source_document_id"] = source_document_id
                if source_filename:
                    metadata["source_filename"] = source_filename

                results.append(ChunkResult(
                    content=sub_content,
                    chunk_index=chunk_index,
                    token_count=self.count_tokens(sub_content),
                    char_count=len(sub_content),
                    start_char=start_char,
                    end_char=end_char,
                    metadata=metadata,
                ))
                chunk_index += 1

        return results

    def _parse_sections(self, markdown: str, split_heading_level: int) -> list[dict]:
        """Split markdown into sections at headings whose level <= split_heading_level.

        Returns list of dicts: {content, heading_path, start_char}.
        char positions are byte-level offsets into the original markdown string.
        """
        sections: list[dict] = []
        heading_stack: list[tuple[int, str]] = []  # (level, title)
        current_lines: list[str] = []
        current_heading_path: list[str] = []
        current_start_char = 0
        char_pos = 0

        for line in markdown.split("\n"):
            m = self._HEADING.match(line)
            if m and len(m.group(1)) <= split_heading_level:
                level = len(m.group(1))
                title = m.group(2).strip()

                if current_lines:
                    sections.append({
                        "content": "\n".join(current_lines),
                        "heading_path": current_heading_path[:],
                        "start_char": current_start_char,
                    })

                # Pop same-or-deeper levels from the heading stack
                heading_stack = [(l, t) for l, t in heading_stack if l < level]
                heading_stack.append((level, title))
                current_heading_path = [t for _, t in heading_stack]
                current_lines = [line]
                current_start_char = char_pos
            else:
                current_lines.append(line)

            char_pos += len(line) + 1  # +1 for the \n separator

        if current_lines:
            sections.append({
                "content": "\n".join(current_lines),
                "heading_path": current_heading_path[:],
                "start_char": current_start_char,
            })

        return sections


_markdown_chunking_service: MarkdownChunkingService | None = None


def get_markdown_chunking_service() -> MarkdownChunkingService:
    global _markdown_chunking_service
    if _markdown_chunking_service is None:
        _markdown_chunking_service = MarkdownChunkingService()
    return _markdown_chunking_service
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest -o "addopts=" \
  tests/services/test_markdown_chunking_service.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/markdown_chunking_service.py \
        backend/tests/services/test_markdown_chunking_service.py
git commit -m "feat(index): add MarkdownChunkingService with heading-boundary splitting"
```

---

## Task 3: Wire `full_markdown` dispatch in the processing service

**Files:**
- Modify: `backend/app/services/index_processing_service.py`
- Modify: `backend/tests/services/test_index_processing_cdm.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `backend/tests/services/test_index_processing_cdm.py`:

```python
from app.services.markdown_chunking_service import MarkdownChunkingService


@pytest.mark.asyncio
async def test_process_index_full_markdown():
    """full_markdown: chunks sourced from ParsedDocument.full_markdown,
    source_type = "full_markdown", heading_path present in chunk metadata."""
    index = _make_mock_index(source_representation="full_markdown")
    index.config = {
        "source_representation": "full_markdown",
        "chunking_strategy": "markdown_heading",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "split_heading_level": 2,
        "max_section_chars": 4000,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_markdown = "# Section\nSome markdown content here."

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    parsed_doc_repo = AsyncMock()
    parsed_doc_repo.get_by_run = AsyncMock(return_value=parsed_doc)

    chunk_repo = AsyncMock()
    chunk_repo.create_batch = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 1, "total_documents": 1,
        "avg_chunk_size_chars": 37.0, "avg_chunk_size_tokens": 8.0,
        "min_chunk_size_chars": 37, "max_chunk_size_chars": 37,
        "total_tokens": 8,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_reg, \
         patch("app.services.index_processing_service.ParsedDocumentRepository",
               return_value=parsed_doc_repo), \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_reg.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )
        await service.process_index(index.id, uuid4(), uuid4())

    parsed_doc_repo.get_by_run.assert_called_once_with(parse_run_id)

    call_args = chunk_repo.create_batch.call_args[0][0]
    assert call_args[0]["source_type"] == "full_markdown"
    assert call_args[0]["parse_run_id"] == str(parse_run_id)
    assert "heading_path" in call_args[0]["chunk_metadata"]


@pytest.mark.asyncio
async def test_full_markdown_missing_raises():
    """ValueError when parse run has no full_markdown."""
    index = _make_mock_index(source_representation="full_markdown")
    index.config = {
        "source_representation": "full_markdown",
        "chunking_strategy": "markdown_heading",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "split_heading_level": 2,
        "max_section_chars": 4000,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_markdown = None  # missing

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    parsed_doc_repo = AsyncMock()
    parsed_doc_repo.get_by_run = AsyncMock(return_value=parsed_doc)

    chunk_repo = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 0, "total_documents": 1,
        "avg_chunk_size_chars": 0.0, "avg_chunk_size_tokens": 0.0,
        "min_chunk_size_chars": 0, "max_chunk_size_chars": 0,
        "total_tokens": 0,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=1536)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_reg, \
         patch("app.services.index_processing_service.ParsedDocumentRepository",
               return_value=parsed_doc_repo), \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_reg.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )
        await service.process_index(index.id, uuid4(), uuid4())

    # Document must be marked failed with a descriptive message
    failed_calls = [
        c for c in index_repo.update_document_status.call_args_list
        if c.args[2] == IndexDocumentStatus.failed
    ]
    assert len(failed_calls) == 1
    error_msg = str(failed_calls[0])
    assert "full_markdown" in error_msg.lower() or "markdown" in error_msg.lower()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest -o "addopts=" \
  tests/services/test_index_processing_cdm.py::test_process_index_full_markdown \
  tests/services/test_index_processing_cdm.py::test_full_markdown_missing_raises -v
```

Expected: FAIL — `full_markdown` hits `NotImplementedError`.

- [ ] **Step 3: Inject `MarkdownChunkingService` and add `full_markdown` dispatch**

In `backend/app/services/index_processing_service.py`:

**3a.** Add the import at the top (after the `ChunkingService` import):

```python
from app.services.chunking_service import ChunkingService, get_chunking_service
from app.services.markdown_chunking_service import (
    MarkdownChunkingService,
    get_markdown_chunking_service,
)
```

**3b.** Add `self.markdown_chunking_service` in `__init__`:

```python
    def __init__(
        self,
        session: AsyncSession,
        index_repo: IndexRepository,
        chunk_repo: ChunkRepository,
        provider_key_repo: ProviderKeyRepository
    ):
        self.session = session
        self.index_repo = index_repo
        self.chunk_repo = chunk_repo
        self.provider_key_service = ProviderKeyService(provider_key_repo)
        self.chunking_service = get_chunking_service()
        self.markdown_chunking_service = get_markdown_chunking_service()
```

**3c.** Replace the entire dispatch block (lines ~175–204) with the new multi-branch version. The current block looks like:

```python
                    # Get document text based on source_representation
                    if config.source_representation == "raw_text":
                        text = document.extracted_text
                        if not text:
                            raise ValueError("Document has no extracted text")
                        source_type = "raw_text"
                        doc_parse_run_id = None
                    elif config.source_representation == "full_text":
                        parsed_doc_repo = ParsedDocumentRepository(self.session)
                        parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
                        if not parsed_doc or not parsed_doc.full_text:
                            raise ValueError(
                                f"Parse run {index_doc.parse_run_id} did not produce full_text. "
                                "Re-parse with a configuration that outputs full text."
                            )
                        text = parsed_doc.full_text
                        source_type = "full_text"
                        doc_parse_run_id = index_doc.parse_run_id
                    else:
                        raise NotImplementedError(
                            f"source_representation '{config.source_representation}' not yet supported"
                        )

                    # Chunk the document
                    chunks = self.chunking_service.chunk_text(
                        text=text,
                        config=config,
                        source_document_id=str(doc_id),
                        source_filename=document.source_metadata.get("filename"),
                        page_boundaries=document.processing_metadata.get("page_boundaries") if document.processing_metadata else None
                    )
```

Replace with:

```python
                    # Dispatch: source representation → chunks
                    if config.source_representation == "raw_text":
                        if not document.extracted_text:
                            raise ValueError("Document has no extracted text")
                        source_type = "raw_text"
                        doc_parse_run_id = None
                        chunks = self.chunking_service.chunk_text(
                            text=document.extracted_text,
                            config=config,
                            source_document_id=str(doc_id),
                            source_filename=document.source_metadata.get("filename"),
                            page_boundaries=document.processing_metadata.get("page_boundaries")
                                if document.processing_metadata else None,
                        )
                    elif config.source_representation == "full_text":
                        parsed_doc_repo = ParsedDocumentRepository(self.session)
                        parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
                        if not parsed_doc or not parsed_doc.full_text:
                            raise ValueError(
                                f"Parse run {index_doc.parse_run_id} did not produce full_text. "
                                "Re-parse with a configuration that outputs full text."
                            )
                        source_type = "full_text"
                        doc_parse_run_id = index_doc.parse_run_id
                        chunks = self.chunking_service.chunk_text(
                            text=parsed_doc.full_text,
                            config=config,
                            source_document_id=str(doc_id),
                            source_filename=document.source_metadata.get("filename"),
                            page_boundaries=document.processing_metadata.get("page_boundaries")
                                if document.processing_metadata else None,
                        )
                    elif config.source_representation == "full_markdown":
                        parsed_doc_repo = ParsedDocumentRepository(self.session)
                        parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
                        if not parsed_doc or not parsed_doc.full_markdown:
                            raise ValueError(
                                "Parse run did not produce full_markdown. "
                                "Re-parse the document with a configuration that outputs markdown."
                            )
                        source_type = "full_markdown"
                        doc_parse_run_id = index_doc.parse_run_id
                        chunks = self.markdown_chunking_service.chunk_markdown(
                            markdown=parsed_doc.full_markdown,
                            config=config,
                            source_document_id=str(doc_id),
                            source_filename=document.source_metadata.get("filename"),
                        )
                    else:
                        raise NotImplementedError(
                            f"source_representation '{config.source_representation}' not yet supported"
                        )
```

- [ ] **Step 4: Run all CDM processing tests to confirm they pass**

```bash
uv run --directory backend python -m pytest -o "addopts=" \
  tests/services/test_index_processing_cdm.py -v
```

Expected: all 8 tests PASS (6 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/index_processing_service.py \
        backend/tests/services/test_index_processing_cdm.py
git commit -m "feat(index): wire full_markdown dispatch in IndexProcessingService"
```

---

## Task 4: Frontend types — add markdown config fields

**Files:**
- Modify: `frontend/src/types/index.ts:23-37`

- [ ] **Step 1: Add `splitHeadingLevel` and `maxSectionChars` to `IndexConfig`**

In `frontend/src/types/index.ts`, update the `IndexConfig` interface:

```typescript
// Index configuration
export interface IndexConfig {
  // CDM binding
  sourceRepresentation: SourceRepresentation
  parser: string | null
  parseConfigHash: string | null
  // Chunking
  chunkingStrategy: ChunkingStrategy
  chunkSize: number
  chunkOverlap: number
  chunkUnit: 'tokens' | 'characters'
  // Markdown-specific chunking
  splitHeadingLevel: number     // 1 | 2 | 3
  maxSectionChars: number       // 500–16000
  // Embedding
  embeddingProvider: string
  embeddingModel: string
  embeddingDimensions: number | null
}
```

- [ ] **Step 2: Run the TypeScript build to confirm no type errors**

```bash
npm --prefix frontend run build 2>&1 | tail -20
```

Expected: build succeeds (pre-existing chunk size warning is acceptable).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): add splitHeadingLevel and maxSectionChars to IndexConfig type"
```

---

## Task 5: Frontend adaptive UI in `IndexCreateDialog`

**Files:**
- Modify: `frontend/src/components/indexes/IndexCreateDialog.tsx`
- Create: `frontend/src/components/indexes/IndexCreateDialog.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/indexes/IndexCreateDialog.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IndexCreateDialog } from './IndexCreateDialog'

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  onSubmit: vi.fn().mockResolvedValue(undefined),
  onPreviewChunks: vi.fn().mockResolvedValue({
    totalChunksEstimate: 0,
    avgChunkSizeChars: 0,
    avgChunkSizeTokens: 0,
    minChunkSizeChars: 0,
    maxChunkSizeChars: 0,
    previewChunks: [],
  }),
  documents: [],
}

describe('IndexCreateDialog — chunking config', () => {
  it('shows text chunking fields by default (raw_text source)', () => {
    render(<IndexCreateDialog {...defaultProps} />)
    expect(screen.getByLabelText('Chunk Size')).toBeInTheDocument()
    expect(screen.getByLabelText('Overlap')).toBeInTheDocument()
    expect(screen.queryByText('Heading split level')).not.toBeInTheDocument()
    expect(screen.queryByText('Max section size')).not.toBeInTheDocument()
  })

  it('shows markdown controls and hides text controls when full_markdown selected', async () => {
    const user = userEvent.setup()
    render(<IndexCreateDialog {...defaultProps} />)

    // Click the "full_markdown" option in the source representation control
    const fullMarkdownButton = screen.getByRole('radio', { name: /full markdown/i })
    await user.click(fullMarkdownButton)

    expect(screen.getByText('Heading split level')).toBeInTheDocument()
    expect(screen.getByText('Max section size')).toBeInTheDocument()
    expect(screen.queryByLabelText('Chunk Size')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Overlap')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npm --prefix frontend run test -- --run src/components/indexes/IndexCreateDialog.test.tsx 2>&1 | tail -30
```

Expected: FAIL — the component doesn't have source representation controls yet.

- [ ] **Step 3: Update `IndexCreateDialog`**

**3a.** Add new imports at the top of `frontend/src/components/indexes/IndexCreateDialog.tsx`:

```typescript
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Slider } from '@/components/ui/slider'
import { SourceRepresentation } from '@/types/index'
```

**3b.** Update `DEFAULT_CONFIG` (around line 43):

```typescript
const DEFAULT_CONFIG: Partial<IndexConfig> = {
  sourceRepresentation: 'raw_text',
  chunkingStrategy: 'recursive_character',
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters',
  splitHeadingLevel: 2,
  maxSectionChars: 4000,
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
}
```

**3c.** Add a handler after `updateConfig` (around line 141) that auto-updates strategy when source representation changes:

```typescript
  const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_markdown') {
      updateConfig('chunkingStrategy', 'markdown_heading')
    } else if (value === 'raw_text' || value === 'full_text') {
      updateConfig('chunkingStrategy', 'recursive_character')
    }
  }
```

**3d.** Replace the entire `<TabsContent value="chunking" ...>` section with the adaptive version. The current content runs from around line 202 to 276. Replace with:

```tsx
              <TabsContent value="chunking" className="space-y-4 mt-4">
                {/* Source representation */}
                <div className="space-y-2">
                  <Label>Source</Label>
                  <ToggleGroup
                    type="single"
                    value={config.sourceRepresentation ?? 'raw_text'}
                    onValueChange={(v) =>
                      v && handleSourceRepresentationChange(v as SourceRepresentation)
                    }
                    className="justify-start"
                  >
                    <ToggleGroupItem value="raw_text" aria-label="Raw text">
                      Raw text
                    </ToggleGroupItem>
                    <ToggleGroupItem value="full_text" aria-label="Full text">
                      Full text
                    </ToggleGroupItem>
                    <ToggleGroupItem value="full_markdown" aria-label="Full Markdown">
                      Full Markdown
                    </ToggleGroupItem>
                  </ToggleGroup>
                </div>

                {config.sourceRepresentation === 'full_markdown' ? (
                  /* Markdown-specific controls */
                  <>
                    <div className="space-y-2">
                      <Label>Heading split level</Label>
                      <ToggleGroup
                        type="single"
                        value={String(config.splitHeadingLevel ?? 2)}
                        onValueChange={(v) =>
                          v && updateConfig('splitHeadingLevel', parseInt(v))
                        }
                        className="justify-start"
                      >
                        <ToggleGroupItem value="1">H1 only</ToggleGroupItem>
                        <ToggleGroupItem value="2">H1 + H2</ToggleGroupItem>
                        <ToggleGroupItem value="3">H1 + H2 + H3</ToggleGroupItem>
                      </ToggleGroup>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>Max section size</Label>
                        <span className="text-sm text-muted-foreground">
                          {(config.maxSectionChars ?? 4000).toLocaleString()} chars
                        </span>
                      </div>
                      <Slider
                        min={500}
                        max={16000}
                        step={500}
                        value={[config.maxSectionChars ?? 4000]}
                        onValueChange={([v]) => updateConfig('maxSectionChars', v)}
                        disabled={isLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        Sections larger than this are split further.
                      </p>
                    </div>
                  </>
                ) : (
                  /* Text-based chunking controls */
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Strategy</Label>
                        <Select
                          value={config.chunkingStrategy}
                          onValueChange={(v) =>
                            updateConfig(
                              'chunkingStrategy',
                              v as IndexConfig['chunkingStrategy']
                            )
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="recursive_character">
                              Recursive Character (Recommended)
                            </SelectItem>
                            <SelectItem value="fixed_size">Fixed Size</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Unit</Label>
                        <Select
                          value={config.chunkUnit}
                          onValueChange={(v) =>
                            updateConfig('chunkUnit', v as IndexConfig['chunkUnit'])
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="characters">Characters</SelectItem>
                            <SelectItem value="tokens">Tokens</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="chunk-size">Chunk Size</Label>
                        <Input
                          id="chunk-size"
                          type="number"
                          min={100}
                          max={8000}
                          value={config.chunkSize}
                          onChange={(e) =>
                            updateConfig('chunkSize', parseInt(e.target.value) || 512)
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          Target size per chunk (100-8000)
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="chunk-overlap">Overlap</Label>
                        <Input
                          id="chunk-overlap"
                          type="number"
                          min={0}
                          max={(config.chunkSize || 512) / 2}
                          value={config.chunkOverlap}
                          onChange={(e) =>
                            updateConfig('chunkOverlap', parseInt(e.target.value) || 0)
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          Overlap between chunks (max{' '}
                          {Math.floor((config.chunkSize || 512) / 2)})
                        </p>
                      </div>
                    </div>
                  </>
                )}
              </TabsContent>
```

Note: the test queries `getByLabelText('Chunk Size')` — this works because the Input now has `id="chunk-size"` and the Label has `htmlFor="chunk-size"`. Same for Overlap.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npm --prefix frontend run test -- --run src/components/indexes/IndexCreateDialog.test.tsx 2>&1 | tail -30
```

Expected: both tests PASS.

- [ ] **Step 5: Run the full frontend lint and build**

```bash
npm --prefix frontend run lint 2>&1 | tail -20
npm --prefix frontend run build 2>&1 | tail -20
```

Expected: no lint errors, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/indexes/IndexCreateDialog.tsx \
        frontend/src/components/indexes/IndexCreateDialog.test.tsx
git commit -m "feat(frontend): add source representation selector and markdown chunking config panel"
```

---

## Self-Review: Spec Coverage

| Spec requirement | Task that covers it |
|-----------------|---------------------|
| `MarkdownChunkingService` splits on heading boundaries | Task 2 |
| `split_heading_level` config knob (ge=1, le=3) | Task 1 |
| `max_section_chars` config knob (ge=500, le=16000) | Task 1 |
| Large section fallback to `RecursiveCharacterTextSplitter` | Task 2 |
| Sub-chunks inherit heading path | Task 2 (test_markdown_chunking_large_section_fallback) |
| Heading path tracked as stack | Task 2 (test_markdown_chunking_heading_path) |
| `source_representation = "full_markdown"` dispatch in processing service | Task 3 |
| `source_type = "full_markdown"` on stored chunks | Task 3 (test_process_index_full_markdown) |
| `heading_path` in `chunk_metadata` | Task 3 (asserts `"heading_path" in chunk_metadata`) |
| `ValueError` when `full_markdown` missing | Task 3 (test_full_markdown_missing_raises) |
| UI: heading split level segmented control | Task 5 |
| UI: max section size slider | Task 5 |
| UI: chunk size / overlap hidden when full_markdown | Task 5 |
| `splitHeadingLevel`, `maxSectionChars` in `IndexConfig` TypeScript type | Task 4 |

All spec requirements are covered. No placeholders remain.
