"""Capture a ParsedDocument for one parser by reusing ParsingService.

Cost/latency come from the returned ParseRun — no bespoke timing.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from app.cdm.models import ParsedDocument
from app.services.parsing.errors import ParseFailedError

logger = logging.getLogger(__name__)

DEFAULT_REPRESENTATION_KIND = "extract_rich"


async def capture(
    parsing_service: Any,
    storage: Any,
    *,
    source_document_id: str,
    storage_uri: str,
    filename: str,
    mime_type: str,
    parser: str,
    project_id: Any,
) -> tuple[ParsedDocument | None, dict, int | None]:
    data = await storage.get(storage_uri)
    source = await parsing_service.ensure_source_document(
        bytes_=data, filename=filename, mime_type=mime_type)

    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        run, doc = await parsing_service.parse_and_persist(
            source=source, file_path=tmp_path,
            representation_kind=DEFAULT_REPRESENTATION_KIND,
            config={"parser": parser}, project_id=project_id, force=False)
        return doc, dict(run.cost or {}), run.duration_ms
    except ParseFailedError as err:
        logger.warning("parser-eval capture failed parser=%s: %s", parser, err)
        return None, {}, None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
