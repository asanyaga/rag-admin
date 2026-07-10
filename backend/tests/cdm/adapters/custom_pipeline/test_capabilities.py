from app.cdm.adapters.custom_pipeline.capabilities import (
    BLOCK_PRODUCING, STAGING, Capability, resolve_precedence,
)

T, TB, O, L = (Capability.TEXT_EXTRACTION, Capability.TABLE_DETECTION,
               Capability.TEXT_OCR, Capability.LAYOUT_ANALYSIS)


def test_capability_kinds():
    assert BLOCK_PRODUCING == frozenset({T, TB, O})
    assert STAGING == frozenset({L})


def test_default_order_table_beats_text_beats_ocr():
    r = resolve_precedence(cid_corrupt=False, ocr_prefer=False)
    assert r[TB] > r[T] > r[O]


def test_cid_corrupt_page_flips_ocr_above_text():
    r = resolve_precedence(cid_corrupt=True, ocr_prefer=False)
    assert r[TB] > r[O] > r[T]


def test_ocr_prefer_flips_ocr_above_text():
    r = resolve_precedence(cid_corrupt=False, ocr_prefer=True)
    assert r[TB] > r[O] > r[T]


def test_staging_capability_has_no_rank():
    assert L not in resolve_precedence(cid_corrupt=False, ocr_prefer=False)
