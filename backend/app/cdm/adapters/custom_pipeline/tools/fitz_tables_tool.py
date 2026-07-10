"""FitzTablesTool — table extraction via PyMuPDF page.find_tables(). Emits CDM TABLE Blocks."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import FitzTablesConfig
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult, clamp01
from app.cdm.models import BBox, Block, BlockRole, Cell, Table


def _html(extracted: List[List[Optional[str]]]) -> str:
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{c or ''}</td>" for c in row) + "</tr>"
        for row in extracted
    )
    return f"<table>{rows_html}</table>"


def _markdown(extracted: List[List[Optional[str]]]) -> str:
    if not extracted:
        return ""
    header = "| " + " | ".join(str(c or "") for c in extracted[0]) + " |"
    sep = "| " + " | ".join("---" for _ in extracted[0]) + " |"
    body_rows = [
        "| " + " | ".join(str(c or "") for c in row) + " |"
        for row in extracted[1:]
    ]
    return "\n".join([header, sep] + body_rows)


def _plain_text(extracted: List[List[Optional[str]]]) -> str:
    return "\n".join(
        " | ".join(str(c or "") for c in row) for row in extracted
    )


class FitzTablesTool:
    tool_id = "fitz_tables"
    provides = frozenset({Capability.TABLE_DETECTION})

    def __init__(self, config: Optional[FitzTablesConfig] = None) -> None:
        self.config = config or FitzTablesConfig()
        self.page_meta: Dict[int, PageMeta] = {}

    def _config_kwargs(self) -> Dict[str, Any]:
        c = self.config
        kwargs: Dict[str, Any] = {
            "vertical_strategy": c.vertical_strategy,
            "horizontal_strategy": c.horizontal_strategy,
            "snap_tolerance": c.snap_tolerance,
            "join_tolerance": c.join_tolerance,
            "edge_min_length": c.edge_min_length,
            "min_words_vertical": c.min_words_vertical,
            "min_words_horizontal": c.min_words_horizontal,
            "intersection_tolerance": c.intersection_tolerance,
            "text_tolerance": c.text_tolerance,
        }
        for key in (
            "snap_x_tolerance", "snap_y_tolerance",
            "join_x_tolerance", "join_y_tolerance",
            "intersection_x_tolerance", "intersection_y_tolerance",
            "text_x_tolerance", "text_y_tolerance",
        ):
            val = getattr(c, key)
            if val is not None:
                kwargs[key] = val
        return kwargs

    def _norm_bbox(self, raw_bbox: Any, pm: PageMeta) -> BBox:
        x0, y0, x1, y1 = raw_bbox  # fitz top-left origin, PDF points — no y-flip
        return BBox(
            x0=clamp01(x0 / pm.width),
            y0=clamp01(y0 / pm.height),
            x1=clamp01(x1 / pm.width),
            y1=clamp01(y1 / pm.height),
            source_space="pdf_points",
            source_coords=(float(x0), float(y0), float(x1), float(y1)),
        )

    def _build_cells(
        self,
        table: Any,
        pm: Optional[PageMeta],
        extracted: List[List[Optional[str]]],
    ) -> List[Cell]:
        cells: List[Cell] = []
        row_count = table.row_count
        col_count = table.col_count
        raw_cells = table.cells  # list of Rect|None in row-major order
        for r in range(row_count):
            for c in range(col_count):
                idx = r * col_count + c
                text = ""
                if r < len(extracted) and c < len(extracted[r]):
                    text = extracted[r][c] or ""
                bbox = None
                if pm is not None and idx < len(raw_cells) and raw_cells[idx] is not None:
                    bbox = self._norm_bbox(raw_cells[idx], pm)
                cells.append(Cell(row=r, col=c, text=text.strip(), bbox=bbox))
        return cells

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
        emit: frozenset[Capability] = frozenset({Capability.TABLE_DETECTION}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")
        self.page_meta = page_meta or {}

        t0 = time.perf_counter()
        blocks: List[Block] = []
        native_by_block: Dict[str, Any] = {}
        warnings: List[str] = []
        kwargs = self._config_kwargs()

        doc = fitz.open(str(pdf_path))
        try:
            for i in range(len(doc)):
                if pages is not None and i not in pages:
                    continue
                page = doc[i]
                pm = self.page_meta.get(i)
                if pm is None:
                    warnings.append(f"page {i}: no page_meta; cell bboxes will be omitted")

                try:
                    finder = page.find_tables(**kwargs)
                    page_tables = finder.tables
                except Exception as exc:
                    warnings.append(f"page {i}: find_tables failed — {exc}")
                    continue

                for seq, table in enumerate(page_tables):
                    extracted = table.extract()
                    row_count = table.row_count
                    col_count = table.col_count
                    cells = self._build_cells(table, pm, extracted)
                    html = _html(extracted)
                    md = _markdown(extracted)
                    text = _plain_text(extracted)
                    cdm_table = Table(
                        rows=row_count,
                        cols=col_count,
                        cells=cells,
                        html=html,
                        markdown=md,
                    )
                    bbox = self._norm_bbox(table.bbox, pm) if pm is not None else None
                    prov_id = f"fitz_tables:{i}:{seq}"
                    block = Block(
                        id=prov_id,
                        role=BlockRole.TABLE,
                        native_type="table",
                        text=text,
                        markdown=md,
                        html=html,
                        page_index=i,
                        bbox=bbox,
                        table=cdm_table,
                        parser_extras={
                            "fitz_tables_row_count": row_count,
                            "fitz_tables_col_count": col_count,
                            "fitz_tables_strategy": (
                                f"{self.config.vertical_strategy}/"
                                f"{self.config.horizontal_strategy}"
                            ),
                        },
                    )
                    blocks.append(block)
                    native_by_block[prov_id] = {
                        "page": i,
                        "seq": seq,
                        "bbox": list(table.bbox),
                        "rows": row_count,
                        "cols": col_count,
                        "html": html,
                    }
        finally:
            doc.close()

        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.TABLE_DETECTION: blocks},
            page_meta=self.page_meta,
            raw={"tables": list(native_by_block.values())},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
