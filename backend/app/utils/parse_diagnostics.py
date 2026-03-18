"""Diagnostics utility for parse results."""
import re
import string


def compute_diagnostics(raw_text: str, markdown: str | None = None) -> dict:
    """Compute parser-agnostic quality diagnostics from raw text.

    Args:
        raw_text: Plain text output from parser.
        markdown: Optional markdown output.

    Returns:
        Dict with diagnostic signals.
    """
    if not raw_text:
        return {
            "non_empty": False,
            "char_count": 0,
            "printable_ratio": 0.0,
            "suspected_cid": False,
            "token_count": 0,
            "has_table_markers": False,
            "has_heading_markers": False,
            "empty_pages": 0,
        }

    char_count = len(raw_text)

    # Printable ratio
    printable_chars = sum(1 for c in raw_text if c in string.printable)
    printable_ratio = printable_chars / char_count if char_count > 0 else 0.0

    # CID detection — (cid:NNN) patterns indicate font encoding issues
    cid_pattern = re.compile(r'\(cid:\d+\)')
    cid_matches = cid_pattern.findall(raw_text)
    suspected_cid = len(cid_matches) > 5

    # Rough token count (whitespace split)
    token_count = len(raw_text.split())

    # Table markers
    has_table_markers = bool(
        re.search(r'\|.*\|.*\|', raw_text)
        or (markdown and re.search(r'\|.*\|.*\|', markdown))
    )

    # Heading markers
    has_heading_markers = bool(
        markdown and re.search(r'^#{1,6}\s', markdown, re.MULTILINE)
    )

    # Empty pages — [Page N] markers with no substantial content after
    page_pattern = re.compile(r'\[Page \d+\]\s*\n?(.*?)(?=\[Page \d+\]|\Z)', re.DOTALL)
    page_matches = page_pattern.findall(raw_text)
    empty_pages = sum(1 for content in page_matches if len(content.strip()) < 10)

    return {
        "non_empty": char_count > 0,
        "char_count": char_count,
        "printable_ratio": round(printable_ratio, 4),
        "suspected_cid": suspected_cid,
        "token_count": token_count,
        "has_table_markers": has_table_markers,
        "has_heading_markers": has_heading_markers,
        "empty_pages": empty_pages,
    }
