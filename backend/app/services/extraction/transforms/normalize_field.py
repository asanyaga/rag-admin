"""normalize_field: apply a rule chain to a source field, write result to a new output column.

Source field is never mutated. If source value is null, output is null.
Rules execute in declaration order; null propagates (remaining rules skipped).
"""
from __future__ import annotations

import re
from typing import Any

from app.services.extraction.transforms.base import TransformInput, TransformResult

_META = "_provenance"


def _apply_rule(value: str, rule: dict) -> str | None:
    t = rule["type"]
    if t == "trim":
        chars = rule.get("chars")
        return value.strip(chars) if chars else value.strip()
    if t == "collapseWhitespace":
        return re.sub(r"\s+", " ", value)
    if t == "lowercase":
        return value.lower()
    if t == "uppercase":
        return value.upper()
    if t == "titlecase":
        return value.title()
    if t == "stripRegex":
        return re.sub(rule["pattern"], "", value)
    if t == "stripTrailingChars":
        chars: list[str] = rule["chars"]
        charset = set(chars)
        prev = None
        while prev != value:
            prev = value
            if value and value[-1] in charset:
                value = value[:-1]
        return value
    if t == "stripPrefix":
        return value.removeprefix(rule["prefix"])
    if t == "stripSuffix":
        return value.removesuffix(rule["suffix"])
    if t == "split":
        parts = value.split(rule["delimiter"])
        idx = rule["index"]
        return parts[idx] if 0 <= idx < len(parts) else value
    if t == "regexExtract":
        m = re.search(rule["pattern"], value)
        if m is None:
            return value
        group = rule.get("group", 0)
        return m.group(group)
    if t == "replace":
        return value.replace(rule["find"], rule["replacement"])
    if t == "alias":
        return rule["map"].get(value, value)
    if t == "nullifyIfIn":
        return None if value in rule["values"] else value
    raise ValueError(f"Unknown rule type: {t!r}")


def _apply_rules(value: str | None, rules: list[dict]) -> str | None:
    for rule in rules:
        if value is None:
            return None
        value = _apply_rule(value, rule)
    return value


class NormalizeField:
    transform_type = "normalize_field"

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult:
        if len(inputs) != 1:
            raise ValueError("normalize_field requires exactly one input")

        source_field: str = config["sourceField"]
        output_field: str = config["outputField"]
        rules: list[dict] = config.get("rules", [])

        inp = inputs[0]
        out_rows: list[dict] = []

        for row in inp.rows:
            new_row = dict(row)
            raw = row.get(source_field)
            if raw is None:
                new_row[output_field] = None
            else:
                new_row[output_field] = _apply_rules(str(raw), rules)

            # Carry provenance forward; tag outputField with sourceField's provenance
            existing_prov = dict(row.get(_META) or {})
            src_prov = existing_prov.get(
                source_field,
                {"sourceResultId": inp.source_result_id, "sourcePage": row.get("sourcePage")},
            )
            existing_prov[output_field] = src_prov
            new_row[_META] = existing_prov

            out_rows.append(new_row)

        return TransformResult(rows=out_rows, flags=[])
