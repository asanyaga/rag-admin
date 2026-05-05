"""Workload functions for document processing."""
from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument


def slice_doc(doc: ParsedDocument, region: ClassifiedRegion) -> ParsedDocument:
    """Return a derived sub-ParsedDocument containing only region pages."""
    page_set = set(range(region.page_start, region.page_end + 1))
    pages = [p for p in doc.pages if p.index in page_set]
    blocks = [b for b in doc.blocks if b.page_index in page_set]
    return doc.model_copy(update={
        "pages": pages,
        "blocks": blocks,
        "page_count": len(pages),
        "derived_from": doc.id,
        "derivation": f"slice:{region.label}:pages {region.page_start}-{region.page_end}",
    })
