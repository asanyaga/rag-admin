import csv
from pathlib import Path

from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.merge_records import MergeRecords

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sammic_price_list.csv"
CFG = {
    "groupBy": ["modelName"],
    "keyNormalize": {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]},
    "spine": {"whereFieldsPresent": ["sku"]},
    "conflict": "prefer_spine",
    "onGroupWithoutSpine": "keep",
}


def _load_rows() -> list[dict]:
    with FIXTURE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        # numeric sentinel sku values (model placeholders) are not real identities
        if not (r["sku"] or "").strip().isdigit():
            r["sku"] = None
    return rows


def test_gp40_family_collapses_to_four_priced_records():
    rows = _load_rows()
    out = MergeRecords().apply([TransformInput(rows=rows, source_result_id="r1")], CFG)
    gp40 = [r for r in out.rows if str(r.get("modelName", "")).startswith("GP-40")]
    assert len(gp40) == 4
    assert all(r["widthMm"] in ("470", 470) for r in gp40)  # inherited base spec
