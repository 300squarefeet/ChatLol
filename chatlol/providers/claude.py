import base64
from typing import AsyncGenerator

import anthropic

from .base import BaseProvider
from .. import config


class ClaudeProvider(BaseProvider):
    def __init__(self):
        # Client is created lazily per call so that tests can patch anthropic.AsyncAnthropic
        pass

    def _get_client(self) -> anthropic.AsyncAnthropic:
        return anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

    async def stream_response(
        self,
        messages: list[dict],
        model: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_data: bytes | None = None,
    ) -> AsyncGenerator[str, None]:
        msgs = _build_claude_messages(messages, file_content, file_name, file_type, file_data)
        client = self._get_client()
        async with client.messages.stream(
            model=model,
            max_tokens=8096,
            messages=msgs,
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield event.delta.text

    @classmethod
    def get_models(cls) -> list[str]:
        return ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"]


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


def _build_claude_messages(
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
    content_parts: list = []

    if file_type == "image" and file_data:
        detected = _detect_image_type(file_data)
        media_type = f"image/{detected}"
        content_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(file_data).decode(),
            },
        })
    elif file_content:
        content_parts.append({
            "type": "text",
            "text": f"File ({file_name}):\n{file_content}",
        })

    content_parts.append({"type": "text", "text": last["content"]})
    return msgs[:-1] + [{"role": "user", "content": content_parts}]
