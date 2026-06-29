import pytest
from app.services.extraction.transforms.base import TransformInput, TransformValidationError
from app.services.extraction.transforms.join_results import JoinResults

_META = "_provenance"

# ── Fixtures ──────────────────────────────────────────────────────────────────

# sourcePage appears in both inputs intentionally — it is a passthrough field
# excluded from column conflict detection.
PRICE_ROWS = [
    {"sku": "12345", "model": "gp-30b", "series": "gp-30", "price": 1000, "sourcePage": "Page 1"},
    {"sku": "54321", "model": "gp-30a", "series": "gp-30", "price": 2000, "sourcePage": "Page 1"},
]

SPEC_ROWS = [
    {"series": "gp-30", "height": 100, "width": 200, "weight": 20, "sourcePage": "Page 2"},
]

PRICE_INPUT = TransformInput(rows=PRICE_ROWS, source_result_id="r_price")
SPEC_INPUT = TransformInput(rows=SPEC_ROWS, source_result_id="r_spec")

CFG_LEFT = {"joinKey": "series", "joinType": "left"}
CFG_INNER = {"joinKey": "series", "joinType": "inner"}


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_left_join_basic_output():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    assert len(out.rows) == 2
    for row in out.rows:
        assert row["height"] == 100
        assert row["width"] == 200
        assert row["weight"] == 20
    skus = {r["sku"] for r in out.rows}
    assert skus == {"12345", "54321"}


def test_left_join_no_flags_on_matched_rows():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    assert out.flags == []


def test_column_order_left_first_then_right_excl_join_key():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    cols = [k for k in out.rows[0] if k != _META]
    # left cols include: sku, model, series, price, sourcePage
    # right cols excl series and sourcePage (passthrough): height, width, weight
    left_pos = cols.index("series")
    height_pos = cols.index("height")
    assert left_pos < height_pos, "left columns must precede right columns"
    assert cols.count("series") == 1, "join key must not repeat"


def test_sourcepage_not_duplicated_in_output():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    cols = [k for k in out.rows[0] if k != _META]
    assert cols.count("sourcePage") == 1, "sourcePage is a passthrough field — must not duplicate"


def test_provenance_left_cells_track_left_result():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    row = out.rows[0]
    assert row[_META]["sku"]["sourceResultId"] == "r_price"
    assert row[_META]["sku"]["sourcePage"] == "Page 1"


def test_provenance_right_cells_track_right_result():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    row = out.rows[0]
    assert row[_META]["height"]["sourceResultId"] == "r_spec"
    assert row[_META]["height"]["sourcePage"] == "Page 2"


# ── inner join ─────────────────────────────────────────────────────────────────

def test_inner_join_excludes_unmatched_left_rows():
    unmatched_price = [
        {"sku": "12345", "model": "gp-30b", "series": "gp-30", "price": 1000},
        {"sku": "99999", "model": "xx-10", "series": "xx-10", "price": 500},  # no spec match
    ]
    out = JoinResults().apply(
        [TransformInput(rows=unmatched_price, source_result_id="rp"), SPEC_INPUT],
        CFG_INNER,
    )
    assert len(out.rows) == 1
    assert out.rows[0]["sku"] == "12345"


def test_inner_join_null_key_rows_always_pass_through():
    rows_with_null = [
        {"sku": "12345", "model": "gp-30b", "series": "gp-30", "price": 1000},
        {"sku": "77777", "model": "gp-40a", "series": None, "price": 750},
    ]
    out = JoinResults().apply(
        [TransformInput(rows=rows_with_null, source_result_id="rp"), SPEC_INPUT],
        CFG_INNER,
    )
    assert len(out.rows) == 2
    null_row = next(r for r in out.rows if r["sku"] == "77777")
    assert null_row["height"] is None
    assert any(f["flag"] == "null_key" for f in out.flags)


# ── Flags ──────────────────────────────────────────────────────────────────────

