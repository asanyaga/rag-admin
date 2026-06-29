"""join_results: assemble target records from N focused single-schema ExtractionResults.

Each input result is authoritative for its own columns. No spine detection or conflict
resolution — columns must be non-overlapping (validated). Flags: unmatched, null_key,
ambiguous_right.

sourcePage is treated as a passthrough field: excluded from column-conflict detection
and from right-side column output (the left result's value is kept; per-field provenance
for right cells is captured in _META).
"""
from __future__ import annotations

from typing import Any

from app.services.extraction.transforms.base import (
    TransformInput,
    TransformResult,
    TransformValidationError,
)

_META = "_provenance"

# Fields excluded from column-conflict detection and right-side column output.
# sourcePage appears in every extraction result as row-level provenance metadata;
# treating it as a conflict would make join_results unusable on real data.
_PASSTHROUGH_FIELDS = frozenset({"sourcePage"})


def _input_columns(inp: TransformInput) -> list[str]:
    """Ordered column list from all rows (excluding _META and passthrough fields)."""
    seen: dict[str, None] = {}
    for row in inp.rows:
        for k in row:
            if k != _META and k not in _PASSTHROUGH_FIELDS:
                seen[k] = None
    return list(seen.keys())


def _prov_from_row(row: dict, rid: str | None) -> dict:
    page = row.get("sourcePage")
    return {k: {"sourceResultId": rid, "sourcePage": page} for k in row if k != _META}


def _null_prov(cols: list[str]) -> dict:
    return {c: {"sourceResultId": None, "sourcePage": None} for c in cols}


class JoinResults:
    transform_type = "join_results"

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult:
        join_key: str = config["joinKey"]
        join_type: str = config.get("joinType", "left")

        # ── Validation ────────────────────────────────────────────────────────
        if len(inputs) < 2 or len(inputs) > 5:
            raise TransformValidationError(
                "invalid_result_count",
                f"join_results requires 2–5 inputs, got {len(inputs)}",
            )

        input_cols: list[list[str]] = [_input_columns(inp) for inp in inputs]

        for i, cols in enumerate(input_cols):
            if join_key not in cols:
                raise TransformValidationError(
                    "join_key_missing",
                    f"joinKey {join_key!r} not found in input {i}",
                )

        seen_in: dict[str, list[int]] = {}
        for i, cols in enumerate(input_cols):
            for c in cols:
                if c == join_key:
                    continue
                seen_in.setdefault(c, []).append(i)
        conflicts = {c: idxs for c, idxs in seen_in.items() if len(idxs) > 1}
        if conflicts:
            detail = "; ".join(
                f"{c!r} in inputs {idxs}" for c, idxs in conflicts.items()
            )
            raise TransformValidationError("column_conflict", detail)

        # ── Setup ─────────────────────────────────────────────────────────────
        left_inp = inputs[0]
        right_inps = inputs[1:]

        # Right-side columns: exclude joinKey and passthrough fields
        right_cols_per: list[list[str]] = [
            [c for c in cols if c != join_key]
            for cols in input_cols[1:]
        ]

        # Right lookup tables: {str(key_value): [row, ...]}; track ambiguous keys
        right_lookups: list[dict[str, list[dict]]] = []
        ambiguous_keys_per: list[set[str]] = []
        for inp in right_inps:
            lookup: dict[str, list[dict]] = {}
            for row in inp.rows:
                kv = row.get(join_key)
                if kv is None:
                    continue  # dead entry — null right keys never match
                lookup.setdefault(str(kv), []).append(row)
            right_lookups.append(lookup)
            ambiguous_keys_per.append({k for k, rows in lookup.items() if len(rows) > 1})

        # ── Join ──────────────────────────────────────────────────────────────
        out_rows: list[dict] = []
        flags: list[dict] = []

        for left_row in left_inp.rows:
            key_val = left_row.get(join_key)
            row_flags: list[str] = []

            # Start with all left row fields (excluding _META)
            merged = {k: v for k, v in left_row.items() if k != _META}
            prov = _prov_from_row(left_row, left_inp.source_result_id)

            if key_val is None:
                # null_key: always pass through regardless of join type
                for rc in right_cols_per:
                    for c in rc:
                        merged[c] = None
                    prov.update(_null_prov(rc))
                row_flags.append("null_key")
            else:
                key_str = str(key_val)
                skip_for_inner = False

                for rc, right_inp, lookup, amb in zip(
                    right_cols_per, right_inps, right_lookups, ambiguous_keys_per
                ):
                    matches = lookup.get(key_str, [])
                    if not matches:
                        for c in rc:
                            merged[c] = None
                        prov.update(_null_prov(rc))
                        if join_type == "inner":
                            skip_for_inner = True
                        else:
                            row_flags.append("unmatched")
                    else:
                        right_row = matches[0]
                        for c in rc:
                            merged[c] = right_row.get(c)
                        right_prov = _prov_from_row(right_row, right_inp.source_result_id)
                        for c in rc:
                            prov[c] = right_prov.get(
                                c, {"sourceResultId": None, "sourcePage": None}
                            )
                        if key_str in amb:
                            row_flags.append("ambiguous_right")

                if skip_for_inner:
                    continue

            idx = len(out_rows)
            merged[_META] = prov
            out_rows.append(merged)
            for f in row_flags:
                flags.append({"rowIndex": idx, "flag": f})

        # ── Column reorder: left cols first, then right cols per input ────────
        # Left columns include sourcePage from the left result (passthrough kept).
        # Right passthrough fields (_PASSTHROUGH_FIELDS) are excluded via input_cols.
        left_col_order = input_cols[0]
        # Also include sourcePage if it was in the original left rows
        if any("sourcePage" in row for row in left_inp.rows):
            if "sourcePage" not in left_col_order:
                left_col_order = left_col_order + ["sourcePage"]

        right_col_order = [c for rc in right_cols_per for c in rc]
        col_order = left_col_order + right_col_order

        reordered = []
        for row in out_rows:
            new_row = {c: row.get(c) for c in col_order if c in row or c in right_col_order}
            new_row[_META] = row[_META]
            reordered.append(new_row)

        return TransformResult(rows=reordered, flags=flags)
