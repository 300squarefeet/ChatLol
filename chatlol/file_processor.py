import io
from dataclasses import dataclass

MAX_BYTES = 10 * 1024 * 1024  # 10MB

ALLOWED_EXTENSIONS: set[str] = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".json", ".yaml", ".yml", ".toml",
    ".sh", ".bash", ".go", ".rs", ".java", ".c", ".cpp",
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass
class ProcessedFile:
    name: str
    type: str          # "text" | "image"
    content: str | None
    data: bytes | None


def process_file(filename: str, file_bytes: bytes) -> ProcessedFile:
    if len(file_bytes) > MAX_BYTES:
        raise ValueError("Ukuran file melebihi batas 10MB")

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Tipe file '{ext}' tidak didukung")

    if ext in IMAGE_EXTENSIONS:
        return ProcessedFile(name=filename, type="image", content=None, data=file_bytes)

    if ext == ".pdf":
        content = _extract_pdf_text(file_bytes)
        return ProcessedFile(name=filename, type="text", content=content, data=None)

    content = file_bytes.decode("utf-8", errors="replace")
    return ProcessedFile(name=filename, type="text", content=content, data=None)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    except Exception:
        return "[Gagal membaca isi PDF]"
