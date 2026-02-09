"""Query request/response schemas for the playground search API."""
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Query request matching the frontend contract."""
    query: str = Field(..., min_length=1, max_length=2000)
    search_type: str = Field(
        "semantic",
        alias="searchType",
        pattern="^(semantic|keyword|hybrid)$",
    )
    top_k: int = Field(5, alias="topK", ge=1, le=50)
    similarity_threshold: float = Field(
        0.0, alias="similarityThreshold", ge=0.0, le=1.0
    )

    model_config = {"populate_by_name": True}


class RetrievalResultMetadata(BaseModel):
    """Metadata about a single retrieval result."""
    document_id: str = Field(alias="documentId")
    document_name: str = Field(alias="documentName")
    page: int | None = None
    page_numbers: list[int] | None = Field(None, alias="pageNumbers")
    chunk_index: int = Field(alias="chunkIndex")
    token_count: int = Field(alias="tokenCount")
    char_count: int = Field(alias="charCount")

    model_config = {"populate_by_name": True}


class RetrievalResult(BaseModel):
    """A single search result."""
    chunk_id: str = Field(alias="chunkId")
    rank: int
    score: float
    content: str
    metadata: RetrievalResultMetadata

    model_config = {"populate_by_name": True}


class QueryResponse(BaseModel):
    """Query response returned to the frontend."""
    query: str
    results: list[RetrievalResult]
    total_results: int = Field(alias="totalResults")
    search_type: str = Field(alias="searchType")
    execution_time_ms: float = Field(alias="executionTimeMs")

    model_config = {"populate_by_name": True}
