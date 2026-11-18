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
from backend.services.template_service import get_template, TemplateSpec, _max_lines_per_slide  # noqa: E402
from backend.services.slide_planner import (  # noqa: E402
    SlideBlock, SectionPlan, plan_section, plan_report_llm, paginate_blocks,
    COMPONENT_TABLE, COMPONENT_CHART, COMPONENT_STAT_ROW, COMPONENT_TIMELINE,
)
import backend.services.slide_planner as slide_planner  # noqa: E402


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def _logo_box_size(asset: Dict[str, Any], tpl: TemplateSpec, kind: str):
    """Scales a logo to fit within the max height/width box defined by
    tpl.art[kind]["logo"] (`kind` is "cover" or "divider"), preserving aspect
    ratio. Thin pptx-specific wrapper around the shared float-returning
    brand_theme.logo_fit_dimensions, wrapping the result in python-pptx's
    own Inches (a different class from python-docx's)."""
    logo_geo = tpl.art[kind]["logo"]
    width_in, height_in = logo_fit_dimensions(asset, logo_geo["max_h"], logo_geo["max_w"])
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
# Content slides now carry the chrome frame (_add_content_chrome): an eyebrow/
# kicker above the heading pushes CONTENT_BODY_TOP_IN down slightly from the
# pre-chrome 1.35in; CONTENT_SAFE_BOTTOM_IN (the hard floor) is unchanged.
CONTENT_BODY_TOP_IN = 1.40
CONTENT_BODY_HEIGHT_IN = 5.20
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


def _bullet_font_size(level: int, tpl: TemplateSpec):
    """Level 0 = top-level bullet (15pt), 1 = sub-bullet (13.5pt), 2+ = sub-sub (12.5pt)."""
    if level <= 0:
        return tpl.type_scale["body"]
    if level == 1:
        return tpl.type_scale["sub_bullet"]
    return tpl.type_scale["subsub_bullet"]


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


# ─────────────────────────────────────────────────────────────────────────────
# art-spec helpers — small, generic readers for the chrome-slide builders'
# tpl.art values, so each builder doesn't repeat its own string->enum mapping.
# ─────────────────────────────────────────────────────────────────────────────
_ALIGN_MAP = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
_ANCHOR_MAP = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}


def _apply_align(paragraph, align: Optional[str]):
    """Applies a named alignment ("left"/"center"/"right") from an art spec to
    `paragraph`, or leaves it unset (python-pptx's own default) when `align`
    is None/falsy — matching elements that today never call `.alignment =`
    at all (e.g. the cover title/wordmark/tagline/meta)."""
    if align:
        paragraph.alignment = _ALIGN_MAP.get(align, PP_ALIGN.LEFT)


def _art_dim(value, canvas_width_in: float):
    """Resolves an art-spec width that may be the literal "full" (the whole
    canvas width) or a plain inch float, as an Inches() Length."""
    return Inches(canvas_width_in) if value == "full" else Inches(value)


def _set_paragraph_indent(paragraph, marL, indent):
    """Sets a left margin + hanging first-line indent on a paragraph (EMU
    Length values) so bullet text gets a clear, consistent left indent —
    python-pptx has no high-level property for this, so it's set directly
    on the <a:pPr> element."""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", str(int(marL)))
    pPr.set("indent", str(int(indent)))


def _apply_text_formatting(paragraph, text: str, theme: dict, tpl: TemplateSpec, bold: bool = False, italic: bool = False,
                            font_size=14, color: Optional[str] = None, font_role: str = "body"):
    """Adds one plain text run to `paragraph` with the given formatting (no
    markdown parsing — see _add_inline_runs for that). `font_role` selects
    which of tpl.fonts ("heading" or "body") the run's font family comes
    from — every caller still resolves to the same family today (both slots
    equal "Calibri" in the default template); this is a seam for a future
    template to diverge on, not a behavior change."""
    run = paragraph.add_run()
    run.text = text
    run.font.name = tpl.fonts[font_role]
    run.font.size = _normalize_size(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color or theme[tpl.slots["body_text"]])
    return run


_INLINE_MD_RE = re.compile(r"(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)")


def _add_inline_runs(paragraph, text: str, theme: dict, tpl: TemplateSpec, base_size=Pt(14), base_bold: bool = False,
                      base_italic: bool = False, color: Optional[str] = None, font_role: str = "body"):
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
            _apply_text_formatting(paragraph, part[3:-3], theme, tpl, bold=True, italic=True, font_size=base_size, color=color, font_role=font_role)
        elif part.startswith("**") and part.endswith("**") and len(part) >= 5:
            _apply_text_formatting(paragraph, part[2:-2], theme, tpl, bold=True, italic=False, font_size=base_size, color=color, font_role=font_role)
        elif part.startswith("*") and part.endswith("*") and len(part) >= 3:
            _apply_text_formatting(paragraph, part[1:-1], theme, tpl, bold=False, italic=True, font_size=base_size, color=color, font_role=font_role)
        else:
            _apply_text_formatting(paragraph, part, theme, tpl, bold=base_bold, italic=base_italic, font_size=base_size, color=color, font_role=font_role)


def _add_title_bar(slide, text: str, theme: dict, tpl: TemplateSpec, subtitle: Optional[str] = None):
    """Thin theme-primary accent bar + heading, used at the top of every
    content/table/chart/TOC slide. All geometry comes from
    tpl.geometry["title_bar"] / ["canvas"]."""
    canvas = tpl.geometry["canvas"]
    tb = tpl.geometry["title_bar"]
    accent_bar = tb["accent_bar"]
    title_box = tb["title_box"]
    subtitle_box = tb["subtitle_box"]

    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(accent_bar["width"]), Inches(canvas["height"]))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme[tpl.slots["accent_bar"]])
    bar.line.fill.background()

    _, tf = _add_textbox(slide, Inches(title_box["x"]), Inches(title_box["y"]), Inches(title_box["w"]), Inches(tb["height"]))
    tf.auto_size = MSO_AUTO_SIZE.NONE
    _add_inline_runs(tf.paragraphs[0], text, theme, tpl, base_size=tpl.type_scale["title"], base_bold=True, color=theme[tpl.slots["title"]], font_role="heading")

    if subtitle:
        _, sub_tf = _add_textbox(slide, Inches(subtitle_box["x"]), Inches(subtitle_box["y"]), Inches(subtitle_box["w"]), Inches(subtitle_box["h"]))
        sub_tf.auto_size = MSO_AUTO_SIZE.NONE
        _add_inline_runs(sub_tf.paragraphs[0], subtitle, theme, tpl, base_size=tpl.type_scale["titlebar_subtitle"], color=theme[tpl.slots["titlebar_subtitle"]])


