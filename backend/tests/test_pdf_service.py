"""Tests for pdf_service.docx_bytes_to_pdf() — run with:
cd backend && python -m pytest tests/test_pdf_service.py -v

Skips gracefully when LibreOffice isn't installed on the machine running
the tests.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from backend.services.export_service import markdown_to_docx
from backend.services.pdf_service import _find_soffice, docx_bytes_to_pdf


def _run(coro):
    return asyncio.run(coro)


def test_docx_to_pdf_produces_valid_pdf():
    try:
        _find_soffice()
    except RuntimeError as e:
        pytest.skip(f"LibreOffice not available: {e}")

    content = (
        "### Market Overview\n"
        "Some findings about the market.\n\n"
        "- First bullet\n"
        "- Second bullet\n\n"
        "| Brand | Share |\n"
        "| --- | --- |\n"
        "| Brand A | 32% |\n"
        "| Brand B | 24% |\n"
    )
    docx_bytes = _run(markdown_to_docx(
        db=None,
        report_id="t1",
        content=content,
        title="Test Report",
        content_override=content,
    ))

    pdf_bytes = docx_bytes_to_pdf(docx_bytes)

    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000
