import base64
from typing import AsyncGenerator

import openai as openai_lib

from .base import BaseProvider
from .. import config


class OpenAIProvider(BaseProvider):
    def __init__(self):
        # Client is created lazily per call so that tests can patch openai.AsyncOpenAI
        pass

    def _get_client(self) -> openai_lib.AsyncOpenAI:
        return openai_lib.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    async def stream_response(
        self,
        messages: list[dict],
        model: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_data: bytes | None = None,
    ) -> AsyncGenerator[str, None]:
        msgs = _build_openai_messages(messages, file_content, file_name, file_type, file_data)
        client = self._get_client()
        async with client.chat.completions.stream(
            model=model,
            messages=msgs,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    @classmethod
    def get_models(cls) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]


def _detect_image_type(data: bytes) -> str:
    """Detect image MIME subtype from magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "jpeg"


def _build_openai_messages(
    messages: list[dict],
    file_content: str | None,
    file_name: str | None,
    file_type: str | None,
    file_data: bytes | None,
) -> list[dict]:
    """Build message list with optional file attachment on the last user message."""
    msgs = list(messages)
    if not file_content and not file_data:
        return msgs

    last = msgs[-1]
    parts: list = []

    if file_type == "image" and file_data:
        ext = _detect_image_type(file_data)
        data_url = f"data:image/{ext};base64,{base64.b64encode(file_data).decode()}"
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    elif file_content:
        parts.append({"type": "text", "text": f"File ({file_name}):\n{file_content}"})

    parts.append({"type": "text", "text": last["content"]})
    return msgs[:-1] + [{"role": "user", "content": parts}]
