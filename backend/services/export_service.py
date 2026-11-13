"""
Export Service — server-side DOCX generation
=============================================
Converts a Report's stored markdown+recharts content into an editable .docx.
Charts are re-rendered from their underlying JSON data via matplotlib (not a
screenshot), so the exported chart is a real, data-accurate image.
"""

import io
import json
import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import markdown as md
from bs4 import BeautifulSoup, NavigableString

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_TAB_ALIGNMENT, WD_ALIGN_PARAGRAPH

from backend.services.output_validator import _resolve_chart_type

logger = logging.getLogger(__name__)

_RECHARTS_FENCE_RE = re.compile(r"```recharts[ \t]*\r?\n(.*?)```", re.DOTALL)

# ─────────────────────────────────────────────────────────────────────────────
# Brand tokens — mirrors frontend/src/utils/pdfExport.ts's cover/footer colors
# and frontend/src/components/ReportRenderer.tsx's EXECUTIVE_COLORS chart palette,
# so the DOCX looks like the same document family as the PDF and on-screen report.
# ─────────────────────────────────────────────────────────────────────────────
DOC_FONT = "Calibri"

BRAND_CHARCOAL = RGBColor(0x1A, 0x1A, 0x1A)       # primary text / title
BRAND_CHARCOAL_DARK = RGBColor(0x2D, 0x2A, 0x26)  # wordmark
BRAND_GOLD = RGBColor(0xD4, 0xA8, 0x43)           # accent / tagline
BRAND_AMBER = RGBColor(0xB4, 0x53, 0x09)          # "{AGENT} REPORT" pill text
BRAND_GRAY = RGBColor(0x57, 0x53, 0x4E)           # "Prepared for ..." line
BRAND_MUTED_GRAY = RGBColor(0x78, 0x71, 0x6C)     # "GENERATED DATE" label
BRAND_FOOTER_GRAY = RGBColor(0x96, 0x91, 0x8C)    # footer text (rgb(150,145,140))

BRAND_BORDER_HEX = "E8E4DC"
BRAND_BADGE_BG_HEX = "F5F1EB"
BRAND_TABLE_HEADER_BG_HEX = "F5F1EB"

# Same order as EXECUTIVE_COLORS in frontend/src/components/ReportRenderer.tsx
EXECUTIVE_COLORS = [
    "#2D2A26",  # Deep Charcoal
    "#D4A843",  # Warm StratAI Gold
    "#3B82F6",  # Corporate Blue
    "#10B981",  # Emerald
    "#8B5CF6",  # Purple
    "#EC4899",  # Rose
    "#F59E0B",  # Amber
    "#06B6D4",  # Cyan
    "#6366F1",  # Indigo
]


def _chart_color(idx: int) -> str:
    return EXECUTIVE_COLORS[idx % len(EXECUTIVE_COLORS)]


# ─────────────────────────────────────────────────────────────────────────────
# OXML branding helpers — python-docx has no high-level API for cell shading,
# cell/table borders, or field codes (PAGE/NUMPAGES), so these drop to the
# underlying XML. Each is narrowly scoped to the one property it sets.
# ─────────────────────────────────────────────────────────────────────────────
def _set_cell_shading(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _set_cell_borders(cell, hex_color: str = BRAND_BORDER_HEX, sz: int = 4):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), hex_color)
        borders.append(el)
    tcPr.append(borders)


def _remove_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)


def _add_field(paragraph, field_code: str):
    """Inserts a Word field (e.g. PAGE, NUMPAGES) that Word evaluates on open."""
    run = paragraph.add_run()
    r = run._r
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = field_code
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r.append(fld_begin)
    r.append(instr)
    r.append(fld_end)
    return run


