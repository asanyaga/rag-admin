"""Table scorer — matches GT tables to parsed tables by page+content, then scores each pair.

Emits `teds` (primary), `teds_struct` (structure-only), `cell_content_f1` (content-only),
and `table_recall`. Aggregates the TEDS-family metrics as a size-weighted mean over matched
pairs; unmatched tables (missing or extra) contribute 0. Matching is order-independent
(Slice 3), replacing Slice 1's positional matching.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.table_match import match_tables
from app.services.parser_eval.scorers.teds import cell_content_f1, cell_count, teds
from app.services.parser_eval.table_html import extract_cdm_tables

_ZERO = {"teds": 0.0, "teds_struct": 0.0, "cell_content_f1": 0.0}


def score_table(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[dict[str, float], dict]:
    expected_tables = expected.get("tables", [])
    parsed = extract_cdm_tables(cdm)  # list[(page_index, html)]
    pairs = match_tables(expected_tables, parsed)

    per_table: list[dict[str, Any]] = []
    acc = {"teds": 0.0, "teds_struct": 0.0, "cell_content_f1": 0.0}
    total_weight = 0.0
    for ei, pj in pairs:
        gt_html = expected_tables[ei]["html"] if ei is not None else None
        par_html = parsed[pj][1] if pj is not None else None
        if ei is not None and pj is not None:
            scores = {"teds": teds(gt_html, par_html),
                      "teds_struct": teds(gt_html, par_html, structure_only=True),
                      "cell_content_f1": cell_content_f1(gt_html, par_html)}
            status = "matched"
            page = int(expected_tables[ei].get("page", 0))
        elif ei is not None:
            scores, status = dict(_ZERO), "missing"
            page = int(expected_tables[ei].get("page", 0))
        else:
            scores, status = dict(_ZERO), "extra"
            page = parsed[pj][0] + 1

        weight = max(cell_count(gt_html) if gt_html else 0,
                     cell_count(par_html) if par_html else 0, 1)
        for k in acc:
            acc[k] += scores[k] * weight
        total_weight += weight
        per_table.append({"expected_index": ei, "parsed_index": pj, "page": page,
                          "status": status, **scores})

    if total_weight:
        metrics = {k: acc[k] / total_weight for k in acc}
    else:
        metrics = {"teds": 1.0, "teds_struct": 1.0, "cell_content_f1": 1.0}

    expected_count = len(expected_tables)
    parsed_count = len(parsed)
    if expected_count == 0:
        metrics["table_recall"] = 1.0 if parsed_count == 0 else 0.0
    else:
        metrics["table_recall"] = min(parsed_count, expected_count) / expected_count

    details = {"per_table": per_table,
               "expected_count": expected_count, "parsed_count": parsed_count}
    return metrics, details
