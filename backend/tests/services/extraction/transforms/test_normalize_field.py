import pytest
from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.normalize_field import NormalizeField, _apply_rules


# ── Rule isolation tests ──────────────────────────────────────────────────────

def test_trim_default():
    assert _apply_rules("  hello  ", [{"type": "trim"}]) == "hello"


def test_trim_custom_chars():
    assert _apply_rules("***hello***", [{"type": "trim", "chars": "*"}]) == "hello"


def test_collapse_whitespace():
    assert _apply_rules("a  b\t\nc", [{"type": "collapseWhitespace"}]) == "a b c"


def test_lowercase():
    assert _apply_rules("GP-40B", [{"type": "lowercase"}]) == "gp-40b"


def test_uppercase():
    assert _apply_rules("gp-40b", [{"type": "uppercase"}]) == "GP-40B"


def test_titlecase():
    assert _apply_rules("gp-40b model", [{"type": "titlecase"}]) == "Gp-40B Model"


def test_strip_regex():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+.*"}]) == "GP-40B"


def test_strip_regex_only_power_token():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+"}]) == "GP-40B DD"


def test_strip_trailing_chars_single():
    assert _apply_rules("GP-40B", [{"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]}]) == "GP-40"


def test_strip_trailing_chars_multiple_stacked():
    assert _apply_rules("GP-40BC", [{"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]}]) == "GP-40"


def test_strip_trailing_chars_preserves_non_option_letter_l():
    assert _apply_rules("UX-50L", [{"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]}]) == "UX-50L"


def test_strip_prefix():
    assert _apply_rules("Model: GP-40", [{"type": "stripPrefix", "prefix": "Model: "}]) == "GP-40"


def test_strip_suffix():
    assert _apply_rules("GP-40 Unit", [{"type": "stripSuffix", "suffix": " Unit"}]) == "GP-40"


def test_split_first_token():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "split", "delimiter": " ", "index": 0}]) == "GP-40B"


def test_split_second_token():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "split", "delimiter": " ", "index": 1}]) == "230/50/1"


def test_regex_extract_group():
    assert _apply_rules("1500W model", [{"type": "regexExtract", "pattern": r"(\d+\.?\d*)", "group": 1}]) == "1500"


def test_regex_extract_no_match_returns_original():
    assert _apply_rules("no-digits", [{"type": "regexExtract", "pattern": r"\d+"}]) == "no-digits"


def test_replace_literal():
    assert _apply_rules("N—A", [{"type": "replace", "find": "—", "replacement": ""}]) == "NA"


def test_alias_match():
    assert _apply_rules("UX-50L", [{"type": "alias", "map": {"UX-50L": "UX-50 LITE"}}]) == "UX-50 LITE"


def test_alias_no_match_passthrough():
    assert _apply_rules("UX-60", [{"type": "alias", "map": {"UX-50L": "UX-50 LITE"}}]) == "UX-60"


def test_nullify_if_in_match():
    assert _apply_rules("N/A", [{"type": "nullifyIfIn", "values": ["N/A", "-", ""]}]) is None


def test_nullify_if_in_no_match():
    assert _apply_rules("GP-40", [{"type": "nullifyIfIn", "values": ["N/A"]}]) == "GP-40"


def test_unknown_rule_type_raises():
    with pytest.raises(ValueError, match="Unknown rule type"):
        _apply_rules("x", [{"type": "bogus"}])


# ── Composition tests ─────────────────────────────────────────────────────────

def test_sammic_gp40_variants_to_base():
    # Use .* after the power-token pattern to also consume any trailing suffix (e.g. " DD")
    rules = [
        {"type": "trim"},
        {"type": "collapseWhitespace"},
        {"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+.*"},
        {"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]},
    ]
    assert _apply_rules("GP-40 230/50/1", rules) == "GP-40"
    assert _apply_rules("GP-40B 230/50/1", rules) == "GP-40"
    assert _apply_rules("GP-40 230/50/1 DD", rules) == "GP-40"
    assert _apply_rules("GP-40B 230/50/1 DD", rules) == "GP-40"


def test_ux50l_alias_never_collapses_to_bare_ux50():
    rules = [
        {"type": "trim"},
        {"type": "collapseWhitespace"},
        {"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+.*"},
        {"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]},
        {"type": "alias", "map": {"UX-50L": "UX-50 LITE"}},
    ]
    assert _apply_rules("UX-50L 230/50/1", rules) == "UX-50 LITE"
    assert _apply_rules("UX-50L", rules) == "UX-50 LITE"


def test_null_propagates_through_rule_chain():
    assert _apply_rules(None, [{"type": "trim"}, {"type": "lowercase"}]) is None


def test_nullify_mid_chain_stops_further_processing():
    rules = [
        {"type": "nullifyIfIn", "values": ["N/A"]},
        {"type": "lowercase"},
    ]
    assert _apply_rules("N/A", rules) is None


# ── NormalizeField primitive ──────────────────────────────────────────────────

_RULES = [
    {"type": "trim"},
    {"type": "collapseWhitespace"},
    {"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+.*"},
    {"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]},
    {"type": "alias", "map": {"UX-50L": "UX-50 LITE"}},
]
_CFG = {"sourceField": "modelName", "outputField": "baseModel", "rules": _RULES}
_ROWS = [
    {"modelName": "GP-40 230/50/1", "sku": "1303050", "sourcePage": "Page 7"},
    {"modelName": "GP-40B 230/50/1 DD", "sku": "1303056", "sourcePage": "Page 7"},
    {"modelName": "UX-50L 230/50/1", "sku": "1406010", "sourcePage": "Page 8"},
    {"modelName": None, "sku": None, "sourcePage": "Page 9"},
]


def test_output_field_present_on_every_row():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    assert all("baseModel" in r for r in out.rows)


def test_source_field_not_mutated():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    for i, row in enumerate(out.rows):
        assert row["modelName"] == _ROWS[i]["modelName"]


def test_all_original_columns_preserved():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    for orig, new in zip(_ROWS, out.rows):
        for key in orig:
            assert key in new


def test_null_source_yields_null_output():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    null_row = next(r for r in out.rows if r["modelName"] is None)
    assert null_row["baseModel"] is None


def test_gp40_variant_produces_correct_base_key():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    row = next(r for r in out.rows if r.get("sku") == "1303056")
    assert row["baseModel"] == "GP-40"


def test_ux50l_maps_to_lite_not_bare_ux50():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    row = next(r for r in out.rows if r.get("sku") == "1406010")
    assert row["baseModel"] == "UX-50 LITE"
    assert row["baseModel"] != "UX-50"


def test_row_count_unchanged():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    assert len(out.rows) == len(_ROWS)


def test_no_flags_emitted():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    assert out.flags == []
