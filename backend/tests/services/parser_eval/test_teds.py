from app.services.parser_eval.scorers.teds import cell_count, teds

_T = "<table><tr><td>Item</td><td>Qty</td></tr><tr><td>Widget</td><td>3</td></tr></table>"


def test_identical_tables_score_one():
    assert teds(_T, _T) == 1.0


def test_single_cell_text_change_is_high_but_below_one():
    changed = _T.replace("<td>3</td>", "<td>8</td>")
    score = teds(_T, changed)
    assert 0.7 < score < 1.0


def test_structural_difference_scores_lower_than_content_difference():
    dropped_col = "<table><tr><td>Item</td></tr><tr><td>Widget</td></tr></table>"
    changed = _T.replace("<td>3</td>", "<td>8</td>")
    assert teds(_T, dropped_col) < teds(_T, changed)


def test_empty_vs_nonempty_scores_low():
    assert teds(_T, "<table></table>") < 0.3


def test_colspan_mismatch_penalized():
    a = "<table><tr><td colspan='2'>H</td></tr></table>"
    b = "<table><tr><td>H</td></tr></table>"
    assert teds(a, b) < 1.0


def test_cell_count():
    assert cell_count(_T) == 4
    assert cell_count("<table></table>") == 0
