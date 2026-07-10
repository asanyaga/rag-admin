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


@pytest.mark.asyncio
async def test_probe_runs_off_the_event_loop(monkeypatch):
    # The synchronous, CPU-bound prober must run on a worker thread, not the
    # event-loop thread — otherwise a large document freezes the whole app.
    import threading
    from types import SimpleNamespace
    import app.services.probe_service as svc_mod

    main_tid = threading.get_ident()
    seen = {}

    class _RecordingProber:
        def __init__(self, backend):
            pass

        def run(self, **kwargs):
            seen["tid"] = threading.get_ident()
            return SimpleNamespace(page_count=0)

    monkeypatch.setattr(svc_mod, "Prober", _RecordingProber)
    svc = ProbeService(_FakeDocService(_pdf_bytes()))
    await svc.probe(uuid.uuid4(), uuid.uuid4(), ProbeConfig())
    assert seen["tid"] != main_tid
