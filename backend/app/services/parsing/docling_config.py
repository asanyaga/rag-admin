"""Validated config surface for ParserKind.DOCLING.

This mirrors docling's own option shape rather than our capability slots — the
point of this parser kind is to see docling as docling. Defaults track docling
2.105.0 exactly, so an empty config behaves like a bare `DocumentConverter()`.

Anything the caller does not set is omitted when building docling's option
objects, so unset fields fall through to docling's defaults instead of being
pinned to ours.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    """Unknown keys are errors, so a typo 422s at the boundary."""
    model_config = ConfigDict(extra="forbid")


# ── Layout ────────────────────────────────────────────────────────────────────

class LayoutModelName(str, Enum):
    V2 = "docling_layout_v2"
    HERON = "docling_layout_heron"
    HERON_101 = "docling_layout_heron_101"
    EGRET_MEDIUM = "docling_layout_egret_medium"
    EGRET_LARGE = "docling_layout_egret_large"
    EGRET_XLARGE = "docling_layout_egret_xlarge"


class LayoutConfig(_Strict):
    model: LayoutModelName = LayoutModelName.HERON
    create_orphan_clusters: bool = True


# ── Table structure ───────────────────────────────────────────────────────────

class TableFormerModeName(str, Enum):
    FAST = "fast"
    ACCURATE = "accurate"


class TableStructureConfig(_Strict):
    mode: TableFormerModeName = TableFormerModeName.ACCURATE
    do_cell_matching: bool = True


# ── OCR engines ───────────────────────────────────────────────────────────────
#
# Engines needing platform support we don't have (ocrmac — macOS only;
# kserve_v2_ocr, nemotron-ocr — remote inference we don't run) are excluded from
# the union rather than exposed and failing mid-parse.

class _BaseOcrConfig(_Strict):
    lang: Optional[List[str]] = None
    force_full_page_ocr: bool = False
    bitmap_area_threshold: float = Field(default=0.05, ge=0.0, le=1.0)


class AutoOcrConfig(_BaseOcrConfig):
    """docling's own engine auto-selector — its default."""
    kind: Literal["auto"] = "auto"


class EasyOcrConfig(_BaseOcrConfig):
    kind: Literal["easyocr"] = "easyocr"
    use_gpu: Optional[bool] = None
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    recog_network: Optional[str] = None
    download_enabled: Optional[bool] = None


class TesseractCliOcrConfig(_BaseOcrConfig):
    kind: Literal["tesseract"] = "tesseract"
    psm: Optional[int] = Field(default=None, ge=0, le=13)
    tesseract_cmd: Optional[str] = None
    path: Optional[str] = None


class TesserOcrConfig(_BaseOcrConfig):
    kind: Literal["tesserocr"] = "tesserocr"
    psm: Optional[int] = Field(default=None, ge=0, le=13)
    path: Optional[str] = None


class RapidOcrConfig(_BaseOcrConfig):
    kind: Literal["rapidocr"] = "rapidocr"
    text_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_det: Optional[bool] = None
    use_cls: Optional[bool] = None
    use_rec: Optional[bool] = None


OcrConfig = Annotated[
    Union[AutoOcrConfig, EasyOcrConfig, TesseractCliOcrConfig,
          TesserOcrConfig, RapidOcrConfig],
    Field(discriminator="kind"),
]


# ── Top level ─────────────────────────────────────────────────────────────────

class DoclingBackend(str, Enum):
    PARSE_V4 = "docling_parse_v4"
    PARSE_V2 = "docling_parse_v2"
    PYPDFIUM2 = "pypdfium2"


#: Fields that only mean anything under the standard (non-VLM) pipeline.
_STANDARD_ONLY = frozenset({
    "do_ocr", "do_table_structure", "do_code_enrichment", "do_formula_enrichment",
    "force_backend_text", "images_scale", "generate_page_images",
    "generate_picture_images", "layout_options", "ocr_options",
    "table_structure_options",
})


#: Keys the router threads through the same dict as parser options. They are
#: part of the persisted ParseRun.config (config_hash depends on them) but are
#: not docling options, so they are stripped before validation. Defined here so
#: the router and the runner cannot drift on what counts as routing.
ROUTING_KEYS = frozenset({"parser", "representation_kind"})


