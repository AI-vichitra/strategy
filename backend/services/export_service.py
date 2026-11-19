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
from typing import Optional, List, Dict

import markdown as md
from bs4 import BeautifulSoup, NavigableString

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_TAB_ALIGNMENT, WD_ALIGN_PARAGRAPH

from backend.utils.chart_renderer import render_chart_image
from backend.services.brand_theme import (
    _resolve_theme,
    _load_logo_asset,
    logo_fit_dimensions,
    _is_lead_in_label,
    _darken,
)

logger = logging.getLogger(__name__)

_RECHARTS_FENCE_RE = re.compile(r"```recharts[ \t]*\r?\n(.*?)```", re.DOTALL)
# Tolerant of trailing spaces; matches the same markdown table-separator row
# shape pptx_service.py's own (regex-based) parser recognizes.
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")

# ─────────────────────────────────────────────────────────────────────────────
# Brand tokens — the NEUTRAL ones (StratAI's own wordmark, muted labels,
# borders) stay fixed; headings/cover title/badge/table header instead pull
# from the resolved brand theme (see brand_theme.py) so the DOCX echoes the
# same client colors as the PPTX.
# ─────────────────────────────────────────────────────────────────────────────
DOC_FONT = "Calibri"

BRAND_CHARCOAL = RGBColor(0x1A, 0x1A, 0x1A)       # primary text
BRAND_CHARCOAL_DARK = RGBColor(0x2D, 0x2A, 0x26)  # StratAI's own wordmark (not client-branded)
BRAND_GRAY = RGBColor(0x57, 0x53, 0x4E)           # "Prepared for ..." line
BRAND_MUTED_GRAY = RGBColor(0x78, 0x71, 0x6C)     # "GENERATED DATE" label
BRAND_FOOTER_GRAY = RGBColor(0x96, 0x91, 0x8C)    # footer text (rgb(150,145,140))

BRAND_BORDER_HEX = "E8E4DC"


def _theme_rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


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


# ─────────────────────────────────────────────────────────────────────────────
# Markdown → docx elements
# ─────────────────────────────────────────────────────────────────────────────
def _add_inline_runs(paragraph, el, bold=None, italic=False, code=False):
    """`bold=None` (the default) leaves a run's bold unset so it inherits
    from its paragraph style — important for headings, whose style is bold;
    explicitly passing True/False (as the bullet renderer does) overrides
    that inheritance for genuine inline/label emphasis."""
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


def _render_list_item(doc, li_el, style: str):
    """Renders one <li> as a paragraph in the given Word list style (List
    Bullet / List Number). Body text is regular weight by default (color
    comes from the style itself, already dark — see _set_default_fonts);
    only a genuine lead-in label (text ending in ":", e.g. "Decision
    Drivers:") renders bold.

    The common LLM habit of wrapping an ENTIRE bullet sentence in
    **markdown** produces a single <strong> spanning the whole <li> — left
    alone, _add_inline_runs would honor that nested <strong> as bold
    regardless of the base `bold` passed in, which is why every bullet used
    to come out bold. When that happens and the bullet is NOT a real label,
    the wrapping <strong> is unwrapped (rendered as if it weren't there) so
    the sentence reads as regular text; genuine partial inline bold
    ("a **key** finding") is unaffected either way."""
    full_text = li_el.get_text().strip()
    is_label = _is_lead_in_label(full_text)

    children = [c for c in li_el.children if not (isinstance(c, NavigableString) and not str(c).strip())]
    whole_wrapped = (
        len(children) == 1
        and not isinstance(children[0], NavigableString)
        and children[0].name in ("strong", "b")
        and children[0].get_text().strip() == full_text
    )

    para = doc.add_paragraph(style=style)
    if is_label:
        _add_inline_runs(para, li_el, bold=True)
    elif whole_wrapped:
        _add_inline_runs(para, children[0], bold=False)
    else:
        _add_inline_runs(para, li_el, bold=False)
    return para


