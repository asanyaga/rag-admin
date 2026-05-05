from app.cdm.models import ParsedDocument


def serialize_pages(doc: ParsedDocument, page_start: int, page_end: int) -> str:
    """Serialize blocks for pages [page_start, page_end] inclusive as compact text."""
    lines = []
    for block in doc.blocks:
        if block.page_index < page_start or block.page_index > page_end:
            continue
        content = block.markdown if block.markdown else block.text
        if not content.strip():
            continue
        lines.append(f"[page {block.page_index}, {block.role.value}] {content}")
    return "\n".join(lines)


def build_batches(page_count: int, batch_size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) page ranges for each batch with given overlap.

    Example: page_count=25, batch_size=10, overlap=3 →
        [(0,9), (7,16), (14,23), (21,24)]
    """
    if page_count == 0:
        return []
    batches = []
    start = 0
    while True:
        end = min(start + batch_size - 1, page_count - 1)
        batches.append((start, end))
        if end >= page_count - 1:
            break
        start = end - overlap + 1
    return batches
