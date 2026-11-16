"""
PPTX Export Service — server-side PowerPoint generation
=========================================================
Mirrors export_service.py's architecture: markdown+recharts content in,
branded file bytes out. Charts are re-rendered from their underlying JSON
via the same shared matplotlib renderer DOCX export uses
(backend/utils/chart_renderer.py), so a chart looks identical whether it
ends up in the DOCX, the PPTX, or on-screen.

Block-level markdown (bullets/paragraphs/tables) is parsed directly off the
raw markdown text (not via a markdown→HTML→BeautifulSoup round trip) so
inline formatting markers (**bold**, *italic*) survive all the way to the
point where they're split into real bold/italic runs — see _add_inline_runs.

Slide layout: cover → TOC → one dark "section divider" slide per H3 section,
then that section's own content slides (bullets/paragraphs/tables/charts) →
closing. H4 subsections do NOT get their own divider slide (that produced
dozens of near-empty slides) — an H4 heading becomes the *title* of the
content slide(s) that follow it instead. Sparse subsections (fewer than 3
bullets or fewer than 50 words, and no table/chart) are merged onto a
neighboring subsection's slide rather than getting a slide of their own.
"""

import io
import itertools
import json
import math
import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

from backend.utils.chart_renderer import render_chart_image
from backend.services.export_service import _split_segments

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Brand theming / logo loading — shared with export_service.py (DOCX) via
# brand_theme.py, so both exports agree on the same colors and logo. Names
# are re-exported here unchanged so existing call sites/tests importing them
# from pptx_service keep working.
# ─────────────────────────────────────────────────────────────────────────────
from backend.services.brand_theme import (  # noqa: E402
    REPORT_THEMES,
    _get_theme,
    _hex_to_rgb,
    _rgb_to_hex,
    _luminance,
    _darken,
    _lighten,
    _readable_text,
    _normalize_brand_hex,
    _build_theme_from_colors,
    _theme_from_brand_kit,
    _resolve_theme,
    _resolve_logo_path,
    _load_logo_asset,
    _is_lead_in_label,
    logo_fit_dimensions,
)


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def _logo_box_size(asset: Dict[str, Any], max_height_in: float, max_width_in: float):
    """Scales a logo to fit within a max height/width box, preserving aspect
    ratio. Thin pptx-specific wrapper around the shared float-returning
    brand_theme.logo_fit_dimensions, wrapping the result in python-pptx's
    own Inches (a different class from python-docx's)."""
    width_in, height_in = logo_fit_dimensions(asset, max_height_in, max_width_in)
    return Inches(width_in), Inches(height_in)


# ─────────────────────────────────────────────────────────────────────────────
# Design system constants (sizes/dimensions — colors come from the theme)
# ─────────────────────────────────────────────────────────────────────────────
SLIDE_FONT = "Calibri"

# Slide title (H4 content heading): 26pt bold. Section divider title: 40pt
# (set directly where used — _add_title_bar / _create_section_title_slide).
TITLE_FONT_SIZE = Pt(26)
SUBTITLE_FONT_SIZE = Pt(20)
BODY_FONT_SIZE = Pt(15)              # paragraphs + top-level (level 0) bullets
SUBSECTION_LABEL_FONT_SIZE = Pt(16)  # merged-subsection lead-in title (bold, dark)
SUB_BULLET_FONT_SIZE = Pt(13.5)      # level 1 bullets (was SUB_BODY_FONT_SIZE = 12pt)
SUBSUB_BULLET_FONT_SIZE = Pt(12.5)   # level 2+ bullets (new tier)
TABLE_HEADER_FONT_SIZE = Pt(11)
TABLE_BODY_FONT_SIZE = Pt(10.5)
CAPTION_FONT_SIZE = Pt(12)
SLIDE_NUMBER_FONT_SIZE = Pt(9)

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# ─────────────────────────────────────────────────────────────────────────────
# Content-area geometry — a plain python-pptx textbox defaults to
# MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT (the box GROWS to fit its text), which is
# exactly what let dense content run past the slide number. Content/heading
# boxes are fixed-size (MSO_AUTO_SIZE.NONE) instead, and the real fix is
# making sure content is split finely enough to always fit this fixed area:
#   heading bar: top 0.35in, height TITLE_BAR_HEIGHT_IN -> bottom ~1.05in
#   body:        top CONTENT_BODY_TOP_IN, height CONTENT_BODY_HEIGHT_IN
#                -> bottom ~6.6in, clearing the slide number (top ~7.05in)
# CONTENT_SAFE_BOTTOM_IN (6.7in) is the hard floor no content box may cross.
# ─────────────────────────────────────────────────────────────────────────────
TITLE_BAR_HEIGHT_IN = 0.7
CONTENT_BODY_TOP_IN = 1.35
CONTENT_BODY_HEIGHT_IN = 5.25
CONTENT_SAFE_BOTTOM_IN = 6.7

# Line-fit estimate used to decide slide splits (see _estimate_item_lines):
# ~98 chars/line at 15pt in the ~11.7in-wide body, ~0.3in per rendered line
# (text + spacing) -> a slide's fixed body area fits ~17 lines before text
# would have to shrink or overflow.
CONTENT_CHARS_PER_LINE = 98
CONTENT_LINE_HEIGHT_IN = 0.3
MAX_LINES_PER_SLIDE = int(CONTENT_BODY_HEIGHT_IN / CONTENT_LINE_HEIGHT_IN)

