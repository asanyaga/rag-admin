"""Field-level matchers for extraction evaluation."""
from datetime import datetime, date
from typing import Any

from rapidfuzz import fuzz


def exact_match(predicted: Any, expected: Any) -> bool:
    """Case-insensitive exact match after stripping whitespace."""
    if predicted is None and expected is None:
        return True
    if predicted is None or expected is None:
        return False
    return str(predicted).strip().lower() == str(expected).strip().lower()


def fuzzy_match(predicted: Any, expected: Any) -> float:
    """Fuzzy string similarity score 0–1."""
    if predicted is None and expected is None:
        return 1.0
    if predicted is None or expected is None:
        return 0.0
    return fuzz.ratio(str(predicted).strip().lower(), str(expected).strip().lower()) / 100.0


def numeric_match(predicted: Any, expected: Any, tolerance: float = 0.01) -> bool:
    """Check if two numeric values are within tolerance."""
    if predicted is None and expected is None:
        return True
    if predicted is None or expected is None:
        return False
    try:
        return abs(float(predicted) - float(expected)) <= tolerance
    except (ValueError, TypeError):
        return False


def date_match(predicted: Any, expected: Any) -> bool:
    """Parse both values to dates and compare equality."""
    if predicted is None and expected is None:
        return True
    if predicted is None or expected is None:
        return False
    try:
        p = _parse_date(predicted)
        e = _parse_date(expected)
        return p == e
    except (ValueError, TypeError):
        return False


def _parse_date(value: Any) -> date:
    """Try to parse a date from various formats."""
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def score_field(
    predicted: Any,
    expected: Any,
    field_type: str = "string",
    numeric_tolerance: float = 0.01,
) -> dict:
    """Score a single field, returning a dict with match details.

    Returns:
        {"exact": bool, "fuzzy_score": float | None, "score": float}
    """
    # Null handling
    if predicted is None and expected is None:
        return {"exact": True, "fuzzy_score": 1.0, "score": 1.0}
    if predicted is None or expected is None:
        return {"exact": False, "fuzzy_score": 0.0, "score": 0.0}

    is_exact = exact_match(predicted, expected)

    if field_type == "number":
        is_numeric = numeric_match(predicted, expected, numeric_tolerance)
        return {
            "exact": is_exact,
            "fuzzy_score": None,
            "score": 1.0 if is_numeric else 0.0,
        }

    if field_type == "date":
        is_date = date_match(predicted, expected)
        return {
            "exact": is_exact or is_date,
            "fuzzy_score": None,
            "score": 1.0 if (is_exact or is_date) else 0.0,
        }

    # Default: string — use fuzzy score
    fuzzy = fuzzy_match(predicted, expected)
    return {
        "exact": is_exact,
        "fuzzy_score": round(fuzzy, 4),
        "score": round(fuzzy, 4),
    }
