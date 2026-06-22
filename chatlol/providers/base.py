from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    @abstractmethod
    async def stream_response(
        self,
        messages: list[dict],
        model: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_data: bytes | None = None,
    ) -> AsyncGenerator[str, None]:
        ...

    @classmethod
    @abstractmethod
    def get_models(cls) -> list[str]:
        ...
