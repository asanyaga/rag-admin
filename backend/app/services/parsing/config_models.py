"""Per-parser config models, and normalization of a config before it is hashed.

Normalization exists for provenance. A ParseRun records what was run, and
`config_hash` is how runs are compared and reused — so a config of
``{"parser": "docling"}`` is a bad record: it does not say which layout model,
OCR engine, or table mode produced the output, and it hashes the same as any
other run that happened to leave everything defaulted.

Resolving through the parser's config model before hashing makes the stored
config self-describing, and has a useful side effect: configs that differ only
in what was left implicit collapse to the same hash, so reuse works across
equivalent spellings.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from app.cdm.models import ParserKind
from app.services.parsing.docling_config import ROUTING_KEYS


def parser_config_models() -> Dict[str, Type[BaseModel]]:
    """Parsers with a validated config model.

    Others pass through unvalidated and unnormalized for now — llamaparse's
    tier/expand/version still get no treatment (review §1.4).
    """
    from app.services.parsing.docling_config import DoclingConfig

    return {ParserKind.DOCLING.value: DoclingConfig}


def normalize_parse_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve a config through its parser's model, keeping routing keys.

    Unknown parsers and parsers without a model are returned unchanged, so this
    is safe to call on every parse. Invalid configs are returned unchanged too —
    validation and its error reporting belong to the boundary and the runner,
    not here.
    """
    config = dict(config or {})
    model = parser_config_models().get(config.get("parser", ""))
    if model is None:
        return config

    options = {k: v for k, v in config.items() if k not in ROUTING_KEYS}
    try:
        resolved = model.model_validate(options).model_dump(mode="json")
    except Exception:  # noqa: BLE001 — invalid configs fail with a real message
        return config                                   # at the boundary/runner

    routing = {k: v for k, v in config.items() if k in ROUTING_KEYS}
    return {**resolved, **routing}
