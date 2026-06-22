import openai as openai_lib

from .openai import OpenAIProvider
from .. import config


class NineRouterProvider(OpenAIProvider):
    """9Router via gateway lokal OpenAI-compatible (default http://localhost:20128/v1).

    9Router (`npm install -g 9router`) adalah gateway yang meneruskan ke 60+
    provider. base_url & API key dapat diatur lewat settings/env
    (NINEROUTER_URL / NINEROUTER_API_KEY). Karena gateway lokal, API key boleh
    placeholder; SDK OpenAI hanya butuh string non-kosong.
    """

    def _get_client(self) -> openai_lib.AsyncOpenAI:
        # SDK OpenAI menolak api_key kosong; pakai placeholder untuk gateway lokal.
        return openai_lib.AsyncOpenAI(
            api_key=config.NINEROUTER_API_KEY or "9router-local",
            base_url=config.NINEROUTER_URL,
        )

    @classmethod
    def get_models(cls) -> list[str]:
        # Slug bergantung pada provider yang dikonfigurasi di dashboard 9Router.
        # Daftar default umum; sesuaikan via dashboard 9Router bila perlu.
        return [
            "claude-sonnet-4",
            "gpt-4o",
            "gemini-2.5-pro",
            "deepseek-chat",
            "glm-4.6",
            "kimi-k2",
        ]
