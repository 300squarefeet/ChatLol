import os
import pytest
from chatlol import database

TEST_DB = "test_chatlol.db"

@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
    yield
    # cleanup otomatis oleh tmp_path

def test_get_or_create_user_creates_new():
    uid = database.get_or_create_user("alice")
    assert isinstance(uid, int)
    assert uid > 0

def test_get_or_create_user_idempotent():
    uid1 = database.get_or_create_user("bob")
    uid2 = database.get_or_create_user("bob")
    assert uid1 == uid2

def test_create_session_returns_id():
    uid = database.get_or_create_user("carol")
    sid = database.create_session(uid, "claude", "claude-sonnet-4-6")
    assert isinstance(sid, int)
    assert sid > 0

def test_save_and_get_messages():
    uid = database.get_or_create_user("dave")
    sid = database.create_session(uid, "ollama", "llama3.2")
    database.save_message(sid, "user", "Hello")
    database.save_message(sid, "assistant", "Hi there!")
    msgs = database.get_messages(sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello"
    assert msgs[1]["role"] == "assistant"

def test_save_message_with_file():
    uid = database.get_or_create_user("eve")
    sid = database.create_session(uid, "openai", "gpt-4o")
    database.save_message(sid, "user", "Here is my file", file_name="report.pdf")
    msgs = database.get_messages(sid)
    assert msgs[0]["file_name"] == "report.pdf"

def test_get_sessions_returns_list():
    uid = database.get_or_create_user("frank")
    database.create_session(uid, "gemini", "gemini-2.0-flash")
    sessions = database.get_sessions(uid)
    assert len(sessions) >= 1
    assert "id" in sessions[0]
    assert "provider" in sessions[0]

def test_update_session_title():
    uid = database.get_or_create_user("grace")
    sid = database.create_session(uid, "claude", "claude-sonnet-4-6")
    database.update_session_title(sid, "Diskusi Python")
    sessions = database.get_sessions(uid)
    match = next(s for s in sessions if s["id"] == sid)
    assert match["title"] == "Diskusi Python"

def test_delete_session():
    uid = database.get_or_create_user("hank")
    sid = database.create_session(uid, "ollama", "llama3.2")
    database.save_message(sid, "user", "test")
    database.delete_session(sid)
    msgs = database.get_messages(sid)
    assert msgs == []
    sessions = database.get_sessions(uid)
    assert all(s["id"] != sid for s in sessions)
