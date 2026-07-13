import pytest
from types import SimpleNamespace
from app.cdm.models import ParsedDocument
from app.services.parser_eval.capture import capture
from app.services.parsing.errors import ParseFailedError


class _FakeStorage:
    async def get(self, path): return b"%PDF-1.4 fake"
    async def save(self, content, rel): return rel


class _FakeParsing:
    async def ensure_source_document(self, *, bytes_, filename, mime_type):
        return SimpleNamespace(id="src-1", sha256="abc", filename=filename,
                               mime_type=mime_type, byte_size=len(bytes_), storage_uri="u")
    async def parse_and_persist(self, *, source, file_path, representation_kind, config, project_id, force=False):
        run = SimpleNamespace(cost={"usd": 0.0}, duration_ms=42,
                              input_tokens=None, output_tokens=None)
        doc = ParsedDocument(id="d", source_document_id="src-1", parse_run_id="r",
                             page_count=1, pages=[], blocks=[], full_text="hi")
        return run, doc


class _FakeParsingFails:
    async def ensure_source_document(self, *, bytes_, filename, mime_type):
        return SimpleNamespace(id="src-1", sha256="abc", filename=filename,
                               mime_type=mime_type, byte_size=len(bytes_), storage_uri="u")
    async def parse_and_persist(self, *, source, file_path, representation_kind, config, project_id, force=False):
        raise ParseFailedError("boom")


@pytest.mark.asyncio
async def test_capture_returns_cdm_and_metrics():
    cdm, cost, latency = await capture(
        _FakeParsing(), _FakeStorage(),
        source_document_id="src-1", storage_uri="u", filename="a.pdf",
        mime_type="application/pdf", parser="custom_pipeline", project_id="p1")
    assert cdm.full_text == "hi"
    assert latency == 42
    assert cost == {"usd": 0.0}


@pytest.mark.asyncio
async def test_capture_returns_none_on_parse_failure():
    cdm, cost, latency = await capture(
        _FakeParsingFails(), _FakeStorage(),
        source_document_id="src-1", storage_uri="u", filename="a.pdf",
        mime_type="application/pdf", parser="custom_pipeline", project_id="p1")
    assert cdm is None
    assert cost == {}
    assert latency is None