def _render_table(doc, table_el, theme: dict):
    rows = table_el.find_all("tr")
    if not rows:
        return
    all_cells = [row.find_all(["th", "td"]) for row in rows]
    ncols = max((len(c) for c in all_cells), default=0)
    if ncols == 0:
        return

    # No built-in style (those default to heavy, blue-tinted banding) — borders
    # and header/row shading are set explicitly instead: brand-primary header
    # (white text) + alternating brand-light-tint body rows, matching the PPTX.
    table = doc.add_table(rows=0, cols=ncols)

    for r_idx, (row, cells) in enumerate(zip(rows, all_cells)):
        is_header = any(c.name == "th" for c in cells)
        docx_row = table.add_row()
        for col_idx in range(ncols):
            cell_text = cells[col_idx].get_text().strip() if col_idx < len(cells) else ""
            cell = docx_row.cells[col_idx]
            _set_cell_borders(cell)
            cell.paragraphs[0].paragraph_format.space_before = Pt(3)
            cell.paragraphs[0].paragraph_format.space_after = Pt(3)
            run = cell.paragraphs[0].add_run(cell_text)
            run.font.name = DOC_FONT
            run.font.size = Pt(10)
            if is_header:
                run.bold = True
                run.font.color.rgb = _theme_rgb(theme["text_light"])
                _set_cell_shading(cell, theme["primary"])
            else:
                run.font.color.rgb = BRAND_CHARCOAL
                if r_idx % 2 == 0:
                    _set_cell_shading(cell, theme["bg_light"])
    return table


def _render_block(doc, el, theme: dict):
    name = getattr(el, "name", None)

    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = min(int(name[1]), 4)
        heading = doc.add_heading("", level=level)
        _add_inline_runs(heading, el)
        if level == 3:
            # Thin accent-colored bottom border under each H3 section heading.
            pPr = heading._p.get_or_add_pPr()
            pBdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "8")
            bottom.set(qn("w:space"), "4")
            bottom.set(qn("w:color"), theme["accent"])
            pBdr.append(bottom)
            pPr.append(pBdr)
    elif name == "p":
        para = doc.add_paragraph()
        _add_inline_runs(para, el)
    elif name in ("ul", "ol"):
        style = "List Bullet" if name == "ul" else "List Number"
        for li in el.find_all("li", recursive=False):
            nested_lists = li.find_all(["ul", "ol"], recursive=False)
            for nl in nested_lists:
                nl.extract()
            _render_list_item(doc, li, style)
            for nl in nested_lists:
                _render_block(doc, nl, theme)
    elif name == "table":
        _render_table(doc, el, theme)
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


def _ensure_blank_line_before_tables(text: str) -> str:
    """python-markdown's `tables` extension only recognizes a pipe table when
    it starts its own block — i.e. is preceded by a blank line. When a table
    immediately follows a non-blank line with no blank line between them
    (e.g. a "Key Players:" lead-in line directly above the header row), the
    label and the table get swallowed into ONE paragraph block, and since a
    plain paragraph never gets pipe-table parsing, the raw `| ... |` syntax
    leaks out as literal text instead of becoming a real table. This inserts
    the missing blank line so a table is always recognized as its own block,
    regardless of what precedes it."""
    lines = (text or "").splitlines()
    out: List[str] = []
    n = len(lines)
    for i, line in enumerate(lines):
        is_table_header = (
            "|" in line.strip()
            and i + 1 < n
            and bool(_TABLE_SEP_RE.match(lines[i + 1]))
        )
        if is_table_header and out and out[-1].strip() != "":
            out.append("")
        out.append(line)
    return "\n".join(out)


def _render_markdown_text(doc, text: str, theme: dict):
    if not text or not text.strip():
        return
    text = _ensure_blank_line_before_tables(text)
    html = md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.contents:
        if isinstance(el, NavigableString):
            if el.strip():
                doc.add_paragraph(el.strip())
            continue
        _render_block(doc, el, theme)


def _add_chart_fallback_text(doc, chart_data: Optional[dict]):
    chart_data = chart_data or {}
    title = chart_data.get("title") or "Chart"
    para = doc.add_paragraph()
    para.add_run(title).bold = True
    takeaway = chart_data.get("takeaway")
    doc.add_paragraph(takeaway if takeaway else "[Chart could not be rendered]")


