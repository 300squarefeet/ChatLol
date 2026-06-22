# ChatLol

Multi-provider AI chat app you can run locally and access from any device on your WiFi. One command, zero config — bring your own API keys or use CLI-based providers with no key at all.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![PyPI](https://img.shields.io/pypi/v/chatlol)

## Features

- **10 AI providers** — Ollama, Claude, OpenAI, Gemini, DeepSeek, OpenRouter, 9Router, Claude CLI, Antigravity (agy), Kiro
- **No-key providers** — Claude CLI and Antigravity use your local CLI login, no API key needed
- **File uploads** — Attach text, code, PDF, or images; content is sent to the model as context
- **Markdown rendering** — Assistant replies render headings, lists, code blocks with copy button, links, and more
- **Chat history** — Per-user sessions with auto-titles, stored in local SQLite
- **File Manager** — Browse, upload, create folders, drag & drop — all from the browser
- **Settings UI** — Manage API keys, port, and Ollama URL from a web page (localhost-only)
- **Dark / light mode** — Warm Claude-inspired design with one-click theme toggle
- **WiFi access** — Accessible from phones, tablets, or any device on the same network
- **Pip installable** — `pip install chatlol` and run from anywhere

## Quick Start

```bash
pip install chatlol
chatlol
```

Open `http://localhost:8000` in your browser. That's it.

Custom port:

```bash
chatlol 9000
```

## Providers

| Provider | Key Required | Notes |
|----------|:---:|-------|
| Ollama | No | Local models (llama3, mistral, etc.) |
| Claude (API) | Yes | `ANTHROPIC_API_KEY` |
| OpenAI | Yes | `OPENAI_API_KEY` |
| Gemini | Yes | `GEMINI_API_KEY` |
| DeepSeek | Yes | `DEEPSEEK_API_KEY` |
| OpenRouter | Yes | `OPENROUTER_API_KEY` — access 300+ models |
| 9Router | Optional | Local gateway at `localhost:20128` — `npm i -g 9router` |
| Claude CLI | No | Uses `claude` CLI login (Claude Code) |
| Antigravity | No | Uses `agy` CLI login — auto-detects models |
| Kiro | — | Coming soon |

## Configuration

Set API keys via:
- **Settings page** → `http://localhost:8000/settings` (localhost only)
- **Environment variables** or `.env` file
- **`~/.chatlol/settings.json`** (auto-created)

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
NINEROUTER_API_KEY=...
OLLAMA_URL=http://localhost:11434
PORT=8000
```

## Development

```bash
git clone https://github.com/300squarefeet/ChatLol.git
cd ChatLol
pip install -e ".[dev]"
pytest
```

Run the dev server:

```bash
python -m chatlol 8000
```

## Project Structure

```
chatlol/
├── main.py            # FastAPI app, websocket chat, file manager routes
├── config.py          # Settings persistence & reload
├── database.py        # SQLite chat history
├── file_processor.py  # Upload handling (text/PDF/image)
├── providers/         # AI provider implementations
│   ├── ollama.py
│   ├── claude.py
│   ├── openai.py
│   ├── gemini.py
│   ├── deepseek.py
│   ├── openrouter.py
│   ├── ninerouter.py
│   ├── claude_cli.py
│   ├── antigravity.py
│   └── kiro.py
└── static/            # Frontend (vanilla HTML/CSS/JS)
```

## Security

- Settings API is **localhost-only** (403 from remote)
- API keys are **never sent to the browser** — only masked placeholders
- CLI providers run in **sandbox mode** with no tool execution
- File content from uploads is treated as **untrusted data**
- No shell execution — all subprocesses use `exec` with argument lists

## License

MIT
