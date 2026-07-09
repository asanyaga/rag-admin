from __future__ import annotations
import os
import tempfile
from pathlib import Path
from uuid import UUID
from app.probe.backends.fitz_backend import FitzBackend
from app.probe.config import ProbeConfig
from app.probe.prober import Prober
from app.probe.report import ProbeReport


class ProbeService:
    def __init__(self, document_service):
        self._documents = document_service

    async def probe(self, document_id: UUID, user_id: UUID, config: ProbeConfig) -> ProbeReport:
        content, filename, _mime = await self._documents.get_file_content(
            document_id=document_id, user_id=user_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return Prober(FitzBackend()).run(
                pdf_path=Path(tmp_path), document_id=str(document_id),
                filename=filename, config=config)
        finally:
            os.unlink(tmp_path)
