"""Unit tests for the extraction evaluation engine."""
import pytest

from app.services.extraction_eval.engine import (
    EvalConfig,
    score_document,
)
from app.services.extraction_eval.field_matchers import (
    exact_match,
    fuzzy_match,
    numeric_match,
    date_match,
    score_field,
)
from app.services.extraction_eval.line_item_matcher import match_line_items


# ---------------------------------------------------------------------------
# Field matchers
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_identical(self):
        assert exact_match("Naivas", "Naivas") is True

    def test_case_insensitive(self):
        assert exact_match("NAIVAS", "naivas") is True

    def test_strips_whitespace(self):
        assert exact_match("  Naivas  ", "Naivas") is True

    def test_different(self):
        assert exact_match("Naivas", "Carrefour") is False

    def test_both_none(self):
        assert exact_match(None, None) is True

    def test_one_none(self):
        assert exact_match(None, "Naivas") is False
        assert exact_match("Naivas", None) is False


class TestFuzzyMatch:
    def test_identical(self):
        assert fuzzy_match("Naivas Supermarket", "Naivas Supermarket") == 1.0

    def test_similar(self):
        score = fuzzy_match("Naivas Ltd", "Naivas Supermarket")
        assert 0.4 < score < 0.9

    def test_both_none(self):
        assert fuzzy_match(None, None) == 1.0

    def test_one_none(self):
        assert fuzzy_match(None, "Naivas") == 0.0


class TestNumericMatch:
    def test_exact(self):
        assert numeric_match(175.00, 175.00) is True

    def test_within_tolerance(self):
        assert numeric_match(175.005, 175.00, tolerance=0.01) is True

    def test_outside_tolerance(self):
        assert numeric_match(176.00, 175.00, tolerance=0.01) is False

    def test_string_numbers(self):
        assert numeric_match("175.00", "175.00") is True

    def test_both_none(self):
        assert numeric_match(None, None) is True

    def test_non_numeric(self):
        assert numeric_match("abc", "175.00") is False


class TestDateMatch:
    def test_same_format(self):
        assert date_match("2025-11-15", "2025-11-15") is True

    def test_different_format(self):
        assert date_match("15/11/2025", "2025-11-15") is True

    def test_different_dates(self):
        assert date_match("2025-11-15", "2025-11-16") is False

    def test_both_none(self):
        assert date_match(None, None) is True

    def test_invalid(self):
        assert date_match("not-a-date", "2025-11-15") is False


class TestScoreField:
    def test_string_exact(self):
        result = score_field("Naivas", "Naivas", "string")
        assert result["exact"] is True
        assert result["score"] == 1.0

    def test_string_fuzzy(self):
        result = score_field("Naivas Ltd", "Naivas Supermarket", "string")
        assert result["exact"] is False
        assert 0.0 < result["score"] < 1.0
        assert result["fuzzy_score"] is not None

    def test_number_match(self):
        result = score_field(175.00, 175.00, "number")
        assert result["score"] == 1.0

    def test_number_mismatch(self):
        result = score_field(176.00, 175.00, "number")
        assert result["score"] == 0.0

    def test_date_match(self):
        result = score_field("2025-11-15", "2025-11-15", "date")
        assert result["score"] == 1.0

    def test_null_both(self):
        result = score_field(None, None, "string")
        assert result["score"] == 1.0

    def test_null_one(self):
        result = score_field(None, "Naivas", "string")
        assert result["score"] == 0.0


# ---------------------------------------------------------------------------
# Line item matcher
# ---------------------------------------------------------------------------


