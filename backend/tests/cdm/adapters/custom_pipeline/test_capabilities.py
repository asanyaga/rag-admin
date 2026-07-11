from app.cdm.adapters.custom_pipeline.capabilities import (
    BLOCK_PRODUCING, STAGING, Capability, resolve_precedence,
)

TB, O, L = (Capability.TABLE_DETECTION, Capability.TEXT_OCR,
            Capability.LAYOUT_ANALYSIS)


def test_capability_kinds():
    assert BLOCK_PRODUCING == frozenset({L, TB, O})
    assert STAGING == frozenset()


def test_layout_analysis_is_block_producing():
    assert Capability.LAYOUT_ANALYSIS in BLOCK_PRODUCING
    assert Capability.LAYOUT_ANALYSIS not in STAGING


def test_text_extraction_is_gone():
    assert not hasattr(Capability, "TEXT_EXTRACTION")


def test_default_order_table_beats_layout_beats_ocr():
    r = resolve_precedence(cid_corrupt=False, ocr_prefer=False)
    assert r[TB] > r[L] > r[O]


def test_cid_corrupt_page_flips_ocr_above_layout():
    r = resolve_precedence(cid_corrupt=True, ocr_prefer=False)
    assert r[TB] > r[O] > r[L]


def test_ocr_prefer_flips_ocr_above_layout():
    r = resolve_precedence(cid_corrupt=False, ocr_prefer=True)
    assert r[TB] > r[O] > r[L]