def _to_num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _infer_numeric_keys(data: List[Dict[str, Any]], exclude: set) -> List[str]:
    keys: List[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            if k in exclude or k in keys:
                continue
            if isinstance(v, (int, float)):
                keys.append(k)
    return keys


# ─────────────────────────────────────────────────────────────────────────────
# Chart rendering: recharts JSON → PNG bytes (matplotlib, headless)
# ─────────────────────────────────────────────────────────────────────────────
def _render_bar(ax, data, keys, x_label, y_label):
    names = [str(d.get("name", "")) for d in data]
    if isinstance(keys, list) and keys:
        n = len(keys)
        width = 0.8 / max(n, 1)
        x = list(range(len(names)))
        for i, k in enumerate(keys):
            vals = [_to_num(d.get(k)) for d in data]
            offset = (i - (n - 1) / 2) * width
            ax.bar([xi + offset for xi in x], vals, width=width, label=str(k), color=_chart_color(i))
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right")
        ax.legend()
    else:
        vals = [_to_num(d.get("value")) for d in data]
        x = list(range(len(names)))
        colors = [_chart_color(i) for i in range(len(names))]
        ax.bar(x, vals, color=colors)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right")
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)


def _render_line(ax, data, keys, x_label, y_label, filled):
    names = [str(d.get("name", "")) for d in data]
    x = list(range(len(names)))
    series_keys = keys if isinstance(keys, list) and keys else _infer_numeric_keys(data, exclude={"name"})
    for i, k in enumerate(series_keys):
        vals = [_to_num(d.get(k)) for d in data]
        color = _chart_color(i)
        ax.plot(x, vals, marker="o", label=str(k), color=color)
        if filled:
            ax.fill_between(x, vals, alpha=0.3, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right")
    if len(series_keys) > 1:
        ax.legend()
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)


def _render_radar(ax, data, keys):
    import math

    subjects = [str(d.get("subject", "")) for d in data]
    n = len(subjects)
    if n == 0:
        return
    angles = [i / n * 2 * math.pi for i in range(n)]
    angles += angles[:1]
    series_keys = keys if isinstance(keys, list) and keys else _infer_numeric_keys(data, exclude={"subject"})
    for i, k in enumerate(series_keys):
        vals = [_to_num(d.get(k)) for d in data]
        vals += vals[:1]
        color = _chart_color(i)
        ax.plot(angles, vals, label=str(k), color=color)
        ax.fill(angles, vals, alpha=0.1, color=color)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(subjects)
    if series_keys:
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))


def _render_pie(ax, data):
    names = [str(d.get("name", "")) for d in data]
    vals = [_to_num(d.get("value")) for d in data]
    colors = [_chart_color(i) for i in range(len(names))]
    ax.pie(vals, labels=names, autopct="%1.0f%%", colors=colors)
    ax.axis("equal")


def render_chart_image(chart_json: Optional[dict]) -> Optional[bytes]:
    """Renders a single recharts JSON block to a PNG via matplotlib. Never raises."""
    try:
        if not isinstance(chart_json, dict):
            return None

        data = chart_json.get("data")
        data = data if isinstance(data, list) else []
        if not data:
            return None

        keys = chart_json.get("keys")
        title = chart_json.get("title", "")
        x_label = chart_json.get("x_label", "")
        y_label = chart_json.get("y_label", "")
        chart_type = _resolve_chart_type(chart_json, data)

        if chart_type == "radar":
            fig = plt.figure(figsize=(6, 4.5))
            ax = fig.add_subplot(111, polar=True)
            _render_radar(ax, data, keys)
        else:
            fig, ax = plt.subplots(figsize=(6, 4))
            if chart_type == "bar":
                _render_bar(ax, data, keys, x_label, y_label)
            elif chart_type == "line":
                _render_line(ax, data, keys, x_label, y_label, filled=False)
            elif chart_type == "area":
                _render_line(ax, data, keys, x_label, y_label, filled=True)
            elif chart_type == "pie":
                _render_pie(ax, data)
            else:
                plt.close(fig)
                return None

        if title:
            ax.set_title(title, pad=16 if chart_type == "radar" else None)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"[export_service] render_chart_image failed (non-fatal): {type(e).__name__}: {e}")
        try:
            plt.close("all")
        except Exception:
            pass
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Markdown → docx elements
# ─────────────────────────────────────────────────────────────────────────────
def _add_inline_runs(paragraph, el, bold=False, italic=False, code=False):
    for child in getattr(el, "children", []):
        if isinstance(child, NavigableString):
            text = str(child)
            if not text:
                continue
            run = paragraph.add_run(text)
            run.bold = bold
            run.italic = italic
            if code:
                run.font.name = "Consolas"
            continue

        name = child.name
        if name in ("strong", "b"):
            _add_inline_runs(paragraph, child, bold=True, italic=italic, code=code)
        elif name in ("em", "i"):
            _add_inline_runs(paragraph, child, bold=bold, italic=True, code=code)
        elif name == "code":
            _add_inline_runs(paragraph, child, bold=bold, italic=italic, code=True)
        elif name == "br":
            paragraph.add_run().add_break()
        else:
            _add_inline_runs(paragraph, child, bold=bold, italic=italic, code=code)


