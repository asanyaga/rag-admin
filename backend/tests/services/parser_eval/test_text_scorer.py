from app.cdm.models import ParsedDocument, Page
from app.services.parser_eval.scorers.text import score_text


def _doc(full_text: str, pages: list[tuple[int, int]]) -> ParsedDocument:
    """Build a minimal ParsedDocument with page char-offsets into full_text."""
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="r1",
        page_count=len(pages),
        pages=[Page(index=i, start_char=s, end_char=e) for i, (s, e) in enumerate(pages)],
        blocks=[], full_text=full_text,
    )


def test_perfect_match_scores_one():
    doc = _doc("hello world", [(0, 11)])
    score, details = score_text(doc, {"pages": ["hello world"]})
    assert score == 1.0
    assert details["omission"] == 0.0
    assert details["hallucination"] == 0.0


def test_omission_detected():
    # reference has two words, parse dropped one
    doc = _doc("hello", [(0, 5)])
    score, details = score_text(doc, {"pages": ["hello world"]})
    assert score < 1.0
    assert details["omission"] > 0.0


def test_hallucination_detected():
    doc = _doc("hello world extra", [(0, 17)])
    score, details = score_text(doc, {"pages": ["hello world"]})
    assert details["hallucination"] > 0.0


def test_page_count_mismatch_penalized():
    # reference has 2 pages, parse produced 1 → missing page fully omitted
    doc = _doc("page one text", [(0, 13)])
    score, details = score_text(doc, {"pages": ["page one text", "page two text"]})
    assert details["page_count_expected"] == 2
    assert details["page_count_parsed"] == 1
    assert score < 1.0


def test_normalization_ignores_whitespace_and_case():
    doc = _doc("Hello    WORLD", [(0, 14)])
    score, _ = score_text(doc, {"pages": ["hello world"]})
    assert score == 1.0