def _add_content_chrome(slide, tpl: TemplateSpec, theme: dict, section_index: int, section_title: str,
                         heading: str, source: Optional[str] = None, takeaway: Optional[str] = None):
    """The shared top/bottom frame for every content-kind slide (bullets,
    table, chart, stat_row, timeline) — replaces the bare _add_title_bar path
    for these five renderers only (TOC/divider/cover/closing keep using
    _add_title_bar/their own art directly):
      - the same left accent bar as _add_title_bar (same geometry/slot, so it
        reads as one continuous deck design);
      - an EYEBROW/kicker: "<NN> · <SECTION TITLE>" (NN = the section's
        1-based running number, 2-digit, matching the TOC/divider numbering),
        uppercase and letter-spaced;
      - the slide's own HEADING, with a thin HAIRLINE RULE beneath it;
      - an optional headline TAKEAWAY line directly under the rule, when the
        planner supplied one (the slide's "so what" — bold-ish, a touch
        larger than body text) — see _content_shift_for_takeaway for how
        callers push their own content down to clear it;
      - a small source-FOOTER slot at the bottom — renders `source` when
        given, else stays blank (real source extraction is a follow-up; this
        just builds the slot).
    All geometry comes from tpl.geometry["chrome"] (eyebrow/heading/rule/
    takeaway/footer boxes), tuned to stack without colliding with
    content_body (which starts below the rule, or below the takeaway when
    present) or the slide number (which shares the footer's vertical band
    but sits at the right edge)."""
    canvas = tpl.geometry["canvas"]
    chrome = tpl.geometry["chrome"]
    accent_bar = tpl.geometry["title_bar"]["accent_bar"]

    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(accent_bar["width"]), Inches(canvas["height"]))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme[tpl.slots["accent_bar"]])
    bar.line.fill.background()

    eb = chrome["eyebrow"]
    _, eb_tf = _add_textbox(slide, Inches(eb["x"]), Inches(eb["y"]), Inches(eb["w"]), Inches(eb["h"]))
    eb_tf.auto_size = MSO_AUTO_SIZE.NONE
    eyebrow_text = f"{section_index:02d}  ·  {(section_title or '').upper()}"
    eb_run = _apply_text_formatting(eb_tf.paragraphs[0], eyebrow_text, theme, tpl, bold=True,
                                     font_size=tpl.type_scale["eyebrow"], color=theme[tpl.slots["eyebrow"]])
    eb_run._r.get_or_add_rPr().set("spc", "100")

    hd = chrome["heading"]
    _, hd_tf = _add_textbox(slide, Inches(hd["x"]), Inches(hd["y"]), Inches(hd["w"]), Inches(hd["h"]))
    hd_tf.auto_size = MSO_AUTO_SIZE.NONE
    _add_inline_runs(hd_tf.paragraphs[0], heading, theme, tpl, base_size=tpl.type_scale["title"], base_bold=True,
                      color=theme[tpl.slots["title"]], font_role="heading")

    rl = chrome["rule"]
    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(rl["x"]), Inches(rl["y"]), Inches(rl["w"]), Pt(rl["thickness_pt"]))
    rule.fill.solid()
    rule.fill.fore_color.rgb = _rgb(theme[tpl.slots["rule"]])
    rule.line.fill.background()

    if takeaway:
        tk = chrome["takeaway"]
        _, tk_tf = _add_textbox(slide, Inches(tk["x"]), Inches(tk["y"]), Inches(tk["w"]), Inches(tk["h"]))
        tk_tf.auto_size = MSO_AUTO_SIZE.NONE
        _add_inline_runs(tk_tf.paragraphs[0], takeaway, theme, tpl, base_size=tpl.type_scale["takeaway"], base_bold=True,
                          color=theme[tpl.slots["takeaway"]])

    ft = chrome["footer"]
    _, ft_tf = _add_textbox(slide, Inches(ft["x"]), Inches(ft["y"]), Inches(ft["w"]), Inches(ft["h"]))
    ft_tf.auto_size = MSO_AUTO_SIZE.NONE
    _apply_text_formatting(ft_tf.paragraphs[0], source or "", theme, tpl, font_size=tpl.type_scale["footer"], color=theme[tpl.slots["footer"]])


def _content_shift_for_takeaway(tpl: TemplateSpec, takeaway: Optional[str]) -> float:
    """Inches to push a content-kind slide's own body/image down (and shrink
    its available height/top ceiling by the same amount) when a takeaway
    line is rendered in the chrome, so the component's own content never
    collides with it. 0 when no takeaway. bullets/stat_row/chart use this;
    timeline's chevron row already starts at geometry["timeline"]["row_top"]
    (2.3in by default), well below the takeaway band, so it never needs it."""
    if not takeaway:
        return 0.0
    tk = tpl.geometry["chrome"]["takeaway"]
    cb_top = tpl.geometry["content_body"]["top"]
    return max((tk["y"] + tk["h"] + 0.05) - cb_top, 0.0)


def _add_slide_number(slide, number: int, theme: dict, tpl: TemplateSpec):
    canvas = tpl.geometry["canvas"]
    sn = tpl.geometry["slide_number"]
    left = Inches(canvas["width"]) - Inches(sn["x_from_right"])
    top = Inches(canvas["height"]) - Inches(sn["y_from_bottom"])
    _, tf = _add_textbox(slide, left, top, Inches(sn["w"]), Inches(sn["h"]))
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _apply_text_formatting(tf.paragraphs[0], str(number), theme, tpl, font_size=tpl.type_scale["slide_number"], color=theme[tpl.slots["slide_number"]])


# ─────────────────────────────────────────────────────────────────────────────
# Cover / TOC / section divider / closing slides
# ─────────────────────────────────────────────────────────────────────────────
def _cover_classic(prs: Presentation, title: str, brand_name: Optional[str], agent_name: Optional[str],
                    theme: dict, tpl: TemplateSpec, date: Optional[str] = None, logo_asset: Optional[Dict[str, Any]] = None):
    """The "classic" cover recipe (the original composition, unchanged).
    Branded cover slide — dark themed background. With a client brand_kit
    logo, it takes the top-left spot (where the StratAI wordmark normally
    sits) — "Powered by StratAI" still appears in the footer meta line below.
    Without one, falls back to the original text-only wordmark/tagline. All
    decorative coordinates/shape-params/copy-strings come from
    tpl.art["cover"]. The big cover title shows the brand name (falling back
    to the report title, then tpl.art["cover"]["title"]["fallback_text"]) so
    the cover reads as "Cog Culture", not the first section heading."""
    cover_art = tpl.art["cover"]
    date_str = date or datetime.now().strftime(tpl.art["date_format"])
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["cover"]]))

    if logo_asset:
        logo_geo = cover_art["logo"]
        width, height = _logo_box_size(logo_asset, tpl, "cover")
        slide.shapes.add_picture(io.BytesIO(logo_asset["bytes"]), Inches(logo_geo["x"]), Inches(logo_geo["y"]), width=width, height=height)
    else:
        wm = cover_art["wordmark"]
        _, wordmark_tf = _add_textbox(slide, Inches(wm["x"]), Inches(wm["y"]), Inches(wm["w"]), Inches(wm["h"]))
        _apply_text_formatting(wordmark_tf.paragraphs[0], wm["text"], theme, tpl, bold=True, font_size=tpl.type_scale["cover_wordmark"], color=theme[tpl.slots["cover_wordmark"]])

        tg = cover_art["tagline"]
        _, tagline_tf = _add_textbox(slide, Inches(tg["x"]), Inches(tg["y"]), Inches(tg["w"]), Inches(tg["h"]))
        _apply_text_formatting(tagline_tf.paragraphs[0], tg["text"], theme, tpl, bold=True, font_size=tpl.type_scale["cover_tagline"], color=theme[tpl.slots["cover_tagline"]])

    date_geo = cover_art["date"]
    _, date_tf = _add_textbox(slide, Inches(date_geo["x"]), Inches(date_geo["y"]), Inches(date_geo["w"]), Inches(date_geo["h"]))
    _apply_align(date_tf.paragraphs[0], date_geo.get("align"))
    _apply_text_formatting(date_tf.paragraphs[0], date_str, theme, tpl, bold=True, font_size=tpl.type_scale["cover_date"], color=theme[tpl.slots["cover_date"]])

    badge_geo = cover_art["badge"]
    badge_text = f"{agent_name.upper()} {badge_geo['agent_suffix']}" if agent_name else badge_geo["label"]
    badge_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if badge_geo.get("rounded", True) else MSO_SHAPE.RECTANGLE
    badge = slide.shapes.add_shape(badge_shape_type, Inches(badge_geo["x"]), Inches(badge_geo["y"]), Inches(badge_geo["w"]), Inches(badge_geo["h"]))
    badge.fill.solid()
    badge.fill.fore_color.rgb = _rgb(theme[tpl.slots["cover_badge_bg"]])
    badge.line.fill.background()
    badge.text_frame.word_wrap = True
    badge.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    _apply_text_formatting(badge.text_frame.paragraphs[0], badge_text, theme, tpl, bold=True, font_size=tpl.type_scale["cover_badge"], color=theme[tpl.slots["cover_badge_text"]])

    # Subtle accent bar ~40% down the slide.
    rule_geo = cover_art["rule"]
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(rule_geo["y"]), _art_dim(rule_geo["width"], tpl.geometry["canvas"]["width"]), Pt(rule_geo["thickness_pt"]))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme[tpl.slots["cover_rule"]])
    bar.line.fill.background()

    title_geo = cover_art["title"]
    cover_title = brand_name or title or title_geo["fallback_text"]
    _, title_tf = _add_textbox(slide, Inches(title_geo["x"]), Inches(title_geo["y"]), Inches(title_geo["w"]), Inches(title_geo["h"]))
    _apply_align(title_tf.paragraphs[0], title_geo.get("align"))
    _apply_text_formatting(title_tf.paragraphs[0], cover_title, theme, tpl, bold=True, font_size=tpl.type_scale["cover_title"], color=theme[tpl.slots["cover_title"]], font_role="heading")

    meta_geo = cover_art["meta"]
    _, meta_tf = _add_textbox(slide, Inches(meta_geo["x"]), Inches(meta_geo["y"]), Inches(meta_geo["w"]), Inches(meta_geo["h"]))
    p = meta_tf.paragraphs[0]
    _apply_text_formatting(p, meta_geo["prepared_for"], theme, tpl, font_size=tpl.type_scale["cover_meta"], color=theme[tpl.slots["cover_meta"]])
    _apply_text_formatting(p, brand_name or meta_geo["brand_fallback"], theme, tpl, bold=True, font_size=tpl.type_scale["cover_meta"], color=theme[tpl.slots["cover_meta_brand"]])
    _apply_text_formatting(p, f"{meta_geo['separator']}{meta_geo['powered_by']}", theme, tpl, font_size=tpl.type_scale["cover_meta"], color=theme[tpl.slots["cover_meta"]])

    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Cover layout recipes — a template picks its cover COMPOSITION via
