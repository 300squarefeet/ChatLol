import openai as openai_lib

from .openai import OpenAIProvider
from .. import config


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek via API OpenAI-compatible (https://api.deepseek.com).

    Mewarisi stream_response + pembentukan pesan dari OpenAIProvider; hanya
    base_url & API key yang berbeda.
    """

    BASE_URL = "https://api.deepseek.com/v1"

    def _get_client(self) -> openai_lib.AsyncOpenAI:
        return openai_lib.AsyncOpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=self.BASE_URL,
        )

    @classmethod
    def get_models(cls) -> list[str]:
        return ["deepseek-chat", "deepseek-reasoner"]