# Raised from 6 to 9 (companion bump alongside the word-budget raise below) —
# a cohesive 2-group subsection (e.g. two lead-in-label bullets with 2-3
# sub-bullets each) can land at 6-8 flat items; capping at the old 6 would
# still force a mid-subsection split on item count alone even once the word
# budget allows it to fit on one slide.
MAX_ITEMS_PER_SLIDE = 9
# Per-CLUSTER budget (a level-0 bullet + its own children, or one paragraph):
# raised from 110 to ~150 — this is the threshold that decides whether a
# single cluster is too big to fit a slide ALONE and must be force-split at
# a child boundary (see _split_oversized_cluster). It is deliberately NOT
# the same number as the combined per-slide ceiling below.
MAX_WORDS_PER_SLIDE = 150
# Multi-cluster packing ceiling: several already-fitting clusters (each
# under MAX_WORDS_PER_SLIDE) keep combining onto the same slide up to this
# total. Set well above MAX_WORDS_PER_SLIDE so a normal cohesive subsection
# — e.g. "Decision Drivers:" + "Channel Preferences:", each with their own
# sub-bullets, ~250-300 words combined — still renders on ONE slide instead
# of splitting between the two sibling groups.
MAX_COMBINED_SLIDE_WORDS = 260
MAX_WORDS_PER_PARAGRAPH = 120
MIN_BULLETS_NOT_SPARSE = 3
MIN_WORDS_NOT_SPARSE = 50

# Hanging-indent step per nesting level, and the max bullet level the
# markdown indent heuristic resolves to (anything deeper collapses into the
# deepest tier's styling — level 2+ all render at SUBSUB_BULLET_FONT_SIZE).
BULLET_INDENT_STEP_IN = 0.3
MAX_BULLET_LEVEL = 2

# A trailing text block after a table/chart is "short" enough to merge onto
# the same slide when it's under both of these.
SHORT_TRAILING_MAX_WORDS = 40
SHORT_TRAILING_MAX_BULLETS = 3


def _bullet_font_size(level: int):
    """Level 0 = top-level bullet (15pt), 1 = sub-bullet (13.5pt), 2+ = sub-sub (12.5pt)."""
    if level <= 0:
        return BODY_FONT_SIZE
    if level == 1:
        return SUB_BULLET_FONT_SIZE
    return SUBSUB_BULLET_FONT_SIZE


