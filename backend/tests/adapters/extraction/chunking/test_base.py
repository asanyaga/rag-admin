from app.adapters.extraction.chunking.base import DocumentChunk
from app.cdm.models import ParsedDocument


def _doc():
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="p1",
        page_count=1, pages=[], blocks=[],
    )


def test_document_chunk_holds_derived_doc_and_indices():
    chunk = DocumentChunk(document=_doc(), chunk_index=0, page_indices=[0, 1])
    assert chunk.chunk_index == 0
    assert chunk.page_indices == [0, 1]
    assert chunk.document.parse_run_id == "p1"
