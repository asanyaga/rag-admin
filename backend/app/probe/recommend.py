from __future__ import annotations
from app.probe.report import ParserSuggestion, ProbeReport


def recommend(report: ProbeReport) -> ParserSuggestion:
    tools = ["fitz"]
    rationale = ["Base extractor fitz for the text layer."]
    ocr_pages = []
    has_table = False

    for page in report.pages:
        for region in page.regions:
            label = region.observation.label
            if label == "table_grid":
                has_table = True
            if label == "text_image" and page.index not in ocr_pages:
                ocr_pages.append(page.index)

    if has_table:
        tools.append("fitz_tables")
        rationale.append("Table grids detected -> add fitz_tables.")
    if ocr_pages:
        rationale.append(f"Text-like images on pages {sorted(ocr_pages)} -> OCR suggested.")

    confidences = [r.observation.confidence for p in report.pages for r in p.regions]
    overall = round(sum(confidences) / len(confidences), 3) if confidences else 0.5

    return ParserSuggestion(authoritative=False, tools=tools, ocr_pages=sorted(ocr_pages),
                            overall_confidence=overall, rationale=rationale)
