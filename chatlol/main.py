import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from . import database
from . import providers as _providers
from .file_processor import process_file, ProcessedFile

database.init_db()

app = FastAPI(title="ChatLol")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# In-memory store untuk uploaded files (keyed by file_id)
_uploaded_files: dict[str, ProcessedFile] = {}

# File Manager
_FM_ROOT: Path = Path(os.getenv("FILE_MANAGER_ROOT", ".")).resolve()


def _safe_path(relative: str) -> Path:
    target = (_FM_ROOT / relative).resolve()
    try:
        target.relative_to(_FM_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path tidak valid")
    return target


class MkdirRequest(BaseModel):
    path: str = ""
    name: str


class SettingsBody(BaseModel):
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    NINEROUTER_API_KEY: str = ""
    PORT: int | None = None      # None = tidak diubah (jangan menimpa nilai lama)
    OLLAMA_URL: str = ""         # "" = tidak diubah (di-skip oleh save_settings_json)


async def require_localhost(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Settings hanya dapat diakses dari host")


def _mask_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 5:
        return "●●●●●"          # key pendek: jangan bocorkan apa pun
    return value[:5] + "●●●●●"


@app.get("/")
async def root():
    return FileResponse(str(_STATIC / "index.html"))


@app.get("/providers")
async def get_providers():
    return _providers.list_providers()


@app.get("/history/{username}")
async def get_history(username: str):
    uid = database.get_user_id(username)
    if uid is None:
        return []
    return database.get_sessions(uid)


@app.get("/history/{username}/{session_id}")
async def get_session_messages(username: str, session_id: int):
    uid = database.get_user_id(username)
    if uid is None or not database.session_belongs_to(session_id, uid):
        raise HTTPException(status_code=403, detail="Access denied")
    return database.get_messages(session_id)


@app.delete("/history/{username}/{session_id}")
async def delete_session(username: str, session_id: int):
    uid = database.get_user_id(username)
    if uid is None or not database.session_belongs_to(session_id, uid):
        raise HTTPException(status_code=403, detail="Access denied")
    database.delete_session(session_id)
    return {"ok": True}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File terlalu besar (maks 10MB)")
    try:
        processed = process_file(file.filename or "file", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file_id = str(uuid.uuid4())
    _uploaded_files[file_id] = processed
    return {"file_id": file_id, "name": processed.name, "type": processed.type}


@app.get("/files")
async def files_page():
    return FileResponse(str(_STATIC / "files.html"))


@app.get("/files/api/list")
async def files_list(path: str = ""):
    target = _safe_path(path)
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Direktori tidak ditemukan")
    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        try:
            stat = item.stat()
        except OSError:
            continue  # lewati symlink rusak / file yang hilang saat di-scan
        entries.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size": stat.st_size if item.is_file() else None,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"path": path, "entries": entries}


@app.post("/files/api/mkdir")
async def files_mkdir(body: MkdirRequest):
    parent = _safe_path(body.path)
    name = body.name.strip()
    if not name or "/" in name or "\\" in name or name == "..":
        raise HTTPException(status_code=400, detail="Nama folder tidak valid")
    new_dir = parent / name
    if new_dir.exists():
        raise HTTPException(status_code=409, detail="Folder sudah ada")
    new_dir.mkdir()
    return {"ok": True}


@app.post("/files/api/upload")
async def files_upload(path: str = "", file: UploadFile = File(...)):
    target_dir = _safe_path(path)
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Direktori tidak ditemukan")
    # Tolak nama file yang mengandung pemisah path (cegah traversal via filename)
    raw_name = file.filename or "upload"
    safe_name = Path(raw_name).name
    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Nama file tidak valid")
    dest = _safe_path(f"{path}/{safe_name}" if path else safe_name)
    if dest.exists():
        raise HTTPException(status_code=409, detail="File sudah ada")
    # Stream ke disk per-chunk (tanpa batas ukuran, tapi tidak menahan seluruh file di RAM → cegah OOM).
    # Mode "xb": exclusive create — gagal jika file muncul di antara cek dan tulis (anti-overwrite/anti-RCE).
    size = 0
    try:
        with dest.open("xb") as out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB per iterasi
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="File sudah ada")
    return {"ok": True, "name": dest.name, "size": size}


@app.get("/files/download")
async def files_download(path: str):
    target = _safe_path(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(
        str(target),
        filename=target.name,
        headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


@app.get("/settings", dependencies=[Depends(require_localhost)])
async def settings_page():
    return FileResponse(str(_STATIC / "settings.html"))


@app.get("/settings/api", dependencies=[Depends(require_localhost)])
async def settings_get():
    return {
        "ANTHROPIC_API_KEY": _mask_key(config.ANTHROPIC_API_KEY),
        "OPENAI_API_KEY": _mask_key(config.OPENAI_API_KEY),
        "GEMINI_API_KEY": _mask_key(config.GEMINI_API_KEY),
        "DEEPSEEK_API_KEY": _mask_key(config.DEEPSEEK_API_KEY),
        "OPENROUTER_API_KEY": _mask_key(config.OPENROUTER_API_KEY),
        "NINEROUTER_API_KEY": _mask_key(config.NINEROUTER_API_KEY),
        "PORT": config.PORT,
        "OLLAMA_URL": config.OLLAMA_URL,
    }


@app.put("/settings/api", dependencies=[Depends(require_localhost)])
async def settings_put(body: SettingsBody):
    config.save_settings_json(body.model_dump())
    config.reload_from_settings()
    return {"ok": True}


@app.websocket("/ws/{username}")
async def websocket_chat(ws: WebSocket, username: str):
    await ws.accept()
    uid = database.get_or_create_user(username)

    try:
        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)

            session_id: int | None = payload.get("session_id")
            provider_name: str = payload.get("provider", "ollama")
            model: str = payload.get("model", "llama3.2")
            user_message: str = payload.get("message", "")
            file_id: str | None = payload.get("file_id")

            # Resolve uploaded file
            pfile: ProcessedFile | None = _uploaded_files.pop(file_id, None) if file_id else None

            # Create or continue session
            if session_id is None:
                session_id = database.create_session(uid, provider_name, model)
            elif not database.session_belongs_to(session_id, uid):
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": "Access denied: session does not belong to you",
                }))
                session_id = database.create_session(uid, provider_name, model)

            await ws.send_text(json.dumps({"type": "session_id", "session_id": session_id}))

            # Save user message
            database.save_message(
                session_id, "user", user_message,
                file_name=pfile.name if pfile else None,
            )

            # Auto-title: set title from first user message if still "New Chat"
            sessions = database.get_sessions(uid)
            current = next((s for s in sessions if s["id"] == session_id), None)
            if current and current["title"] == "New Chat":
                title = user_message[:40] + ("..." if len(user_message) > 40 else "")
                database.update_session_title(session_id, title)

            # Build conversation history for provider
            history = database.get_messages(session_id)
            messages = [{"role": m["role"], "content": m["content"]} for m in history]

            # Stream response from provider
            provider = _providers.get_provider(provider_name)
            full_response = ""
            try:
                async for token in provider.stream_response(
                    messages=messages,
                    model=model,
                    file_content=pfile.content if pfile else None,
                    file_name=pfile.name if pfile else None,
                    file_type=pfile.type if pfile else None,
                    file_data=pfile.data if pfile else None,
                ):
                    full_response += token
                    await ws.send_text(json.dumps({"type": "token", "content": token}))
            except NotImplementedError as e:
                await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "message": f"Provider error: {e}"}))
            else:
                # Only save assistant reply when no exception occurred
                database.save_message(session_id, "assistant", full_response)

            await ws.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
