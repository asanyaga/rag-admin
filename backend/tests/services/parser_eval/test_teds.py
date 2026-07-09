from app.services.parser_eval.scorers.teds import cell_content_f1, cell_count, teds

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


def test_structure_only_ignores_text():
    changed = _T.replace("<td>3</td>", "<td>999</td>").replace("<td>Item</td>", "<td>zzz</td>")
    assert teds(_T, changed, structure_only=True) == 1.0
    assert teds(_T, changed) < 1.0


def test_structure_only_penalizes_grid_change():
    dropped_col = "<table><tr><td>Item</td></tr><tr><td>Widget</td></tr></table>"
    assert teds(_T, dropped_col, structure_only=True) < 1.0


def test_cell_content_f1_identical():
    assert cell_content_f1(_T, _T) == 1.0


def test_cell_content_f1_structure_independent():
    flat = ("<table><tr><td>Item</td></tr><tr><td>Qty</td></tr>"
            "<tr><td>Widget</td></tr><tr><td>3</td></tr></table>")
    assert cell_content_f1(_T, flat) == 1.0


def test_cell_content_f1_disjoint_is_zero():
    other = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
    assert cell_content_f1(_T, other) == 0.0


def test_cell_content_f1_one_empty_is_zero():
    assert cell_content_f1(_T, "<table></table>") == 0.0
