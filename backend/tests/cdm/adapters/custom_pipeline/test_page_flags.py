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
