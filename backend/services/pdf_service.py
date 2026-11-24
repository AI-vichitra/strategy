"""
PDF Service — DOCX -> PDF conversion via headless LibreOffice.

Requires LibreOffice installed (soffice). Dev: Windows installer;
Prod: apt-get install --no-install-recommends libreoffice-writer libreoffice-core.
"""

import os
import pathlib
import shutil
import subprocess
import tempfile

from fastapi import HTTPException


def _find_soffice() -> str:
    """Locate the LibreOffice binary cross-platform. Raises RuntimeError with
    install guidance if none is found."""
    override = os.environ.get("LIBREOFFICE_PATH")
    if override and os.path.isfile(override):
        return override

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        if os.path.isfile(candidate):
            return candidate

    raise RuntimeError(
        "LibreOffice (soffice) was not found on this machine.\n"
        "  Windows: install from https://www.libreoffice.org/download/download/\n"
        "  macOS: brew install --cask libreoffice\n"
        "  Linux: apt-get install --no-install-recommends libreoffice-writer libreoffice-core\n"
        "Or set the LIBREOFFICE_PATH environment variable to the soffice binary path."
    )


def docx_bytes_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert .docx bytes to PDF bytes via LibreOffice headless."""
    try:
        soffice = _find_soffice()
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="PDF export is unavailable in this environment. Use DOCX or PPTX export.",
        )

    work_dir = tempfile.mkdtemp(prefix="pdf_convert_")
    profile_dir = tempfile.mkdtemp(prefix="pdf_profile_")
    try:
        input_path = os.path.join(work_dir, "input.docx")
        with open(input_path, "wb") as f:
            f.write(docx_bytes)

        profile_uri = pathlib.Path(profile_dir).as_uri()
        cmd = [
            soffice,
            "--headless",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to", "pdf",
            "--outdir", work_dir,
            input_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=90)
        except subprocess.TimeoutExpired as e:
            stderr_tail = (e.stderr or b"").decode(errors="replace")[-2000:]
            raise RuntimeError(
                f"LibreOffice conversion timed out after 90s. stderr: {stderr_tail}"
            )

        output_path = os.path.join(work_dir, "input.pdf")
        if result.returncode != 0 or not os.path.isfile(output_path):
            stderr_tail = result.stderr.decode(errors="replace")[-2000:]
            raise RuntimeError(
                f"LibreOffice conversion failed (exit {result.returncode}). stderr: {stderr_tail}"
            )

        with open(output_path, "rb") as f:
            return f.read()
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        shutil.rmtree(profile_dir, ignore_errors=True)
