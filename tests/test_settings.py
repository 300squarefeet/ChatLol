import json
import pytest
from chatlol import config
from chatlol import database as _database
from chatlol.main import app


@pytest.fixture
def settings_file(monkeypatch, tmp_path):
    sf = tmp_path / "settings.json"
    monkeypatch.setattr(config, "_SETTINGS_FILE", sf)
    return sf


def test_load_settings_empty(settings_file):
    assert config.load_settings_json() == {}


def test_load_settings_reads_file(settings_file):
    settings_file.write_text(json.dumps({"ANTHROPIC_API_KEY": "sk-ant-abc"}))
    data = config.load_settings_json()
    assert data["ANTHROPIC_API_KEY"] == "sk-ant-abc"


def test_save_settings_merges(settings_file):
    settings_file.write_text(json.dumps({"ANTHROPIC_API_KEY": "old-key"}))
    config.save_settings_json({"OPENAI_API_KEY": "new-openai"})
    saved = json.loads(settings_file.read_text())
    assert saved["ANTHROPIC_API_KEY"] == "old-key"
    assert saved["OPENAI_API_KEY"] == "new-openai"


def test_save_settings_skips_empty_string(settings_file):
    settings_file.write_text(json.dumps({"ANTHROPIC_API_KEY": "sk-ant-keep"}))
    config.save_settings_json({"ANTHROPIC_API_KEY": "", "OLLAMA_URL": "http://new:11434"})
    saved = json.loads(settings_file.read_text())
    assert saved["ANTHROPIC_API_KEY"] == "sk-ant-keep"
    assert saved["OLLAMA_URL"] == "http://new:11434"


def test_save_settings_always_saves_port(settings_file):
    config.save_settings_json({"PORT": 9000, "OLLAMA_URL": "http://localhost:11434"})
    saved = json.loads(settings_file.read_text())
    assert saved["PORT"] == 9000


def test_save_settings_skips_empty_ollama_url(settings_file):
    # OLLAMA_URL kosong TIDAK boleh menimpa nilai lama (jika tidak Ollama rusak)
    settings_file.write_text(json.dumps({"OLLAMA_URL": "http://keep:11434"}))
    config.save_settings_json({"OLLAMA_URL": "", "PORT": 8000})
    saved = json.loads(settings_file.read_text())
    assert saved["OLLAMA_URL"] == "http://keep:11434"


def test_reload_updates_ollama_url(monkeypatch, settings_file):
    settings_file.write_text(json.dumps({"OLLAMA_URL": "http://192.168.1.5:11434"}))
    config.reload_from_settings()
    assert config.OLLAMA_URL == "http://192.168.1.5:11434"
    monkeypatch.setattr(config, "OLLAMA_URL", "http://localhost:11434")


def test_reload_updates_api_key(monkeypatch, settings_file):
    settings_file.write_text(json.dumps({"ANTHROPIC_API_KEY": "sk-ant-reloaded"}))
    config.reload_from_settings()
    assert config.ANTHROPIC_API_KEY == "sk-ant-reloaded"
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)


def test_ollama_url_default():
    assert hasattr(config, "OLLAMA_URL")
    assert config.OLLAMA_URL.startswith("http")


from fastapi.testclient import TestClient


def _setup_db(monkeypatch, tmp_path, suffix=""):
    db_path = str(tmp_path / f"settings{suffix}.db")
    monkeypatch.setattr(_database, "DB_PATH", db_path)
    _database.init_db()


# Fixture: override require_localhost untuk simulate akses dari localhost
@pytest.fixture
def client(settings_file, monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    from chatlol.main import require_localhost  # lazy — belum ada sebelum Step 4

    async def allow_all():
        pass

    app.dependency_overrides[require_localhost] = allow_all
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# Fixture: TANPA override → simulate akses dari remote (TestClient host = "testclient")
@pytest.fixture
def client_remote(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, suffix="_remote")
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()  # bersihkan juga di teardown (robust thd urutan test)


def test_settings_blocked_from_remote(client_remote):
    resp = client_remote.get("/settings")
    assert resp.status_code == 403


def test_settings_api_blocked_from_remote(client_remote):
    resp = client_remote.get("/settings/api")
    assert resp.status_code == 403


def test_settings_put_blocked_from_remote(client_remote):
    resp = client_remote.put("/settings/api", json={
        "ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
        "PORT": 8000, "OLLAMA_URL": "http://localhost:11434",
    })
    assert resp.status_code == 403


def test_settings_page_accessible_localhost(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_settings_api_get_masked_key(client, settings_file):
    settings_file.write_text(json.dumps({"ANTHROPIC_API_KEY": "sk-ant-abcdefgh"}))
    config.reload_from_settings()
    resp = client.get("/settings/api")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ANTHROPIC_API_KEY"] == "sk-an●●●●●"
    assert "abcdefgh" not in data["ANTHROPIC_API_KEY"]


def test_settings_api_get_empty_unset_key(client, settings_file):
    resp = client.get("/settings/api")
    data = resp.json()
    # key belum diset → kembalikan ""
    assert isinstance(data["OPENAI_API_KEY"], str)


def test_settings_api_get_has_all_fields(client):
    resp = client.get("/settings/api")
    data = resp.json()
    assert set(data.keys()) == {
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "NINEROUTER_API_KEY",
        "PORT", "OLLAMA_URL",
    }


def test_settings_api_put_saves_and_reloads(client, settings_file, monkeypatch):
    resp = client.put("/settings/api", json={
        "ANTHROPIC_API_KEY": "sk-ant-newkey",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": "",
        "PORT": 8000,
        "OLLAMA_URL": "http://localhost:11434",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    saved = json.loads(settings_file.read_text())
    assert saved["ANTHROPIC_API_KEY"] == "sk-ant-newkey"
    assert config.ANTHROPIC_API_KEY == "sk-ant-newkey"
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)


def test_settings_api_put_empty_preserves_old(client, settings_file, monkeypatch):
    settings_file.write_text(json.dumps({"ANTHROPIC_API_KEY": "sk-ant-keep"}))
    config.reload_from_settings()
    resp = client.put("/settings/api", json={
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": "",
        "PORT": 8000,
        "OLLAMA_URL": "http://localhost:11434",
    })
    assert resp.status_code == 200
    saved = json.loads(settings_file.read_text())
    assert saved["ANTHROPIC_API_KEY"] == "sk-ant-keep"
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)


def test_settings_api_put_updates_ollama_url(client, settings_file, monkeypatch):
    resp = client.put("/settings/api", json={
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": "",
        "PORT": 8000,
        "OLLAMA_URL": "http://192.168.1.10:11434",
    })
    assert resp.status_code == 200
    assert config.OLLAMA_URL == "http://192.168.1.10:11434"
    monkeypatch.setattr(config, "OLLAMA_URL", "http://localhost:11434")
