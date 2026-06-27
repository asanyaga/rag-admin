# backend/app/services/extraction/transforms/merge_records.py
"""merge_records: group rows by a normalized key; collapse non-spine rows into spine rows."""
from __future__ import annotations

from typing import Any

from app.services.extraction.transforms.base import TransformInput, TransformResult
from app.services.extraction.transforms.keys import normalize_key

_META = "_provenance"


def _is_present(row: dict, fields: list[str]) -> bool:
    return all(row.get(f) not in (None, "", 0) for f in fields)


def _group_key(row: dict, group_by: list[str], norm_cfg: dict) -> str:
    return "|".join(normalize_key(row.get(f), norm_cfg) for f in group_by)


class MergeRecords:
    transform_type = "merge_records"

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult:
        group_by = config["groupBy"]
        norm_cfg = config.get("keyNormalize", {})
        spine_fields = config["spine"]["whereFieldsPresent"]
        conflict = config.get("conflict", "prefer_spine")
        on_no_spine = config.get("onGroupWithoutSpine", "keep")

        # pool rows, tagging each with its source result id
        pooled: list[tuple[dict, str | None]] = [
            (row, inp.source_result_id) for inp in inputs for row in inp.rows
        ]

        groups: dict[str, list[tuple[dict, str | None]]] = {}
        out_rows: list[dict] = []
        flags: list[dict] = []

        for row, rid in pooled:
            key = _group_key(row, group_by, norm_cfg)
            if key == "" or key == "|".join([""] * len(group_by)):
                idx = len(out_rows)
                out_rows.append({**{k: v for k, v in row.items() if k != _META},
                                 _META: self._prov(row, rid)})
                flags.append({"rowIndex": idx, "flag": "unjoinable"})
                continue
            groups.setdefault(key, []).append((row, rid))

        for key, members in groups.items():
            spine = [(r, rid) for r, rid in members if _is_present(r, spine_fields)]
            enrich = [(r, rid) for r, rid in members if not _is_present(r, spine_fields)]

            if not spine:
                if on_no_spine == "drop":
                    continue
                for r, rid in members:
                    idx = len(out_rows)
                    out_rows.append({**{k: v for k, v in r.items() if k != _META},
                                     _META: self._prov(r, rid)})
                    flags.append({"rowIndex": idx, "flag": "no_spine"})
                continue

            for r, rid in spine:
                merged = {k: v for k, v in r.items() if k != _META}
                prov = self._prov(r, rid)
                had_enrich = False
                for er, erid in enrich:
                    had_enrich = True
                    for k, v in er.items():
                        if k == _META or v in (None, "", 0):
                            continue
                        cur = merged.get(k)
                        if cur in (None, "", 0):
                            merged[k] = v
                            prov[k] = {"sourceResultId": erid, "sourcePage": er.get("sourcePage")}
                        elif cur != v and conflict == "first_non_null":
                            pass  # keep spine value; first-non-null already satisfied
                        elif cur != v:
                            flags.append({"rowIndex": len(out_rows), "flag": "conflict"})
                idx = len(out_rows)
                merged[_META] = prov
                out_rows.append(merged)
                if not had_enrich:
                    flags.append({"rowIndex": idx, "flag": "no_specs"})

        return TransformResult(rows=out_rows, flags=flags)

    @staticmethod
    def _prov(row: dict, rid: str | None) -> dict:
        page = row.get("sourcePage")
        return {k: {"sourceResultId": rid, "sourcePage": page}
                for k in row if k != _META}
