from app.services.parser_eval.scorers.table_match import match_tables

A = "<table><tr><td>a</td><td>b</td></tr></table>"
B = "<table><tr><td>c</td><td>d</td></tr></table>"


def test_identity_order():
    expected = [{"page": 1, "html": A}, {"page": 1, "html": B}]
    assert match_tables(expected, [(0, A), (0, B)]) == [(0, 0), (1, 1)]


def test_reversed_parsed_matches_by_content():
    expected = [{"page": 1, "html": A}, {"page": 1, "html": B}]
    assert match_tables(expected, [(0, B), (0, A)]) == [(0, 1), (1, 0)]


def test_missing_gt_table():
    expected = [{"page": 1, "html": A}, {"page": 1, "html": B}]
    assert match_tables(expected, [(0, A)]) == [(0, 0), (1, None)]


def test_extra_parsed_table():
    expected = [{"page": 1, "html": A}]
    assert match_tables(expected, [(0, A), (0, B)]) == [(0, 0), (None, 1)]


def test_pages_do_not_cross_match():
    # GT page 1, parsed page_index 2 -> page 3: different buckets, no match.
    assert match_tables([{"page": 1, "html": A}], [(2, A)]) == [(0, None), (None, 0)]
