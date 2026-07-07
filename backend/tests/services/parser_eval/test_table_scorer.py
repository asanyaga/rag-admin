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
    assert set(spec.emits) == {"teds", "table_recall"}
