"""Registry of dimension scorers. Add a dimension = add one ScorerSpec entry here (seam #1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.table import score_table
from app.services.parser_eval.scorers.text import score_text

ScorerFn = Callable[[ParsedDocument, dict[str, Any]], "tuple[dict[str, float], dict]"]


@dataclass(frozen=True)
class ScorerSpec:
    fn: ScorerFn
    emits: tuple[str, ...]
    primary: str


SCORERS: dict[str, ScorerSpec] = {
    "text": ScorerSpec(fn=score_text, emits=("similarity", "omission", "hallucination"),
                       primary="similarity"),
    "table": ScorerSpec(fn=score_table, emits=("teds", "table_recall"), primary="teds"),
}


def get_scorer(dimension: str) -> ScorerSpec:
    return SCORERS[dimension]
