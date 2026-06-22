import json
from typing import AsyncGenerator

import httpx

from .base import BaseProvider
from .. import config


class OllamaProvider(BaseProvider):
    async def stream_response(
        self,
        messages: list[dict],
        model: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_data: bytes | None = None,
    ) -> AsyncGenerator[str, None]:
        msgs = list(messages)
        if file_content and file_type == "text":
            msgs = msgs[:-1] + [
                {
                    "role": "user",
                    "content": f"File ({file_name}):\n{file_content}\n\n{msgs[-1]['content']}",
                }
            ]

        payload = {"model": model, "messages": msgs, "stream": True}
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{config.OLLAMA_URL}/api/chat", json=payload
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break

    @classmethod
    def get_models(cls) -> list[str]:
        return ["llama3.2", "llama3.1", "mistral", "gemma2", "llava", "phi3"]
