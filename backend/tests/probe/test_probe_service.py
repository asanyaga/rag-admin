import uuid
import fitz
import pytest
from app.probe.config import ProbeConfig
from app.services.probe_service import ProbeService


class _FakeDocService:
    def __init__(self, content, filename="f.pdf"):
        self._content = content; self._filename = filename
    async def get_file_content(self, document_id, user_id):
        return self._content, self._filename, "application/pdf"


def _pdf_bytes():
    doc = fitz.open(); page = doc.new_page(); page.insert_text((72, 72), "hello world text")
    data = doc.tobytes(); doc.close(); return data


@pytest.mark.asyncio
async def test_probe_service_returns_report():
    svc = ProbeService(_FakeDocService(_pdf_bytes()))
    report = await svc.probe(uuid.uuid4(), uuid.uuid4(), ProbeConfig())
    assert report.page_count == 1
    assert report.filename == "f.pdf"
    assert report.suggestion is not None