_H3_SPLIT_RE = re.compile(r"(?=^###[ \t]+.+$)", re.MULTILINE)
_H4_SPLIT_RE = re.compile(r"(?=^####[ \t]+.+$)", re.MULTILINE)
_HEADING_LINE_RE = re.compile(r"^(#{3,4})[ \t]+(.+)$", re.MULTILINE)
_BULLET_LINE_RE = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
# A line that is ONLY a markdown horizontal rule (---, ***, ___) — discarded
# entirely, never becomes a text block or a slide.
_HR_LINE_RE = re.compile(r"^[\-\*_]{3,}$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# ─────────────────────────────────────────────────────────────────────────────
# Low-level slide/text helpers
# ─────────────────────────────────────────────────────────────────────────────
def _new_slide(prs: Presentation, background: RGBColor):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # "Blank" layout
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = background
    return slide


def _add_textbox(slide, left, top, width, height, anchor=None):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    if anchor is not None:
        tf.vertical_anchor = anchor
    return box, tf


def _normalize_size(size):
    return size if hasattr(size, "emu") else Pt(size)


def _set_paragraph_indent(paragraph, marL, indent):
    """Sets a left margin + hanging first-line indent on a paragraph (EMU
    Length values) so bullet text gets a clear, consistent left indent —
    python-pptx has no high-level property for this, so it's set directly
    on the <a:pPr> element."""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", str(int(marL)))
    pPr.set("indent", str(int(indent)))


def _apply_text_formatting(paragraph, text: str, theme: dict, bold: bool = False, italic: bool = False,
                            font_size=14, color: Optional[str] = None):
    """Adds one plain text run to `paragraph` with the given formatting (no
    markdown parsing — see _add_inline_runs for that)."""
    run = paragraph.add_run()
    run.text = text
    run.font.name = SLIDE_FONT
    run.font.size = _normalize_size(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color or theme["text_dark"])
    return run


_INLINE_MD_RE = re.compile(r"(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)")


def _add_inline_runs(paragraph, text: str, theme: dict, base_size=Pt(14), base_bold: bool = False,
                      base_italic: bool = False, color: Optional[str] = None):
    """Parses inline markdown (**bold**, *italic*, ***bold italic***) out of a
    RAW markdown string and adds one properly formatted run per segment. This
    is the single function used everywhere text reaches a slide — titles,
    bullets, body text, table cells — so bold/italic markers are never left
    showing as literal asterisks."""
    parts = _INLINE_MD_RE.split(text or "")
    for part in parts:
        if not part:
            continue
        if part.startswith("***") and part.endswith("***") and len(part) >= 7:
            _apply_text_formatting(paragraph, part[3:-3], theme, bold=True, italic=True, font_size=base_size, color=color)
        elif part.startswith("**") and part.endswith("**") and len(part) >= 5:
            _apply_text_formatting(paragraph, part[2:-2], theme, bold=True, italic=False, font_size=base_size, color=color)
        elif part.startswith("*") and part.endswith("*") and len(part) >= 3:
            _apply_text_formatting(paragraph, part[1:-1], theme, bold=False, italic=True, font_size=base_size, color=color)
        else:
            _apply_text_formatting(paragraph, part, theme, bold=base_bold, italic=base_italic, font_size=base_size, color=color)


def _add_title_bar(slide, text: str, theme: dict, subtitle: Optional[str] = None):
    """Thin theme-primary accent bar + heading, used at the top of every
    content/table/chart/TOC slide."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.18), SLIDE_HEIGHT)
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme["primary"])
    bar.line.fill.background()

    _, tf = _add_textbox(slide, Inches(0.6), Inches(0.35), Inches(12.0), Inches(TITLE_BAR_HEIGHT_IN))
    tf.auto_size = MSO_AUTO_SIZE.NONE
    _add_inline_runs(tf.paragraphs[0], text, theme, base_size=TITLE_FONT_SIZE, base_bold=True, color=theme["primary"])

    if subtitle:
        _, sub_tf = _add_textbox(slide, Inches(0.6), Inches(1.0), Inches(12.0), Inches(0.5))
        sub_tf.auto_size = MSO_AUTO_SIZE.NONE
        _add_inline_runs(sub_tf.paragraphs[0], subtitle, theme, base_size=Pt(16), color=theme["accent"])


def _add_slide_number(slide, number: int, theme: dict):
    _, tf = _add_textbox(slide, SLIDE_WIDTH - Inches(1.0), SLIDE_HEIGHT - Inches(0.45), Inches(0.8), Inches(0.35))
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _apply_text_formatting(tf.paragraphs[0], str(number), theme, font_size=SLIDE_NUMBER_FONT_SIZE, color=theme["text_muted"])


# ─────────────────────────────────────────────────────────────────────────────
# Cover / TOC / section divider / closing slides
# ─────────────────────────────────────────────────────────────────────────────
def _create_cover_slide(prs: Presentation, title: str, brand_name: Optional[str], agent_name: Optional[str],
                         theme: dict, date: Optional[str] = None, logo_asset: Optional[Dict[str, Any]] = None):
    """Branded cover slide — dark themed background. With a client brand_kit
    logo, it takes the top-left spot (where the StratAI wordmark normally
    sits) — "Powered by StratAI" still appears in the footer meta line below.
    Without one, falls back to the original text-only wordmark/tagline."""
    date_str = date or datetime.now().strftime("%B %d, %Y")
    slide = _new_slide(prs, _rgb(theme["bg_dark"]))

    if logo_asset:
        width, height = _logo_box_size(logo_asset, max_height_in=1.2, max_width_in=4.0)
        slide.shapes.add_picture(io.BytesIO(logo_asset["bytes"]), Inches(0.6), Inches(0.4), width=width, height=height)
    else:
        _, wordmark_tf = _add_textbox(slide, Inches(0.6), Inches(0.5), Inches(4), Inches(0.6))
        _apply_text_formatting(wordmark_tf.paragraphs[0], "StratAI", theme, bold=True, font_size=18, color=theme["text_light"])

        _, tagline_tf = _add_textbox(slide, Inches(0.6), Inches(1.0), Inches(5), Inches(0.4))
        _apply_text_formatting(tagline_tf.paragraphs[0], "STRATEGIC MARKET INTELLIGENCE", theme, bold=True, font_size=11, color=theme["accent"])

    _, date_tf = _add_textbox(slide, Inches(9.0), Inches(0.5), Inches(3.7), Inches(0.6))
    date_tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _apply_text_formatting(date_tf.paragraphs[0], date_str, theme, bold=True, font_size=11, color=theme["secondary"])

    badge_text = f"{agent_name.upper()} REPORT" if agent_name else "EXECUTIVE STRATEGY DOCUMENT"
    badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.7), Inches(3.8), Inches(0.5))
    badge.fill.solid()
    badge.fill.fore_color.rgb = _rgb(theme["accent"])
    badge.line.fill.background()
    badge.text_frame.word_wrap = True
    badge.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    _apply_text_formatting(badge.text_frame.paragraphs[0], badge_text, theme, bold=True, font_size=11, color=theme["text_light"])

    # Subtle full-width accent bar ~40% down the slide.
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(3.0), SLIDE_WIDTH, Pt(4))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme["accent"])
    bar.line.fill.background()

    _, title_tf = _add_textbox(slide, Inches(0.6), Inches(3.3), Inches(11.5), Inches(1.6))
    _apply_text_formatting(title_tf.paragraphs[0], title or "Strategic Intelligence Report", theme, bold=True, font_size=32, color=theme["text_light"])

    _, meta_tf = _add_textbox(slide, Inches(0.6), Inches(4.9), Inches(11.5), Inches(0.5))
    p = meta_tf.paragraphs[0]
    _apply_text_formatting(p, "Prepared for ", theme, font_size=13, color=theme["secondary"])
    _apply_text_formatting(p, brand_name or "StratAI Intelligence", theme, bold=True, font_size=13, color=theme["text_light"])
    _apply_text_formatting(p, " • Powered by StratAI Multi-Agent Strategy Engine", theme, font_size=13, color=theme["secondary"])

    return slide


def _create_toc_slide(prs: Presentation, sections: List[Dict[str, Any]], theme: dict):
    """Table of contents — one line per H3 section title."""
    slide = _new_slide(prs, _rgb(theme["bg_light"]))
    _add_title_bar(slide, "Table of Contents", theme)

    _, tf = _add_textbox(slide, Inches(1.0), Inches(1.8), Inches(11.3), Inches(5.0))
    first = True
    for idx, section in enumerate(sections, 1):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(10)
        _apply_text_formatting(p, f"{idx:02d}", theme, bold=True, font_size=16, color=theme["primary"])
        _apply_text_formatting(p, "   •   ", theme, bold=True, font_size=16, color=theme["accent"])
        _add_inline_runs(p, section.get("title") or f"Section {idx}", theme, base_size=Pt(16), base_bold=True, color=theme["text_dark"])
    return slide


def _create_section_title_slide(prs: Presentation, section_title: str, theme: dict, index: int,
                                 logo_asset: Optional[Dict[str, Any]] = None):
    """Section divider slide — ONLY for H3 main sections, centered on a dark
    themed background with a numbered label and accent bar. With a client
    brand_kit logo, a small low-prominence mark sits in the bottom-right corner."""
    slide = _new_slide(prs, _rgb(theme["bg_dark"]))

    _, num_tf = _add_textbox(slide, Inches(0), Inches(2.5), SLIDE_WIDTH, Inches(0.5))
    num_tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    _apply_text_formatting(num_tf.paragraphs[0], f"{index:02d}", theme, bold=True, font_size=16, color=theme["accent"])

    _, tf = _add_textbox(slide, Inches(0.6), Inches(3.0), Inches(12.1), Inches(1.4))
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    _add_inline_runs(tf.paragraphs[0], section_title, theme, base_size=Pt(40), base_bold=True, color=theme["text_light"])

    bar_width = Inches(1.6)
    bar_left = (SLIDE_WIDTH - bar_width) // 2
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, bar_left, Inches(4.5), bar_width, Pt(4))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme["accent"])
    bar.line.fill.background()

    if logo_asset:
        width, height = _logo_box_size(logo_asset, max_height_in=0.6, max_width_in=2.0)
        left = SLIDE_WIDTH - width - Inches(0.4)
        top = SLIDE_HEIGHT - height - Inches(0.4)
        slide.shapes.add_picture(io.BytesIO(logo_asset["bytes"]), left, top, width=width, height=height)

    return slide


def _create_closing_slide(prs: Presentation, theme: dict, date: Optional[str] = None):
    date_str = date or datetime.now().strftime("%B %d, %Y")
    slide = _new_slide(prs, _rgb(theme["bg_dark"]))
    _, tf = _add_textbox(slide, Inches(1.0), Inches(3.0), Inches(11.3), Inches(1.5), anchor=MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _apply_text_formatting(p, "Generated by StratAI", theme, bold=True, font_size=26, color=theme["text_light"])

    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    _apply_text_formatting(p2, date_str, theme, font_size=13, color=theme["accent"])
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Content slides: bullets / paragraphs / tables / charts
# ─────────────────────────────────────────────────────────────────────────────
def _estimate_item_lines(text: str) -> int:
    """Wrapped-line estimate for one item's text at body font size in the
    ~11.7in-wide content box (~CONTENT_CHARS_PER_LINE chars/line) — each item
    always starts its own paragraph/line, so this is a per-item ceiling, not
    a shared running total."""
    length = len((text or "").strip())
    return max(1, math.ceil(length / CONTENT_CHARS_PER_LINE))


def _items_estimated_lines(items: List[Dict[str, Any]]) -> int:
    return sum(_estimate_item_lines(item.get("text", "")) for item in items)


def _add_content_slide(prs: Presentation, title: str, items: List[Dict[str, Any]], theme: dict):
    """`items`: [{"bullet": bool, "text": <raw markdown>, "level": int,
    "is_subsection_label": bool}, ...]. Body top sits at CONTENT_BODY_TOP_IN
    (1.35in) so the title box (bottom ~1.05in) has a clear ~0.3in gap before
    the body starts, and the body is a FIXED size (MSO_AUTO_SIZE.NONE) ending
    at CONTENT_BODY_TOP_IN + CONTENT_BODY_HEIGHT_IN (~6.6in) — comfortably
    clear of the slide number at ~7.05in. Callers are expected to have
    already split `items` to fit within MAX_LINES_PER_SLIDE (see
    _pack_clusters_to_slides); TEXT_TO_FIT_SHAPE is only a safety net for the
    rare slide that still estimates over budget, so it shrinks rather than
    overflows.

    Text is always dark + regular weight (theme text_dark) — only the bullet
    MARKER glyph and a standalone lead-in label (merged subsection title) use
    bold/accent; a bullet whose own text is a lead-in label (ends in ":",
    e.g. "Decision Drivers:") is bold but still dark, never colored."""
    slide = _new_slide(prs, _rgb(theme["bg_white"]))
    _add_title_bar(slide, title, theme)

    _, tf = _add_textbox(slide, Inches(0.8), Inches(CONTENT_BODY_TOP_IN), Inches(11.5), Inches(CONTENT_BODY_HEIGHT_IN))
    tf.auto_size = (
        MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        if _items_estimated_lines(items) > MAX_LINES_PER_SLIDE
        else MSO_AUTO_SIZE.NONE
    )
    first = True
    for item in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        level = item.get("level", 0)
        p.level = min(level, 1)  # python-pptx outline level has no visual effect in a plain textbox

        if item.get("is_subsection_label"):
            p.space_after = Pt(10)
            p.line_spacing = 1.2
            _add_inline_runs(p, item.get("text", ""), theme, base_size=SUBSECTION_LABEL_FONT_SIZE,
                              base_bold=True, color=theme["text_dark"])
            continue

        if item.get("bullet"):
            size = _bullet_font_size(level)
            p.space_after = Pt(8)
            p.line_spacing = 1.2
            _set_paragraph_indent(p, Inches(BULLET_INDENT_STEP_IN * (level + 1)), Inches(-0.25))
            # Only the bullet glyph itself gets the accent color — the body
            # text stays theme text_dark, so gold isn't used for whole lines.
            bullet_run = p.add_run()
            bullet_run.text = "•  "
            bullet_run.font.name = SLIDE_FONT
            bullet_run.font.size = size
            bullet_run.font.bold = True
            bullet_run.font.color.rgb = _rgb(theme["accent"])
            text = item.get("text", "")
            _add_inline_runs(p, text, theme, base_size=size, base_bold=_is_lead_in_label(text), color=theme["text_dark"])
        else:
            size = BODY_FONT_SIZE
            p.space_after = Pt(10)
            p.line_spacing = 1.2
            _add_inline_runs(p, item.get("text", ""), theme, base_size=size, color=theme["text_dark"])
    return slide


def _table_height_inches(rows: int) -> float:
    return min(0.5 * rows, 5.1)


def _table_note_top_inches(rows: int) -> float:
    """Where a short trailing note goes when merged onto a table's own slide:
    table top (1.7in, unchanged) + the table's own height + a 0.3in gap."""
    return 1.7 + _table_height_inches(rows) + 0.3


def _add_table_to_slide(slide, table_data: List[List[str]], theme: dict):
    """Native PowerPoint table (not an image): theme-primary header row (white
    text), alternating white / theme bg_light body rows, bold preserved in
    cell text via _add_inline_runs. Table top stays at 1.7in."""
    if not table_data or not table_data[0]:
        return None
    rows = len(table_data)
    cols = len(table_data[0])
    left, top = Inches(0.8), Inches(1.7)
    width, height = Inches(11.7), Inches(_table_height_inches(rows))

    shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = shape.table

    for r, row_data in enumerate(table_data):
        is_header = r == 0
        if is_header:
            bg = theme["primary"]
        else:
            bg = theme["bg_light"] if r % 2 == 0 else "FFFFFF"
        text_color = theme["text_light"] if is_header else theme["text_dark"]
        size = TABLE_HEADER_FONT_SIZE if is_header else TABLE_BODY_FONT_SIZE

        for c in range(cols):
            text = row_data[c] if c < len(row_data) else ""
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(bg)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.1)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            p = cell.text_frame.paragraphs[0]
            _add_inline_runs(p, str(text), theme, base_size=size, base_bold=is_header, color=text_color)
    return table