def _render_table(doc, table_el):
    rows = table_el.find_all("tr")
    if not rows:
        return
    all_cells = [row.find_all(["th", "td"]) for row in rows]
    ncols = max((len(c) for c in all_cells), default=0)
    if ncols == 0:
        return

    # No built-in style (those default to heavy, blue-tinted banding) — borders
    # and header shading are set explicitly instead, to match the PDF's light
    # gray header row + thin neutral gridlines.
    table = doc.add_table(rows=0, cols=ncols)

    for row, cells in zip(rows, all_cells):
        is_header = any(c.name == "th" for c in cells)
        docx_row = table.add_row()
        for col_idx in range(ncols):
            cell_text = cells[col_idx].get_text().strip() if col_idx < len(cells) else ""
            cell = docx_row.cells[col_idx]
            _set_cell_borders(cell)
            cell.paragraphs[0].paragraph_format.space_before = Pt(2)
            cell.paragraphs[0].paragraph_format.space_after = Pt(2)
            run = cell.paragraphs[0].add_run(cell_text)
            run.font.name = DOC_FONT
            run.font.size = Pt(10)
            if is_header:
                run.bold = True
                run.font.color.rgb = BRAND_CHARCOAL
                _set_cell_shading(cell, BRAND_TABLE_HEADER_BG_HEX)


def _render_block(doc, el):
    name = getattr(el, "name", None)

    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = min(int(name[1]), 4)
        heading = doc.add_heading("", level=level)
        _add_inline_runs(heading, el)
    elif name == "p":
        para = doc.add_paragraph()
        _add_inline_runs(para, el)
    elif name in ("ul", "ol"):
        style = "List Bullet" if name == "ul" else "List Number"
        for li in el.find_all("li", recursive=False):
            nested_lists = li.find_all(["ul", "ol"], recursive=False)
            for nl in nested_lists:
                nl.extract()
            para = doc.add_paragraph(style=style)
            _add_inline_runs(para, li)
            for nl in nested_lists:
                _render_block(doc, nl)
    elif name == "table":
        _render_table(doc, el)
    elif name == "blockquote":
        para = doc.add_paragraph()
        para.add_run(el.get_text().strip()).italic = True
    elif name == "pre":
        para = doc.add_paragraph()
        run = para.add_run(el.get_text())
        run.font.name = "Consolas"
    elif name in (None, "hr"):
        pass
    else:
        text = el.get_text().strip()
        if text:
            doc.add_paragraph(text)


def _render_markdown_text(doc, text: str):
    if not text or not text.strip():
        return
    html = md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.contents:
        if isinstance(el, NavigableString):
            if el.strip():
                doc.add_paragraph(el.strip())
            continue
        _render_block(doc, el)


def _add_chart_fallback_text(doc, chart_data: Optional[dict]):
    chart_data = chart_data or {}
    title = chart_data.get("title") or "Chart"
    para = doc.add_paragraph()
    para.add_run(title).bold = True
    takeaway = chart_data.get("takeaway")
    doc.add_paragraph(takeaway if takeaway else "[Chart could not be rendered]")


