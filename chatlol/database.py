import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Simpan DB di ~/.chatlol/ — tidak mengotori CWD
_DATA_DIR = Path.home() / ".chatlol"
_DATA_DIR.mkdir(exist_ok=True)
DB_PATH: str = str(_DATA_DIR / "chatlol.db")


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title TEXT DEFAULT 'New Chat',
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT CHECK(role IN ('user','assistant')) NOT NULL,
                content TEXT NOT NULL,
                file_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def get_user_id(username: str) -> int | None:
    """Lookup user by username, return None if not found (no create)."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row["id"] if row else None


def session_belongs_to(session_id: int, user_id: int) -> bool:
    """Return True if session_id exists and belongs to user_id."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        return row is not None


def get_or_create_user(username: str) -> int:
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO users (username) VALUES (?)", (username,)
        )
        row = con.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row["id"]


def create_session(user_id: int, provider: str, model: str) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO sessions (user_id, provider, model) VALUES (?, ?, ?)",
            (user_id, provider, model),
        )
        return cur.lastrowid


def update_session_title(session_id: int, title: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
        )


def save_message(
    session_id: int, role: str, content: str, file_name: str | None = None
) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content, file_name) VALUES (?, ?, ?, ?)",
            (session_id, role, content, file_name),
        )


def get_sessions(user_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT id, title, provider, model, created_at
               FROM sessions WHERE user_id = ?
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_messages(session_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content, file_name FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_session(session_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