# tpl.art["cover"]["layout"] ("classic" when omitted/unknown). Every recipe
# reads the same palette/slots/fonts/type_scale (colors via
# theme[tpl.slots[...]], never a hex literal); only the coordinates below —
# which ARE the layout — are internal to each recipe. Text that sits on a
# filled band/sidebar uses the "cover_band_text" slot against
# "cover_band_fill" (not cover_title/cover_meta, which are chosen against the
# slide background).
# ─────────────────────────────────────────────────────────────────────────────
_HERO_TITLE_SCALE = 1.4
_SIDEBAR_FRACTION = 0.38
_BAND_HEIGHT_IN = 2.2


def _cv_rect(slide, left_in, top_in, w_in, h_in, hex_color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left_in), Inches(top_in), Inches(w_in), Inches(h_in))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(hex_color)
    shape.line.fill.background()
    return shape


def _cv_brand_mark(slide, theme, tpl, logo_asset, x, y, w, align, wordmark_slot, tagline_slot):
    """Logo (or wordmark+tagline fallback) in the area starting at (x, y) that
    is `w` wide, left- or center-aligned within it."""
    cover_art = tpl.art["cover"]
    if logo_asset:
        width, height = _logo_box_size(logo_asset, tpl, "cover")
        left = Inches(x) if align == "left" else Inches(x) + (Inches(w) - width) // 2
        slide.shapes.add_picture(io.BytesIO(logo_asset["bytes"]), left, Inches(y), width=width, height=height)
        return
    wm, tg = cover_art["wordmark"], cover_art["tagline"]
    _, wm_tf = _add_textbox(slide, Inches(x), Inches(y + 0.1), Inches(w), Inches(wm["h"]))
    _apply_align(wm_tf.paragraphs[0], align)
    _apply_text_formatting(wm_tf.paragraphs[0], wm["text"], theme, tpl, bold=True, font_size=tpl.type_scale["cover_wordmark"], color=theme[tpl.slots[wordmark_slot]])
    _, tg_tf = _add_textbox(slide, Inches(x), Inches(y + 0.6), Inches(w), Inches(tg["h"]))
    _apply_align(tg_tf.paragraphs[0], align)
    _apply_text_formatting(tg_tf.paragraphs[0], tg["text"], theme, tpl, bold=True, font_size=tpl.type_scale["cover_tagline"], color=theme[tpl.slots[tagline_slot]])


def _cv_date(slide, theme, tpl, date):
    date_geo = tpl.art["cover"]["date"]
    date_str = date or datetime.now().strftime(tpl.art["date_format"])
    _, date_tf = _add_textbox(slide, Inches(date_geo["x"]), Inches(date_geo["y"]), Inches(date_geo["w"]), Inches(date_geo["h"]))
    _apply_align(date_tf.paragraphs[0], date_geo.get("align"))
    _apply_text_formatting(date_tf.paragraphs[0], date_str, theme, tpl, bold=True, font_size=tpl.type_scale["cover_date"], color=theme[tpl.slots["cover_date"]])


def _cv_badge(slide, theme, tpl, agent_name, x, y, w, h):
    badge_geo = tpl.art["cover"]["badge"]
    badge_text = f"{agent_name.upper()} {badge_geo['agent_suffix']}" if agent_name else badge_geo["label"]
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if badge_geo.get("rounded", True) else MSO_SHAPE.RECTANGLE
    badge = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    badge.fill.solid()
    badge.fill.fore_color.rgb = _rgb(theme[tpl.slots["cover_badge_bg"]])
    badge.line.fill.background()
    badge.text_frame.word_wrap = True
    badge.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    _apply_text_formatting(badge.text_frame.paragraphs[0], badge_text, theme, tpl, bold=True, font_size=tpl.type_scale["cover_badge"], color=theme[tpl.slots["cover_badge_text"]])


def _cv_title(slide, theme, tpl, title, brand_name, x, y, w, h, align, color_slot, anchor=None, scale=1.0):
    title_geo = tpl.art["cover"]["title"]
    text = brand_name or title or title_geo["fallback_text"]
    _, tf = _add_textbox(slide, Inches(x), Inches(y), Inches(w), Inches(h), anchor=anchor)
    _apply_align(tf.paragraphs[0], align)
    _apply_text_formatting(tf.paragraphs[0], text, theme, tpl, bold=True, font_size=tpl.type_scale["cover_title"] * scale, color=theme[tpl.slots[color_slot]], font_role="heading")


def _cv_meta(slide, theme, tpl, brand_name, x, y, w, h, align, meta_slot, brand_slot):
    meta_geo = tpl.art["cover"]["meta"]
    _, tf = _add_textbox(slide, Inches(x), Inches(y), Inches(w), Inches(h))
    p = tf.paragraphs[0]
    _apply_align(p, align)
    size = tpl.type_scale["cover_meta"]
    _apply_text_formatting(p, meta_geo["prepared_for"], theme, tpl, font_size=size, color=theme[tpl.slots[meta_slot]])
    _apply_text_formatting(p, brand_name or meta_geo["brand_fallback"], theme, tpl, bold=True, font_size=size, color=theme[tpl.slots[brand_slot]])
    _apply_text_formatting(p, f"{meta_geo['separator']}{meta_geo['powered_by']}", theme, tpl, font_size=size, color=theme[tpl.slots[meta_slot]])


def _cv_short_rule(slide, theme, tpl, x, y, length_in):
    rule_geo = tpl.art["cover"]["rule"]
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(length_in), Pt(rule_geo["thickness_pt"]))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme[tpl.slots["cover_rule"]])
    bar.line.fill.background()


def _cover_centered(prs, title, brand_name, agent_name, theme, tpl, date=None, logo_asset=None):
    """Logo top-center; badge centered above a vertically-centered title; short
    centered rule under it; meta centered near the bottom; date top-right."""
    canvas_w = tpl.geometry["canvas"]["width"]
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["cover"]]))
    _cv_brand_mark(slide, theme, tpl, logo_asset, x=(canvas_w - 4.0) / 2, y=0.4, w=4.0, align="center", wordmark_slot="cover_wordmark", tagline_slot="cover_tagline")
    _cv_date(slide, theme, tpl, date)
    badge_geo = tpl.art["cover"]["badge"]
    _cv_badge(slide, theme, tpl, agent_name, (canvas_w - badge_geo["w"]) / 2, 2.4, badge_geo["w"], badge_geo["h"])
    _cv_title(slide, theme, tpl, title, brand_name, 0.9, 3.2, canvas_w - 1.8, 1.6, "center", "cover_title", anchor=MSO_ANCHOR.MIDDLE)
    _cv_short_rule(slide, theme, tpl, (canvas_w - 1.6) / 2, 5.0, 1.6)
    _cv_meta(slide, theme, tpl, brand_name, 0.9, 6.3, canvas_w - 1.8, 0.6, "center", "cover_meta", "cover_meta_brand")
    return slide


def _cover_sidebar(prs, title, brand_name, agent_name, theme, tpl, date=None, logo_asset=None):
    """Full-height left band (~38% wide) in cover_band_fill holding the logo,
    badge, title, and meta in cover_band_text; the right area is the plain
    slide background, with only the date top-right."""
    canvas_w, canvas_h = tpl.geometry["canvas"]["width"], tpl.geometry["canvas"]["height"]
    band_w = canvas_w * _SIDEBAR_FRACTION
    inner_w = band_w - 1.0
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["cover"]]))
    _cv_rect(slide, 0, 0, band_w, canvas_h, theme[tpl.slots["cover_band_fill"]])
    _cv_brand_mark(slide, theme, tpl, logo_asset, x=0.5, y=0.5, w=inner_w, align="left", wordmark_slot="cover_band_text", tagline_slot="cover_band_text")
    _cv_date(slide, theme, tpl, date)
    badge_geo = tpl.art["cover"]["badge"]
    _cv_badge(slide, theme, tpl, agent_name, 0.5, 2.1, min(badge_geo["w"], inner_w), badge_geo["h"])
    _cv_title(slide, theme, tpl, title, brand_name, 0.5, 3.0, inner_w, 2.4, None, "cover_band_text")
    _cv_meta(slide, theme, tpl, brand_name, 0.5, 5.7, inner_w, 1.3, None, "cover_band_text", "cover_band_text")
    return slide


