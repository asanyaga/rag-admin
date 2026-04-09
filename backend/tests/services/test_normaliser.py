"""Tests for the extraction result normaliser."""
import pytest

from app.services.extraction.normaliser import normalise


# ---------------------------------------------------------------------------
# Schema fixtures
# ---------------------------------------------------------------------------

SCHEMA_ARRAY_ONLY = {
    "properties": {
        "transactions": {
            "type": "array",
            "items": {
                "properties": {
                    "receipt_number": {"type": "string"},
                    "amount": {"type": "number"},
                }
            },
        }
    }
}

SCHEMA_SCALAR_ONLY = {
    "properties": {
        "invoice_number": {"type": "string"},
        "total_amount": {"type": "number"},
    }
}

SCHEMA_MIXED = {
    "properties": {
        "vendor_name": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": {
                "properties": {
                    "description": {"type": "string"},
                    "price": {"type": "number"},
                }
            },
        },
    }
}


# ---------------------------------------------------------------------------
# LlamaExtract (merge_pages) — array-only schema
# ---------------------------------------------------------------------------

class TestMergePages:
    def test_merges_array_fields_across_pages(self):
        data = [
            {"transactions": [{"receipt_number": "A", "amount": 100}]},
            {"transactions": [{"receipt_number": "B", "amount": 200}]},
        ]
        result = normalise(data, "llamaextract", SCHEMA_ARRAY_ONLY)
        assert "transactions" in result
        assert len(result["transactions"]) == 2
        assert result["transactions"][0]["receipt_number"] == "A"
        assert result["transactions"][1]["receipt_number"] == "B"

    def test_single_page(self):
        data = [
            {"transactions": [{"receipt_number": "A", "amount": 100}]},
        ]
        result = normalise(data, "llamaextract", SCHEMA_ARRAY_ONLY)
        assert len(result["transactions"]) == 1

    def test_empty_pages(self):
        data = [
            {"transactions": []},
            {"transactions": [{"receipt_number": "A", "amount": 100}]},
        ]
        result = normalise(data, "llamaextract", SCHEMA_ARRAY_ONLY)
        assert len(result["transactions"]) == 1

    def test_mixed_schema_merges_arrays_keeps_first_scalar(self):
        data = [
            {"vendor_name": "Acme", "line_items": [{"description": "Widget", "price": 10}]},
            {"vendor_name": "Acme Corp", "line_items": [{"description": "Gadget", "price": 20}]},
        ]
        result = normalise(data, "llamaextract", SCHEMA_MIXED)
        assert result["vendor_name"] == "Acme"  # first_page
        assert len(result["line_items"]) == 2


# ---------------------------------------------------------------------------
# Flat pipeline — already a dict
# ---------------------------------------------------------------------------

class TestFlatDict:
    def test_dict_passes_through(self):
        data = {"transactions": [{"receipt_number": "A"}]}
        result = normalise(data, "landing_ai", SCHEMA_ARRAY_ONLY)
        assert result == data

    def test_scalar_dict_passes_through(self):
        data = {"invoice_number": "INV-001", "total_amount": 1500}
        result = normalise(data, "landing_ai", SCHEMA_SCALAR_ONLY)
        assert result == data


# ---------------------------------------------------------------------------
# Flat pipeline — list input
# ---------------------------------------------------------------------------

class TestFlatList:
    def test_flat_list_wraps_under_single_array_field(self):
        data = [
            {"receipt_number": "A", "amount": 100},
            {"receipt_number": "B", "amount": 200},
        ]
        result = normalise(data, "landing_ai", SCHEMA_ARRAY_ONLY)
        assert "transactions" in result
        assert len(result["transactions"]) == 2

    def test_flat_list_with_scalar_schema_returns_first(self):
        data = [
            {"invoice_number": "INV-001", "total_amount": 1500},
        ]
        result = normalise(data, "landing_ai", SCHEMA_SCALAR_ONLY)
        assert result["invoice_number"] == "INV-001"


# ---------------------------------------------------------------------------
# Unknown extraction method — auto-detect fallback
# ---------------------------------------------------------------------------

class TestAutoDetect:
    def test_unknown_method_with_paginated_list(self):
        data = [
            {"transactions": [{"receipt_number": "A"}]},
            {"transactions": [{"receipt_number": "B"}]},
        ]
        result = normalise(data, "some_new_pipeline", SCHEMA_ARRAY_ONLY)
        assert len(result["transactions"]) == 2

    def test_unknown_method_with_dict(self):
        data = {"invoice_number": "INV-001"}
        result = normalise(data, "some_new_pipeline", SCHEMA_SCALAR_ONLY)
        assert result == data

    def test_unknown_method_with_flat_records(self):
        data = [
            {"receipt_number": "A", "amount": 100},
            {"receipt_number": "B", "amount": 200},
        ]
        result = normalise(data, "some_new_pipeline", SCHEMA_ARRAY_ONLY)
        assert "transactions" in result
        assert len(result["transactions"]) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_none_returns_empty(self):
        result = normalise(None, "llamaextract", SCHEMA_ARRAY_ONLY)
        assert result == {}

    def test_empty_list_returns_empty(self):
        result = normalise([], "llamaextract", SCHEMA_ARRAY_ONLY)
        assert result == {}

    def test_empty_dict_returns_empty(self):
        result = normalise({}, "llamaextract", SCHEMA_ARRAY_ONLY)
        assert result == {}

    def test_empty_schema_properties(self):
        result = normalise({"foo": "bar"}, "llamaextract", {"properties": {}})
        assert result == {"foo": "bar"}

    def test_missing_properties_key(self):
        result = normalise({"foo": "bar"}, "llamaextract", {})
        assert result == {"foo": "bar"}
