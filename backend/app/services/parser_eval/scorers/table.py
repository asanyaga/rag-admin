"""Table-structure+content scorer — compares parsed tables to expected tables via TEDS.

Slice 1 matches tables by order (i-th expected vs i-th parsed); an unmatched table on
either side scores TEDS 0. Aggregate TEDS is size-weighted by the larger table's cell
count so big tables dominate. Robust position-based matching is Slice 3.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.teds import cell_count, teds
from app.services.parser_eval.table_html import extract_cdm_tables


def score_table(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[dict[str, float], dict]:
    expected_html = [t.get("html", "") for t in expected.get("tables", [])]
    parsed_html = [html for _page, html in extract_cdm_tables(cdm)]

    n = max(len(expected_html), len(parsed_html))
    per_table: list[dict[str, Any]] = []
    weighted_sum = 0.0
    total_weight = 0.0
    for i in range(n):
        exp = expected_html[i] if i < len(expected_html) else None
        par = parsed_html[i] if i < len(parsed_html) else None
        score = teds(exp, par) if (exp is not None and par is not None) else 0.0
        weight = max(cell_count(exp) if exp else 0, cell_count(par) if par else 0, 1)
        weighted_sum += score * weight
        total_weight += weight
        per_table.append({"index": i, "teds": score,
                          "expected_present": exp is not None, "parsed_present": par is not None})

    teds_metric = weighted_sum / total_weight if total_weight else 1.0

    expected_count = len(expected_html)
    if expected_count == 0:
        recall = 1.0 if len(parsed_html) == 0 else 0.0
    else:
        recall = min(len(parsed_html), expected_count) / expected_count

    metrics = {"teds": teds_metric, "table_recall": recall}
    details = {"per_table": per_table,
               "expected_count": expected_count, "parsed_count": len(parsed_html)}
    return metrics, details
