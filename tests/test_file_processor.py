import pytest
from chatlol.file_processor import process_file, ProcessedFile, ALLOWED_EXTENSIONS


def test_process_text_file():
    result = process_file("hello.py", b"print('hello')")
    assert result.type == "text"
    assert "print('hello')" in result.content
    assert result.name == "hello.py"


def test_process_pdf_file():
    # Buat PDF minimal valid
    pdf_bytes = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF"""
    result = process_file("doc.pdf", pdf_bytes)
    assert result.type == "text"
    assert result.name == "doc.pdf"


def test_process_image_file():
    # 1x1 pixel PNG
    import base64
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    png_bytes = base64.b64decode(png_b64)
    result = process_file("photo.png", png_bytes)
    assert result.type == "image"
    assert result.data == png_bytes
    assert result.content is None


def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="tidak didukung"):
        process_file("virus.exe", b"bad")


def test_file_too_large_raises():
    with pytest.raises(ValueError, match="10MB"):
        process_file("big.txt", b"x" * (10 * 1024 * 1024 + 1))
