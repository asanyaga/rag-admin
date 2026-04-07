"""Line item matching using the Hungarian algorithm."""
from typing import Any

import numpy as np
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment


def match_line_items(
    predicted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    numeric_tolerance: float = 0.01,
    cost_threshold: float = 0.5,
) -> dict:
    """Match predicted line items to expected using Hungarian algorithm.

    Returns:
        {
            "precision": float,
            "recall": float,
            "f1": float,
            "matched": int,
            "predicted": int,
            "expected": int,
            "matches": [{"predicted_idx": int, "expected_idx": int, "cost": float}, ...],
        }
    """
    n_pred = len(predicted)
    n_exp = len(expected)

    if n_pred == 0 and n_exp == 0:
        return {
            "precision": 1.0, "recall": 1.0, "f1": 1.0,
            "matched": 0, "predicted": 0, "expected": 0, "matches": [],
        }
    if n_pred == 0 or n_exp == 0:
        return {
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "matched": 0, "predicted": n_pred, "expected": n_exp, "matches": [],
        }

    # Build cost matrix
    cost_matrix = np.zeros((n_pred, n_exp))
    for i, pred in enumerate(predicted):
        for j, exp in enumerate(expected):
            cost_matrix[i, j] = _item_cost(pred, exp, numeric_tolerance)

    # Solve assignment
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    # Filter matches that exceed threshold
    matches = []
    matched = 0
    for r, c in zip(row_ind, col_ind):
        cost = cost_matrix[r, c]
        if cost <= cost_threshold:
            matched += 1
            matches.append({
                "predicted_idx": int(r),
                "expected_idx": int(c),
                "cost": round(float(cost), 4),
            })

    precision = matched / n_pred if n_pred > 0 else 0.0
    recall = matched / n_exp if n_exp > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "matched": matched,
        "predicted": n_pred,
        "expected": n_exp,
        "matches": matches,
    }


def _item_cost(
    pred: dict[str, Any],
    exp: dict[str, Any],
    numeric_tolerance: float = 0.01,
) -> float:
    """Compute cost between a predicted and expected line item.

    Cost = 0.6 * (1 - description_similarity) + 0.4 * amount_mismatch
    """
    # Description similarity
    pred_desc = str(pred.get("description", "")).strip().lower()
    exp_desc = str(exp.get("description", "")).strip().lower()
    desc_sim = fuzz.ratio(pred_desc, exp_desc) / 100.0 if (pred_desc or exp_desc) else 1.0

    # Amount/total comparison
    amount_mismatch = 0.0
    for key in ("total", "amount", "price", "unit_price"):
        if key in exp:
            try:
                pred_val = float(pred.get(key, 0))
                exp_val = float(exp[key])
                if abs(pred_val - exp_val) > numeric_tolerance:
                    amount_mismatch = 1.0
            except (ValueError, TypeError):
                amount_mismatch = 1.0
            break

    return 0.6 * (1.0 - desc_sim) + 0.4 * amount_mismatch
