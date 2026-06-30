# Custom Pipeline — Feature Spec

**Status:** Draft — intro only, to be extended
**Date:** 2026-06-30

---

## Overview

The **custom pipeline** is a locally-executed, configurable PDF parsing pipeline that chains tools in a user-defined order. It is the planned rename of the current `local_pipeline` feature throughout the codebase (`LocalPipelineAdapter`, `LocalPipelineConfig`, `local_pipeline_runner`, parser kind `LOCAL_PIPELINE`, UI labels).

The goal is to expose a spectrum of parse configurations — from very fast with acceptable results on simple documents, to slower, higher-fidelity configs for complex documents — without requiring cloud API calls. Cloud parsers (LlamaParse, Landing AI) remain a separate tier above the custom pipeline.

---

## Parse Quality Tiers

The pipeline is designed around a clear fast→quality axis. Each tier is a distinct parse config the user can select or the system can recommend based on probe results.

| Tier | Tools | Speed | DRM-safe | Capability |
|------|-------|-------|----------|------------|
| 1 | `fitz` | ~50 ms/page | ✓ | Text blocks + figures. Best for clean digital PDFs with no table structure needed. |
| 2 | `fitz + fitz_tables` | ~80 ms/page | ✓ | Adds heuristic table detection using PyMuPDF's `page.find_tables()` (built-in since 1.23). No new dependencies. Handles most simple tabular layouts. |
| 3 | `fitz + camelot` | ~200–400 ms/page | ✗ | Structural table extraction from PDF drawing commands. Best local table accuracy for unrestricted PDFs with visible grid lines. Fails on DRM-restricted documents. |
| 4 | `docling` | 2–15 s/page | ✓ | ML-based layout analysis. Handles scanned pages, multi-column layouts, complex academic/financial documents. Already installed. |
| 5 | Cloud (LlamaParse / Landing AI) | 5–60 s/doc | ✓ | Highest quality. External API call. Best for handwritten, non-standard, or proprietary layouts. |

Tiers 1–4 run locally inside the container. Tier 5 requires configured provider credentials.

---

## Tool Inventory (current install)

| Tool | Package | DRM enforcement | Notes |
|------|---------|----------------|-------|
| `fitz` | PyMuPDF 1.27 | None — MuPDF ignores `PDF_PERM_COPY` by design | Text + image extraction. Current pipeline. |
| `fitz_tables` | PyMuPDF 1.27 (`page.find_tables()`) | None | Not yet registered in `TOOL_REGISTRY`. Planned addition. |
| `camelot` | camelot-py + playa | Enforces `PDF_PERM_COPY` via `playa.is_extractable` | Raises `PDFTextExtractionNotAllowed` on soft-restricted PDFs. |
| `docling` | docling + docling_parse | None — uses pypdfium2 | Separate runner (`docling_runner.py`), not yet in `TOOL_REGISTRY`. |

---

## DRM Restriction Behaviour

Some PDFs carry a `PDF_PERM_COPY = 0` permission bit in their security dictionary (common in vendor-exported price lists and commercial documents). This is a **soft restriction** — the document is not encrypted or password-protected; viewers open it freely. It is a hint to compliant software.

- **Tiers 1, 2, 4** are immune: PyMuPDF and docling both ignore the bit.
- **Tier 3 fails** on these documents: camelot uses playa, which enforces `is_extractable`, raising `PDFTextExtractionNotAllowed`. This propagates as a `FAILED` parse run.

The probe (`DocumentProbe`) already detects structural signals (`table_signal`, `has_scanned_pages`, `has_cid_corruption`). Detecting `copy_restricted` (`doc.permissions & fitz.PDF_PERM_COPY == 0`) is a natural addition that would let the UI surface the restriction and filter camelot from recommended configs.

---

## Scope Notes (to be detailed)

- Rename `local_pipeline` → `custom_pipeline` across router, service, models, UI, and parser kind enum
- Register `fitz_tables` tool: `FitzTableTool` using `page.find_tables()`, outputting `BlockRole.TABLE` consistent with `CamelotTool`
- Integrate `docling` as a registered tool/tier (vs. the current separate runner)
- Probe: add `copy_restricted` field and filter recommendations accordingly
- UI: parse config selector should present tiers with speed/quality tradeoff labels
- UI: allow custom tool composition beyond the named tiers (advanced mode)
