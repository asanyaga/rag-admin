"""Match ground-truth tables to parsed tables by page bucket + content similarity.

Slice 3: replaces Slice 1's order-based matching. Within each page, greedily pair
the highest-TEDS GT/parsed tables; leftovers are missing (GT) or extra (parsed).
Page is the only locator shared by both sides — GT is authored HTML with no bbox.
"""
from __future__ import annotations

from app.services.parser_eval.scorers.teds import teds


def match_tables(expected: list[dict],
                 parsed: list[tuple[int, str]]) -> list[tuple[int | None, int | None]]:
    exp_by_page: dict[int, list[int]] = {}
    for i, t in enumerate(expected):
        exp_by_page.setdefault(int(t.get("page", 0)), []).append(i)
    par_by_page: dict[int, list[int]] = {}
    for j, (page_index, _html) in enumerate(parsed):
        par_by_page.setdefault(page_index + 1, []).append(j)

    matched: list[tuple[int, int]] = []
    used_exp: set[int] = set()
    used_par: set[int] = set()
    for page in sorted(set(exp_by_page) | set(par_by_page)):
        pairs = [(teds(expected[ei]["html"], parsed[pj][1]), ei, pj)
                 for ei in exp_by_page.get(page, [])
                 for pj in par_by_page.get(page, [])]
        pairs.sort(key=lambda p: (-p[0], p[1], p[2]))  # best first, deterministic ties
        for _score, ei, pj in pairs:
            if ei in used_exp or pj in used_par:
                continue
            used_exp.add(ei)
            used_par.add(pj)
            matched.append((ei, pj))

    result: list[tuple[int | None, int | None]] = [
        (i, next((p for e, p in matched if e == i), None)) for i in range(len(expected))
    ]
    result.extend((None, j) for j in range(len(parsed)) if j not in used_par)
    return result