def _add_chart_image_to_slide(slide, chart_json: Any, theme: dict):
    """Renders recharts-style JSON to a matplotlib image (shared renderer) and
    adds it to `slide`, centered, ~8in wide."""
    data = chart_json
    if isinstance(chart_json, str):
        try:
            data = json.loads(chart_json)
        except Exception:
            data = None

    image_bytes = render_chart_image(data, figsize=(9, 5)) if isinstance(data, dict) else None
    if not image_bytes:
        _, tf = _add_textbox(slide, Inches(2.0), Inches(3.0), Inches(9.3), Inches(1.5))
        title = (data or {}).get("title") if isinstance(data, dict) else None
        _add_inline_runs(tf.paragraphs[0], title or "Chart", theme, base_size=Pt(16), base_bold=True, color=theme["text_dark"])
        takeaway = (data or {}).get("takeaway") if isinstance(data, dict) else None
        p2 = tf.add_paragraph()
        _apply_text_formatting(p2, takeaway or "[Chart could not be rendered]", theme, italic=True, font_size=13, color=theme["text_muted"])
        return None

    pic_width = Inches(8)
    left = (SLIDE_WIDTH - pic_width) // 2
    top = Inches(1.6)
    picture = slide.shapes.add_picture(io.BytesIO(image_bytes), left, top, width=pic_width)

    takeaway = (data or {}).get("takeaway") if isinstance(data, dict) else None
    if takeaway:
        _, tf = _add_textbox(slide, Inches(1.2), Inches(6.7), Inches(10.9), Inches(0.6))
        _add_inline_runs(tf.paragraphs[0], takeaway, theme, base_size=Pt(12), color=theme["text_muted"])
    return picture


