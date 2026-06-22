import openai as openai_lib

from .openai import OpenAIProvider
from .. import config


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter via API OpenAI-compatible (https://openrouter.ai/api/v1).

    Slug model berbentuk `provider/model`, mis. `openai/gpt-4o`.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def _get_client(self) -> openai_lib.AsyncOpenAI:
        return openai_lib.AsyncOpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url=self.BASE_URL,
        )

    @classmethod
    def get_models(cls) -> list[str]:
        return [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-sonnet-4",
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b-instruct",
        ]