def _add_cover(doc, title: str, brand_name: Optional[str], agent_name: Optional[str],
                theme: dict, date: Optional[str] = None, logo_asset: Optional[dict] = None):
    """
    Branded cover page — the first page, followed by a page break so the
    report body always starts on page 2. With a client brand_kit logo, it
    takes the top-left spot (where the StratAI wordmark normally sits) —
    "Powered by StratAI" still appears in the "Prepared for ..." line below.
    Title, badge, and accent rule use the resolved brand theme so the DOCX
    echoes the same colors as the PPTX.
    """
    date_str = date or datetime.now().strftime("%B %d, %Y")

    # Logo (or StratAI wordmark/tagline) on the left, generated-date on the
    # right — a borderless 1x2 table gives the same left/right split the
    # PDF's flex header uses.
    header_table = doc.add_table(rows=1, cols=2)
    _remove_table_borders(header_table)
    left_cell, right_cell = header_table.rows[0].cells

    if logo_asset:
        width_in, _ = logo_fit_dimensions(logo_asset, max_height_in=1.5, max_width_in=3.5)
        logo_run = left_cell.paragraphs[0].add_run()
        logo_run.add_picture(io.BytesIO(logo_asset["bytes"]), width=Inches(width_in))
    else:
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
        tagline_run.font.color.rgb = _theme_rgb(theme["accent"])

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

    # "{AGENT} REPORT" pill badge — brand-accent shaded, matching the PPTX cover.
    badge_text = f"{agent_name.upper()} REPORT" if agent_name else "EXECUTIVE STRATEGY DOCUMENT"
    badge_table = doc.add_table(rows=1, cols=1)
    _remove_table_borders(badge_table)
    badge_cell = badge_table.rows[0].cells[0]
    badge_cell.width = Inches(2.6)
    _set_cell_shading(badge_cell, theme["accent"])
    badge_run = badge_cell.paragraphs[0].add_run(badge_text)
    badge_run.font.name = DOC_FONT
    badge_run.font.size = Pt(9)
    badge_run.bold = True
    badge_run.font.color.rgb = _theme_rgb(theme["text_light"])

    # Accent rule in the brand accent color, between the badge and the title.
    accent_rule = doc.add_paragraph()
    accent_rule.paragraph_format.space_before = Pt(10)
    accent_rule.paragraph_format.space_after = Pt(10)
    rule_pPr = accent_rule._p.get_or_add_pPr()
    rule_pBdr = OxmlElement("w:pBdr")
    rule_bottom = OxmlElement("w:bottom")
    rule_bottom.set(qn("w:val"), "single")
    rule_bottom.set(qn("w:sz"), "24")
    rule_bottom.set(qn("w:space"), "1")
    rule_bottom.set(qn("w:color"), theme["accent"])
    rule_pBdr.append(rule_bottom)
    rule_pPr.append(rule_pBdr)

    # Title — brand primary color.
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_after = Pt(6)
    title_run = title_p.add_run(title or "Strategic Intelligence Report")
    title_run.font.name = DOC_FONT
    title_run.font.size = Pt(24)
    title_run.bold = True
    title_run.font.color.rgb = _theme_rgb(theme["primary"])

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

    # Page break — the report body always starts on page 2.
    doc.add_page_break()


_HEADING_SIZES_PT = {1: 22, 2: 20, 3: 18, 4: 14}


def _set_default_fonts(doc, theme: dict):
    """Word-safe sans-serif body/heading fonts, themed to the resolved brand
    colors: H3 (section) in brand primary at 18pt, H4 (subsection) in a
    darker tint of primary at 14pt — same visual family as the PPTX."""
    normal = doc.styles["Normal"]
    normal.font.name = DOC_FONT
    normal.font.size = Pt(11)
    normal.font.color.rgb = BRAND_CHARCOAL

    heading_color = {
        1: theme["primary"],
        2: theme["primary"],
        3: theme["primary"],
        4: _darken(theme["primary"], 0.2),
    }
    for level in range(1, 5):
        try:
            heading_style = doc.styles[f"Heading {level}"]
        except KeyError:
            continue
        heading_style.font.name = DOC_FONT
        heading_style.font.bold = True
        heading_style.font.size = Pt(_HEADING_SIZES_PT[level])
        heading_style.font.color.rgb = _theme_rgb(heading_color[level])

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
    brand_kit: Optional[dict] = None,
    extracted_palette: Optional[dict] = None,
    logo_data: Optional[bytes] = None,
    logo_mime: Optional[str] = None,
) -> bytes:
    """
    `brand_kit` ({"logo_url": ..., "colors": {...}}) and `extracted_palette`
    ({"primary"/"secondary"/"accent"}) mirror generate_pptx's inputs — same
    precedence (manual brand_kit colors > extracted_palette > report-type
    theme, via _resolve_theme) so the DOCX and PPTX always theme identically.
    The logo comes from `logo_data` (Project.logo_data, the DB source of
    truth) when given, else falls back to brand_kit["logo_url"] on disk —
    same as the PPTX.
    """
    resolved_content = await _resolve_export_content(db, report_id, content, content_override)
    theme = _resolve_theme(brand_kit, extracted_palette, agent_name or "default")
    logo_asset = _load_logo_asset(brand_kit, logo_data=logo_data, logo_mime=logo_mime)

    doc = Document()
    section = doc.sections[0]
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)

    _set_default_fonts(doc, theme)
    _add_footer(doc)
    _add_cover(doc, title, brand_name, agent_name, theme, logo_asset=logo_asset)

    for seg in _split_segments(resolved_content or ""):
        if seg["type"] == "text":
            _render_markdown_text(doc, seg["text"], theme)
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
