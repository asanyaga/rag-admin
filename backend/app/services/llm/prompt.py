"""RAG prompt construction for answer generation."""
from app.schemas.query import RetrievalResult

DEFAULT_RAG_SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided context.\n"
    "Cite sources using [1], [2], etc. corresponding to the chunk numbers.\n"
    "If the context doesn't contain enough information, say so."
)


def build_rag_prompt(
    query: str,
    chunks: list[RetrievalResult],
    system_prompt: str | None = None,
) -> list[dict]:
    """Build the messages array for a RAG answer generation request.

    If system_prompt is provided it replaces the default entirely.
    """
    system_content = system_prompt or DEFAULT_RAG_SYSTEM_PROMPT
    context = "\n\n".join(
        f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks)
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
