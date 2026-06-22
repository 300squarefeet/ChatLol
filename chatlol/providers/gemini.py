from typing import AsyncGenerator

import google.generativeai as genai

from .base import BaseProvider
from .. import config


class GeminiProvider(BaseProvider):
    def __init__(self):
        # Configure on instantiation; safe to call multiple times
        genai.configure(api_key=config.GEMINI_API_KEY)

    async def stream_response(
        self,
        messages: list[dict],
        model: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
        file_data: bytes | None = None,
    ) -> AsyncGenerator[str, None]:
        gemini_model = genai.GenerativeModel(model)

        # Convert history (all but last message): "assistant" -> "model"
        history = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [m["content"]],
            }
            for m in messages[:-1]
        ]

        last_content = messages[-1]["content"]
        if file_content:
            last_content = f"File ({file_name}):\n{file_content}\n\n{last_content}"

        chat = gemini_model.start_chat(history=history)
        response = await chat.send_message_async(last_content, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    @classmethod
    def get_models(cls) -> list[str]:
        return ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
