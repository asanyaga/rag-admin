"""Port + DTOs for ExtractionResult transforms. Primitives are pure functions over rows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TransformInput:
    rows: list[dict]
    source_result_id: str | None = None


@dataclass
class TransformResult:
    rows: list[dict]
    flags: list[dict] = field(default_factory=list)


@runtime_checkable
class ExtractionResultTransform(Protocol):
    @property
    def transform_type(self) -> str: ...

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult: ...


class TransformValidationError(Exception):
    """Raised by a primitive when config or input data fails structural validation."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