def _chart_note_top_inches(chart_json: Any) -> float:
    """Where a short trailing note goes when merged onto a chart's own slide:
    below the rendered image (top 1.6in, unchanged), or below the chart's own
    takeaway caption when it has one, plus a 0.25in gap."""
    bottom = 1.6 + (8 * 5 / 9)  # image top + height at 8in wide, 9:5 aspect
    data = chart_json
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = None
    if isinstance(data, dict) and data.get("takeaway"):
        bottom = max(bottom, 6.7 + 0.35)  # existing takeaway box top=6.7in, ~1 line
    return bottom + 0.25


# ─────────────────────────────────────────────────────────────────────────────
# Markdown → blocks (raw-text parsing — keeps ** / * markers intact so
# _add_inline_runs can still see them)
# ─────────────────────────────────────────────────────────────────────────────
def _clean_heading(text: str) -> str:
    return text.strip().strip("*").strip()


def _is_hr_only(text: str) -> bool:
    """True for text that, after parsing, is nothing but a markdown
    horizontal rule (or is empty) — this must never produce a slide."""
    t = (text or "").strip()
    return not t or bool(_HR_LINE_RE.match(t))


def _split_long_paragraph(text: str, max_words: int = MAX_WORDS_PER_PARAGRAPH) -> List[str]:
    """Splits one long paragraph's text into ~max_words-sized chunks at
    sentence boundaries (never mid-sentence), so a single huge paragraph
    (e.g. a 280-word Executive Summary with no blank lines) still gets
    spread across multiple slides instead of overflowing one."""
    words = text.split()
    if len(words) <= max_words:
        return [text]

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s]
    if len(sentences) <= 1:
        return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

    chunks: List[str] = []
    current: List[str] = []
    current_words = 0
    for sentence in sentences:
        sw = len(sentence.split())
        if current and current_words + sw > max_words:
            chunks.append(" ".join(current))
            current, current_words = [], 0
        current.append(sentence)
        current_words += sw
    if current:
        chunks.append(" ".join(current))
    return chunks


def _split_into_blocks(text: str) -> List[Dict[str, Any]]:
    """Splits raw markdown into an ordered list of block dicts:
      {"type": "paragraph", "text": str}
      {"type": "bullets", "items": [{"text": str, "level": int}, ...]}
      {"type": "table", "rows": [[str, ...], ...]}
    `level` is the bullet's nesting depth (0 = top-level), derived from its
    leading indent in 2-space increments and capped at MAX_BULLET_LEVEL.
    """
    lines = (text or "").splitlines()
    blocks: List[Dict[str, Any]] = []
    i = 0
    n = len(lines)
    paragraph_buf: List[str] = []

    def flush_paragraph():
        if paragraph_buf:
            joined = " ".join(l.strip() for l in paragraph_buf if l.strip())
            if joined and not _is_hr_only(joined):
                blocks.append({"type": "paragraph", "text": joined})
            paragraph_buf.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        if _HR_LINE_RE.match(stripped):
            # A markdown horizontal rule (---, ***, ___) on its own line —
            # discard entirely, it must never become a slide.
            flush_paragraph()
            i += 1
            continue

        bullet_m = _BULLET_LINE_RE.match(line)
        if bullet_m:
            flush_paragraph()
            items: List[Dict[str, Any]] = []
            while i < n:
                m = _BULLET_LINE_RE.match(lines[i])
                if not m:
                    break
                indent, item_text = m.group(1), m.group(2).strip()
                level = min(len(indent) // 2, MAX_BULLET_LEVEL)
                items.append({"text": item_text, "level": level})
                i += 1
            blocks.append({"type": "bullets", "items": items})
            continue

        if "|" in stripped and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            flush_paragraph()
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            rows = [header_cells]
            i += 2  # skip header + separator row
            while i < n and lines[i].strip() and "|" in lines[i]:
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row_cells)
                i += 1
            blocks.append({"type": "table", "rows": rows})
            continue

        paragraph_buf.append(line)
        i += 1

    flush_paragraph()
    return blocks


