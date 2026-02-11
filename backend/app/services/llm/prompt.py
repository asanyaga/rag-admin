"""RAG prompt construction for answer generation."""

from app.schemas.query import RetrievalResult


def build_rag_prompt(
    query: str,
    chunks: list[RetrievalResult],
    instructions: str | None = None,
) -> list[dict]:
    """Build the messages array for a RAG answer generation request.

    Constructs a system + user message pair with retrieved chunks as context
    and the user's query. The system prompt instructs the LLM to cite sources
    using [N] notation.

    This function is the "seam" for future prompt template presets (Phase 2)
    and a full template editor (Phase 3).
    """
    system_parts = [
        "Answer the user's question using ONLY the provided context.",
        "Cite sources using [1], [2], etc. corresponding to the chunk numbers.",
        "If the context doesn't contain enough information, say so.",
    ]
    if instructions:
        system_parts.append(f"\nAdditional instructions: {instructions}")

    context = "\n\n".join(
        f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks)
    )

    return [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
