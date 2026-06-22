from typing import AsyncGenerator

from .base import BaseProvider


class KiroProvider(BaseProvider):
    async def stream_response(
        self,
        messages: list[dict],
        model: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_data: bytes | None = None,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError(
            "Kiro AI belum memiliki public API. "
            "Fitur ini akan diaktifkan saat API tersedia."
        )
        yield  # makes this an async generator function

    @classmethod
    def get_models(cls) -> list[str]:
        return ["kiro-default"]
