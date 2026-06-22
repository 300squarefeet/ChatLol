import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from chatlol.providers.ollama import OllamaProvider
from chatlol.providers.claude import ClaudeProvider
from chatlol.providers.openai import OpenAIProvider
from chatlol.providers.gemini import GeminiProvider
from chatlol.providers.kiro import KiroProvider
from chatlol.providers.deepseek import DeepSeekProvider
from chatlol.providers.openrouter import OpenRouterProvider
from chatlol.providers.ninerouter import NineRouterProvider
from chatlol.providers import get_provider, list_providers
from chatlol import config


@pytest.mark.asyncio
async def test_ollama_stream_response():
    provider = OllamaProvider()
    messages = [{"role": "user", "content": "Say hi"}]

    # Mock httpx async stream
    mock_response_lines = [
        b'{"message":{"content":"Hi"},"done":false}\n',
        b'{"message":{"content":" there"},"done":false}\n',
        b'{"message":{"content":"!"},"done":true}\n',
    ]

    async def mock_aiter_lines():
        for line in mock_response_lines:
            yield line.decode()

    mock_response = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient.stream", return_value=mock_response):
        tokens = []
        async for token in provider.stream_response(messages, "llama3.2"):
            tokens.append(token)

    assert tokens == ["Hi", " there", "!"]


def test_ollama_get_models():
    models = OllamaProvider.get_models()
    assert "llama3.2" in models
    assert isinstance(models, list)


@pytest.mark.asyncio
async def test_claude_stream_response():
    provider = ClaudeProvider()
    messages = [{"role": "user", "content": "Say hi"}]

    mock_event1 = MagicMock()
    mock_event1.type = "content_block_delta"
    mock_event1.delta = MagicMock(type="text_delta", text="Hi")

    mock_event2 = MagicMock()
    mock_event2.type = "content_block_delta"
    mock_event2.delta = MagicMock(type="text_delta", text=" there!")

    mock_event3 = MagicMock()
    mock_event3.type = "message_stop"

    async def mock_aiter():
        for e in [mock_event1, mock_event2, mock_event3]:
            yield e

    mock_stream = MagicMock()
    mock_stream.__aiter__ = lambda self: mock_aiter()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    with patch("anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.stream.return_value = mock_stream
        tokens = []
        async for token in provider.stream_response(messages, "claude-sonnet-4-6"):
            tokens.append(token)

    assert "".join(tokens) == "Hi there!"


def test_claude_get_models():
    models = ClaudeProvider.get_models()
    assert "claude-sonnet-4-6" in models


@pytest.mark.asyncio
async def test_openai_stream_response():
    provider = OpenAIProvider()
    messages = [{"role": "user", "content": "Say hi"}]

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hi"), finish_reason=None)]
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock(delta=MagicMock(content=" there!"), finish_reason="stop")]

    async def mock_aiter():
        for c in [mock_chunk1, mock_chunk2]:
            yield c

    mock_stream = MagicMock()
    mock_stream.__aiter__ = lambda self: mock_aiter()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    with patch("openai.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.stream.return_value = mock_stream
        tokens = []
        async for token in provider.stream_response(messages, "gpt-4o"):
            tokens.append(token)

    assert "".join(tokens) == "Hi there!"


@pytest.mark.asyncio
async def test_kiro_raises():
    provider = KiroProvider()
    with pytest.raises(NotImplementedError):
        async for _ in provider.stream_response([], "kiro"):
            pass


def test_get_provider_registry():
    assert isinstance(get_provider("ollama"), __import__("chatlol.providers.ollama", fromlist=["OllamaProvider"]).OllamaProvider)
    assert isinstance(get_provider("claude"), __import__("chatlol.providers.claude", fromlist=["ClaudeProvider"]).ClaudeProvider)
    with pytest.raises(ValueError):
        get_provider("nonexistent")


# ── New OpenAI-compatible providers: DeepSeek / OpenRouter / 9Router ──

def test_new_providers_registered():
    assert isinstance(get_provider("deepseek"), DeepSeekProvider)
    assert isinstance(get_provider("openrouter"), OpenRouterProvider)
    assert isinstance(get_provider("9router"), NineRouterProvider)
    ids = [p["id"] for p in list_providers()]
    for pid in ("deepseek", "openrouter", "9router"):
        assert pid in ids


def test_new_providers_get_models():
    assert "deepseek-chat" in DeepSeekProvider.get_models()
    assert any("/" in m for m in OpenRouterProvider.get_models())  # slug provider/model
    assert len(NineRouterProvider.get_models()) > 0


def test_deepseek_client_uses_base_url(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-deepseek")
    with patch("openai.AsyncOpenAI") as M:
        DeepSeekProvider()._get_client()
    M.assert_called_once_with(api_key="sk-deepseek", base_url="https://api.deepseek.com/v1")


def test_openrouter_client_uses_base_url(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or")
    with patch("openai.AsyncOpenAI") as M:
        OpenRouterProvider()._get_client()
    M.assert_called_once_with(api_key="sk-or", base_url="https://openrouter.ai/api/v1")


def test_ninerouter_client_defaults_local(monkeypatch):
    # API key kosong -> placeholder; base_url dari config (gateway lokal)
    monkeypatch.setattr(config, "NINEROUTER_API_KEY", None)
    monkeypatch.setattr(config, "NINEROUTER_URL", "http://localhost:20128/v1")
    with patch("openai.AsyncOpenAI") as M:
        NineRouterProvider()._get_client()
    M.assert_called_once_with(api_key="9router-local", base_url="http://localhost:20128/v1")


@pytest.mark.asyncio
async def test_deepseek_stream_inherits_openai(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-x")
    provider = DeepSeekProvider()
    messages = [{"role": "user", "content": "Say hi"}]

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hi"), finish_reason=None)]
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock(delta=MagicMock(content=" there!"), finish_reason="stop")]

    async def mock_aiter():
        for c in [mock_chunk1, mock_chunk2]:
            yield c

    mock_stream = MagicMock()
    mock_stream.__aiter__ = lambda self: mock_aiter()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=False)

    with patch("openai.AsyncOpenAI") as MockClient:
        MockClient.return_value.chat.completions.stream.return_value = mock_stream
        tokens = []
        async for token in provider.stream_response(messages, "deepseek-chat"):
            tokens.append(token)

    assert "".join(tokens) == "Hi there!"
