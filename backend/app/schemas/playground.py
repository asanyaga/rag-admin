"""Request schemas for the Answer Playground endpoint."""

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """Retrieval parameters for the answer pipeline."""

    search_type: str = Field("hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(5, ge=1, le=50)
    similarity_threshold: float = Field(0.0, ge=0.0, le=1.0)


class LLMConfigSchema(BaseModel):
    """LLM configuration for answer generation."""

    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=64, le=16384)


class PlaygroundAnswerRequest(BaseModel):
    """Request body for the SSE answer endpoint."""

    query: str = Field(..., min_length=1, max_length=2000)
    instructions: str | None = None
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm_config: LLMConfigSchema = Field(default_factory=LLMConfigSchema)
