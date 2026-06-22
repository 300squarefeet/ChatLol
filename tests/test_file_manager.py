import pytest
import chatlol.main as main_module
from fastapi.testclient import TestClient
from chatlol import database
from chatlol.main import app


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()


@pytest.fixture
def fm_root(monkeypatch, tmp_path):
    root = tmp_path / "fm"
    root.mkdir()
    monkeypatch.setattr(main_module, "_FM_ROOT", root.resolve())
    return root


@pytest.fixture
def client():
    return TestClient(app)


def test_files_page_returns_html(client):
    resp = client.get("/files")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_list_empty_dir(client, fm_root):
    resp = client.get("/files/api/list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entries"] == []
    assert data["path"] == ""


def test_list_dirs_before_files(client, fm_root):
    (fm_root / "zzz.txt").write_text("z")
    (fm_root / "aaa-dir").mkdir()
    resp = client.get("/files/api/list")
    entries = resp.json()["entries"]
    names = [e["name"] for e in entries]
    assert names.index("aaa-dir") < names.index("zzz.txt")


def test_list_file_metadata(client, fm_root):
    (fm_root / "data.txt").write_bytes(b"hello")
    resp = client.get("/files/api/list")
    entry = resp.json()["entries"][0]
    assert entry["name"] == "data.txt"
    assert entry["type"] == "file"
    assert entry["size"] == 5
    assert "modified" in entry


def test_list_subdir(client, fm_root):
    (fm_root / "sub").mkdir()
    (fm_root / "sub" / "nested.txt").write_text("hi")
    resp = client.get("/files/api/list", params={"path": "sub"})
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert entries[0]["name"] == "nested.txt"


def test_path_traversal_blocked(client, fm_root):
    resp = client.get("/files/api/list", params={"path": "../../etc"})
    assert resp.status_code == 400


def test_mkdir_creates_folder(client, fm_root):
    resp = client.post("/files/api/mkdir", json={"path": "", "name": "newfolder"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert (fm_root / "newfolder").is_dir()


def test_mkdir_invalid_name_slash(client, fm_root):
    resp = client.post("/files/api/mkdir", json={"path": "", "name": "a/b"})
    assert resp.status_code == 400


def test_mkdir_invalid_name_dotdot(client, fm_root):
    resp = client.post("/files/api/mkdir", json={"path": "", "name": ".."})
    assert resp.status_code == 400


def test_mkdir_duplicate(client, fm_root):
    (fm_root / "existing").mkdir()
    resp = client.post("/files/api/mkdir", json={"path": "", "name": "existing"})
    assert resp.status_code == 409


def test_upload_file(client, fm_root):
    resp = client.post(
        "/files/api/upload",
        params={"path": ""},
        files={"file": ("hello.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["name"] == "hello.txt"
    assert data["size"] == 11
    assert (fm_root / "hello.txt").read_bytes() == b"hello world"


def test_upload_to_subdir(client, fm_root):
    (fm_root / "sub").mkdir()
    resp = client.post(
        "/files/api/upload",
        params={"path": "sub"},
        files={"file": ("file.txt", b"data", "text/plain")},
    )
    assert resp.status_code == 200
    assert (fm_root / "sub" / "file.txt").read_bytes() == b"data"


def test_upload_filename_traversal_sanitized(client, fm_root):
    # Nama file dengan komponen path harus disanitasi → tetap di dalam root
    resp = client.post(
        "/files/api/upload",
        params={"path": ""},
        files={"file": ("../../evil.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "evil.txt"
    assert (fm_root / "evil.txt").is_file()


def test_upload_no_overwrite(client, fm_root):
    # Hardening: upload TIDAK boleh menimpa file yang sudah ada (anti-clobber/anti-RCE)
    (fm_root / "exists.txt").write_bytes(b"original")
    resp = client.post(
        "/files/api/upload",
        params={"path": ""},
        files={"file": ("exists.txt", b"malicious", "text/plain")},
    )
    assert resp.status_code == 409
    # Isi file lama harus tetap utuh
    assert (fm_root / "exists.txt").read_bytes() == b"original"


def test_download_file(client, fm_root):
    (fm_root / "report.txt").write_bytes(b"report content")
    resp = client.get("/files/download", params={"path": "report.txt"})
    assert resp.status_code == 200
    assert resp.content == b"report content"


def test_download_nonexistent(client, fm_root):
    resp = client.get("/files/download", params={"path": "ghost.txt"})
    assert resp.status_code == 404


def test_download_traversal_blocked(client, fm_root):
    resp = client.get("/files/download", params={"path": "../../etc/passwd"})
    assert resp.status_code == 400