def _parse_subsections(content: str) -> List[Dict[str, Any]]:
    """Splits one section's raw markdown on H4 headings into subsection
    records: {"title": str|None, "raw": str}. title=None for content that
    appears before any H4 (it uses the parent section's own title)."""
    records: List[Dict[str, Any]] = []
    for h4_chunk in _H4_SPLIT_RE.split(content):
        if not h4_chunk.strip():
            continue
        is_h4 = h4_chunk.lstrip().startswith("####")
        title = None
        raw = h4_chunk
        if is_h4:
            m = _HEADING_LINE_RE.match(h4_chunk.lstrip())
            if m:
                title = _clean_heading(m.group(2))
                raw = h4_chunk[m.end():]
        records.append({"title": title, "raw": raw})
    return records


def _subsection_elements(raw: str) -> List[Dict[str, Any]]:
    """Flattens one subsection's raw markdown (text + recharts fences) into an
    ordered list of {"kind": "item"|"table"|"chart", ...} elements."""
    elements: List[Dict[str, Any]] = []
    for seg in _split_segments(raw):
        if seg["type"] == "chart":
            try:
                chart_json = json.loads(seg["raw"])
            except Exception:
                chart_json = None
            elements.append({"kind": "chart", "chart_json": chart_json})
            continue

        for block in _split_into_blocks(seg["text"]):
            if block["type"] == "table":
                elements.append({"kind": "table", "rows": block["rows"]})
            elif block["type"] == "paragraph":
                for chunk in _split_long_paragraph(block["text"]):
                    if not _is_hr_only(chunk):
                        elements.append({"kind": "item", "bullet": False, "text": chunk, "level": 0})
            else:  # bullets
                for it in block["items"]:
                    if not _is_hr_only(it["text"]):
                        elements.append({"kind": "item", "bullet": True, "text": it["text"], "level": it["level"]})
    return elements


def _is_sparse(elements: List[Dict[str, Any]]) -> bool:
    """A subsection is sparse (and gets merged into a neighbor) when it has no
    table/chart AND it has fewer than 3 bullets OR fewer than 50 words."""
    if any(el["kind"] in ("table", "chart") for el in elements):
        return False
    bullets = sum(1 for el in elements if el["kind"] == "item" and el.get("bullet"))
    words = sum(len(el["text"].split()) for el in elements if el["kind"] == "item")
    return bullets < MIN_BULLETS_NOT_SPARSE or words < MIN_WORDS_NOT_SPARSE


