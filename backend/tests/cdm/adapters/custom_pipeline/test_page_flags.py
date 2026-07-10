import fitz
from app.cdm.adapters.custom_pipeline.page_flags import (
    PageFlagsConfig, compute_page_flags, pua_ratio,
)


def _pdf(tmp_path, text: str):
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    if text:
        page.insert_text((72, 72), text, fontsize=11)
    p = tmp_path / "f.pdf"; doc.save(str(p)); doc.close()
    return p


def test_empty_page_has_no_usable_text_layer(tmp_path):
    flags = compute_page_flags(_pdf(tmp_path, ""), PageFlagsConfig())
    assert flags[0].char_count == 0
    assert flags[0].cid_corrupt is False


def test_text_page_reports_char_count(tmp_path):
    flags = compute_page_flags(_pdf(tmp_path, "Hello invoice world"), PageFlagsConfig())
    assert flags[0].char_count >= 15
    assert flags[0].pua_ratio == 0.0
    assert flags[0].cid_corrupt is False


def test_pua_ratio_detects_private_use_characters():
    # A broken CID font decodes to private-use codepoints. We cannot synthesize
    # such a PDF (base-14 fonts substitute these glyphs on write), so the
    # heuristic is tested directly on the text it would extract.
    corrupt = "".join(chr(0xE000 + (i % 10)) for i in range(60))
    assert pua_ratio(corrupt) == 1.0
    assert pua_ratio("Hello invoice world") == 0.0
    assert pua_ratio("") == 0.0
    assert pua_ratio("ab" + chr(0xE000) * 2) == 0.5


def test_cid_corrupt_is_derived_from_the_configured_threshold(tmp_path):
    # Drive the threshold below any achievable ratio to prove cid_corrupt is
    # wired to config rather than hardcoded.
    pdf = _pdf(tmp_path, "Hello invoice world")
    assert compute_page_flags(pdf, PageFlagsConfig()).get(0).cid_corrupt is False
    assert compute_page_flags(pdf, PageFlagsConfig(cid_ratio=-0.1))[0].cid_corrupt is True


from app.cdm.adapters.custom_pipeline.page_flags import image_is_uncovered

CFG = PageFlagsConfig()  # min_uncovered_coverage=0.10, covered_overlap=0.6


def test_image_is_uncovered_true_for_large_untexted_image():
    # image covers 25% of a 100x100 page, no words over it
    assert image_is_uncovered((0, 0, 50, 50), [], 100.0, 100.0, CFG) is True


def test_image_is_uncovered_false_when_text_covers_it():
    # a word box spanning the whole image -> covered
    assert image_is_uncovered((0, 0, 50, 50), [(0, 0, 50, 50)], 100.0, 100.0, CFG) is False


def test_image_is_uncovered_false_for_tiny_image_below_coverage_floor():
    # image covers 1% of page -> below min_uncovered_coverage -> ignored
    assert image_is_uncovered((0, 0, 10, 10), [], 100.0, 100.0, CFG) is False


def test_flags_expose_has_text_layer(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Plenty of real text here on the page", fontsize=11)
    p = tmp_path / "t.pdf"; doc.save(str(p)); doc.close()
    flags = compute_page_flags(p, PageFlagsConfig())
    assert flags[0].has_text_layer is True
    assert flags[0].has_uncovered_image is False


def test_flags_flag_a_full_bleed_untexted_image(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=200, height=200)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 180, 180))
    pix.set_rect(pix.irect, (10, 20, 30))
    page.insert_image(fitz.Rect(10, 10, 190, 190), pixmap=pix)
    p = tmp_path / "img.pdf"; doc.save(str(p)); doc.close()
    flags = compute_page_flags(p, PageFlagsConfig())
    assert flags[0].has_text_layer is False       # no text
    assert flags[0].has_uncovered_image is True    # big image, nothing over it
