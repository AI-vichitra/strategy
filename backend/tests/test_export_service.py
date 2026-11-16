"""Tests for export_service.markdown_to_docx() — run with:
cd backend && python -m pytest tests/test_export_service.py -v
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from PIL import Image
from docx import Document
from docx.shared import RGBColor

from backend.services.export_service import markdown_to_docx
from backend.services.brand_theme import _resolve_theme

_STATIC_LOGOS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos")


def _run(coro):
    return asyncio.run(coro)


def _generate(content, out_name="t1.docx", **kwargs):
    import io
    data = _run(markdown_to_docx(
        db=None,
        report_id="t1",
        content=content,
        title=kwargs.pop("title", "Report"),
        content_override=content,
        **kwargs,
    ))
    return Document(io.BytesIO(data)), data


def _write_test_logo(filename="_test_export_logo.png"):
    os.makedirs(_STATIC_LOGOS_DIR, exist_ok=True)
    path = os.path.join(_STATIC_LOGOS_DIR, filename)
    Image.new("RGB", (300, 120), (106, 27, 154)).save(path, "PNG")
    return f"/static/uploads/logos/{filename}", path


def test_docx_cover_page_has_logo_when_brand_kit_present():
    logo_url, path = _write_test_logo()
    try:
        doc, data = _generate(
            "### Section\n- A bullet.\n",
            brand_kit={"logo_url": logo_url},
        )
        assert data[:2] == b"PK"
        assert len(doc.inline_shapes) >= 1
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_docx_headings_use_brand_color():
    brand_kit = {"colors": {"primary": "#6A1B9A", "secondary": "#AB47BC", "accent": "#FFB300"}}
    doc, _ = _generate(
        "### Market Overview\nSome text.\n\n#### Consumer Behavior\n- A bullet.\n",
        brand_kit=brand_kit,
        agent_name="brand-positioning",
    )
    theme = _resolve_theme(brand_kit, None, "brand-positioning")
    h3 = doc.styles["Heading 3"]
    assert h3.font.bold is True
    assert h3.font.color.rgb == RGBColor.from_string(theme["primary"])


def test_docx_bullets_not_all_bold():
    content = (
        "### Section\n"
        "- **Decision Drivers:** Consumers weigh price and quality heavily before purchasing.\n"
        "- This whole bullet got wrapped by the LLM for no real reason at all here.\n"
        "- A **key** finding is that mobile browsing dominates discovery.\n"
    )
    # Make the second bullet's whole sentence accidentally wrapped in **.
    content = content.replace(
        "This whole bullet got wrapped by the LLM for no real reason at all here.",
        "**This whole bullet got wrapped by the LLM for no real reason at all here.**",
    )
    doc, _ = _generate(content)

    bullet_paragraphs = [p for p in doc.paragraphs if p.style.name == "List Bullet"]
    assert len(bullet_paragraphs) == 3

    # Label bullet: "Decision Drivers:" bold, rest of the sentence not.
    label_runs = [(r.text, r.bold) for r in bullet_paragraphs[0].runs]
    assert ("Decision Drivers:", True) in label_runs
    assert any(t.strip().startswith("Consumers") and b is not True for t, b in label_runs)

    # Whole-sentence-wrapped bullet: must NOT render bold despite the ** wrapping.
    assert all(r.bold is not True for r in bullet_paragraphs[1].runs)

    # Partial inline bold: "key" bold, rest of the sentence not.
    partial_runs = [(r.text, r.bold) for r in bullet_paragraphs[2].runs]
    assert ("key", True) in partial_runs
    assert any(t.strip().startswith("A") and b is not True for t, b in partial_runs)


def test_docx_pipe_table_after_label_converts_to_table():
    content = (
        "### Market Landscape\n"
        "Key Players:\n"
        "| Brand | Share |\n"
        "| --- | --- |\n"
        "| Brand A | 32% |\n"
        "| Brand B | 24% |\n"
    )
    doc, _ = _generate(content)

    # The label survives as its own paragraph, with no leaked pipe syntax anywhere.
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Key Players" in all_text
    assert "|" not in all_text

    # A real table with the header + 2 data rows exists.
    matching_tables = [t for t in doc.tables if len(t.rows) == 3 and len(t.columns) == 2]
    assert len(matching_tables) == 1
    table = matching_tables[0]
    assert table.rows[0].cells[0].text == "Brand"
    assert table.rows[1].cells[0].text == "Brand A"
    assert table.rows[2].cells[0].text == "Brand B"
