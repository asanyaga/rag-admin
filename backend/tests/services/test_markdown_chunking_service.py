import pytest
from app.schemas.index import IndexConfig
from app.services.markdown_chunking_service import MarkdownChunkingService


def _config(**kwargs) -> IndexConfig:
    defaults = dict(
        source_representation="full_markdown",
        chunking_strategy="markdown_heading",
        parser="llamaparse",
        parse_config_hash="h" * 64,
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
    # Force fallback: max_section_chars=500, section is ~5000 chars
    large_body = ("word " * 50 + "\n") * 20  # ~5000 chars
    md = f"# Big Section\n{large_body}"
    chunks = svc.chunk_markdown(md, _config(max_section_chars=500))

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata["heading_path"] == ["Big Section"]
        assert len(chunk.content) <= 1000  # each sub-chunk must be smaller than section


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
