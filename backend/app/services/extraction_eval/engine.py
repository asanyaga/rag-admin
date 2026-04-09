"""Extraction evaluation engine — pure computation, no DB calls.

Input: predicted dict, expected dict, config dict
Output: DocumentScore with field-level and line-item scores
"""
from dataclasses import dataclass, field
from typing import Any

from app.services.extraction_eval.field_matchers import score_field
from app.services.extraction_eval.line_item_matcher import match_line_items


@dataclass
class EvalConfig:
    """Configuration for the evaluation engine."""
    fuzzy_threshold: int = 85
    numeric_tolerance: float = 0.01
    line_item_cost_threshold: float = 0.5
    weights: dict[str, float] = field(default_factory=lambda: {
        "exact": 0.3,
        "fuzzy": 0.2,
        "numeric": 0.25,
        "line_items": 0.25,
    })
    # Field type overrides: {"total": "number", "date": "date"}
    field_types: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "EvalConfig":
        return cls(
            fuzzy_threshold=d.get("fuzzy_threshold", d.get("fuzzyThreshold", 85)),
            numeric_tolerance=d.get("numeric_tolerance", d.get("numericTolerance", 0.01)),
            line_item_cost_threshold=d.get("line_item_cost_threshold", 0.5),
            weights=d.get("weights", {}),
            field_types=d.get("field_types", d.get("fieldTypes", {})),
        )


@dataclass
class DocumentScore:
    """Scoring result for a single document."""
    overall_score: float
    field_scores: dict[str, dict]
    line_items_score: dict | None
    evaluation_metadata: dict


def infer_field_type(key: str, value: Any) -> str:
    """Infer field type from key name and value."""
    key_lower = key.lower()
    if any(kw in key_lower for kw in ("total", "amount", "price", "cost", "tax", "subtotal", "quantity", "qty")):
        return "number"
    if any(kw in key_lower for kw in ("date", "_at", "timestamp")):
        return "date"
    return "string"


def score_document(
    predicted: dict[str, Any],
    expected: dict[str, Any],
    config: EvalConfig | None = None,
) -> DocumentScore:
    """Score a predicted extraction against expected ground truth.

    Args:
        predicted: The extraction result's structured_data
        expected: The ground truth item's expected_data
        config: Evaluation configuration

    Returns:
        DocumentScore with field-level breakdown and overall score
    """
    if config is None:
        config = EvalConfig()

    field_scores: dict[str, dict] = {}
    line_items_score: dict | None = None

    # Separate line items from scalar fields
    predicted_line_items = None
    expected_line_items = None
    has_line_items = False

    # Collect all field keys (union of predicted and expected)
    all_keys = set()
    for key in expected:
        val = expected[key]
        if isinstance(val, list) and val and isinstance(val[0], dict):
            expected_line_items = val
            has_line_items = True
            continue
        all_keys.add(key)

    for key in predicted:
        val = predicted[key]
        if isinstance(val, list) and val and isinstance(val[0], dict):
            predicted_line_items = val
            has_line_items = True
            continue
        all_keys.add(key)

    # Score each scalar field
    for key in sorted(all_keys):
        pred_val = predicted.get(key)
        exp_val = expected.get(key)
        field_type = config.field_types.get(key, infer_field_type(key, exp_val))
        field_scores[key] = score_field(
            pred_val, exp_val, field_type, config.numeric_tolerance
        )

    # Score line items if present
    if has_line_items:
        pred_items = predicted_line_items if isinstance(predicted_line_items, list) else []
        exp_items = expected_line_items if isinstance(expected_line_items, list) else []
        line_items_score = match_line_items(
            pred_items, exp_items,
            numeric_tolerance=config.numeric_tolerance,
            cost_threshold=config.line_item_cost_threshold,
        )

    # Compute overall score
    overall = _compute_overall_score(field_scores, line_items_score, config, has_line_items)

    return DocumentScore(
        overall_score=round(overall, 4),
        field_scores=field_scores,
        line_items_score=line_items_score,
        evaluation_metadata={
            "fuzzy_threshold": config.fuzzy_threshold,
            "numeric_tolerance": config.numeric_tolerance,
            "weights": config.weights,
            "has_line_items": has_line_items,
        },
    )


def _compute_overall_score(
    field_scores: dict[str, dict],
    line_items_score: dict | None,
    config: EvalConfig,
    has_line_items: bool,
) -> float:
    """Compute weighted overall score from field and line-item scores."""
    if not field_scores and not line_items_score:
        return 0.0

    weights = config.weights or {
        "exact": 0.3, "fuzzy": 0.2, "numeric": 0.25, "line_items": 0.25,
    }

    # Compute field-level aggregates
    exact_matches = 0
    total_fields = 0
    fuzzy_scores = []
    numeric_scores = []

    for _key, score_data in field_scores.items():
        total_fields += 1
        if score_data.get("exact"):
            exact_matches += 1
        if score_data.get("fuzzy_score") is not None:
            fuzzy_scores.append(score_data["fuzzy_score"])
        else:
            numeric_scores.append(score_data["score"])

    exact_rate = exact_matches / total_fields if total_fields > 0 else 0.0
    avg_fuzzy = sum(fuzzy_scores) / len(fuzzy_scores) if fuzzy_scores else 0.0
    numeric_accuracy = (
        sum(1 for s in numeric_scores if s >= 1.0) / len(numeric_scores)
        if numeric_scores else 0.0
    )

    # Build weighted components
    components: list[tuple[float, float]] = []  # (weight, value)

    if has_line_items and line_items_score:
        w_exact = weights.get("exact", 0.3)
        w_fuzzy = weights.get("fuzzy", 0.2)
        w_numeric = weights.get("numeric", 0.25)
        w_line = weights.get("line_items", 0.25)
    else:
        w_exact = 0.4
        w_fuzzy = 0.25
        w_numeric = 0.35
        w_line = 0.0

    # No scalar fields at all — give all weight to line items
    if total_fields == 0 and has_line_items and line_items_score:
        return line_items_score["f1"]

    if total_fields > 0:
        components.append((w_exact, exact_rate))

        if fuzzy_scores:
            components.append((w_fuzzy, avg_fuzzy))
        else:
            components[0] = (components[0][0] + w_fuzzy, components[0][1])

        if numeric_scores:
            components.append((w_numeric, numeric_accuracy))
        else:
            components[0] = (components[0][0] + w_numeric, components[0][1])

    if has_line_items and line_items_score and w_line > 0:
        components.append((w_line, line_items_score["f1"]))

    total_w = sum(w for w, _ in components)
    if total_w == 0:
        return exact_rate

    return sum(w * v for w, v in components) / total_w
