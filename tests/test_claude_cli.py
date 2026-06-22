import shutil
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from chatlol.providers.claude_cli import ClaudeCliProvider
from chatlol import providers


def _fake_proc(stdout=b"", stderr=b"", returncode=0):
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.wait = AsyncMock(return_value=returncode)
    proc.kill = MagicMock()
    proc.returncode = returncode
    return proc


async def _collect(gen):
    out = []
    async for chunk in gen:
        out.append(chunk)
    return out


def test_get_models():
    models = ClaudeCliProvider.get_models()
    assert "sonnet" in models and "opus" in models


@pytest.mark.asyncio
async def test_stream_yields_stdout_text():
    p = ClaudeCliProvider()
    with patch("chatlol.providers.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
         patch("chatlol.providers.claude_cli.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stdout=b"Halo dunia"))) as mock_exec:
        chunks = await _collect(p.stream_response(
            [{"role": "user", "content": "hai"}], "sonnet"))
    assert "".join(chunks) == "Halo dunia"
    # argv list, tanpa shell: binary + -p + prompt
    args = mock_exec.call_args.args
    assert args[0] == "claude" and "-p" in args
    # Lockdown keamanan: read-only plan mode + tool berbahaya dilarang
    assert "--permission-mode" in args and "plan" in args
    assert "--disallowedTools" in args and "Bash" in args


@pytest.mark.asyncio
async def test_rejects_unknown_model():
    p = ClaudeCliProvider()
    with patch("chatlol.providers.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
         patch("chatlol.providers.claude_cli.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stdout=b"x"))) as mock_exec:
        with pytest.raises(RuntimeError):
            await _collect(p.stream_response([{"role": "user", "content": "hai"}], "evil; rm -rf"))
    mock_exec.assert_not_called()  # model tak valid → subprocess tak pernah dijalankan


@pytest.mark.asyncio
async def test_error_does_not_leak_stderr():
    p = ClaudeCliProvider()
    with patch("chatlol.providers.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
         patch("chatlol.providers.claude_cli.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stderr=b"SECRET-INTERNAL-PATH", returncode=2))):
        with pytest.raises(RuntimeError) as ei:
            await _collect(p.stream_response([{"role": "user", "content": "hai"}], "sonnet"))
    assert "SECRET-INTERNAL-PATH" not in str(ei.value)  # stderr tak bocor ke pesan


@pytest.mark.asyncio
async def test_stream_raises_on_nonzero_exit():
    p = ClaudeCliProvider()
    with patch("chatlol.providers.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
         patch("chatlol.providers.claude_cli.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stderr=b"boom", returncode=1))):
        with pytest.raises(RuntimeError):
            await _collect(p.stream_response([{"role": "user", "content": "hai"}], "sonnet"))


@pytest.mark.asyncio
async def test_stream_raises_when_cli_missing():
    p = ClaudeCliProvider()
    with patch("chatlol.providers.claude_cli.shutil.which", return_value=None):
        with pytest.raises(RuntimeError):
            await _collect(p.stream_response([{"role": "user", "content": "hai"}], "sonnet"))


@pytest.mark.asyncio
async def test_prompt_includes_history_and_file():
    p = ClaudeCliProvider()
    captured = {}
    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        return _fake_proc(stdout=b"ok")
    with patch("chatlol.providers.claude_cli.shutil.which", return_value="/usr/bin/claude"), \
         patch("chatlol.providers.claude_cli.asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await _collect(p.stream_response(
            [{"role": "user", "content": "tanya"}, {"role": "assistant", "content": "jawab"}],
            "sonnet", file_content="ISI", file_name="a.txt", file_type="text"))
    prompt = captured["args"][2]  # claude, -p, <prompt>
    assert "tanya" in prompt and "jawab" in prompt and "ISI" in prompt


def test_registry_has_claude_cli():
    prov = providers.get_provider("claude-cli")
    assert isinstance(prov, ClaudeCliProvider)
    ids = [p["id"] for p in providers.list_providers()]
    assert "claude-cli" in ids
