"""Judge service for evaluating answer quality (faithfulness + relevance)."""

import json
import logging
import re
from dataclasses import dataclass, field

from app.services.llm.types import LLMConfig, CompletionResult
from app.services.llm.port import LLMPort

logger = logging.getLogger(__name__)

JUDGE_PROMPT_TEMPLATE = """\
You are an impartial judge evaluating the quality of an AI-generated answer.

## Task
Given a QUESTION, a set of CONTEXT chunks, and an AI-generated ANSWER, evaluate:

1. **Faithfulness**: Is the answer supported by the context? Break the answer into individual claims and classify each as:
   - "supported" — the claim is directly supported by the context
   - "unsupported" — the claim contradicts or is not found in the context
   - "unclear" — the claim is partially supported or ambiguous

2. **Answer Relevance**: Does the answer address the question? Score from 0.0 to 1.0.
   - 1.0 = perfectly addresses the question
   - 0.0 = completely irrelevant to the question

## Output Format
Respond with a JSON object (no markdown, no explanation):
{{
  "claims": [
    {{"text": "claim text", "label": "supported|unsupported|unclear", "source": "chunk number or null"}}
  ],
  "relevance_score": 0.0
}}

## Input

QUESTION: {question}

CONTEXT:
{context}

ANSWER: {answer}
"""


@dataclass
class ClaimItem:
    text: str
    label: str  # "supported" | "unsupported" | "unclear"
    source: str | None = None


@dataclass
class JudgeResult:
    claims: list[ClaimItem] = field(default_factory=list)
    faithfulness_score: float = 0.0
    relevance_score: float = 0.0
    error: str | None = None


class JudgeService:
    """Evaluates answer quality using an LLM judge."""

    async def evaluate(
        self,
        question: str,
        chunks: list[dict],
        answer: str,
        judge_adapter: LLMPort,
        judge_config: LLMConfig,
    ) -> JudgeResult:
        """Run judge evaluation on a generated answer."""
        # Format chunks for the prompt
        context = "\n\n".join(
            f"[{i + 1}] {chunk.get('content', '')}"
            for i, chunk in enumerate(chunks)
        )

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            question=question,
            context=context,
            answer=answer,
        )

        messages = [
            {"role": "user", "content": prompt},
        ]

        try:
            config = LLMConfig(
                provider=judge_config.provider,
                model=judge_config.model,
                temperature=0.0,
                max_tokens=2048,
                structured_output_mode="json_mode",
            )
            result: CompletionResult = await judge_adapter.complete(messages, config)
            return self._parse_response(result.content)
        except Exception as e:
            logger.warning(f"Judge evaluation failed: {e}")
            return JudgeResult(error=str(e))

    def _parse_response(self, content: str) -> JudgeResult:
        """Parse the judge response with fallback chain."""
        parsed = None

        # Try direct JSON parse
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if parsed is None:
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        # Try finding any JSON object in the content
        if parsed is None:
            match = re.search(r'\{[^{}]*"claims"[^{}]*\[.*?\].*?\}', content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        if parsed is None:
            return JudgeResult(error=f"Failed to parse judge response: {content[:200]}")

        # Extract and validate claims
        claims = []
        raw_claims = parsed.get("claims", [])
        if isinstance(raw_claims, list):
            for c in raw_claims:
                if isinstance(c, dict) and "text" in c and "label" in c:
                    label = c["label"]
                    if label not in ("supported", "unsupported", "unclear"):
                        label = "unclear"
                    claims.append(ClaimItem(
                        text=c["text"],
                        label=label,
                        source=c.get("source"),
                    ))

        # Compute faithfulness score
        total = len(claims)
        if total > 0:
            supported = sum(1 for c in claims if c.label == "supported")
            faithfulness_score = supported / total
        else:
            faithfulness_score = 0.0

        # Extract and validate relevance score
        relevance_score = parsed.get("relevance_score", 0.0)
        try:
            relevance_score = float(relevance_score)
            relevance_score = max(0.0, min(1.0, relevance_score))
        except (TypeError, ValueError):
            relevance_score = 0.0

        return JudgeResult(
            claims=claims,
            faithfulness_score=round(faithfulness_score, 4),
            relevance_score=round(relevance_score, 4),
        )
