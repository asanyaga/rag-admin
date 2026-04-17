"""Unit tests for field_mapper — pure functions, no DB needed."""
import pytest

from app.services.agent.field_mapper import validate_field_mapping, flatten_to_rows


# ── validate_field_mapping ────────────────────────────────────────

SAMPLE_SCHEMA = [
    {"name": "receipt_date", "type": "text", "nullable": False},
    {"name": "vendor", "type": "text", "nullable": False},
    {"name": "item_description", "type": "text", "nullable": True},
    {"name": "item_price", "type": "numeric", "nullable": True},
    {"name": "item_units", "type": "integer", "nullable": True},
]


def test_validate_valid_mapping():
    mapping = {
        "receipt_date": "receipt_date",
        "vendor": "vendor",
        "items.description": "item_description",
    }
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert errors == []


def test_validate_empty_mapping():
    errors = validate_field_mapping({}, SAMPLE_SCHEMA)
    assert any("at least one" in e.lower() for e in errors)


def test_validate_nested_array_path():
    mapping = {"items.subitems.name": "item_description"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("nested" in e.lower() for e in errors)


def test_validate_unknown_destination():
    mapping = {"vendor": "nonexistent_column"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("nonexistent_column" in e for e in errors)


def test_validate_duplicate_destination():
    mapping = {"vendor": "receipt_date", "date": "receipt_date"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("duplicate" in e.lower() for e in errors)


def test_validate_missing_required_destination():
    # receipt_date and vendor are NOT nullable, only mapping one of them
    mapping = {"vendor": "vendor"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("receipt_date" in e for e in errors)


# ── flatten_to_rows ───────────────────────────────────────────────

def test_flatten_scalar_only():
    state = {"receipt_date": "2026-04-15", "vendor": "Costco"}
    mapping = {"receipt_date": "receipt_date", "vendor": "vendor"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 1
    assert rows[0] == {"receipt_date": "2026-04-15", "vendor": "Costco"}


def test_flatten_single_array():
    state = {
        "receipt_date": "2026-04-15",
        "vendor": "Costco",
        "items": [
            {"description": "Bread", "price": 2.50, "units": 1},
            {"description": "Milk", "price": 1.20, "units": 2},
        ],
    }
    mapping = {
        "receipt_date": "receipt_date",
        "vendor": "vendor",
        "items.description": "item_description",
        "items.price": "item_price",
        "items.units": "item_units",
    }
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 2
    assert rows[0] == {
        "receipt_date": "2026-04-15",
        "vendor": "Costco",
        "item_description": "Bread",
        "item_price": 2.50,
        "item_units": 1,
    }
    assert rows[1] == {
        "receipt_date": "2026-04-15",
        "vendor": "Costco",
        "item_description": "Milk",
        "item_price": 1.20,
        "item_units": 2,
    }


def test_flatten_empty_array():
    state = {"vendor": "Costco", "items": []}
    mapping = {"vendor": "vendor", "items.description": "item_description"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 0


def test_flatten_multiple_arrays_cartesian():
    state = {
        "vendor": "Costco",
        "items": [{"name": "A"}, {"name": "B"}],
        "taxes": [{"rate": 0.08}, {"rate": 0.10}],
    }
    mapping = {
        "vendor": "vendor",
        "items.name": "item_name",
        "taxes.rate": "tax_rate",
    }
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 4  # 2 items × 2 taxes
    vendors = {r["vendor"] for r in rows}
    assert vendors == {"Costco"}
    item_names = [r["item_name"] for r in rows]
    assert item_names.count("A") == 2
    assert item_names.count("B") == 2


def test_flatten_missing_field_in_element():
    state = {
        "items": [
            {"description": "Bread", "price": 2.50},
            {"description": "Milk"},  # no price
        ],
    }
    mapping = {
        "items.description": "item_description",
        "items.price": "item_price",
    }
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 2
    assert rows[0]["item_price"] == 2.50
    assert rows[1]["item_price"] is None


def test_flatten_missing_source_path():
    state = {"vendor": "Costco"}
    mapping = {"vendor": "vendor", "total": "total_amount"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 1
    assert rows[0]["vendor"] == "Costco"
    assert rows[0]["total_amount"] is None


def test_flatten_non_list_treated_as_single():
    """If a dot-path's first segment is not a list, wrap it as [value]."""
    state = {"item": {"description": "Solo", "price": 5.00}}
    mapping = {"item.description": "item_description", "item.price": "item_price"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 1
    assert rows[0] == {"item_description": "Solo", "item_price": 5.00}
