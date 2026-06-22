from __future__ import annotations

from app.cdm.source import ParseRun


class ParseRunError(RuntimeError):
    """Base for all runner errors. Carries the unpersisted failed ParseRun."""
    def __init__(self, message: str, *, run: ParseRun) -> None:
        super().__init__(message)
        self.run = run


class LlamaParseRunError(ParseRunError):
    """Raised by llamaparse_runner when the SDK call fails."""


class LandingAIRunError(ParseRunError):
    """Raised by landingai_runner when the SDK call or polling fails."""


class SimpleRunError(ParseRunError):
    """Raised by simple_runner when local extraction fails."""


class DoclingRunError(ParseRunError):
    """Raised by docling_runner when conversion fails on any batch."""


class ParseFailedError(RuntimeError):
    """Domain error raised by ParsingService to callers (routers) after
    a failed ParseRun has been persisted."""
