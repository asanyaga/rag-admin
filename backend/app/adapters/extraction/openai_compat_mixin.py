"""OpenAI-compatible REST protocol mixin.

Shared by OllamaExtractor and future Together/Groq/OpenAI adapters.
"""
import json
import logging

import openai
from openai import AsyncOpenAI

from app.ports.data_extraction import ExtractionError

logger = logging.getLogger(__name__)


class OpenAICompatMixin:
    """Provides _build_client() and _call_model() for OpenAI-compatible endpoints."""

    def _build_client(self, endpoint: str, api_key: str | None) -> AsyncOpenAI:
        return AsyncOpenAI(
            base_url=endpoint,
            api_key=api_key or "ollama",
        )

    async def _call_model(
        self,
        messages: list[dict],
        augmented_schema: dict,
        config: dict,
    ) -> dict:
        endpoint = config.get("endpoint", "http://localhost:11434/v1")
        api_key = config.get("api_key")
        model = config.get("model")
        temperature = config.get("temperature", 0.0)
        mode = config.get("structured_output_mode", "json_schema")

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if mode == "json_schema":
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_result",
                    "strict": True,
                    "schema": augmented_schema,
                },
            }
        elif mode == "json_mode":
            kwargs["response_format"] = {"type": "json_object"}
        # prompt_only: no response_format key

        try:
            async with self._build_client(endpoint, api_key) as client:
                response = await client.chat.completions.create(**kwargs)
        except openai.BadRequestError as e:
            if e.status_code in (400, 422):
                logger.warning(
                    "Structured output rejected by model (HTTP %s). "
                    "Consider switching structured_output_mode to 'json_mode'.",
                    e.status_code,
                )
            raise
        except openai.APIConnectionError as e:
            raise ExtractionError(
                f"Cannot connect to endpoint {endpoint!r}: connection refused."
            ) from e

        raw_content = response.choices[0].message.content
        try:
            return json.loads(raw_content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ExtractionError(
                f"Model returned non-JSON response: {raw_content[:200]!r}"
            ) from exc