def _cover_band(prs, title, brand_name, agent_name, theme, tpl, date=None, logo_asset=None):
    """Horizontal cover_band_fill block (~2.2in) across the vertical middle with
    the title inside it in cover_band_text; logo top-left and badge above the
    band, meta below it, date top-right."""
    canvas_w, canvas_h = tpl.geometry["canvas"]["width"], tpl.geometry["canvas"]["height"]
    band_top = (canvas_h - _BAND_HEIGHT_IN) / 2
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["cover"]]))
    _cv_rect(slide, 0, band_top, canvas_w, _BAND_HEIGHT_IN, theme[tpl.slots["cover_band_fill"]])
    logo_geo = tpl.art["cover"]["logo"]
    _cv_brand_mark(slide, theme, tpl, logo_asset, x=logo_geo["x"], y=logo_geo["y"], w=5.0, align="left", wordmark_slot="cover_wordmark", tagline_slot="cover_tagline")
    _cv_date(slide, theme, tpl, date)
    badge_geo = tpl.art["cover"]["badge"]
    _cv_badge(slide, theme, tpl, agent_name, 0.6, band_top - 0.8, badge_geo["w"], badge_geo["h"])
    _cv_title(slide, theme, tpl, title, brand_name, 0.6, band_top, canvas_w - 1.2, _BAND_HEIGHT_IN, None, "cover_band_text", anchor=MSO_ANCHOR.MIDDLE)
    _cv_meta(slide, theme, tpl, brand_name, 0.6, band_top + _BAND_HEIGHT_IN + 0.25, canvas_w - 1.2, 0.5, None, "cover_meta", "cover_meta_brand")
    return slide


def _cover_hero(prs, title, brand_name, agent_name, theme, tpl, date=None, logo_asset=None):
    """Oversized title (cover_title x1.4) in the upper-left ~70%; small logo
    top-left; a compact badge above the title; a short rule; small meta footer.
    All text on the slide background (existing cover_* slots)."""
    canvas_w = tpl.geometry["canvas"]["width"]
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["cover"]]))
    logo_geo = tpl.art["cover"]["logo"]
    _cv_brand_mark(slide, theme, tpl, logo_asset, x=logo_geo["x"], y=logo_geo["y"], w=5.0, align="left", wordmark_slot="cover_wordmark", tagline_slot="cover_tagline")
    _cv_date(slide, theme, tpl, date)
    badge_geo = tpl.art["cover"]["badge"]
    _cv_badge(slide, theme, tpl, agent_name, 0.6, 1.85, badge_geo["w"], 0.4)
    _cv_title(slide, theme, tpl, title, brand_name, 0.6, 2.4, canvas_w * 0.7, 3.0, None, "cover_title", scale=_HERO_TITLE_SCALE)
    _cv_short_rule(slide, theme, tpl, 0.6, 5.6, 1.6)
    _cv_meta(slide, theme, tpl, brand_name, 0.6, 6.7, canvas_w - 1.2, 0.4, None, "cover_meta", "cover_meta_brand")
    return slide


_COVER_LAYOUTS = {
    "classic": _cover_classic,
    "centered": _cover_centered,
    "sidebar": _cover_sidebar,
    "band": _cover_band,
    "hero": _cover_hero,
}


def _create_cover_slide(prs: Presentation, title: str, brand_name: Optional[str], agent_name: Optional[str],
                         theme: dict, tpl: TemplateSpec, date: Optional[str] = None, logo_asset: Optional[Dict[str, Any]] = None):
    """Dispatches to the cover recipe named by tpl.art["cover"]["layout"];
    an omitted or unknown layout renders "classic"."""
    builder = _COVER_LAYOUTS.get(tpl.art["cover"].get("layout", "classic"), _cover_classic)
    return builder(prs, title, brand_name, agent_name, theme, tpl, date=date, logo_asset=logo_asset)


def _create_toc_slide(prs: Presentation, sections: List[Dict[str, Any]], theme: dict, tpl: TemplateSpec):
    """Table of contents — one line per H3 section title. Heading text, list
    box, row spacing, separator glyph, and per-row fallback all come from
    tpl.art["toc"]."""
    toc_art = tpl.art["toc"]
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["toc"]]))
    _add_title_bar(slide, toc_art["heading_text"], theme, tpl)

    lb = toc_art["list_box"]
    _, tf = _add_textbox(slide, Inches(lb["x"]), Inches(lb["y"]), Inches(lb["w"]), Inches(lb["h"]))
    first = True
    for idx, section in enumerate(sections, 1):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(toc_art["item_space_after"])
        _apply_text_formatting(p, f"{idx:02d}", theme, tpl, bold=True, font_size=tpl.type_scale["toc_item"], color=theme[tpl.slots["toc_number"]])
        _apply_text_formatting(p, toc_art["separator"], theme, tpl, bold=True, font_size=tpl.type_scale["toc_item"], color=theme[tpl.slots["toc_separator"]])
        fallback_title = f"{toc_art['section_fallback']} {idx}"
        _add_inline_runs(p, section.get("title") or fallback_title, theme, tpl, base_size=tpl.type_scale["toc_item"], base_bold=True, color=theme[tpl.slots["toc_title"]])
    return slide


def _create_section_title_slide(prs: Presentation, section_title: str, theme: dict, tpl: TemplateSpec, index: int,
                                 logo_asset: Optional[Dict[str, Any]] = None):
    """Section divider slide — ONLY for H3 main sections, centered on a dark
    themed background with a numbered label and accent bar. With a client
    brand_kit logo, a small low-prominence mark sits in the bottom-right
    corner. All decorative coordinates/shape-params come from
    tpl.art["divider"]."""
    divider_art = tpl.art["divider"]
    canvas = tpl.geometry["canvas"]
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["divider"]]))

    num_geo = divider_art["number"]
    _, num_tf = _add_textbox(slide, Inches(num_geo["x"]), Inches(num_geo["y"]), _art_dim(num_geo["w"], canvas["width"]), Inches(num_geo["h"]))
    _apply_align(num_tf.paragraphs[0], num_geo.get("align"))
    _apply_text_formatting(num_tf.paragraphs[0], f"{index:02d}", theme, tpl, bold=True, font_size=tpl.type_scale["divider_number"], color=theme[tpl.slots["divider_number"]])

    title_geo = divider_art["title"]
    _, tf = _add_textbox(slide, Inches(title_geo["x"]), Inches(title_geo["y"]), Inches(title_geo["w"]), Inches(title_geo["h"]))
    _apply_align(tf.paragraphs[0], title_geo.get("align"))
    _add_inline_runs(tf.paragraphs[0], section_title, theme, tpl, base_size=tpl.type_scale["divider_title"], base_bold=True, color=theme[tpl.slots["divider_title"]], font_role="heading")

    bar_geo = divider_art["bar"]
    bar_width = Inches(bar_geo["length"])
    if bar_geo.get("align", "center") == "center":
        bar_left = (Inches(canvas["width"]) - bar_width) // 2
    else:
        bar_left = Inches(0)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, bar_left, Inches(bar_geo["y"]), bar_width, Pt(bar_geo["thickness_pt"]))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme[tpl.slots["divider_bar"]])
    bar.line.fill.background()

    if logo_asset:
        logo_geo = divider_art["logo"]
        width, height = _logo_box_size(logo_asset, tpl, "divider")
        inset = Inches(logo_geo["inset"])
        if logo_geo.get("corner", "bottom-right") == "bottom-right":
            left = Inches(canvas["width"]) - width - inset
            top = Inches(canvas["height"]) - height - inset
        else:
            left, top = inset, inset
        slide.shapes.add_picture(io.BytesIO(logo_asset["bytes"]), left, top, width=width, height=height)

    return slide


