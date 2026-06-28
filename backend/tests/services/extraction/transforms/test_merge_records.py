# backend/tests/services/extraction/transforms/test_merge_records.py
from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.merge_records import MergeRecords

CFG = {
    "groupBy": ["productFamily"],
    "spine": {"whereFieldsPresent": ["sku"]},
    "conflict": "prefer_spine",
    "onGroupWithoutSpine": "keep",
}

# GP-40 family: one base spec row + 4 priced variants.
# productFamily is a pre-normalized field (as derive_field would produce).
GP40 = [
    {"sku": None, "productFamily": "GP-40", "modelName": "GP-40", "widthMm": 470, "netWeightKg": 41, "listPrice": 0, "sourcePage": "Page 6"},
    {"sku": "1303050", "productFamily": "GP-40", "modelName": "GP-40 230/50/1", "listPrice": 1908, "sourcePage": "Page 7"},
    {"sku": "1303054", "productFamily": "GP-40", "modelName": "GP-40B 230/50/1", "listPrice": 2140, "sourcePage": "Page 7"},
    {"sku": "1303052", "productFamily": "GP-40", "modelName": "GP-40 230/50/1 DD", "listPrice": 2081, "sourcePage": "Page 7"},
    {"sku": "1303056", "productFamily": "GP-40", "modelName": "GP-40B 230/50/1 DD", "listPrice": 2313, "sourcePage": "Page 7"},
]


def test_collapses_base_spec_into_each_priced_variant():
    out = MergeRecords().apply([TransformInput(rows=GP40, source_result_id="r1")], CFG)
    assert len(out.rows) == 4
    for row in out.rows:
        assert row["sku"] is not None
        assert row["widthMm"] == 470          # inherited from base spec row
        assert row["netWeightKg"] == 41
    prices = sorted(r["listPrice"] for r in out.rows)
    assert prices == [1908, 2081, 2140, 2313]


def test_provenance_tracks_source_page_per_field():
    out = MergeRecords().apply([TransformInput(rows=GP40, source_result_id="r1")], CFG)
    row = next(r for r in out.rows if r["sku"] == "1303050")
    assert row["_provenance"]["widthMm"]["sourcePage"] == "Page 6"
    assert row["_provenance"]["listPrice"]["sourcePage"] == "Page 7"


def test_group_without_spine_kept_and_flagged():
    rows = [{"sku": None, "productFamily": "ZZ-1", "widthMm": 5, "sourcePage": "Page 1"}]
    out = MergeRecords().apply([TransformInput(rows=rows, source_result_id="r1")], CFG)
    assert len(out.rows) == 1
    assert any(f["flag"] == "no_spine" for f in out.flags)


def test_unjoinable_when_group_key_empty():
    rows = [{"sku": "X1", "productFamily": "", "listPrice": 9, "sourcePage": "Page 2"}]
    out = MergeRecords().apply([TransformInput(rows=rows, source_result_id="r1")], CFG)
    assert any(f["flag"] == "unjoinable" for f in out.flags)