class TestMatchLineItems:
    def test_perfect_match(self):
        predicted = [
            {"description": "Bread White 400g", "total": 65.00},
            {"description": "Milk 500ml", "total": 45.00},
        ]
        expected = [
            {"description": "Bread White 400g", "total": 65.00},
            {"description": "Milk 500ml", "total": 45.00},
        ]
        result = match_line_items(predicted, expected)
        assert result["matched"] == 2
        assert result["f1"] == 1.0

    def test_partial_match(self):
        predicted = [
            {"description": "Bread White", "total": 65.00},
            {"description": "Eggs 6-pack", "total": 30.00},
        ]
        expected = [
            {"description": "Bread White 400g", "total": 65.00},
            {"description": "Milk 500ml", "total": 45.00},
        ]
        result = match_line_items(predicted, expected)
        # Bread should match, eggs/milk probably not
        assert result["matched"] >= 1
        assert 0 < result["f1"] <= 1.0

    def test_empty_both(self):
        result = match_line_items([], [])
        assert result["f1"] == 1.0
        assert result["matched"] == 0

    def test_empty_predicted(self):
        result = match_line_items([], [{"description": "Bread", "total": 65}])
        assert result["f1"] == 0.0

    def test_empty_expected(self):
        result = match_line_items([{"description": "Bread", "total": 65}], [])
        assert result["f1"] == 0.0

    def test_more_predicted_than_expected(self):
        predicted = [
            {"description": "Bread", "total": 65},
            {"description": "Milk", "total": 45},
            {"description": "Eggs", "total": 30},
        ]
        expected = [
            {"description": "Bread", "total": 65},
        ]
        result = match_line_items(predicted, expected)
        assert result["recall"] == 1.0
        assert result["precision"] < 1.0


# ---------------------------------------------------------------------------
# Document scoring
# ---------------------------------------------------------------------------


class TestScoreDocument:
    def test_perfect_match(self):
        predicted = {
            "vendor_name": "Naivas Supermarket",
            "date": "2025-11-15",
            "total": 175.00,
            "payment_method": "M-Pesa",
        }
        expected = dict(predicted)
        result = score_document(predicted, expected)
        assert result.overall_score >= 0.95

    def test_partial_match(self):
        predicted = {
            "vendor_name": "Naivas Ltd",
            "date": "2025-11-15",
            "total": 175.00,
            "payment_method": "Mpesa",
        }
        expected = {
            "vendor_name": "Naivas Supermarket",
            "date": "2025-11-15",
            "total": 175.00,
            "payment_method": "M-Pesa",
        }
        result = score_document(predicted, expected)
        assert 0.5 < result.overall_score < 1.0
        assert "vendor_name" in result.field_scores
        assert result.field_scores["vendor_name"]["exact"] is False

    def test_with_line_items(self):
        predicted = {
            "vendor_name": "Naivas",
            "total": 110.00,
            "line_items": [
                {"description": "Bread White 400g", "total": 65.00},
                {"description": "Milk 500ml", "total": 45.00},
            ],
        }
        expected = {
            "vendor_name": "Naivas",
            "total": 110.00,
            "line_items": [
                {"description": "Bread White 400g", "total": 65.00},
                {"description": "Milk 500ml", "total": 45.00},
            ],
        }
        result = score_document(predicted, expected)
        assert result.overall_score >= 0.95
        assert result.line_items_score is not None
        assert result.line_items_score["f1"] == 1.0

    def test_empty_predicted(self):
        predicted = {}
        expected = {"vendor_name": "Naivas", "total": 175.00}
        result = score_document(predicted, expected)
        assert result.overall_score == 0.0

    def test_custom_config(self):
        config = EvalConfig(
            numeric_tolerance=0.1,
            weights={"exact": 0.5, "fuzzy": 0.5, "numeric": 0.0, "line_items": 0.0},
        )
        predicted = {"vendor_name": "Naivas Ltd", "total": 175.05}
        expected = {"vendor_name": "Naivas Supermarket", "total": 175.00}
        result = score_document(predicted, expected, config)
        assert result.evaluation_metadata["numeric_tolerance"] == 0.1

    def test_missing_fields(self):
        predicted = {"vendor_name": "Naivas"}
        expected = {"vendor_name": "Naivas", "total": 175.00, "date": "2025-11-15"}
        result = score_document(predicted, expected)
        # Should score vendor_name as 1.0, total and date as 0.0
        assert result.field_scores["vendor_name"]["score"] == 1.0
        assert result.field_scores["total"]["score"] == 0.0
        assert result.field_scores["date"]["score"] == 0.0
