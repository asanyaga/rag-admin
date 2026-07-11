from app.cdm.adapters.custom_pipeline.tools.tesseract_tool import (
    OcrParagraph, aggregate_paragraphs,
)


def _data(rows):
    """rows: list of (block, par, line, left, top, w, h, conf, text)."""
    keys = ["block_num", "par_num", "line_num", "left", "top", "width", "height",
            "conf", "text"]
    cols = {k: [] for k in keys}
    for r in rows:
        for k, v in zip(keys, r):
            cols[k].append(v)
    return cols


def test_words_group_into_a_single_paragraph_in_order():
    data = _data([
        (1, 1, 1, 10, 10, 40, 12, 95.0, "Hello"),
        (1, 1, 1, 55, 10, 40, 12, 90.0, "world"),
        (1, 1, 2, 10, 25, 90, 12, 80.0, "again"),
    ])
    paras = aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.0)
    assert len(paras) == 1
    assert paras[0].text == "Hello world\nagain"
    assert paras[0].bbox[0] == 0.05 and paras[0].bbox[1] == 0.10
    # union x1 = max(50, 95, 10+90=100) / 200
    assert abs(paras[0].bbox[2] - (100 / 200)) < 1e-9
    assert abs(paras[0].confidence - 0.8833) < 1e-3


def test_two_paragraphs_stay_separate():
    data = _data([
        (1, 1, 1, 10, 10, 40, 12, 90.0, "para"),
        (1, 1, 1, 55, 10, 40, 12, 90.0, "one"),
        (2, 1, 1, 10, 50, 40, 12, 70.0, "para"),
        (2, 1, 1, 55, 50, 40, 12, 70.0, "two"),
    ])
    paras = aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.0)
    assert [p.text for p in paras] == ["para one", "para two"]


def test_low_confidence_words_and_blanks_are_dropped():
    data = _data([
        (1, 1, 1, 10, 10, 40, 12, 95.0, "keep"),
        (1, 1, 1, 55, 10, 40, 12, -1.0, ""),      # tesseract's non-word rows
        (1, 1, 1, 90, 10, 40, 12, 5.0, "noise"),  # below min_confidence
    ])
    paras = aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.5)
    assert len(paras) == 1
    assert paras[0].text == "keep"
    assert isinstance(paras[0], OcrParagraph)


def test_paragraph_with_no_surviving_words_is_omitted():
    data = _data([(1, 1, 1, 10, 10, 40, 12, 1.0, "noise")])
    assert aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.5) == []
