from app.cdm.models import Block, BlockRole, Cell, Page, ParsedDocument, Table
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.scorers.table import score_table

_HTML = "<table><tr><td>Item</td><td>Qty</td></tr><tr><td>Widget</td><td>3</td></tr></table>"


def _doc(*tables: Table) -> ParsedDocument:
    blocks = [Block(id=f"b{i}", role=BlockRole.TABLE, native_type="table",
                    page_index=0, reading_order=i, table=t) for i, t in enumerate(tables)]
    return ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                          page_count=1, pages=[Page(index=0)], blocks=blocks)


def test_exact_match_scores_one():
    doc = _doc(Table(rows=2, cols=2, cells=[], html=_HTML))
    metrics, details = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    assert metrics["teds"] == 1.0
    assert metrics["table_recall"] == 1.0
    assert details["expected_count"] == 1
    assert details["parsed_count"] == 1


def test_dropped_column_lowers_teds():
    dropped = "<table><tr><td>Item</td></tr><tr><td>Widget</td></tr></table>"
    doc = _doc(Table(rows=2, cols=1, cells=[], html=dropped))
    metrics, _ = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    assert metrics["teds"] < 1.0


def test_missing_table_reduces_recall():
    doc = _doc()  # parser found no tables
    metrics, details = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    assert metrics["table_recall"] == 0.0
    assert metrics["teds"] == 0.0
    assert details["parsed_count"] == 0


def test_cells_fallback_when_parser_gives_no_html():
    cells = [Cell(row=0, col=0, text="Item", is_header=True),
             Cell(row=0, col=1, text="Qty", is_header=True),
             Cell(row=1, col=0, text="Widget"), Cell(row=1, col=1, text="3")]
    doc = _doc(Table(rows=2, cols=2, cells=cells))  # html=None -> synthesized
    expected_html = "<table><tr><th>Item</th><th>Qty</th></tr><tr><td>Widget</td><td>3</td></tr></table>"
    metrics, _ = score_table(doc, {"tables": [{"page": 1, "html": expected_html}]})
    assert metrics["teds"] == 1.0


def test_no_tables_expected_or_parsed_is_perfect():
    metrics, _ = score_table(_doc(), {"tables": []})
    assert metrics["teds"] == 1.0
    assert metrics["table_recall"] == 1.0


def test_registered_in_scorers():
    spec = get_scorer("table")
    assert spec.primary == "teds"
    assert set(spec.emits) == {"teds", "teds_struct", "cell_content_f1", "table_recall"}


def _doc_pages(tables):  # tables: list[(page_index, html)]
    blocks = [Block(id=f"b{i}", role=BlockRole.TABLE, native_type="table",
                    page_index=pi, reading_order=i, table=Table(rows=1, cols=2, cells=[], html=h))
              for i, (pi, h) in enumerate(tables)]
    return ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                          page_count=3, pages=[Page(index=0), Page(index=1), Page(index=2)],
                          blocks=blocks)


def test_extra_spurious_table_does_not_shift_matches():
    t1 = "<table><tr><td>a</td><td>b</td></tr></table>"
    t2 = "<table><tr><td>c</td><td>d</td></tr></table>"
    spurious = "<table><tr><td>zzz</td></tr></table>"
    expected = {"tables": [{"page": 1, "html": t1}, {"page": 1, "html": t2}]}
    doc = _doc(Table(rows=1, cols=2, cells=[], html=t1),
               Table(rows=1, cols=1, cells=[], html=spurious),
               Table(rows=1, cols=2, cells=[], html=t2))
    _metrics, details = score_table(doc, expected)
    matched = [e for e in details["per_table"] if e["status"] == "matched"]
    assert len(matched) == 2
    assert all(e["teds"] == 1.0 for e in matched)


def test_emits_structure_and_content_axes():
    gt = "<table><tr><td>Item</td><td>Qty</td></tr><tr><td>Widget</td><td>3</td></tr></table>"
    text_wrong = "<table><tr><td>xxx</td><td>yyy</td></tr><tr><td>zzz</td><td>9</td></tr></table>"
    doc = _doc(Table(rows=2, cols=2, cells=[], html=text_wrong))
    metrics, _ = score_table(doc, {"tables": [{"page": 1, "html": gt}]})
    assert metrics["teds_struct"] == 1.0
    assert metrics["cell_content_f1"] < 0.5


def test_details_per_table_carries_axes_and_status():
    doc = _doc(Table(rows=2, cols=2, cells=[], html=_HTML))
    _metrics, details = score_table(doc, {"tables": [{"page": 1, "html": _HTML}]})
    entry = details["per_table"][0]
    assert entry["status"] == "matched"
    assert entry["page"] == 1
    assert entry["expected_index"] == 0 and entry["parsed_index"] == 0
    assert entry["teds"] == 1.0 and entry["teds_struct"] == 1.0 and entry["cell_content_f1"] == 1.0


def test_cross_page_matching():
    t1 = "<table><tr><td>a</td></tr></table>"
    t2 = "<table><tr><td>b</td></tr></table>"
    expected = {"tables": [{"page": 1, "html": t1}, {"page": 2, "html": t2}]}
    doc = _doc_pages([(0, t1), (1, t2)])
    metrics, _ = score_table(doc, expected)
    assert metrics["teds"] == 1.0