def _add_cover(doc, title: str, brand_name: Optional[str], agent_name: Optional[str]):
    """
    Mirrors the PDF's cover header (frontend/src/utils/pdfExport.ts): wordmark +
    tagline on the left, generated-date on the right, then an accent-colored
    "{AGENT} REPORT" label, the title, and the "Prepared for ..." line.
    """
    date_str = datetime.now().strftime("%B %d, %Y")

    # Wordmark/tagline (left) + Generated Date (right) — a borderless 1x2 table
    # gives the same left/right split the PDF's flex header uses.
    header_table = doc.add_table(rows=1, cols=2)
    _remove_table_borders(header_table)
    left_cell, right_cell = header_table.rows[0].cells

    wordmark_p = left_cell.paragraphs[0]
    wordmark_run = wordmark_p.add_run("StratAI")
    wordmark_run.font.name = DOC_FONT
    wordmark_run.font.size = Pt(15)
    wordmark_run.bold = True
    wordmark_run.font.color.rgb = BRAND_CHARCOAL_DARK

    tagline_p = left_cell.add_paragraph()
    tagline_run = tagline_p.add_run("STRATEGIC MARKET INTELLIGENCE")
    tagline_run.font.name = DOC_FONT
    tagline_run.font.size = Pt(9)
    tagline_run.bold = True
    tagline_run.font.color.rgb = BRAND_GOLD

    right_cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    label_run = right_cell.paragraphs[0].add_run("GENERATED DATE")
    label_run.font.name = DOC_FONT
    label_run.font.size = Pt(8)
    label_run.bold = True
    label_run.font.color.rgb = BRAND_MUTED_GRAY

    date_p = right_cell.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    date_run = date_p.add_run(date_str)
    date_run.font.name = DOC_FONT
    date_run.font.size = Pt(10)
    date_run.bold = True
    date_run.font.color.rgb = BRAND_CHARCOAL

    # Divider line under the header, like the PDF's 2px border-bottom.
    divider = doc.add_paragraph()
    divider_fmt = divider.paragraph_format
    divider_fmt.space_before = Pt(6)
    divider_fmt.space_after = Pt(12)
    pPr = divider._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), BRAND_BORDER_HEX)
    pBdr.append(bottom)
    pPr.append(pBdr)

    # "{AGENT} REPORT" pill badge — a 1-cell borderless table with accent
    # shading, matching the PDF's rounded pill (python-docx has no border-radius).
    badge_text = f"{agent_name.upper()} REPORT" if agent_name else "EXECUTIVE STRATEGY DOCUMENT"
    badge_table = doc.add_table(rows=1, cols=1)
    _remove_table_borders(badge_table)
    badge_cell = badge_table.rows[0].cells[0]
    badge_cell.width = Inches(2.6)
    _set_cell_shading(badge_cell, BRAND_BADGE_BG_HEX)
    badge_run = badge_cell.paragraphs[0].add_run(badge_text)
    badge_run.font.name = DOC_FONT
    badge_run.font.size = Pt(9)
    badge_run.bold = True
    badge_run.font.color.rgb = BRAND_AMBER

    doc.add_paragraph()

    # Title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_after = Pt(6)
    title_run = title_p.add_run(title or "Strategic Intelligence Report")
    title_run.font.name = DOC_FONT
    title_run.font.size = Pt(22)
    title_run.bold = True
    title_run.font.color.rgb = BRAND_CHARCOAL

    # "Prepared for {brand} • Powered by StratAI Multi-Agent Strategy Engine"
    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(18)
    prefix_run = meta_p.add_run("Prepared for ")
    prefix_run.font.name = DOC_FONT
    prefix_run.font.size = Pt(10.5)
    prefix_run.font.color.rgb = BRAND_GRAY

    brand_run = meta_p.add_run(brand_name or "StratAI Intelligence")
    brand_run.font.name = DOC_FONT
    brand_run.font.size = Pt(10.5)
    brand_run.bold = True
    brand_run.font.color.rgb = BRAND_CHARCOAL

    suffix_run = meta_p.add_run(" • Powered by StratAI Multi-Agent Strategy Engine")
    suffix_run.font.name = DOC_FONT
    suffix_run.font.size = Pt(10.5)
    suffix_run.font.color.rgb = BRAND_GRAY


def _set_default_fonts(doc):
    """Word-safe sans-serif body/heading fonts in brand colors (not Word's default blue)."""
    normal = doc.styles["Normal"]
    normal.font.name = DOC_FONT
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = BRAND_CHARCOAL

    for level in range(1, 5):
        try:
            heading_style = doc.styles[f"Heading {level}"]
        except KeyError:
            continue
        heading_style.font.name = DOC_FONT
        heading_style.font.bold = True
        heading_style.font.color.rgb = BRAND_CHARCOAL_DARK

    try:
        list_bullet = doc.styles["List Bullet"]
        list_bullet.font.name = DOC_FONT
        list_bullet.font.color.rgb = BRAND_CHARCOAL
    except KeyError:
        pass
    try:
        list_number = doc.styles["List Number"]
        list_number.font.name = DOC_FONT
        list_number.font.color.rgb = BRAND_CHARCOAL
    except KeyError:
        pass