def _merge_sparse_subsections(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges a sparse subsection's elements into the NEXT subsection (or the
    previous one, if it's last), prefixing a bold lead-in line with its own
    title so that context isn't silently dropped."""
    n = len(records)
    if n <= 1:
        return records

    merged: List[Dict[str, Any]] = []
    i = 0
    while i < n:
        rec = records[i]
        if _is_sparse(rec["elements"]):
            lead_in = [{"kind": "item", "bullet": False, "text": rec["title"], "level": 0, "is_subsection_label": True}] if rec["title"] else []
            if i + 1 < n:
                records[i + 1]["elements"] = lead_in + rec["elements"] + records[i + 1]["elements"]
                i += 1
                continue
            if merged:
                merged[-1]["elements"] = merged[-1]["elements"] + lead_in + rec["elements"]
                i += 1
                continue
        merged.append(rec)
        i += 1
    return merged


def _trailing_group_is_short(group: List[Dict[str, Any]]) -> bool:
    """A trailing text block right after a table/chart is short enough to
    merge onto that same slide when it's under BOTH the word and bullet
    caps — a long block still spills to its own slide."""
    words = sum(len(el["text"].split()) for el in group)
    bullets = sum(1 for el in group if el.get("bullet"))
    return words < SHORT_TRAILING_MAX_WORDS and bullets < SHORT_TRAILING_MAX_BULLETS


def _estimate_note_height_inches(group: List[Dict[str, Any]]) -> float:
    """Rough rendered-height estimate for a short trailing note at caption
    size (12pt) in an ~11.7in-wide box — used only to decide whether it still
    fits below a table/chart, not for exact layout."""
    words = sum(len(el["text"].split()) for el in group)
    bullets = sum(1 for el in group if el.get("bullet"))
    lines = max(1, bullets, math.ceil(words / 16))
    return 0.15 + lines * 0.28


def _cluster_words(cluster: Dict[str, Any]) -> int:
    return len(cluster["parent"]["text"].split()) + sum(len(c["text"].split()) for c in cluster["children"])


def _cluster_lines(cluster: Dict[str, Any]) -> int:
    """Line-fit estimate for a whole cluster (parent + its children) — the
    real layout constraint a slide must fit under, since it accounts for
    wrapping instead of just raw word count (see _estimate_item_lines)."""
    return _estimate_item_lines(cluster["parent"]["text"]) + sum(
        _estimate_item_lines(c["text"]) for c in cluster["children"]
    )


def _cluster_item_count(cluster: Dict[str, Any]) -> int:
    return 1 + len(cluster["children"])


def _cluster_to_items(cluster: Dict[str, Any], children: Optional[List[Dict[str, Any]]] = None,
                       continued: bool = False) -> List[Dict[str, Any]]:
    """Flattens a cluster (or a child subset of one, when an oversized cluster
    had to be split) back into the flat item list _add_content_slide expects.
    `continued` marks a split-off continuation slide so the repeated parent
    label reads as "(cont'd)" instead of silently duplicating it verbatim —
    sub-bullets on a continuation slide are never left without their parent."""
    parent = dict(cluster["parent"])
    if continued:
        parent["text"] = f"{parent['text']} (cont'd)"
    kids = cluster["children"] if children is None else children
    return [parent] + list(kids)


def _split_oversized_cluster(cluster: Dict[str, Any], max_lines: int) -> List[List[Dict[str, Any]]]:
    """A single cluster too large for one slide alone: splits its CHILDREN
    (the parent itself is never split, and is repeated on each continuation
    slide) into groups that each fit under `max_lines` (a wrapped-line
    estimate, not raw word count — see _estimate_item_lines) alongside that
    repeated parent. Rebalances so a continuation slide is never left with
    just one orphaned child when its neighbor has more than 2 to spare."""
    parent = cluster["parent"]
    children = cluster["children"]
    parent_lines = _estimate_item_lines(parent["text"])

    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_lines = parent_lines
    for child in children:
        cl = _estimate_item_lines(child["text"])
        if current and current_lines + cl > max_lines:
            groups.append(current)
            current, current_lines = [], parent_lines
        current.append(child)
        current_lines += cl
    groups.append(current)  # always >=1 group, even empty (a bare oversized parent with no children)

    for gi in range(1, len(groups)):
        if len(groups[gi]) == 1 and len(groups[gi - 1]) > 2:
            groups[gi].insert(0, groups[gi - 1].pop())

    return groups


def _group_into_clusters(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Groups a flat run of "item" elements (bullets + paragraphs, no
    tables/charts) into clusters: {"parent": item, "children": [item, ...]}.
    A new cluster starts at a non-bullet paragraph OR a level-0 bullet;
    any bullet at level >= 1 attaches as a child of the current cluster.
    This is the unit the slide-mid-list-split fix never splits apart."""
    clusters: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for el in items:
        is_top = (not el.get("bullet")) or el.get("level", 0) == 0
        if is_top or current is None:
            current = {"parent": el, "children": []}
            clusters.append(current)
        else:
            current["children"].append(el)
    return clusters


def _pack_clusters_to_slides(clusters: List[Dict[str, Any]], title: str) -> List[Dict[str, Any]]:
    """Packs clusters onto content slides. A new slide may only START at a
    cluster boundary — never in the middle of a parent bullet's children —
    so a nested list is never split mid-group. A single cluster that's too
    big to fit a slide alone is split at a child boundary (see
    _split_oversized_cluster); otherwise clusters keep combining onto the
    current slide up to MAX_ITEMS_PER_SLIDE / MAX_COMBINED_SLIDE_WORDS /
    MAX_LINES_PER_SLIDE.

    The budget check happens BEFORE a cluster is added, not after — several
    small clusters (e.g. a run of ordinary-length prose paragraphs, none
    individually over MAX_WORDS_PER_SLIDE) could otherwise all land on one
    slide and only trip the combined-budget flush once already over it,
    which is exactly how a ~280-word Executive Summary used to end up
    overflowing a single slide instead of splitting."""
    slides: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []
    pending_words = 0
    pending_items = 0
    pending_lines = 0

    def slide_title() -> str:
        return title if not slides else f"{title} (cont'd)"

    def flush():
        nonlocal pending, pending_words, pending_items, pending_lines
        if pending:
            slides.append({"type": "content", "title": slide_title(), "items": pending})
        pending, pending_words, pending_items, pending_lines = [], 0, 0, 0

    for cluster in clusters:
        cw = _cluster_words(cluster)
        cl = _cluster_lines(cluster)
        ci = _cluster_item_count(cluster)

        if cw > MAX_WORDS_PER_SLIDE or cl > MAX_LINES_PER_SLIDE:
            flush()
            groups = _split_oversized_cluster(cluster, MAX_LINES_PER_SLIDE)
            for gi, grp in enumerate(groups):
                slides.append({
                    "type": "content",
                    "title": slide_title(),
                    "items": _cluster_to_items(cluster, children=grp, continued=(gi > 0)),
                })
            continue

        if pending and (
            pending_items + ci > MAX_ITEMS_PER_SLIDE
            or pending_words + cw > MAX_COMBINED_SLIDE_WORDS
            or pending_lines + cl > MAX_LINES_PER_SLIDE
        ):
            flush()

        pending.extend(_cluster_to_items(cluster))
        pending_words += cw
        pending_items += ci
        pending_lines += cl

    flush()
    return slides


def _elements_to_slides(elements: List[Dict[str, Any]], title: str) -> List[Dict[str, Any]]:
    """Chunks a subsection's flat element list into slide specs. Bullet/
    paragraph runs are first grouped into clusters (a level-0 bullet or
    paragraph plus its nested children) and packed cluster-by-cluster (see
    _pack_clusters_to_slides) so a slide can only start at a cluster
    boundary — never orphaning a nested bullet from its parent. Tables and
    charts get their own dedicated slide — UNLESS the content immediately
    following one is a short text block (< 40 words and < 3 bullets) that
    still fits below it vertically, in which case it's attached to that same
    slide as `trailing_items` instead of spilling to a near-empty slide of
    its own."""
    slides: List[Dict[str, Any]] = []
    item_run: List[Dict[str, Any]] = []

    def flush_item_run():
        nonlocal item_run
        if item_run:
            slides.extend(_pack_clusters_to_slides(_group_into_clusters(item_run), title))
        item_run = []

    i = 0
    n = len(elements)
    while i < n:
        el = elements[i]

        if el["kind"] in ("table", "chart"):
            flush_item_run()

            trailing: List[Dict[str, Any]] = []
            j = i + 1
            while j < n and elements[j]["kind"] == "item":
                trailing.append(elements[j])
                j += 1

            merge_ok = False
            if trailing and _trailing_group_is_short(trailing):
                note_top = (
                    _table_note_top_inches(len(el["rows"])) if el["kind"] == "table"
                    else _chart_note_top_inches(el["chart_json"])
                )
                merge_ok = (note_top + _estimate_note_height_inches(trailing)) <= CONTENT_SAFE_BOTTOM_IN

            if el["kind"] == "table":
                spec = {"type": "table", "title": title, "rows": el["rows"]}
            else:
                spec = {"type": "chart", "title": title, "chart_json": el["chart_json"]}

            if merge_ok:
                spec["trailing_items"] = trailing
                i = j
            else:
                i += 1
            slides.append(spec)
            continue

        item_run.append(el)
        i += 1

    flush_item_run()
    return slides


def _parse_markdown_to_slides(content: str, default_title: str = "Overview") -> List[Dict[str, Any]]:
    """
    Splits one section's markdown body into slide-sized chunks. Returns a
    list of dicts, each one of:
      {"type": "content", "title": str, "items": [...]}
      {"type": "table", "title": str, "rows": [[...]]}
      {"type": "chart", "title": str, "chart_json": dict}

    `default_title` is the slide heading for content that appears before any
    H4 subsection — normally the parent section's own title.
    """
    records = _parse_subsections(content)
    for rec in records:
        rec["elements"] = _subsection_elements(rec["raw"])
    records = _merge_sparse_subsections(records)

    slides: List[Dict[str, Any]] = []
    for rec in records:
        title = rec["title"] or default_title
        slides.extend(_elements_to_slides(rec["elements"], title))
    return slides


def _add_trailing_note_to_slide(slide, items: List[Dict[str, Any]], theme: dict, top_inches: float):
    """Renders a short text block directly below a table/chart on the SAME
    slide, at caption size, instead of letting it spill to its own slide."""
    top = Inches(top_inches)
    height = max(Inches(CONTENT_SAFE_BOTTOM_IN) - top, Inches(0.3))
    _, tf = _add_textbox(slide, Inches(0.8), top, Inches(11.7), height)
    tf.auto_size = MSO_AUTO_SIZE.NONE
    first = True
    for item in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(6)
        p.line_spacing = 1.1

        if item.get("bullet"):
            _set_paragraph_indent(p, Inches(0.3), Inches(-0.25))
            bullet_run = p.add_run()
            bullet_run.text = "•  "
            bullet_run.font.name = SLIDE_FONT
            bullet_run.font.size = CAPTION_FONT_SIZE
            bullet_run.font.bold = True
            bullet_run.font.color.rgb = _rgb(theme["accent"])
            _add_inline_runs(p, item.get("text", ""), theme, base_size=CAPTION_FONT_SIZE, color=theme["text_dark"])
        else:
            _add_inline_runs(p, item.get("text", ""), theme, base_size=CAPTION_FONT_SIZE,
                              base_italic=True, color=theme["text_muted"])


def _create_section_slides(prs: Presentation, section_title: str, content: str, theme: dict,
                            section_index: int, slide_counter: "itertools.count",
                            logo_asset: Optional[Dict[str, Any]] = None):
    """Section divider slide (H3), then one slide per parsed chunk of `content`."""
    _create_section_title_slide(prs, section_title, theme, section_index, logo_asset=logo_asset)

    for slide_spec in _parse_markdown_to_slides(content, default_title=section_title):
        kind = slide_spec["type"]
        if kind == "content":
            slide = _add_content_slide(prs, slide_spec["title"], slide_spec["items"], theme)
        elif kind == "table":
            slide = _new_slide(prs, _rgb(theme["bg_white"]))
            _add_title_bar(slide, slide_spec["title"], theme)
            _add_table_to_slide(slide, slide_spec["rows"], theme)
            if slide_spec.get("trailing_items"):
                top = _table_note_top_inches(len(slide_spec["rows"]))
                _add_trailing_note_to_slide(slide, slide_spec["trailing_items"], theme, top)
        elif kind == "chart":
            slide = _new_slide(prs, _rgb(theme["bg_white"]))
            _add_title_bar(slide, slide_spec["title"], theme)
            _add_chart_image_to_slide(slide, slide_spec["chart_json"], theme)
            if slide_spec.get("trailing_items"):
                top = _chart_note_top_inches(slide_spec["chart_json"])
                _add_trailing_note_to_slide(slide, slide_spec["trailing_items"], theme, top)
        else:
            continue
        _add_slide_number(slide, next(slide_counter), theme)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level section splitting (mirrors section_service's H3 split)
# ─────────────────────────────────────────────────────────────────────────────
def _split_into_sections(content: str) -> List[Dict[str, str]]:
    """Splits full report markdown on H3 headings. Content before the first H3
    (if any) is dropped from the TOC/section list — same "intro" convention
    ReportRenderer.tsx's accordion uses for always-visible lead-in text."""
    sections: List[Dict[str, str]] = []
    for block in _H3_SPLIT_RE.split(content or ""):
        if not block.strip() or not block.lstrip().startswith("###"):
            continue
        m = _HEADING_LINE_RE.match(block.lstrip())
        title = _clean_heading(m.group(2)) if m else "Untitled Section"
        body = block[m.end():] if m else block
        sections.append({"title": title, "content": body})
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────
async def generate_pptx(report_data: dict) -> bytes:
    """
    Main entry point — returns PPTX file as bytes.

    `report_data` keys: `title` (str), `content` (str — already-resolved
    markdown with recharts fences), `brand_name` (optional str), the
    agent/report type under either `agent_name` or `agent_type` (both
    accepted — the router uses the former, ad-hoc scripts the latter),
    used to pick the fallback color theme and the cover's "{TYPE} REPORT"
    badge, an optional `brand_kit` dict ({"logo_url": ..., "colors": {...}}),
    and an optional `extracted_palette` dict ({"primary"/"secondary"/"accent"})
    inferred by the agent during generation. Theme precedence: manual brand_kit
    colors > extracted_palette > report-type theme (see _resolve_theme). The
    logo always comes from brand_kit only. With neither set, behavior is
    unchanged from the plain report-type theme.
    """
    title = report_data.get("title") or "Strategic Intelligence Report"
    content = report_data.get("content") or ""
    brand_name = report_data.get("brand_name")
    agent_name = report_data.get("agent_name") or report_data.get("agent_type")
    date = report_data.get("created_at")
    brand_kit = report_data.get("brand_kit")
    extracted_palette = report_data.get("extracted_palette")
    theme = _resolve_theme(brand_kit, extracted_palette, agent_name or "default")
    logo_asset = _load_logo_asset(brand_kit)

    sections = _split_into_sections(content)

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    _create_cover_slide(prs, title, brand_name, agent_name, theme, date=date, logo_asset=logo_asset)
    _create_toc_slide(prs, sections, theme)

    slide_counter = itertools.count(1)
    for idx, section in enumerate(sections, 1):
        _create_section_slides(prs, section["title"], section["content"], theme, idx, slide_counter, logo_asset=logo_asset)

    _create_closing_slide(prs, theme, date=date)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
