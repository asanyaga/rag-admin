from __future__ import annotations
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from app.probe.backends.base import DocumentPrimitives, InspectionBackend, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.observe import observe_image, observe_table
from app.probe.recommend import recommend
from app.probe.report import PageProfile, ProbeReport, RegionFinding, Signal
from app.probe.signals import page_signals, region_signals
from app.probe.signals.edge_density import edge_density


class Prober:
    def __init__(self, backend: InspectionBackend):
        self.backend = backend

    def run(self, pdf_path: Path, document_id: str, filename: str, config: ProbeConfig) -> ProbeReport:
        t0 = time.monotonic()
        enabled = set(config.enabled_signals)
        with self.backend.open(pdf_path) as session:
            prims = session.inspect()
            pages = [self._page(session, prims, page, enabled, config) for page in prims.pages]
        report = ProbeReport(
            document_id=document_id, filename=filename, page_count=prims.page_count,
            inspection={"backend": self.backend.name, "backend_version": self.backend.version,
                        "config_used": config.model_dump()},
            pages=pages, suggestion=None,
            duration_ms=int((time.monotonic() - t0) * 1000),
            probed_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        report.suggestion = recommend(report)
        return report

    def _page(self, session, doc: DocumentPrimitives, page: PagePrimitives, enabled, cfg) -> PageProfile:
        signals: List[Signal] = []
        if "text_layer" in enabled:
            signals += page_signals.text_layer(page, cfg)
        if "font_health" in enabled:
            signals += page_signals.font_health(page, cfg)
        if "copy_restricted" in enabled:
            signals += page_signals.copy_restricted(doc, cfg)

        regions: List[RegionFinding] = []
        for idx, image in enumerate(page.images):
            rsigs: List[Signal] = []
            if "coverage" in enabled:
                rsigs.append(region_signals.coverage(page, image, cfg))
            if "dpi" in enabled:
                rsigs.append(region_signals.dpi(page, image, cfg))
            if "text_overlap" in enabled:
                rsigs.append(region_signals.text_overlap(page, image, cfg))
            if "edge_density" in enabled:
                gray = session.render_gray(page.index, image.bbox)
                rsigs.append(edge_density(gray, cfg))
            regions.append(RegionFinding(
                id=f"p{page.index}:img{idx}", page_index=page.index, kind="image",
                bbox=image.bbox, signals=rsigs, observation=observe_image(rsigs, cfg)))

        if "table_grid" in enabled:
            for tidx, (bbox, sig) in enumerate(region_signals.table_grid(page, cfg)):
                regions.append(RegionFinding(
                    id=f"p{page.index}:tbl{tidx}", page_index=page.index, kind="table",
                    bbox=bbox, signals=[sig], observation=observe_table([sig], cfg)))

        return PageProfile(index=page.index, page_type=self._page_type(page), signals=signals, regions=regions)

    @staticmethod
    def _page_type(page: PagePrimitives) -> str:
        has_text = len(page.text.strip()) >= 10
        has_img = len(page.images) > 0
        if has_text and has_img:
            return "mixed"
        if has_img:
            return "scanned"
        if has_text:
            return "text"
        return "empty"
