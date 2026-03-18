"""Document parsing port interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class ParserType(str, Enum):
    """The tool/vendor — not the output shape."""
    SIMPLE = "simple"
    LLAMAPARSE = "llamaparse"


class ParseFidelity(str, Enum):
    """Level of structural description in the parse output."""
    TEXT = "text"
    MARKDOWN = "markdown"
    LAYOUT_JSON = "layout_json"


@dataclass
class ParseOutput:
    """A parser's description of a document — parser-agnostic output contract.

    Every parser MUST populate raw_text. Everything else is optional.
    """
    raw_text: str
    fidelity: str = "text"
    parser_type: str = ""
    markdown: str | None = None
    pages: list[dict[str, Any]] | None = None
    document_structure: dict[str, Any] | None = None
    parser_config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentParser(ABC):
    """Port: Parse documents into structural descriptions."""

    @abstractmethod
    async def parse(
        self,
        file_path: str,
        config: dict[str, Any] | None = None,
    ) -> ParseOutput:
        """Parse a document from a local file path."""
        ...

    @abstractmethod
    def supported_file_types(self) -> list[str]:
        """MIME types this parser can handle."""
        ...

    @property
    @abstractmethod
    def parser_type(self) -> ParserType:
        ...

    @property
    @abstractmethod
    def default_fidelity(self) -> ParseFidelity:
        """The fidelity level this parser naturally produces."""
        ...
