"""Answer generation service for eval runs."""
import logging

from app.schemas.prompt_config import PromptConfig
from app.services.llm.types import LLMConfig, CompletionResult
from app.services.llm.port import LLMPort
from app.services.llm.prompt import DEFAULT_RAG_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def generate_answer(
    question: str,
    chunks: list[dict],
    generation_adapter: LLMPort,
    generation_config: LLMConfig,
    prompt_config: PromptConfig | None = None,
) -> str:
    """Generate an answer from retrieved chunks using an LLM."""
    sys_prompt = (
        prompt_config.system_prompt
        if prompt_config and prompt_config.system_prompt
        else DEFAULT_RAG_SYSTEM_PROMPT
    )

    context = "\n\n".join(
        f"[{i + 1}] {chunk.get('content', '')}"
        for i, chunk in enumerate(chunks)
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]

    result: CompletionResult = await generation_adapter.complete(messages, generation_config)
    return result.content
