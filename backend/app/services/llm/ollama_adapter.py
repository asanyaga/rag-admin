# backend/app/services/llm/ollama_adapter.py
from app.services.llm.openai_adapter import OpenAIAdapter


class OllamaAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter for Ollama (local or cloud).

    Local:  base_url="http://localhost:11434/v1", api_key="ollama" (dummy)
    Cloud:  base_url="https://ollama.com/v1",    api_key=<real key>
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ):
        super().__init__(api_key=api_key, base_url=base_url)
