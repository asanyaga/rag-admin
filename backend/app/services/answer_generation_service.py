"""Answer generation service for eval runs."""

import logging

from app.services.llm.types import LLMConfig, CompletionResult
from app.services.llm.port import LLMPort

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided context.\n"
    "Cite sources using [1], [2], etc. corresponding to the chunk numbers.\n"
    "If the context doesn't contain enough information, say so."
)


async def generate_answer(
    question: str,
    chunks: list[dict],
    generation_adapter: LLMPort,
    generation_config: LLMConfig,
    system_prompt: str | None = None,
) -> str:
    """Generate an answer from retrieved chunks using an LLM.

    Args:
        question: The user's query
        chunks: Retrieved chunk dicts (must have 'content' key)
        generation_adapter: LLM adapter to use
        generation_config: LLM configuration
        system_prompt: Optional custom system prompt

    Returns:
        Generated answer text
    """
    sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    context = "\n\n".join(
        f"[{i + 1}] {chunk.get('content', '')}"
        for i, chunk in enumerate(chunks)
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]

    config = LLMConfig(
        provider=generation_config.provider,
        model=generation_config.model,
        temperature=generation_config.temperature,
        max_tokens=generation_config.max_tokens,
        json_mode=False,
    )

    result: CompletionResult = await generation_adapter.complete(messages, config)
    return result.content
