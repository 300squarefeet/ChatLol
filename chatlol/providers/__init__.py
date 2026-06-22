from .base import BaseProvider
from .ollama import OllamaProvider
from .claude import ClaudeProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider
from .kiro import KiroProvider
from .claude_cli import ClaudeCliProvider
from .antigravity import AntigravityProvider
from .deepseek import DeepSeekProvider
from .openrouter import OpenRouterProvider
from .ninerouter import NineRouterProvider

_REGISTRY: dict[str, type[BaseProvider]] = {
    "ollama": OllamaProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "kiro": KiroProvider,
    "claude-cli": ClaudeCliProvider,
    "antigravity": AntigravityProvider,
    "deepseek": DeepSeekProvider,
    "openrouter": OpenRouterProvider,
    "9router": NineRouterProvider,
}


def get_provider(name: str) -> BaseProvider:
    """Return a new instance of the named provider.

    Raises ValueError for unknown provider names.
    """
    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider: '{name}'. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]()


def list_providers() -> list[dict]:
    """Return metadata for all registered providers."""
    return [
        {"id": "ollama",  "label": "Ollama (Lokal)",       "models": OllamaProvider.get_models()},
        {"id": "claude",  "label": "Claude (Anthropic)",   "models": ClaudeProvider.get_models()},
        {"id": "openai",  "label": "OpenAI (GPT)",         "models": OpenAIProvider.get_models()},
        {"id": "gemini",  "label": "Gemini (Google)",      "models": GeminiProvider.get_models()},
        {"id": "kiro",    "label": "Kiro AI (Segera)",     "models": KiroProvider.get_models()},
        {"id": "claude-cli", "label": "Claude (CLI · tanpa API key)", "models": ClaudeCliProvider.get_models()},
        {"id": "antigravity", "label": "Gemini (Antigravity · tanpa API key)", "models": AntigravityProvider.get_models()},
        {"id": "deepseek",   "label": "DeepSeek",                 "models": DeepSeekProvider.get_models()},
        {"id": "openrouter", "label": "OpenRouter",               "models": OpenRouterProvider.get_models()},
        {"id": "9router",    "label": "9Router (gateway lokal)",  "models": NineRouterProvider.get_models()},
    ]
