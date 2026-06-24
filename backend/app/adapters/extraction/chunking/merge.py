"""Schema-guided merge of per-chunk extraction outputs."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.ports.data_extraction import ExtractionOutput, FieldCitation

_ARRAY_HEAD_RE = re.compile(r"^([A-Za-z_][\w]*)\[(\d+)\]")


def merge_outputs(
    outputs: list[ExtractionOutput],
    schema: dict[str, Any],
    dedupe_key: str | None,
) -> ExtractionOutput:
    props = schema.get("properties") or {}
    array_fields = {k for k, v in props.items() if v.get("type") == "array"}

    merged_data: dict[str, Any] = {}
    scalar_conflicts: list[dict[str, Any]] = []
    # offset[field] = how many records already merged into that array
    offsets: dict[str, int] = {f: 0 for f in array_fields}
    citations: list[FieldCitation] = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for out in outputs:
        data = out.structured_data or {}
        # arrays: concat with optional dedupe
        for field in array_fields:
            incoming = data.get(field) or []
            bucket = merged_data.setdefault(field, [])
            base = offsets[field]
            added = 0
            for rec in incoming:
                if dedupe_key and isinstance(rec, dict):
                    if any(isinstance(e, dict) and e.get(dedupe_key) == rec.get(dedupe_key)
                           for e in bucket):
                        continue
                if not dedupe_key and rec in bucket:
                    continue
                bucket.append(rec)
                added += 1
            # citations for this chunk's array entries shift by `base`
            _repath_array_citations(out.citations or [], field, base, citations)
            offsets[field] = base + added

        # scalars / objects: first non-null wins
        for key, value in data.items():
            if key in array_fields:
                continue
            if value is None:
                continue
            if key not in merged_data or merged_data[key] is None:
                merged_data[key] = value
            elif merged_data[key] != value:
                scalar_conflicts.append(
                    {"path": key, "kept": merged_data[key], "discarded": value}
                )

        # non-array citations pass straight through
        for c in out.citations or []:
            if not _ARRAY_HEAD_RE.match(c.field_path):
                citations.append(c)

        u = ((out.extraction_metadata or {}).get("usage")) or {}
        for k in usage:
            usage[k] += int(u.get(k, 0) or 0)

    metadata: dict[str, Any] = {"usage": usage, "chunkCount": len(outputs)}
    if scalar_conflicts:
        metadata["scalarConflicts"] = scalar_conflicts

    return ExtractionOutput(
        structured_data=merged_data,
        source_parse_run_id=outputs[0].source_parse_run_id,
        citations=citations,
        provider_response_raw=None,
        extraction_metadata=metadata,
    )


def _repath_array_citations(
    chunk_citations: list[FieldCitation],
    field: str,
    base: int,
    out: list[FieldCitation],
) -> None:
    for c in chunk_citations:
        m = _ARRAY_HEAD_RE.match(c.field_path)
        if not m or m.group(1) != field:
            continue
        old_idx = int(m.group(2))
        new_path = f"{field}[{base + old_idx}]" + c.field_path[m.end():]
        out.append(replace(c, field_path=new_path))
