from __future__ import annotations

from app.cdm.source import ParseRun


class LlamaParseRunError(RuntimeError):
    """Raised by llamaparse_runner when the SDK call fails.

    Carries the constructed (but unpersisted) failed ParseRun so the service
    layer can persist it before surfacing the error to callers.
    """
    def __init__(self, message: str, *, run: ParseRun):
        super().__init__(message)
        self.run = run


class ParseFailedError(RuntimeError):
    """Domain error raised by ParsingService to callers (routers) after
    a failed ParseRun has been persisted."""