def _create_closing_slide(prs: Presentation, theme: dict, tpl: TemplateSpec, date: Optional[str] = None):
    """Decorative box position, anchor, alignment, and the headline copy all
    come from tpl.art["closing"]; the date line shares tpl.art["date_format"]
    with the cover slide."""
    closing_art = tpl.art["closing"]
    box_geo = closing_art["box"]
    date_str = date or datetime.now().strftime(tpl.art["date_format"])
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["closing"]]))
    anchor = _ANCHOR_MAP.get(box_geo.get("anchor"), MSO_ANCHOR.MIDDLE)
    _, tf = _add_textbox(slide, Inches(box_geo["x"]), Inches(box_geo["y"]), Inches(box_geo["w"]), Inches(box_geo["h"]), anchor=anchor)
    p = tf.paragraphs[0]
    _apply_align(p, box_geo.get("align"))
    _apply_text_formatting(p, closing_art["headline_text"], theme, tpl, bold=True, font_size=tpl.type_scale["closing_headline"], color=theme[tpl.slots["closing_headline"]], font_role="heading")

    p2 = tf.add_paragraph()
    _apply_align(p2, box_geo.get("align"))
    _apply_text_formatting(p2, date_str, theme, tpl, font_size=tpl.type_scale["closing_date"], color=theme[tpl.slots["closing_date"]])
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Content slides: bullets / paragraphs / tables / charts
# ─────────────────────────────────────────────────────────────────────────────
def _estimate_item_lines(text: str, chars_per_line: int) -> int:
    """Wrapped-line estimate for one item's text at body font size in the
    content box (~chars_per_line chars/line, from tpl.fit) — each item always
    starts its own paragraph/line, so this is a per-item ceiling, not a
    shared running total."""
    length = len((text or "").strip())
    return max(1, math.ceil(length / chars_per_line))


def _items_estimated_lines(items: List[Dict[str, Any]], chars_per_line: int) -> int:
    return sum(_estimate_item_lines(item.get("text", ""), chars_per_line) for item in items)


def _add_content_slide(prs: Presentation, title: str, items: List[Dict[str, Any]], theme: dict, tpl: TemplateSpec,
                        section_index: int = 1, section_title: str = "", takeaway: Optional[str] = None):
    """`items`: [{"bullet": bool, "text": <raw markdown>, "level": int,
    "is_subsection_label": bool}, ...]. Body geometry comes from
    tpl.geometry["content_body"] (x/top/w/height) — the body is a FIXED size
    (MSO_AUTO_SIZE.NONE), clear of the chrome frame above and the slide number
    below. Callers are expected to have already split `items` to fit within
    _max_lines_per_slide(tpl) (see _pack_clusters_to_slides);
    TEXT_TO_FIT_SHAPE is only a safety net for the rare slide that still
    estimates over budget, so it shrinks rather than overflows.

    `takeaway`, when given, renders in the chrome (see _add_content_chrome)
    and pushes this body box down/shorter by _content_shift_for_takeaway so
    it never collides with it.

    Text is always dark + regular weight (theme text_dark) — only the bullet
    MARKER glyph and a standalone lead-in label (merged subsection title) use
    bold/accent; a bullet whose own text is a lead-in label (ends in ":",
    e.g. "Decision Drivers:") is bold but still dark, never colored."""
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["content"]]))
    _add_content_chrome(slide, tpl, theme, section_index, section_title, title, takeaway=takeaway)

    cb = tpl.geometry["content_body"]
    bullets_geo = tpl.geometry["bullets"]
    spacing = tpl.geometry["spacing"]
    chars_per_line = tpl.fit["chars_per_line"]
    max_lines = _max_lines_per_slide(tpl)

    shift = _content_shift_for_takeaway(tpl, takeaway)
    body_top, body_height = cb["top"] + shift, cb["height"] - shift
    if shift:
        max_lines -= math.ceil(shift / tpl.fit["line_height"])

    _, tf = _add_textbox(slide, Inches(cb["x"]), Inches(body_top), Inches(cb["w"]), Inches(body_height))
    tf.auto_size = (
        MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        if _items_estimated_lines(items, chars_per_line) > max_lines
        else MSO_AUTO_SIZE.NONE
    )
    first = True
    for item in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        level = item.get("level", 0)
        p.level = min(level, 1)  # python-pptx outline level has no visual effect in a plain textbox

        if item.get("is_subsection_label"):
            p.space_after = Pt(spacing["label"]["space_after"])
            p.line_spacing = spacing["label"]["line"]
            _add_inline_runs(p, item.get("text", ""), theme, tpl, base_size=tpl.type_scale["subsection_label"],
                              base_bold=True, color=theme[tpl.slots["label"]])
            continue

        if item.get("bullet"):
            size = _bullet_font_size(level, tpl)
            p.space_after = Pt(spacing["bullet"]["space_after"])
            p.line_spacing = spacing["bullet"]["line"]
            _set_paragraph_indent(p, Inches(bullets_geo["indent_step"] * (level + 1)), Inches(bullets_geo["hanging_indent"]))
            # Only the bullet glyph itself gets the accent color — the body
            # text stays theme text_dark, so gold isn't used for whole lines.
            bullet_run = p.add_run()
            bullet_run.text = "•  "
            bullet_run.font.name = tpl.fonts["body"]
            bullet_run.font.size = _normalize_size(size)
            bullet_run.font.bold = True
            bullet_run.font.color.rgb = _rgb(theme[tpl.slots["bullet_marker"]])
            text = item.get("text", "")
            _add_inline_runs(p, text, theme, tpl, base_size=size, base_bold=_is_lead_in_label(text), color=theme[tpl.slots["body_text"]])
        else:
            size = tpl.type_scale["body"]
            p.space_after = Pt(spacing["paragraph"]["space_after"])
            p.line_spacing = spacing["paragraph"]["line"]
            _add_inline_runs(p, item.get("text", ""), theme, tpl, base_size=size, color=theme[tpl.slots["body_text"]])
    return slide


def _table_height_inches(rows: int, tpl: TemplateSpec) -> float:
    t = tpl.geometry["table"]
    return min(t["row_height"] * rows, t["max_height"])


def _table_note_top_inches(rows: int, tpl: TemplateSpec) -> float:
    """Where a short trailing note goes when merged onto a table's own slide:
    table top + the table's own height + a fixed 0.3in gap. Derived from
    tpl.geometry["table"] so it can never drift from _add_table_to_slide's
    own placement."""
    return tpl.geometry["table"]["top"] + _table_height_inches(rows, tpl) + 0.3


def _add_table_to_slide(slide, table_data: List[List[str]], theme: dict, tpl: TemplateSpec):
    """Native PowerPoint table (not an image): theme-primary header row (white
    text), alternating white / theme bg_light body rows, bold preserved in
    cell text via _add_inline_runs. All geometry comes from
    tpl.geometry["table"]."""
    if not table_data or not table_data[0]:
        return None
    rows = len(table_data)
    cols = len(table_data[0])
    t = tpl.geometry["table"]
    left, top = Inches(t["x"]), Inches(t["top"])
    width, height = Inches(t["w"]), Inches(_table_height_inches(rows, tpl))

    shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = shape.table

    for r, row_data in enumerate(table_data):
        is_header = r == 0
        if is_header:
            bg = theme[tpl.slots["table_header_bg"]]
        else:
            bg = theme[tpl.slots["table_row_a"]] if r % 2 == 0 else theme[tpl.slots["table_row_b"]]
        text_color = theme[tpl.slots["table_header_text"]] if is_header else theme[tpl.slots["body_text"]]
        size = tpl.type_scale["table_header"] if is_header else tpl.type_scale["table_body"]

        for c in range(cols):
            text = row_data[c] if c < len(row_data) else ""
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(bg)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(t["cell_margin_h"])
            cell.margin_right = Inches(t["cell_margin_h"])
            cell.margin_top = Inches(t["cell_margin_v"])
            cell.margin_bottom = Inches(t["cell_margin_v"])
            p = cell.text_frame.paragraphs[0]
            _add_inline_runs(p, str(text), theme, tpl, base_size=size, base_bold=is_header, color=text_color)
    return table


