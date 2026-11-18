"""
Reference Document Service
===========================
Handles brand-setup reference-document uploads: text extraction, storage on
disk, and lookup by ref_id. Extracted text is capped at 50,000 chars so a
single document can't reproduce the multi-hundred-KB blob problem the scraped
sources already have (see pipeline_service._compile_knowledge_base).
"""

import os
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_CHARS = 50_000
_TRUNCATION_MARKER = "…[truncated]"

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UPLOAD_DIR = os.path.normpath(os.path.join(_BACKEND_ROOT, "static", "uploads", "references"))


def _resolve_ref_path(ref_id: str, suffix: str) -> Optional[str]:
    """Maps a ref_id + suffix (e.g. ".txt", ".pdf") to a filesystem path confined
    to the references upload dir (guards against path traversal via a crafted
    ref_id), mirroring brand_theme._resolve_logo_path's guard."""
    if not ref_id or not isinstance(ref_id, str):
        return None
    filename = f"{ref_id}{suffix}"
    path = os.path.normpath(os.path.join(_UPLOAD_DIR, filename))
    if not (path == _UPLOAD_DIR or path.startswith(_UPLOAD_DIR + os.sep)):
        return None
    return path


def extract_text(file_path: str, ext: str) -> str:
    """Extracts text from a .txt/.md/.docx/.pdf file, truncated to 50,000 chars."""
    ext = ext.lower()
    if ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    elif ext == ".docx":
        from docx import Document
        doc = Document(file_path)
        text = "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".pdf":
        text = _extract_pdf_text(file_path)
    else:
        raise ValueError(f"Unsupported reference document extension: {ext}")

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + _TRUNCATION_MARKER
    return text


def _extract_pdf_text(file_path: str) -> str:
    """Extracts PDF text via pypdf if available, else pdfplumber. Raises a
    clear RuntimeError if neither library is installed."""
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except ImportError:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except ImportError:
        pass

    raise RuntimeError(
        "No PDF text-extraction library is installed. Install 'pypdf' or "
        "'pdfplumber' to enable .pdf reference document uploads."
    )


def save_reference(filename: str, contents: bytes) -> dict:
    """Writes the raw uploaded bytes to {uuid}{ext} and the extracted text to
    {uuid}.txt under the references upload dir. Returns
    {ref_id, filename, char_count}. Caller (the router) is responsible for
    ext/size validation before calling this, mirroring projects.upload_logo."""
    ext = os.path.splitext(filename or "")[1].lower()
    ref_id = uuid.uuid4().hex
    os.makedirs(_UPLOAD_DIR, exist_ok=True)

    raw_path = _resolve_ref_path(ref_id, ext)
    with open(raw_path, "wb") as f:
        f.write(contents)

    try:
        text = extract_text(raw_path, ext)
    except Exception:
        # Extraction failed (e.g. missing PDF lib) — no ref_id is ever returned
        # to the caller in that case, so don't leave an orphaned raw file behind.
        if os.path.isfile(raw_path):
            os.remove(raw_path)
        raise

    text_path = _resolve_ref_path(ref_id, ".txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {"ref_id": ref_id, "filename": filename, "char_count": len(text)}


def load_reference_text(ref_id: str) -> str:
    """Reads the extracted text for ref_id, returning "" if missing."""
    path = _resolve_ref_path(ref_id, ".txt")
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[ReferenceService] Failed to read reference text for {ref_id}: {e}")
        return ""
