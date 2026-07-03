"""Registry of dimension scorers. Add a dimension = add one entry here (seam #1)."""
from __future__ import annotations

from typing import Any, Callable

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.text import score_text

Scorer = Callable[[ParsedDocument, dict[str, Any]], tuple[float, dict[str, Any]]]

SCORERS: dict[str, Scorer] = {
    "text": score_text,
}


def get_scorer(dimension: str) -> Scorer:
    return SCORERS[dimension]