def _add_chart_image_to_slide(slide, chart_json: Any, theme: dict, tpl: TemplateSpec, top_shift: float = 0.0):
    """Renders recharts-style JSON to a matplotlib image (shared renderer) and
    adds it to `slide`, centered, per tpl.geometry["chart"]. `top_shift`
    (inches) pushes the image down — used when the slide's own chrome-level
    takeaway (see _content_shift_for_takeaway) is present; the chart's own
    under-image caption (chart_json's "takeaway" key, a different, older
    field) stays at its fixed position since it never collides either way."""
    data = chart_json
    if isinstance(chart_json, str):
        try:
            data = json.loads(chart_json)
        except Exception:
            data = None

    chart_geo = tpl.geometry["chart"]
    image_bytes = render_chart_image(data, figsize=tuple(chart_geo["figsize"]), palette=tpl.chart_palette) if isinstance(data, dict) else None
    if not image_bytes:
        _, tf = _add_textbox(slide, Inches(2.0), Inches(3.0), Inches(9.3), Inches(1.5))
        title = (data or {}).get("title") if isinstance(data, dict) else None
        _add_inline_runs(tf.paragraphs[0], title or "Chart", theme, tpl, base_size=tpl.type_scale["chart_fallback"], base_bold=True, color=theme[tpl.slots["chart_fallback"]])
        takeaway = (data or {}).get("takeaway") if isinstance(data, dict) else None
        p2 = tf.add_paragraph()
        _apply_text_formatting(p2, takeaway or "[Chart could not be rendered]", theme, tpl, italic=True, font_size=tpl.type_scale["chart_fallback_sub"], color=theme[tpl.slots["chart_takeaway"]])
        return None

    pic_width = Inches(chart_geo["width"])
    left = (Inches(tpl.geometry["canvas"]["width"]) - pic_width) // 2
    top = Inches(chart_geo["top"] + top_shift)
    picture = slide.shapes.add_picture(io.BytesIO(image_bytes), left, top, width=pic_width)

    takeaway = (data or {}).get("takeaway") if isinstance(data, dict) else None
    if takeaway:
        tk = chart_geo["takeaway"]
        _, tf = _add_textbox(slide, Inches(tk["x"]), Inches(tk["y"]), Inches(tk["w"]), Inches(tk["h"]))
        _add_inline_runs(tf.paragraphs[0], takeaway, theme, tpl, base_size=tpl.type_scale["chart_takeaway"], color=theme[tpl.slots["chart_takeaway"]])
    return picture


def _chart_note_top_inches(chart_json: Any, tpl: TemplateSpec, top_shift: float = 0.0) -> float:
    """Where a short trailing note goes when merged onto a chart's own slide:
    below the rendered image (chart.top + top_shift + width scaled by the
    figsize aspect ratio), or below the chart's own takeaway caption box when
    it has one, plus a fixed 0.25in gap. `top_shift` must match whatever was
    passed to _add_chart_image_to_slide for this same slide, or this drifts
    from its actual placement."""
    chart_geo = tpl.geometry["chart"]
    fig_w, fig_h = chart_geo["figsize"]
    bottom = chart_geo["top"] + top_shift + (chart_geo["width"] * fig_h / fig_w)  # image top + height at the rendered width
    data = chart_json
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = None
    if isinstance(data, dict) and data.get("takeaway"):
        bottom = max(bottom, chart_geo["takeaway"]["y"] + 0.35)  # existing takeaway box top, ~1 line
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