class DoclingConfig(_Strict):
    pipeline: Literal["standard", "vlm"] = "standard"
    backend: DoclingBackend = DoclingBackend.PARSE_V4

    # -- standard pipeline
    do_ocr: bool = True
    do_table_structure: bool = True
    do_code_enrichment: bool = False
    do_formula_enrichment: bool = False
    force_backend_text: bool = False
    images_scale: float = Field(default=1.0, gt=0.0, le=8.0)
    generate_page_images: bool = False
    generate_picture_images: bool = False
    layout_options: LayoutConfig = LayoutConfig()
    ocr_options: OcrConfig = AutoOcrConfig()
    table_structure_options: TableStructureConfig = TableStructureConfig()

    # -- vlm pipeline
    vlm_model: str = "smoldocling"

    # -- ours, not docling's: how many pages per conversion call
    page_batch_size: int = Field(default=20, ge=1, le=1000)

    @classmethod
    def from_parse_config(cls, config: Optional[Dict[str, Any]]) -> "DoclingConfig":
        """Validate a config as the router sends it — routing keys included."""
        options = {k: v for k, v in (config or {}).items() if k not in ROUTING_KEYS}
        return cls.model_validate(options)

    @model_validator(mode="after")
    def _check_stage_options_have_their_stage(self) -> "DoclingConfig":
        set_fields = self.model_fields_set

        if self.pipeline == "vlm":
            leaked = sorted(set_fields & _STANDARD_ONLY)
            if leaked:
                raise ValueError(
                    f"{leaked} only apply to the standard pipeline, not vlm"
                )
            return self

        if "ocr_options" in set_fields and not self.do_ocr:
            raise ValueError("ocr_options requires do_ocr=True")
        if "table_structure_options" in set_fields and not self.do_table_structure:
            raise ValueError(
                "table_structure_options requires do_table_structure=True"
            )
        return self

    # -- bridge into docling's own option objects

    def to_pipeline_options(self) -> Any:
        """Build docling's `PdfPipelineOptions`. Unset fields are omitted so
        docling's defaults apply rather than ours."""
        from docling.datamodel import layout_model_specs
        from docling.datamodel.pipeline_options import (
            LayoutOptions,
            PdfPipelineOptions,
            TableFormerMode,
            TableStructureOptions,
        )

        return PdfPipelineOptions(
            do_ocr=self.do_ocr,
            do_table_structure=self.do_table_structure,
            do_code_enrichment=self.do_code_enrichment,
            do_formula_enrichment=self.do_formula_enrichment,
            force_backend_text=self.force_backend_text,
            images_scale=self.images_scale,
            generate_page_images=self.generate_page_images,
            generate_picture_images=self.generate_picture_images,
            layout_options=LayoutOptions(
                create_orphan_clusters=self.layout_options.create_orphan_clusters,
                model_spec=getattr(
                    layout_model_specs, _LAYOUT_SPEC_ATTR[self.layout_options.model]
                ),
            ),
            ocr_options=self._build_ocr_options(),
            table_structure_options=TableStructureOptions(
                mode=TableFormerMode(self.table_structure_options.mode.value),
                do_cell_matching=self.table_structure_options.do_cell_matching,
            ),
        )

    def _build_ocr_options(self) -> Any:
        from docling.datamodel.pipeline_options import (
            EasyOcrOptions,
            OcrAutoOptions,
            RapidOcrOptions,
            TesseractCliOcrOptions,
            TesseractOcrOptions,
        )

        by_kind = {
            "auto": OcrAutoOptions,
            "easyocr": EasyOcrOptions,
            "tesseract": TesseractCliOcrOptions,
            "tesserocr": TesseractOcrOptions,
            "rapidocr": RapidOcrOptions,
        }
        # exclude_unset is load-bearing: it is what lets docling's own per-engine
        # defaults (e.g. easyocr's lang) survive instead of being overwritten.
        fields: Dict[str, Any] = self.ocr_options.model_dump(
            exclude_unset=True, exclude={"kind"}
        )
        return by_kind[self.ocr_options.kind](**fields)


_LAYOUT_SPEC_ATTR: Dict[LayoutModelName, str] = {
    LayoutModelName.V2: "DOCLING_LAYOUT_V2",
    LayoutModelName.HERON: "DOCLING_LAYOUT_HERON",
    LayoutModelName.HERON_101: "DOCLING_LAYOUT_HERON_101",
    LayoutModelName.EGRET_MEDIUM: "DOCLING_LAYOUT_EGRET_MEDIUM",
    LayoutModelName.EGRET_LARGE: "DOCLING_LAYOUT_EGRET_LARGE",
    LayoutModelName.EGRET_XLARGE: "DOCLING_LAYOUT_EGRET_XLARGE",
}