def test_unmatched_flag_for_left_join_no_match():
    price_with_unknown = PRICE_ROWS + [
        {"sku": "99999", "model": "xx-10", "series": "xx-10", "price": 500}
    ]
    out = JoinResults().apply(
        [TransformInput(rows=price_with_unknown, source_result_id="rp"), SPEC_INPUT],
        CFG_LEFT,
    )
    assert len(out.rows) == 3
    unmatched_idx = next(i for i, r in enumerate(out.rows) if r["sku"] == "99999")
    assert {"rowIndex": unmatched_idx, "flag": "unmatched"} in out.flags
    assert out.rows[unmatched_idx]["height"] is None


def test_null_key_flag_left_join():
    rows = PRICE_ROWS + [{"sku": "77777", "model": "gp-40a", "series": None, "price": 750}]
    out = JoinResults().apply(
        [TransformInput(rows=rows, source_result_id="rp"), SPEC_INPUT],
        CFG_LEFT,
    )
    null_idx = next(i for i, r in enumerate(out.rows) if r["sku"] == "77777")
    assert {"rowIndex": null_idx, "flag": "null_key"} in out.flags
    assert out.rows[null_idx]["height"] is None


def test_null_key_provenance_is_null_for_right_cells():
    rows = [{"sku": "X", "series": None}]
    out = JoinResults().apply(
        [TransformInput(rows=rows, source_result_id="rp"), SPEC_INPUT],
        CFG_LEFT,
    )
    row = out.rows[0]
    assert row[_META]["height"]["sourceResultId"] is None
    assert row[_META]["height"]["sourcePage"] is None


def test_ambiguous_right_flag_uses_first_match():
    dup_spec = [
        {"series": "gp-30", "height": 100, "width": 200, "weight": 20},
        {"series": "gp-30", "height": 999, "width": 888, "weight": 77},  # duplicate key
    ]
    out = JoinResults().apply(
        [PRICE_INPUT, TransformInput(rows=dup_spec, source_result_id="rs")],
        CFG_LEFT,
    )
    assert len(out.rows) == 2
    for row in out.rows:
        assert row["height"] == 100  # first match used
    ambiguous_indices = {f["rowIndex"] for f in out.flags if f["flag"] == "ambiguous_right"}
    assert ambiguous_indices == {0, 1}  # both left rows flagged


# ── Validation errors ──────────────────────────────────────────────────────────

def test_invalid_result_count_too_few():
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([PRICE_INPUT], CFG_LEFT)
    assert exc_info.value.code == "invalid_result_count"


def test_invalid_result_count_too_many():
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([PRICE_INPUT] * 6, CFG_LEFT)
    assert exc_info.value.code == "invalid_result_count"


def test_join_key_missing_from_input():
    no_series = TransformInput(
        rows=[{"sku": "A", "price": 10}],
        source_result_id="r1",
    )
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([no_series, SPEC_INPUT], CFG_LEFT)
    assert exc_info.value.code == "join_key_missing"


def test_column_conflict_raises():
    conflicting = TransformInput(
        rows=[{"series": "gp-30", "height": 50, "notes": "spec notes"}],
        source_result_id="rs",
    )
    price_with_notes = TransformInput(
        rows=[{"sku": "X", "series": "gp-30", "price": 100, "notes": "price notes"}],
        source_result_id="rp",
    )
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([price_with_notes, conflicting], CFG_LEFT)
    assert exc_info.value.code == "column_conflict"


def test_sourcepage_does_not_trigger_column_conflict():
    # sourcePage is a passthrough field — must not cause column_conflict even when in both inputs
    price = TransformInput(
        rows=[{"sku": "X", "series": "gp-30", "price": 100, "sourcePage": "Page 1"}],
        source_result_id="rp",
    )
    spec = TransformInput(
        rows=[{"series": "gp-30", "height": 50, "sourcePage": "Page 2"}],
        source_result_id="rs",
    )
    out = JoinResults().apply([price, spec], CFG_LEFT)
    assert len(out.rows) == 1
    assert out.rows[0]["height"] == 50


# ── Three-input join ───────────────────────────────────────────────────────────

def test_three_input_join():
    dims_rows = [{"series": "gp-30", "depth": 300}]
    dims_input = TransformInput(rows=dims_rows, source_result_id="r_dims")
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT, dims_input], CFG_LEFT)
    assert len(out.rows) == 2
    for row in out.rows:
        assert row["height"] == 100
        assert row["depth"] == 300
