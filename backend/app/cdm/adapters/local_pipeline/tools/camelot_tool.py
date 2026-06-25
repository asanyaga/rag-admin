"""CamelotTool — table extraction via camelot-py. Emits CDM TABLE Blocks.

Camelot uses 1-indexed page numbers and a bottom-left coordinate origin.
This tool converts to 0-based page indices and top-left normalized bboxes
using page geometry supplied by FitzTool (via `page_meta`).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import camelot

from app.cdm.adapters.local_pipeline.config import CamelotConfig
from app.cdm.adapters.local_pipeline.tools.base import (
    PageMeta,
    ToolResult,
    clamp01,
)
from app.cdm.models import BBox, Block, BlockRole, Cell, Table


class CamelotTool:
    tool_id = "camelot"

    def __init__(
        self,
        config: Optional[CamelotConfig] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
    ) -> None:
        self.config = config or CamelotConfig()
        self.page_meta = page_meta or {}

    @staticmethod
    def _pages_arg(pages: Optional[List[int]]) -> str:
        """Translate 0-based CDM page indices to camelot's 1-indexed string."""
        if not pages:
            return "1-end"
        return ",".join(str(p + 1) for p in sorted(pages))

    def _norm_bbox(self, native_bbox, page_meta: PageMeta) -> BBox:
        x1, y1, x2, y2 = native_bbox  # bottom-left origin
        w, h = page_meta.width, page_meta.height
        # Flip y: top-left y = page_height - bottom_left_y.
        return BBox(
            x0=clamp01(min(x1, x2) / w),
            y0=clamp01((h - max(y1, y2)) / h),
            x1=clamp01(max(x1, x2) / w),
            y1=clamp01((h - min(y1, y2)) / h),
            source_space="pdf_points",
            source_coords=(float(x1), float(y1), float(x2), float(y2)),
        )

    def _cells(self, table: Any, page_meta: PageMeta) -> List[Cell]:
        cells: List[Cell] = []
        for r, row in enumerate(table.cells):
            for c, cell in enumerate(row):
                cells.append(Cell(
                    row=r,
                    col=c,
                    text=(cell.text or "").strip(),
                    bbox=self._norm_bbox(
                        (cell.x1, cell.y1, cell.x2, cell.y2), page_meta
                    ),
                ))
        return cells

    def _table_to_block(
        self, table: Any, page_index: int, page_meta: Optional[PageMeta], table_seq: int
    ) -> Block:
        report = table.parsing_report or {}
        rows, cols = table.df.shape
        cdm_table = Table(
            rows=int(rows),
            cols=int(cols),
            cells=self._cells(table, page_meta) if page_meta else [],
            html=table.df.to_html(),
        )
        bbox = self._norm_bbox(table._bbox, page_meta) if page_meta else None
        return Block(
            id=f"camelot:{page_index}:{table_seq}",
            role=BlockRole.TABLE,
            native_type="table",
            page_index=page_index,
            bbox=bbox,
            table=cdm_table,
            parser_extras={
                "camelot_accuracy": report.get("accuracy"),
                "camelot_order": report.get("order"),
                "camelot_flavor": self.config.flavor,
            },
        )

    def run(self, pdf_path: Path, pages: Optional[List[int]] = None) -> ToolResult:
        t0 = time.perf_counter()
        warnings: List[str] = []
        blocks: List[Block] = []
        native_by_block: Dict[str, Any] = {}
        raw_tables: List[Dict[str, Any]] = []

        read_kwargs: Dict[str, Any] = {
            "flavor": self.config.flavor,
            "pages": self._pages_arg(pages),
            "edge_tol": self.config.edge_tol,
            "row_tol": self.config.row_tol,
        }
        if self.config.copy_text:
            read_kwargs["copy_text"] = self.config.copy_text

        tables = camelot.read_pdf(str(pdf_path), **read_kwargs)

        seq_by_page: Dict[int, int] = {}
        for table in tables:
            page_index = int(table.page) - 1
            seq = seq_by_page.get(page_index, 0)
            seq_by_page[page_index] = seq + 1
            pm = self.page_meta.get(page_index)
            if pm is None:
                warnings.append(
                    f"page {page_index}: no page_meta; table bbox omitted"
                )
            block = self._table_to_block(table, page_index, pm, seq)
            blocks.append(block)
            native_record = {
                "page": int(table.page),
                "parsing_report": table.parsing_report,
                "html": table.df.to_html(),
            }
            native_by_block[block.id] = native_record
            raw_tables.append(native_record)

        return ToolResult(
            tool_id=self.tool_id,
            blocks=blocks,
            page_meta=self.page_meta,
            raw={"tables": raw_tables},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
