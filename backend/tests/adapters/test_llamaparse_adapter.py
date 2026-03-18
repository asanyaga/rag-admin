"""Tests for LlamaParseAdapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.parsing.llamaparse import LlamaParseAdapter
from app.ports.document_parsing import ParserType, ParseFidelity


class MockJob:
    def __init__(self, job_id="job-123"):
        self.id = job_id
        self.status = "SUCCESS"


class MockTextPage:
    def __init__(self, page_number, text):
        self.page_number = page_number
        self.text = text


class MockMarkdownPage:
    def __init__(self, page_number, markdown, success=True):
        self.page_number = page_number
        self.markdown = markdown
        self.success = success


class MockTextResult:
    def __init__(self, pages):
        self.pages = pages


class MockMarkdownResult:
    def __init__(self, pages):
        self.pages = pages


class MockParseResult:
    """Mimics the result of client.parsing.parse()."""
    def __init__(self, job_id="job-123", text_pages=None, markdown_pages=None):
        self.job = MockJob(job_id)
        if text_pages is not None:
            self.text = MockTextResult(text_pages)
        else:
            self.text = None
        if markdown_pages is not None:
            self.markdown = MockMarkdownResult(markdown_pages)
        else:
            self.markdown = None
        self.items = None


class TestLlamaParseAdapter:

    def test_parser_type(self):
        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud"):
            adapter = LlamaParseAdapter(api_key="test-key")
            assert adapter.parser_type == ParserType.LLAMAPARSE

    def test_default_fidelity(self):
        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud"):
            adapter = LlamaParseAdapter(api_key="test-key")
            assert adapter.default_fidelity == ParseFidelity.MARKDOWN

    def test_supported_file_types(self):
        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud"):
            adapter = LlamaParseAdapter(api_key="test-key")
            types = adapter.supported_file_types()
            assert "application/pdf" in types
            assert "image/jpeg" in types

    @pytest.mark.asyncio
    async def test_parse_text_only(self):
        mock_client = MagicMock()
        mock_client.parsing.parse = AsyncMock(return_value=MockParseResult(
            text_pages=[
                MockTextPage(1, "Page 1 content"),
                MockTextPage(2, "Page 2 content"),
            ],
        ))

        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud", return_value=mock_client):
            adapter = LlamaParseAdapter(api_key="test-key")
            result = await adapter.parse("/tmp/test.pdf", {"tier": "fast"})

        assert result.fidelity == "text"
        assert "Page 1 content" in result.raw_text
        assert "Page 2 content" in result.raw_text
        assert result.markdown is None
        # Should only expand text for fast tier
        assert result.parser_config["expand"] == ["text"]

    @pytest.mark.asyncio
    async def test_parse_with_markdown(self):
        mock_client = MagicMock()
        mock_client.parsing.parse = AsyncMock(return_value=MockParseResult(
            text_pages=[MockTextPage(1, "Plain text")],
            markdown_pages=[MockMarkdownPage(1, "# Heading\n\nParagraph")],
        ))

        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud", return_value=mock_client):
            adapter = LlamaParseAdapter(api_key="test-key")
            result = await adapter.parse("/tmp/test.pdf", {"tier": "agentic"})

        assert result.fidelity == "markdown"
        assert result.markdown == "# Heading\n\nParagraph"
        assert "Plain text" in result.raw_text

    @pytest.mark.asyncio
    async def test_fast_tier_only_expands_text(self):
        mock_client = MagicMock()
        mock_client.parsing.parse = AsyncMock(return_value=MockParseResult(
            text_pages=[MockTextPage(1, "text")],
        ))

        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud", return_value=mock_client):
            adapter = LlamaParseAdapter(api_key="test-key")
            result = await adapter.parse("/tmp/test.pdf", {
                "tier": "fast",
                "expand": ["markdown", "text", "items"],
            })

        # parse() should be called with expand=["text"] only
        call_kwargs = mock_client.parsing.parse.call_args.kwargs
        assert call_kwargs["expand"] == ["text"]

    @pytest.mark.asyncio
    async def test_metadata_includes_job_id(self):
        mock_client = MagicMock()
        mock_client.parsing.parse = AsyncMock(return_value=MockParseResult(
            job_id="my-job-456",
            text_pages=[MockTextPage(1, "text")],
        ))

        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud", return_value=mock_client):
            adapter = LlamaParseAdapter(api_key="test-key")
            result = await adapter.parse("/tmp/test.pdf", {"tier": "fast"})

        assert result.metadata["llamaparse_job_id"] == "my-job-456"
        assert "latency_ms" in result.metadata

    @pytest.mark.asyncio
    async def test_parse_error_propagates(self):
        mock_client = MagicMock()
        mock_client.parsing.parse = AsyncMock(side_effect=Exception("API error"))

        with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud", return_value=mock_client):
            adapter = LlamaParseAdapter(api_key="test-key")
            with pytest.raises(Exception, match="API error"):
                await adapter.parse("/tmp/test.pdf")
