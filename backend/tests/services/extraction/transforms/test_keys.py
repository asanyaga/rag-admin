from app.services.extraction.transforms.keys import normalize_key


def test_first_token_and_option_letters_collapse_variants():
    cfg = {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]}
    assert normalize_key("GP-40 230/50/1", cfg) == "gp-40"
    assert normalize_key("GP-40B 230/50/1", cfg) == "gp-40"
    assert normalize_key("UX-40SBC 230/50/1 DD", cfg) == "ux-40"


def test_model_line_letter_l_is_preserved():
    cfg = {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]}
    # 'L' (LITE) is not an option letter -> must NOT collapse into bare UX-50
    assert normalize_key("UX-50L 230/50/1", cfg) == "ux-50l"
    assert normalize_key("UX-50 LITE", {"firstTokenOnly": True}) == "ux-50"


def test_trim_casefold_and_none():
    assert normalize_key("  GP-35 ", {}) == "gp-35"
    assert normalize_key(None, {}) == ""
