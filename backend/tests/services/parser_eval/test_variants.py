from app.services.parser_eval.variants import variant_key


def test_variant_key_is_order_independent():
    assert variant_key("docling", {"a": 1, "b": 2}) == variant_key("docling", {"b": 2, "a": 1})


def test_variant_key_distinguishes_config_and_adapter():
    assert variant_key("custom_pipeline", {"tool": "pdfplumber"}) != variant_key("custom_pipeline", {"tool": "fitz"})
    assert variant_key("docling", {}) != variant_key("simple", {})


def test_variant_key_none_config_equals_empty():
    assert variant_key("docling", None) == variant_key("docling", {})
    assert variant_key("docling", {}).startswith("docling@")
