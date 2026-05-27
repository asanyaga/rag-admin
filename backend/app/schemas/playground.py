"""Request schemas for the Answer Playground endpoint."""
from pydantic import BaseModel, Field

from app.schemas.prompt_config import PromptConfig


class RetrievalConfig(BaseModel):
    """Retrieval parameters for the answer pipeline."""
    search_type: str = Field("hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(5, ge=1, le=50)
    similarity_threshold: float = Field(0.0, ge=0.0, le=1.0)


class PlaygroundAnswerRequest(BaseModel):
    """Request body for the SSE answer endpoint."""
    query: str = Field(..., min_length=1, max_length=2000)
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm_config: PromptConfig | None = None