def _cluster_lines(cluster: Dict[str, Any], chars_per_line: int) -> int:
    """Line-fit estimate for a whole cluster (parent + its children) — the
    real layout constraint a slide must fit under, since it accounts for
    wrapping instead of just raw word count (see _estimate_item_lines)."""
    return _estimate_item_lines(cluster["parent"]["text"], chars_per_line) + sum(
        _estimate_item_lines(c["text"], chars_per_line) for c in cluster["children"]
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


def _split_oversized_cluster(cluster: Dict[str, Any], max_lines: int, chars_per_line: int) -> List[List[Dict[str, Any]]]:
    """A single cluster too large for one slide alone: splits its CHILDREN
    (the parent itself is never split, and is repeated on each continuation
    slide) into groups that each fit under `max_lines` (a wrapped-line
    estimate, not raw word count — see _estimate_item_lines) alongside that
    repeated parent. Rebalances so a continuation slide is never left with
    just one orphaned child when its neighbor has more than 2 to spare."""
    parent = cluster["parent"]
    children = cluster["children"]
    parent_lines = _estimate_item_lines(parent["text"], chars_per_line)

    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_lines = parent_lines
    for child in children:
        cl = _estimate_item_lines(child["text"], chars_per_line)
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


def _pack_clusters_to_slides(clusters: List[Dict[str, Any]], title: str, max_lines: int, chars_per_line: int) -> List[Dict[str, Any]]:
    """Packs clusters onto content slides. A new slide may only START at a
    cluster boundary — never in the middle of a parent bullet's children —
    so a nested list is never split mid-group. A single cluster that's too
    big to fit a slide alone is split at a child boundary (see
    _split_oversized_cluster); otherwise clusters keep combining onto the
    current slide up to MAX_ITEMS_PER_SLIDE / MAX_COMBINED_SLIDE_WORDS /
    `max_lines` (the template's derived fit ceiling — see
    template_service._max_lines_per_slide).

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
        cl = _cluster_lines(cluster, chars_per_line)
        ci = _cluster_item_count(cluster)

        if cw > MAX_WORDS_PER_SLIDE or cl > max_lines:
            flush()
            groups = _split_oversized_cluster(cluster, max_lines, chars_per_line)
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
            or pending_lines + cl > max_lines
        ):
            flush()

        pending.extend(_cluster_to_items(cluster))
        pending_words += cw
        pending_items += ci
        pending_lines += cl

    flush()
    return slides


def _elements_to_slides(elements: List[Dict[str, Any]], title: str, tpl: TemplateSpec) -> List[Dict[str, Any]]:
    """Chunks a subsection's flat element list into slide specs. Bullet/
    paragraph runs are first grouped into clusters (a level-0 bullet or
    paragraph plus its nested children) and packed cluster-by-cluster (see
    _pack_clusters_to_slides) so a slide can only start at a cluster
    boundary — never orphaning a nested bullet from its parent. Tables and
    charts get their own dedicated slide — UNLESS the content immediately
    following one is a short text block (< 40 words and < 3 bullets) that
    still fits below it vertically, in which case it's attached to that same
    slide as `trailing_items` instead of spilling to a near-empty slide of
    its own. The fit model (chars_per_line, max_lines) and the table/chart
    placement geometry both come from `tpl`."""
    chars_per_line = tpl.fit["chars_per_line"]
    max_lines = _max_lines_per_slide(tpl)
    safe_bottom = tpl.geometry["content_body"]["safe_bottom"]

    slides: List[Dict[str, Any]] = []
    item_run: List[Dict[str, Any]] = []

    def flush_item_run():
        nonlocal item_run
        if item_run:
            slides.extend(_pack_clusters_to_slides(_group_into_clusters(item_run), title, max_lines, chars_per_line))
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
                    _table_note_top_inches(len(el["rows"]), tpl) if el["kind"] == "table"
                    else _chart_note_top_inches(el["chart_json"], tpl)
                )
                merge_ok = (note_top + _estimate_note_height_inches(trailing)) <= safe_bottom

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


def _parse_markdown_to_slides(content: str, tpl: TemplateSpec, default_title: str = "Overview") -> List[Dict[str, Any]]:
    """
    Splits one section's markdown body into slide-sized chunks. Returns a
    list of dicts, each one of:
      {"type": "content", "title": str, "items": [...]}
      {"type": "table", "title": str, "rows": [[...]]}
      {"type": "chart", "title": str, "chart_json": dict}

    `default_title` is the slide heading for content that appears before any
    H4 subsection — normally the parent section's own title. `tpl` supplies
    the fit model and placement geometry used to decide slide splits (see
    _elements_to_slides) — the markdown parsing itself (_parse_subsections,
    _subsection_elements, _merge_sparse_subsections) is template-independent.
    """
    records = _parse_subsections(content)
    for rec in records:
        rec["elements"] = _subsection_elements(rec["raw"])
    records = _merge_sparse_subsections(records)

    slides: List[Dict[str, Any]] = []
    for rec in records:
        title = rec["title"] or default_title
        slides.extend(_elements_to_slides(rec["elements"], title, tpl))
    return slides


def _add_trailing_note_to_slide(slide, items: List[Dict[str, Any]], theme: dict, tpl: TemplateSpec, top_inches: float):
    """Renders a short text block directly below a table/chart on the SAME
    slide, at caption size, instead of letting it spill to its own slide."""
    top = Inches(top_inches)
    height = max(Inches(tpl.geometry["content_body"]["safe_bottom"]) - top, Inches(0.3))
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
            bullet_run.font.name = tpl.fonts["body"]
            bullet_run.font.size = _normalize_size(tpl.type_scale["caption"])
            bullet_run.font.bold = True
            bullet_run.font.color.rgb = _rgb(theme[tpl.slots["bullet_marker"]])
            _add_inline_runs(p, item.get("text", ""), theme, tpl, base_size=tpl.type_scale["caption"], color=theme[tpl.slots["body_text"]])
        else:
            _add_inline_runs(p, item.get("text", ""), theme, tpl, base_size=tpl.type_scale["caption"],
                              base_italic=True, color=theme[tpl.slots["trailing_note_text"]])


def _create_section_slides(prs: Presentation, section_title: str, blocks: List[SlideBlock], theme: dict, tpl: TemplateSpec,
                            section_index: int, slide_counter: "itertools.count",
                            logo_asset: Optional[Dict[str, Any]] = None):
    """Section divider slide (H3), then one slide per already render-ready
    block. `blocks` is planned (and paginated) upstream in generate_pptx —
    this function no longer plans anything itself."""
    _create_section_title_slide(prs, section_title, theme, tpl, section_index, logo_asset=logo_asset)

    for block in blocks:
        slide = _render_block(prs, block, theme, tpl, section_index)
        _add_slide_number(slide, next(slide_counter), theme, tpl)


def _render_bullets_block(prs: Presentation, block: SlideBlock, theme: dict, tpl: TemplateSpec, section_index: int = 1):
    return _add_content_slide(prs, block.data["title"], block.data["items"], theme, tpl, section_index,
                               block.source_section, takeaway=block.data.get("takeaway"))


def _render_table_block(prs: Presentation, block: SlideBlock, theme: dict, tpl: TemplateSpec, section_index: int = 1):
    data = block.data
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["table"]]))
    _add_content_chrome(slide, tpl, theme, section_index, block.source_section, data["title"])
    _add_table_to_slide(slide, data["rows"], theme, tpl)
    if data.get("trailing_items"):
        top = _table_note_top_inches(len(data["rows"]), tpl)
        _add_trailing_note_to_slide(slide, data["trailing_items"], theme, tpl, top)
    return slide


def _render_chart_block(prs: Presentation, block: SlideBlock, theme: dict, tpl: TemplateSpec, section_index: int = 1):
    data = block.data
    takeaway = data.get("takeaway")
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["chart"]]))
    _add_content_chrome(slide, tpl, theme, section_index, block.source_section, data["title"], takeaway=takeaway)
    shift = _content_shift_for_takeaway(tpl, takeaway)
    _add_chart_image_to_slide(slide, data["chart_json"], theme, tpl, top_shift=shift)
    if data.get("trailing_items"):
        top = _chart_note_top_inches(data["chart_json"], tpl, top_shift=shift)
        _add_trailing_note_to_slide(slide, data["trailing_items"], theme, tpl, top)
    return slide


def _render_stat_row_block(prs: Presentation, block: SlideBlock, theme: dict, tpl: TemplateSpec, section_index: int = 1):
    """2-4 KPI tiles as rounded-rect cards. Tile 1 = hero (filled primary,
    light text); tiles 2..N = neutral tile background with normal slot colors.
    Each tile: uppercase label at top, big value center, sublabel at bottom."""
    data = block.data
    stats = data["stats"]
    n = len(stats)
    ts = tpl.type_scale
    cb = tpl.geometry["content_body"]
    tg = tpl.geometry.get("stat_tile", {})
    gap = tg.get("gap", 0.25)
    pad = tg.get("pad", 0.3)
    corner_r = tg.get("corner_radius", 0.08)
    tile_h = tg.get("height", 2.4)

    takeaway = data.get("takeaway")
    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["content"]]))
    _add_content_chrome(slide, tpl, theme, section_index, block.source_section, data.get("heading") or block.source_section,
                         takeaway=takeaway)

    takeaway_shift = _content_shift_for_takeaway(tpl, takeaway)
    top, avail = cb["top"] + takeaway_shift, cb["height"] - takeaway_shift
    if data.get("context"):
        ctx_h = ts["body"] / 72 * 2 * 1.4
        _, ctx_tf = _add_textbox(slide, Inches(cb["x"]), Inches(top + 0.2), Inches(cb["w"]), Inches(ctx_h))
        ctx_tf.auto_size = MSO_AUTO_SIZE.NONE
        ctx_tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        _add_inline_runs(ctx_tf.paragraphs[0], data["context"], theme, tpl, base_size=ts["body"], color=theme[tpl.slots["body_text"]])
        shift = ctx_h + 0.2
        top, avail = top + shift, avail - shift

    tile_w = (cb["w"] - gap * (n - 1)) / n
    row_top = top + max((avail - tile_h) / 2, 0)

    label_h = ts["stat_label"] / 72 * 2.0
    value_h = ts["stat_value"] / 72 * 1.8
    sub_h = ts["stat_sublabel"] / 72 * 2.0

    for i, stat in enumerate(stats):
        x = cb["x"] + i * (tile_w + gap)
        is_hero = (i == 0)

        fill_hex = theme[tpl.slots["stat_hero_bg"]] if is_hero else theme[tpl.slots["stat_tile_bg"]]
        rect = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x), Inches(row_top), Inches(tile_w), Inches(tile_h),
        )
        rect.fill.solid()
        rect.fill.fore_color.rgb = _rgb(fill_hex)
        rect.line.fill.background()
        shorter = min(tile_w, tile_h)
        if shorter > 0:
            rect.adjustments[0] = corner_r / shorter

        if is_hero:
            val_c = lbl_c = sub_c = theme[tpl.slots["stat_hero_text"]]
        else:
            val_c = theme[tpl.slots["stat_value"]]
            lbl_c = theme[tpl.slots["stat_label"]]
            sub_c = theme[tpl.slots["stat_sublabel"]]

        ix, iw = x + pad, tile_w - 2 * pad
        iy = row_top + pad
        ih = tile_h - 2 * pad

        lbl_text = (stat.get("label") or "").upper()
        if lbl_text:
            _, tf = _add_textbox(slide, Inches(ix), Inches(iy), Inches(iw), Inches(label_h))
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            run = _apply_text_formatting(tf.paragraphs[0], lbl_text, theme, tpl, font_size=ts["stat_label"], color=lbl_c, font_role="body")
            run._r.get_or_add_rPr().set("spc", "100")

        val_text = stat.get("value", "")
        if val_text:
            val_top = iy + (ih - value_h) / 2
            _, tf = _add_textbox(slide, Inches(ix), Inches(val_top), Inches(iw), Inches(value_h))
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            _apply_text_formatting(tf.paragraphs[0], val_text, theme, tpl, bold=True, font_size=ts["stat_value"], color=val_c, font_role="heading")

        sub_text = stat.get("sublabel", "")
        if sub_text:
            sub_top = iy + ih - sub_h
            _, tf = _add_textbox(slide, Inches(ix), Inches(sub_top), Inches(iw), Inches(sub_h))
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            _apply_text_formatting(tf.paragraphs[0], sub_text, theme, tpl, font_size=ts["stat_sublabel"], color=sub_c, font_role="body")

    return slide


def _render_timeline_block(prs: Presentation, block: SlideBlock, theme: dict, tpl: TemplateSpec, section_index: int = 1):
    """3-6 horizontal chevrons graduating from timeline_start to timeline_end,
    with phase title/description/deliverable columns below and an optional
    footer note band."""
    data = block.data
    phases = data["phases"]
    n = len(phases)
    ts = tpl.type_scale
    cb = tpl.geometry["content_body"]
    tg = tpl.geometry.get("timeline", {})
    chev_h = tg.get("chevron_height", 0.7)
    overlap = tg.get("overlap", 0.1)
    row_top = tg.get("row_top", 2.3)
    body_gap = tg.get("body_gap", 0.2)
    footer_h = tg.get("footer_height", 0.9)

    slide = _new_slide(prs, _rgb(theme[tpl.backgrounds["content"]]))
    _add_content_chrome(slide, tpl, theme, section_index, block.source_section, data.get("heading") or block.source_section,
                         takeaway=data.get("takeaway"))

    # No _content_shift_for_takeaway call here: the chevron row already
    # starts at row_top (2.3in by default), well below the takeaway band, so
    # it never needs to move for one.
    chev_w = (cb["w"] + (n - 1) * overlap) / n
    start_rgb = _hex_to_rgb(theme[tpl.slots["timeline_start"]])
    end_rgb = _hex_to_rgb(theme[tpl.slots["timeline_end"]])

    col_w = cb["w"] / n
    col_top = row_top + chev_h + body_gap
    body_bottom = cb["safe_bottom"] - (footer_h + 0.15 if data.get("footer_note") else 0)

    for i, phase in enumerate(phases):
        cx = cb["x"] + i * (chev_w - overlap)
        t = i / max(n - 1, 1)
        fr = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
        fg = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
        fb = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
        fill_hex = f"{fr:02X}{fg:02X}{fb:02X}"

        l_fill = _luminance(fill_hex)
        l_lt = _luminance(theme["text_light"])
        l_dk = _luminance(theme["text_dark"])
        r_lt = (max(l_fill, l_lt) + 0.05) / (min(l_fill, l_lt) + 0.05)
        r_dk = (max(l_fill, l_dk) + 0.05) / (min(l_fill, l_dk) + 0.05)
        text_hex = theme["text_light"] if r_lt > r_dk else theme["text_dark"]

        chev = slide.shapes.add_shape(
            MSO_SHAPE.CHEVRON, Inches(cx), Inches(row_top), Inches(chev_w), Inches(chev_h),
        )
        chev.fill.solid()
        chev.fill.fore_color.rgb = _rgb(fill_hex)
        chev.line.fill.background()
        if chev_w > 0:
            chev.adjustments[0] = max(0.08, min(0.25, 0.4 / chev_w))

        chev.text_frame.word_wrap = True
        chev.text_frame.auto_size = MSO_AUTO_SIZE.NONE
        p = chev.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        label_text = phase.get("label", "").upper()
        _apply_text_formatting(p, label_text, theme, tpl, bold=True,
                               font_size=ts.get("timeline_phase_label", 12), color=text_hex, font_role="body")
        if phase.get("period"):
            p2 = chev.text_frame.add_paragraph()
            p2.alignment = PP_ALIGN.CENTER
            _apply_text_formatting(p2, phase["period"], theme, tpl,
                                   font_size=max(ts.get("timeline_phase_label", 12) - 2, 8), color=text_hex, font_role="body")

        col_x = cb["x"] + i * col_w + 0.1
        cw = col_w - 0.2
        y = col_top

        title_text = phase.get("title", "")
        if title_text:
            t_h = ts.get("timeline_phase_title", 14) / 72 * 2.5
            _, tf = _add_textbox(slide, Inches(col_x), Inches(y), Inches(cw), Inches(t_h))
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.word_wrap = True
            _apply_text_formatting(tf.paragraphs[0], title_text, theme, tpl, bold=True,
                                   font_size=ts.get("timeline_phase_title", 14),
                                   color=theme[tpl.slots["timeline_body"]], font_role="body")
            y += t_h

        desc_text = phase.get("description", "")
        if desc_text:
            d_h = min(ts.get("timeline_body", 11) / 72 * 4.0, body_bottom - y - 0.3)
            if d_h > 0.2:
                _, tf = _add_textbox(slide, Inches(col_x), Inches(y), Inches(cw), Inches(d_h))
                tf.auto_size = MSO_AUTO_SIZE.NONE
                tf.word_wrap = True
                _apply_text_formatting(tf.paragraphs[0], desc_text, theme, tpl,
                                       font_size=ts.get("timeline_body", 11),
                                       color=theme[tpl.slots["timeline_body"]], font_role="body")
                y += d_h

        deliv_text = phase.get("deliverable", "")
        if deliv_text and y < body_bottom - 0.3:
            dl_h = min(ts.get("timeline_deliverable", 11) / 72 * 3.0, body_bottom - y)
            _, tf = _add_textbox(slide, Inches(col_x), Inches(y), Inches(cw), Inches(dl_h))
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = "DELIVERABLE"
            run.font.name = tpl.fonts["body"]
            run.font.size = Pt(max(ts.get("timeline_deliverable", 11) - 1, 8))
            run.font.bold = True
            run.font.color.rgb = _rgb(theme[tpl.slots["timeline_deliverable_label"]])
            p2 = tf.add_paragraph()
            _apply_text_formatting(p2, deliv_text, theme, tpl,
                                   font_size=ts.get("timeline_deliverable", 11),
                                   color=theme[tpl.slots["timeline_body"]], font_role="body")

    if data.get("footer_note"):
        ft = cb["safe_bottom"] - footer_h
        rect = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cb["x"]), Inches(ft), Inches(cb["w"]), Inches(footer_h),
        )
        rect.fill.solid()
        rect.fill.fore_color.rgb = _rgb(theme[tpl.slots["timeline_footer_bg"]])
        rect.line.fill.background()
        shorter = min(cb["w"], footer_h)
        if shorter > 0:
            rect.adjustments[0] = 0.08 / shorter
        _, tf = _add_textbox(slide, Inches(cb["x"] + 0.3), Inches(ft + 0.15),
                             Inches(cb["w"] - 0.6), Inches(footer_h - 0.3))
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.word_wrap = True
        _add_inline_runs(tf.paragraphs[0], data["footer_note"], theme, tpl,
                         base_size=ts.get("timeline_body", 11),
                         color=theme[tpl.slots["timeline_body"]])

    return slide


def _render_block(prs: Presentation, block: SlideBlock, theme: dict, tpl: TemplateSpec, section_index: int = 1):
    """Dispatches a planned SlideBlock to its component renderer and returns
    the new slide. An unknown component renders as bullets (forward-safety
    for components a future planner may emit). `section_index` is the
    section's 1-based running number (threaded from _create_section_slides,
    which already iterates sections in order) — every renderer passes it to
    _add_content_chrome for the eyebrow's "<NN> · <SECTION>" line."""
    if block.component == COMPONENT_TABLE:
        return _render_table_block(prs, block, theme, tpl, section_index)
    if block.component == COMPONENT_CHART:
        return _render_chart_block(prs, block, theme, tpl, section_index)
    if block.component == COMPONENT_STAT_ROW:
        return _render_stat_row_block(prs, block, theme, tpl, section_index)
    if block.component == COMPONENT_TIMELINE:
        return _render_timeline_block(prs, block, theme, tpl, section_index)
    return _render_bullets_block(prs, block, theme, tpl, section_index)


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
    unchanged from the plain report-type theme. An optional `template_id`
    (str) selects a visual TemplateSpec (see template_service.get_template) —
    fonts, type scale, a base color palette + per-slide-kind background slot
    mapping, and now box geometry/spacing/bullet-indent plus the line-wrap
    fit model (see _max_lines_per_slide); cover/divider/closing decorative
    art and the content-packing budgets stay fixed. The template's palette is
    a lower-priority base than brand_kit/extracted_palette (passed as
    `_resolve_theme(..., base=tpl.palette)`), never above them. An unset or
    unknown id resolves to DEFAULT_TEMPLATE, which reproduces today's look
    exactly.
    """
    title = report_data.get("title") or "Strategic Intelligence Report"
    content = report_data.get("content") or ""
    brand_name = report_data.get("brand_name")
    agent_name = report_data.get("agent_name") or report_data.get("agent_type")
    date = report_data.get("created_at")
    brand_kit = report_data.get("brand_kit")
    extracted_palette = report_data.get("extracted_palette")
    tpl = get_template(report_data.get("template_id"))
    theme = _resolve_theme(brand_kit, extracted_palette, agent_name or "default", base=tpl.palette)
    logo_asset = _load_logo_asset(brand_kit)

    sections = _split_into_sections(content)

    # Build the section IR ONCE, upstream of rendering. Flag OFF routes through
    # the exact same plan_section call today's renderer already made, so its
    # output (and therefore the deck) is unchanged. Flag ON asks the LLM
    # planner instead, grounded against each section's own deterministic chart
    # blocks and falling back to plan_section per-section on any failure.
    _llm_flag = slide_planner.SLIDE_PLANNER_LLM
    logger.info("[slide_planner] flag=%s path=%s", _llm_flag, "llm" if _llm_flag else "deterministic")

    if _llm_flag:
        chart_blocks = {
            s["title"]: [b for b in plan_section(s["content"], s["title"], tpl) if b.component == COMPONENT_CHART]
            for s in sections
        }
        section_plans = plan_report_llm(
            [(s["title"], s["content"]) for s in sections],
            chart_blocks,
            slide_planner._default_llm_completion,
            tpl,
        )
    else:
        section_plans = [
            SectionPlan(section_title=s["title"], blocks=plan_section(s["content"], s["title"], tpl))
            for s in sections
        ]

    # Pagination pass: a long bullets block (arbitrary-length when LLM-planned)
    # is split across one-or-more fitted slides via the same packer the
    # deterministic path already uses. Non-bullets blocks pass through as-is.
    section_plans = [
        SectionPlan(section_title=sp.section_title, blocks=paginate_blocks(sp.blocks, tpl))
        for sp in section_plans
    ]

    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])

    _create_cover_slide(prs, title, brand_name, agent_name, theme, tpl, date=date, logo_asset=logo_asset)
    _create_toc_slide(prs, sections, theme, tpl)

    slide_counter = itertools.count(1)
    for idx, sp in enumerate(section_plans, 1):
        _create_section_slides(prs, sp.section_title, sp.blocks, theme, tpl, idx, slide_counter, logo_asset=logo_asset)

    _create_closing_slide(prs, theme, tpl, date=date)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
