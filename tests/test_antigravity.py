import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from chatlol.providers.antigravity import AntigravityProvider
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


@pytest.fixture(autouse=True)
def _reset_model_cache():
    # Cache model bersifat per-proses (class attr); reset agar test terisolasi.
    AntigravityProvider._cached_models = None
    yield
    AntigravityProvider._cached_models = None


# ── get_models ─────────────────────────────────────────────

def test_get_models_falls_back_when_cli_missing():
    with patch("chatlol.providers.antigravity.shutil.which", return_value=None):
        models = AntigravityProvider.get_models()
    assert models == AntigravityProvider._FALLBACK_MODELS
    assert "Gemini 3.5 Flash (Low)" in models
    assert "default" not in models  # jangan hanya "default" lagi


def test_get_models_parses_agy_models_output():
    fake = MagicMock(returncode=0, stdout="Gemini 3.5 Flash (Low)\nClaude Opus 4.6 (Thinking)\n\n")
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.subprocess.run", return_value=fake) as mrun:
        models = AntigravityProvider.get_models()
    assert models == ["Gemini 3.5 Flash (Low)", "Claude Opus 4.6 (Thinking)"]
    assert mrun.call_args.args[0] == ["agy", "models"]


def test_get_models_is_cached():
    fake = MagicMock(returncode=0, stdout="Gemini 3.5 Flash (Low)\n")
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.subprocess.run", return_value=fake) as mrun:
        AntigravityProvider.get_models()
        AntigravityProvider.get_models()
    assert mrun.call_count == 1  # query hanya sekali, sisanya dari cache


def test_get_models_falls_back_on_nonzero_exit():
    fake = MagicMock(returncode=1, stdout="")
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.subprocess.run", return_value=fake):
        models = AntigravityProvider.get_models()
    assert models == AntigravityProvider._FALLBACK_MODELS


# ── stream_response ────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_yields_stdout_and_is_locked_down():
    AntigravityProvider._cached_models = ["Gemini 3.5 Flash (Low)", "Claude Opus 4.6 (Thinking)"]
    p = AntigravityProvider()
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stdout=b"PINGOK"))) as mock_exec:
        chunks = await _collect(p.stream_response([{"role": "user", "content": "hai"}], "default"))
    assert "".join(chunks) == "PINGOK"
    args = mock_exec.call_args.args
    assert args[0] == "agy" and "-p" in args
    # Lockdown: sandbox aktif, TANPA auto-approve berbahaya
    assert "--sandbox" in args
    assert "--dangerously-skip-permissions" not in args


@pytest.mark.asyncio
async def test_stream_passes_selected_model():
    AntigravityProvider._cached_models = ["Gemini 3.5 Flash (Low)", "Claude Opus 4.6 (Thinking)"]
    p = AntigravityProvider()
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stdout=b"ok"))) as mock_exec:
        await _collect(p.stream_response(
            [{"role": "user", "content": "hai"}], "Claude Opus 4.6 (Thinking)"))
    args = list(mock_exec.call_args.args)
    assert "--model" in args
    assert args[args.index("--model") + 1] == "Claude Opus 4.6 (Thinking)"


@pytest.mark.asyncio
async def test_stream_unknown_model_falls_back_to_first():
    AntigravityProvider._cached_models = ["Gemini 3.5 Flash (Low)", "Claude Opus 4.6 (Thinking)"]
    p = AntigravityProvider()
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stdout=b"ok"))) as mock_exec:
        await _collect(p.stream_response(
            [{"role": "user", "content": "hai"}], "Model Palsu Tidak Ada"))
    args = list(mock_exec.call_args.args)
    assert "--model" in args
    # Model tak dikenal -> jatuh ke model pertama (default), bukan diteruskan mentah
    assert args[args.index("--model") + 1] == "Gemini 3.5 Flash (Low)"


@pytest.mark.asyncio
async def test_stream_raises_when_cli_missing():
    p = AntigravityProvider()
    with patch("chatlol.providers.antigravity.shutil.which", return_value=None):
        with pytest.raises(RuntimeError):
            await _collect(p.stream_response([{"role": "user", "content": "hai"}], "default"))


@pytest.mark.asyncio
async def test_error_does_not_leak_stderr():
    AntigravityProvider._cached_models = ["Gemini 3.5 Flash (Low)"]
    p = AntigravityProvider()
    with patch("chatlol.providers.antigravity.shutil.which", return_value="/usr/bin/agy"), \
         patch("chatlol.providers.antigravity.asyncio.create_subprocess_exec",
               AsyncMock(return_value=_fake_proc(stderr=b"SECRET-PATH", returncode=3))):
        with pytest.raises(RuntimeError) as ei:
            await _collect(p.stream_response([{"role": "user", "content": "hai"}], "default"))
    assert "SECRET-PATH" not in str(ei.value)


def test_registry_has_antigravity():
    prov = providers.get_provider("antigravity")
    assert isinstance(prov, AntigravityProvider)
    ids = [p["id"] for p in providers.list_providers()]
    assert "antigravity" in ids
