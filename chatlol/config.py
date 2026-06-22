import json
import os
from pathlib import Path
from dotenv import load_dotenv

# .env lookup: CWD dulu → ~/.chatlol/.env fallback
_cwd_env = Path.cwd() / ".env"
_home_env = Path.home() / ".chatlol" / ".env"
if _cwd_env.exists():
    load_dotenv(_cwd_env)
elif _home_env.exists():
    load_dotenv(_home_env)

ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY: str | None = os.getenv("DEEPSEEK_API_KEY")
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
NINEROUTER_API_KEY: str | None = os.getenv("NINEROUTER_API_KEY")
# 9Router adalah gateway lokal OpenAI-compatible (default port npm `9router`).
NINEROUTER_URL: str = os.getenv("NINEROUTER_URL", "http://localhost:20128/v1")
PORT: int = int(os.getenv("PORT", "8000"))
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Data dir di home agar tidak mengotori CWD
_DATA_DIR = Path.home() / ".chatlol"
_DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR: str = str(_DATA_DIR / "uploads")
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

Path(UPLOAD_DIR).mkdir(exist_ok=True)

_SETTINGS_FILE: Path = _DATA_DIR / "settings.json"


def load_settings_json() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_settings_json(data: dict) -> None:
    """Merge ke settings.json. String kosong di-SKIP (preserve nilai lama)
    — termasuk OLLAMA_URL, agar URL tak pernah jadi "" dan merusak Ollama.
    Nilai None di-skip. Nilai non-string (mis. PORT int) disimpan apa adanya."""
    existing = load_settings_json()
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str):
            if value:  # skip string kosong
                existing[key] = value
        else:
            existing[key] = value
    _SETTINGS_FILE.write_text(json.dumps(existing, indent=2))


def reload_from_settings() -> None:
    import sys
    this = sys.modules[__name__]
    data = load_settings_json()
    if "ANTHROPIC_API_KEY" in data:
        this.ANTHROPIC_API_KEY = data["ANTHROPIC_API_KEY"]
    if "OPENAI_API_KEY" in data:
        this.OPENAI_API_KEY = data["OPENAI_API_KEY"]
    if "GEMINI_API_KEY" in data:
        this.GEMINI_API_KEY = data["GEMINI_API_KEY"]
    if "DEEPSEEK_API_KEY" in data:
        this.DEEPSEEK_API_KEY = data["DEEPSEEK_API_KEY"]
    if "OPENROUTER_API_KEY" in data:
        this.OPENROUTER_API_KEY = data["OPENROUTER_API_KEY"]
    if "NINEROUTER_API_KEY" in data:
        this.NINEROUTER_API_KEY = data["NINEROUTER_API_KEY"]
    if "NINEROUTER_URL" in data:
        this.NINEROUTER_URL = data["NINEROUTER_URL"]
    if "OLLAMA_URL" in data:
        this.OLLAMA_URL = data["OLLAMA_URL"]
    if "PORT" in data:
        this.PORT = int(data["PORT"])


reload_from_settings()
