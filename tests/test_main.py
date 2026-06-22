import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from chatlol import database


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()


@pytest.fixture
def client():
    from chatlol.main import app
    return TestClient(app)


def test_get_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_get_providers(client):
    resp = client.get("/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["id"] == "claude" for p in data)
    assert any(p["id"] == "ollama" for p in data)


def test_history_empty(client):
    resp = client.get("/history/newuser")
    assert resp.status_code == 200
    assert resp.json() == []


def test_history_after_messages(client):
    uid = database.get_or_create_user("tester")
    sid = database.create_session(uid, "ollama", "llama3.2")
    database.save_message(sid, "user", "Hello")
    resp = client.get("/history/tester")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1


def test_get_session_messages(client):
    uid = database.get_or_create_user("tester2")
    sid = database.create_session(uid, "ollama", "llama3.2")
    database.save_message(sid, "user", "Test")
    resp = client.get(f"/history/tester2/{sid}")
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Test"


def test_delete_session(client):
    uid = database.get_or_create_user("tester3")
    sid = database.create_session(uid, "ollama", "llama3.2")
    resp = client.delete(f"/history/tester3/{sid}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert database.get_messages(sid) == []


def test_upload_text_file(client):
    resp = client.post(
        "/upload",
        files={"file": ("hello.py", b"print('hello')", "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data
    assert data["type"] == "text"


def test_history_unknown_user_returns_empty(client):
    """GET /history for a non-existent user must return [] without creating the user."""
    resp = client.get("/history/ghost_user_xyz")
    assert resp.status_code == 200
    assert resp.json() == []
    # Confirm the user was NOT created in the database
    assert database.get_user_id("ghost_user_xyz") is None


def test_get_session_messages_idor_denied(client):
    """A user must not be able to read another user's session messages."""
    owner_uid = database.get_or_create_user("owner_user")
    attacker_uid = database.get_or_create_user("attacker_user")  # noqa: F841
    sid = database.create_session(owner_uid, "ollama", "llama3.2")
    database.save_message(sid, "user", "Secret")
    # Attacker tries to read owner's session
    resp = client.get(f"/history/attacker_user/{sid}")
    assert resp.status_code == 403


def test_delete_session_idor_denied(client):
    """A user must not be able to delete another user's session."""
    owner_uid = database.get_or_create_user("owner_del")
    attacker_uid = database.get_or_create_user("attacker_del")  # noqa: F841
    sid = database.create_session(owner_uid, "ollama", "llama3.2")
    resp = client.delete(f"/history/attacker_del/{sid}")
    assert resp.status_code == 403
    # Session must still exist for the real owner
    assert database.session_belongs_to(sid, owner_uid)


def test_websocket_chat(client):
    async def fake_stream(*args, **kwargs):
        yield "Hello"
        yield " world"

    with patch("chatlol.providers.get_provider") as mock_get:
        mock_provider = AsyncMock()
        mock_provider.stream_response = fake_stream
        mock_get.return_value = mock_provider

        with client.websocket_connect("/ws/testuser") as ws:
            ws.send_text(json.dumps({
                "session_id": None,
                "provider": "ollama",
                "model": "llama3.2",
                "message": "Hi",
                "file_id": None,
            }))
            msgs = []
            for _ in range(4):
                msg = json.loads(ws.receive_text())
                msgs.append(msg)
                if msg["type"] == "done":
                    break

        types = [m["type"] for m in msgs]
        assert "session_id" in types
        assert "token" in types
        assert "done" in types


def test_websocket_cross_tenant_session_rejected(client):
    """WS: supplying another user's session_id must trigger an error and a new session."""
    owner_uid = database.get_or_create_user("ws_owner")
    owner_sid = database.create_session(owner_uid, "ollama", "llama3.2")

    async def fake_stream(*args, **kwargs):
        yield "ok"

    with patch("chatlol.providers.get_provider") as mock_get:
        mock_provider = AsyncMock()
        mock_provider.stream_response = fake_stream
        mock_get.return_value = mock_provider

        with client.websocket_connect("/ws/ws_attacker") as ws:
            ws.send_text(json.dumps({
                "session_id": owner_sid,
                "provider": "ollama",
                "model": "llama3.2",
                "message": "steal",
                "file_id": None,
            }))
            msgs = []
            for _ in range(10):
                msg = json.loads(ws.receive_text())
                msgs.append(msg)
                if msg["type"] == "done":
                    break

    types = [m["type"] for m in msgs]
    # Must have sent an access-denied error
    assert any(m["type"] == "error" and "Access denied" in m.get("message", "") for m in msgs)
    # Must have created a new session (session_id message present)
    assert "session_id" in types
    # The owner's session must be untouched
    assert database.get_messages(owner_sid) == []