def _add_footer(doc):
    """'Confidential & Proprietary • Generated by StratAI' + 'Page X of Y', matching the PDF footer."""
    section = doc.sections[0]
    footer_p = section.footer.paragraphs[0]
    footer_p.text = ""

    tab_stops = footer_p.paragraph_format.tab_stops
    usable_width = section.page_width - section.left_margin - section.right_margin
    tab_stops.add_tab_stop(usable_width, WD_TAB_ALIGNMENT.RIGHT)

    left_run = footer_p.add_run("Confidential & Proprietary • Generated by StratAI")
    left_run.font.name = DOC_FONT
    left_run.font.size = Pt(8)
    left_run.font.color.rgb = BRAND_FOOTER_GRAY

    footer_p.add_run("\t")

    page_prefix_run = footer_p.add_run("Page ")
    page_prefix_run.font.name = DOC_FONT
    page_prefix_run.font.size = Pt(8)
    page_prefix_run.font.color.rgb = BRAND_FOOTER_GRAY

    page_field_run = _add_field(footer_p, "PAGE")
    page_field_run.font.name = DOC_FONT
    page_field_run.font.size = Pt(8)
    page_field_run.font.color.rgb = BRAND_FOOTER_GRAY

    of_run = footer_p.add_run(" of ")
    of_run.font.name = DOC_FONT
    of_run.font.size = Pt(8)
    of_run.font.color.rgb = BRAND_FOOTER_GRAY

    numpages_field_run = _add_field(footer_p, "NUMPAGES")
    numpages_field_run.font.name = DOC_FONT
    numpages_field_run.font.size = Pt(8)
    numpages_field_run.font.color.rgb = BRAND_FOOTER_GRAY


def _split_segments(content: str) -> List[Dict[str, str]]:
    segments: List[Dict[str, str]] = []
    last_end = 0
    for m in _RECHARTS_FENCE_RE.finditer(content or ""):
        if m.start() > last_end:
            segments.append({"type": "text", "text": content[last_end:m.start()]})
        segments.append({"type": "chart", "raw": m.group(1).strip()})
        last_end = m.end()
    if last_end < len(content or ""):
        segments.append({"type": "text", "text": content[last_end:]})
    return segments


async def _resolve_export_content(
    db,
    report_id: str,
    legacy_content: str,
    content_override: Optional[str],
) -> str:
    """
    Priority order for what markdown gets rendered into the DOCX:
      a. content_override, when given explicitly (frontend sent finalized section content).
      b. the visible, ordered sections for report_id reassembled via
         section_service.get_finalized_content, when sections exist for it.
      c. legacy_content (the report's raw, immutable content) — reports that were
         never parsed into sections.
    """
    if content_override is not None:
        return content_override

    from backend.services import section_service

    sections = await section_service.get_sections(db, report_id)
    if sections:
        return await section_service.get_finalized_content(db, report_id)

    return legacy_content


async def markdown_to_docx(
    db,
    report_id: str,
    content: str,
    title: str,
    brand_name: Optional[str] = None,
    agent_name: Optional[str] = None,
    content_override: Optional[str] = None,
) -> bytes:
    resolved_content = await _resolve_export_content(db, report_id, content, content_override)

    doc = Document()
    _set_default_fonts(doc)
    _add_footer(doc)
    _add_cover(doc, title, brand_name, agent_name)

    for seg in _split_segments(resolved_content or ""):
        if seg["type"] == "text":
            _render_markdown_text(doc, seg["text"])
            continue

        chart_data = None
        try:
            chart_data = json.loads(seg["raw"])
        except Exception:
            chart_data = None

        image_bytes = render_chart_image(chart_data) if isinstance(chart_data, dict) else None
        if image_bytes:
            try:
                doc.add_picture(io.BytesIO(image_bytes), width=Inches(6.0))
                takeaway = (chart_data or {}).get("takeaway")
                if takeaway:
                    doc.add_paragraph().add_run(takeaway).italic = True
                continue
            except Exception as e:
                logger.warning(f"[export_service] add_picture failed, falling back to text: {e}")

        _add_chart_fallback_text(doc, chart_data)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
