"""
Template Service
=================
Loads and caches the PPTX visual-template catalog from
backend/data/pptx_templates.json. Mirrors registry_service.py's lazy-cache /
fail-to-empty pattern so a missing or malformed templates file degrades to
the built-in default look instead of breaking export.

Step 1 added `fonts` and `type_scale` (the font family and the ten named
sizes pptx_service used to read off its own module constants). Step 2 added
`palette` and `backgrounds` (base color slots + which slot each slide kind's
background reads from). Step 3 added `geometry` (box coordinates/dimensions,
spacing, bullet indent) and `fit` (the line-wrap estimate model) — the
layout values pptx_service used to read off its own module constants. Step 4a
extends `type_scale` with every remaining inline font-size literal, and adds
`slots` (every remaining per-ELEMENT foreground/fill color — bullet marker,
table header/row fills, cover/divider/closing/TOC text colors — as a name ->
one-of-the-9-theme-slots mapping, distinct from `backgrounds`, which only
covers whole-SLIDE background fills). Step 4b adds `art` — every remaining
decorative coordinate, shape parameter, logo max-box, and copy string in the
four "chrome" slide builders (cover, section-divider, closing, TOC). The
content-packing BUDGETS (max words/items, sparse/trailing thresholds) and
markdown parsing stay exactly where they are today (pptx_service.py module
constants).
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.chart_renderer import EXECUTIVE_COLORS

logger = logging.getLogger(__name__)

TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "data" / "pptx_templates.json"

_cache: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class TemplateSpec:
    """The typed shape pptx_service consumes.
    - `fonts`: "heading"/"body" keys.
    - `type_scale`: the ten named size slots, in points (plain floats —
      callers wrap with pptx.util.Pt via _normalize_size).
    - `palette`: None, or a (possibly partial) dict using the same 9 slot
      keys as a brand_theme.REPORT_THEMES entry (hex strings, no '#'). Passed
      as `_resolve_theme(..., base=palette)` — brand_kit/extracted_palette
      still win over it; None means "defer entirely to the per-agent
      REPORT_THEMES color, as today."
    - `backgrounds`: maps a slide kind ("cover"/"divider"/"closing"/"toc"/
      "content"/"table"/"chart") to which of the 9 theme slots that slide's
      background reads from.
    - `geometry`: nested dict of box coordinates/dimensions (inches, plain
      floats), spacing, and bullet indent — see DEFAULT_TEMPLATE below for
      the exact shape (canvas, title_bar, slide_number, content_body,
      bullets, spacing, table, chart).
    - `fit`: {"chars_per_line": int, "line_height": float} — the line-wrap
      estimate model pptx_service's packing/splitting logic uses to decide
      how much content fits one slide. See _max_lines_per_slide().
    - `slots`: maps an element name (e.g. "title", "bullet_marker",
      "table_row_b", "cover_title") to one of the 9 theme slot keys
      (primary/secondary/accent/bg_dark/bg_light/bg_white/text_dark/
      text_light/text_muted). The actual hex always comes from the resolved
      theme (brand_kit/extracted_palette/template palette/report-type), so
      this only controls WHICH slot an element reads, never a literal color —
      brand precedence is unaffected. Distinct from `backgrounds`, which maps
      a slide KIND to its whole-slide background slot; `slots` covers every
      other per-element foreground/fill color.
    - `art`: nested dict of decorative coordinates/shape-params/copy-strings
      for the cover, section-divider, closing, and TOC "chrome" slides, plus
      a shared `date_format` strftime string — see DEFAULT_TEMPLATE below for
      the exact shape. Geometry for content/table/chart slides lives in
      `geometry` instead (Step 3); `art` is specifically the one-off
      decorative layout of the four chrome slide builders.
    - `chart_palette`: ordered list of hex color strings (with or without
      the leading '#' — chart_renderer normalizes) used as the series color
      list for every exported chart (bar/line/area/radar/pie/scatter),
      cycling if there are more series than colors. DEFAULT_TEMPLATE's is
      chart_renderer.EXECUTIVE_COLORS verbatim, so the default template's
      charts are byte-identical to today's."""
    id: str
    name: str
    fonts: Dict[str, str]
    type_scale: Dict[str, float]
    palette: Optional[Dict[str, str]] = None
    backgrounds: Dict[str, str] = field(default_factory=dict)
    geometry: Dict[str, Any] = field(default_factory=dict)
    fit: Dict[str, Any] = field(default_factory=dict)
    slots: Dict[str, str] = field(default_factory=dict)
    art: Dict[str, Any] = field(default_factory=dict)
    chart_palette: List[str] = field(default_factory=lambda: list(EXECUTIVE_COLORS))


# Values here MUST equal pptx_service's old module-level *_FONT_SIZE
# constants, the old hardcoded per-kind bg_dark/bg_light/bg_white literals,
# and the old hardcoded geometry/fit constants, exactly — this is what makes
# an unset/unknown template_id reproduce today's deck exactly. See
# test_template_service.py.
DEFAULT_TEMPLATE = TemplateSpec(
    id="default",
    name="Default",
    fonts={"heading": "Calibri", "body": "Calibri"},
    type_scale={
        "title": 26,
        "subtitle": 20,
        "body": 15,
        "subsection_label": 16,
        "sub_bullet": 13.5,
        "subsub_bullet": 12.5,
        "table_header": 11,
        "table_body": 10.5,
        "caption": 12,
        "slide_number": 9,
        # Step 4a — every remaining inline font-size literal pptx_service
        # used to hardcode directly at the call site.
        "cover_title": 32,
        "divider_title": 40,
        "closing_headline": 26,
        "closing_date": 13,
        "titlebar_subtitle": 16,
        "toc_item": 16,
        "divider_number": 16,
        "cover_wordmark": 18,
        "cover_tagline": 11,
        "cover_badge": 11,
        "cover_date": 11,
        "cover_meta": 13,
        "chart_takeaway": 12,
        "chart_fallback": 16,
        "chart_fallback_sub": 13,
        # stat_row component (big-number callouts)
        "stat_value": 40,
        "stat_label": 14,
        "stat_sublabel": 11,
        # timeline component
        "timeline_phase_label": 12,
        "timeline_phase_title": 14,
        "timeline_body": 11,
        "timeline_deliverable": 11,
    },
    palette=None,
    backgrounds={
        "cover": "bg_dark",
        "divider": "bg_dark",
        "closing": "bg_dark",
        "toc": "bg_light",
        "content": "bg_white",
        "table": "bg_white",
        "chart": "bg_white",
    },
    geometry={
        "canvas": {"width": 13.333, "height": 7.5},
        "title_bar": {
            "height": 0.7,
            "accent_bar": {"on": True, "width": 0.18, "side": "left"},
            "title_box": {"x": 0.6, "y": 0.35, "w": 12.0},
            "subtitle_box": {"x": 0.6, "y": 1.0, "w": 12.0, "h": 0.5},
        },
        "slide_number": {
            "on": True, "w": 0.8, "h": 0.35,
            "x_from_right": 1.0, "y_from_bottom": 0.45, "align": "right",
        },
        "content_body": {"x": 0.8, "top": 1.35, "w": 11.5, "height": 5.25, "safe_bottom": 6.7},
        "bullets": {"indent_step": 0.3, "max_level": 2, "hanging_indent": -0.25},
        "spacing": {
            "label": {"space_after": 10, "line": 1.2},
            "bullet": {"space_after": 8, "line": 1.2},
            "paragraph": {"space_after": 10, "line": 1.2},
        },
        "table": {
            "x": 0.8, "top": 1.7, "w": 11.7,
            "row_height": 0.5, "max_height": 5.1,
            "cell_margin_h": 0.1, "cell_margin_v": 0.05,
        },
        "chart": {
            "width": 8.0, "top": 1.6, "figsize": [9, 5],
            "takeaway": {"x": 1.2, "y": 6.7, "w": 10.9, "h": 0.6},
        },
        "stat_tile": {"gap": 0.25, "pad": 0.3, "corner_radius": 0.08, "height": 2.4},
        "timeline": {"chevron_height": 0.7, "overlap": 0.1, "row_top": 2.3, "body_gap": 0.2, "footer_height": 0.9},
    },
    fit={"chars_per_line": 98, "line_height": 0.3},
    slots={
        "title": "primary",
        "titlebar_subtitle": "accent",
        "accent_bar": "primary",
        "slide_number": "text_muted",
        "bullet_marker": "accent",
        "body_text": "text_dark",
        "label": "text_dark",
        "table_header_bg": "primary",
        "table_header_text": "text_light",
        "table_row_a": "bg_light",
        "table_row_b": "bg_white",
        "chart_takeaway": "text_muted",
        "chart_fallback": "text_dark",
        "cover_title": "text_light",
        "cover_wordmark": "text_light",
        "cover_tagline": "accent",
        "cover_date": "secondary",
        "cover_badge_bg": "accent",
        "cover_badge_text": "text_light",
        "cover_rule": "accent",
        "cover_meta": "secondary",
        "divider_number": "accent",
        "divider_title": "text_light",
        "divider_bar": "accent",
        "closing_headline": "text_light",
        "closing_date": "accent",
        "toc_number": "primary",
        "toc_title": "text_dark",
        # Found during the sweep, not in the original 28-name list — flagged
        # in the Step 4a report:
        "cover_meta_brand": "text_light",    # the bold brand-name run in the cover meta line (its own color, distinct from the other two "cover_meta" runs)
        "toc_separator": "accent",           # the "   •   " glyph between a TOC row's index number and its title
        "trailing_note_text": "text_muted",  # a short italic paragraph note merged below a table/chart (the non-bullet path)
        # Cover layout recipes "sidebar"/"band" fill a block with cover_band_fill
        # and put cover_band_text on it (text is checked against the fill, not
        # the slide background). Unused by the "classic" layout.
        "cover_band_fill": "bg_dark",
        "cover_band_text": "text_light",
        # stat_row component: KPI tiles drawn on the "content" background.
        "stat_value": "primary",
        "stat_label": "text_dark",
        "stat_sublabel": "text_muted",
        "stat_separator": "accent",
        "stat_tile_bg": "bg_light",
        "stat_hero_bg": "primary",
        "stat_hero_text": "text_light",
        # timeline component: chevron ramp, body text, deliverable label, footer
        "timeline_start": "bg_light",
        "timeline_end": "primary",
        "timeline_deliverable_label": "accent",
        "timeline_body": "text_dark",
        "timeline_footer_bg": "bg_light",
    },
    art={
        # Shared by the cover and closing slides' date line.
        "date_format": "%B %d, %Y",
        "cover": {
            # Cover composition recipe: classic | centered | sidebar | band | hero.
            # Omitted/unknown renders "classic".
            "layout": "classic",
            "logo": {"x": 0.6, "y": 0.4, "max_h": 1.2, "max_w": 4.0},
            "wordmark": {"text": "StratAI", "x": 0.6, "y": 0.5, "w": 4.0, "h": 0.6},
            "tagline": {"text": "STRATEGIC MARKET INTELLIGENCE", "x": 0.6, "y": 1.0, "w": 5.0, "h": 0.4},
            "date": {"x": 9.0, "y": 0.5, "w": 3.7, "h": 0.6, "align": "right"},
            "badge": {
                "x": 0.6, "y": 1.7, "w": 3.8, "h": 0.5, "rounded": True,
                "label": "EXECUTIVE STRATEGY DOCUMENT",
                # Found during the sweep (not in the original example dict):
                # the " REPORT" suffix appended to an agent name, e.g.
                # "BRAND POSITIONING REPORT".
                "agent_suffix": "REPORT",
            },
            "rule": {"y": 3.0, "thickness_pt": 4, "width": "full"},
            "title": {
                "x": 0.6, "y": 3.3, "w": 11.5, "h": 1.6,
                # None == today's actual behavior: no .alignment is ever set
                # on the cover title paragraph (python-pptx's own default).
                "align": None,
                # Found during the sweep: the fallback title text used when
                # report_data has none.
                "fallback_text": "Strategic Intelligence Report",
            },
            "meta": {
                "x": 0.6, "y": 4.9, "w": 11.5, "h": 0.5,
                "prepared_for": "Prepared for ",
                # Found during the sweep: the fallback brand name, and the
                # " • " separator joining it to the "powered by" copy.
                "brand_fallback": "StratAI Intelligence",
                "separator": " • ",
                "powered_by": "Powered by StratAI Multi-Agent Strategy Engine",
            },
        },
        "divider": {
            # Found during the sweep: the number box's own x/w/h — the
            # original request only named its y.
            "number": {"x": 0.0, "y": 2.5, "w": "full", "h": 0.5, "align": "center"},
            "title": {"x": 0.6, "y": 3.0, "w": 12.1, "h": 1.4, "align": "center"},
            "bar": {"y": 4.5, "length": 1.6, "thickness_pt": 4, "align": "center"},
            "logo": {"max_h": 0.6, "max_w": 2.0, "inset": 0.4, "corner": "bottom-right"},
        },
        "closing": {
            "box": {"x": 1.0, "y": 3.0, "w": 11.3, "h": 1.5, "anchor": "middle", "align": "center"},
            "headline_text": "Generated by StratAI",
        },
        "toc": {
            # Found during the sweep: the TOC's own title-bar heading text,
            # and the per-row fallback title used when a section has none.
            "heading_text": "Table of Contents",
            "list_box": {"x": 1.0, "y": 1.8, "w": 11.3, "h": 5.0},
            "item_space_after": 10,
            "separator": "   •   ",
            "section_fallback": "Section",
        },
    },
    chart_palette=EXECUTIVE_COLORS,
)


def _max_lines_per_slide(tpl: TemplateSpec) -> int:
    """The fit model's derived ceiling: how many wrapped text lines fit in
    one content body before text would have to shrink or overflow. A pure
    function of tpl.geometry["content_body"]["height"] and
    tpl.fit["line_height"] — using this single helper everywhere (instead of
    inlining the division) is what keeps every call site in sync with the
    same formula. For DEFAULT_TEMPLATE this equals the old module-level
    MAX_LINES_PER_SLIDE constant (17) exactly."""
    return int(tpl.geometry["content_body"]["height"] / tpl.fit["line_height"])


def _load_templates() -> Dict[str, Any]:
    """Reads and parses the templates JSON file. Never raises — falls back to
    an empty registry; get_template() still returns DEFAULT_TEMPLATE."""
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("pptx_templates.json root must be a JSON object")
        data.setdefault("templates", [])
        return data
    except Exception as e:
        logger.error(f"[template_service] Failed to load {TEMPLATES_PATH}: {e}")
        return {"templates": []}


def _get_cache() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _load_templates()
    return _cache


def get_registry() -> Dict[str, Any]:
    """Returns the full raw registry dict: {"templates": [...]}."""
    return _get_cache()


def get_templates(enabled_only: bool = True) -> List[Dict[str, Any]]:
    """Returns the list of raw template entry dicts, optionally filtered to
    only enabled templates."""
    templates = _get_cache().get("templates", [])
    if enabled_only:
        return [t for t in templates if t.get("enabled", True)]
    return templates


def _deep_merge(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recursively merges `override` onto a copy of `base` — a nested dict
    value merges key-by-key instead of replacing the whole sub-dict, so a
    template JSON entry that only overrides e.g. geometry["chart"]["top"]
    doesn't silently drop the rest of geometry["chart"]."""
    if not override:
        return dict(base)
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _entry_to_spec(entry: Dict[str, Any]) -> TemplateSpec:
    """Merges a (possibly partial) JSON template entry over DEFAULT_TEMPLATE
    so a template that only overrides a couple of fields still produces a
    complete, valid TemplateSpec. `palette` is passed through as-is (None or
    a possibly-partial dict) rather than merged — _resolve_theme is what
    fills any gaps against the per-agent report theme, not this function."""
    fonts = {**DEFAULT_TEMPLATE.fonts, **(entry.get("fonts") or {})}
    type_scale = {**DEFAULT_TEMPLATE.type_scale, **(entry.get("type_scale") or {})}
    palette = entry.get("palette")
    backgrounds = {**DEFAULT_TEMPLATE.backgrounds, **(entry.get("backgrounds") or {})}
    geometry = _deep_merge(DEFAULT_TEMPLATE.geometry, entry.get("geometry"))
    fit = _deep_merge(DEFAULT_TEMPLATE.fit, entry.get("fit"))
    slots = {**DEFAULT_TEMPLATE.slots, **(entry.get("slots") or {})}
    art = _deep_merge(DEFAULT_TEMPLATE.art, entry.get("art"))
    chart_palette = entry.get("chart_palette") or DEFAULT_TEMPLATE.chart_palette
    return TemplateSpec(
        id=entry.get("id") or DEFAULT_TEMPLATE.id,
        name=entry.get("name") or DEFAULT_TEMPLATE.name,
        fonts=fonts,
        type_scale=type_scale,
        palette=palette if isinstance(palette, dict) else None,
        backgrounds=backgrounds,
        geometry=geometry,
        fit=fit,
        slots=slots,
        art=art,
        chart_palette=chart_palette,
    )


def get_template(template_id: Optional[str]) -> TemplateSpec:
    """Returns the TemplateSpec for `template_id` (looked up by `id`,
    regardless of `enabled`), or DEFAULT_TEMPLATE when template_id is
    None/empty, doesn't match any entry, or the registry file is
    missing/broken — export must never fail over a bad template id."""
    if not template_id:
        return DEFAULT_TEMPLATE
    for entry in _get_cache().get("templates", []):
        if entry.get("id") == template_id:
            return _entry_to_spec(entry)
    return DEFAULT_TEMPLATE


def reload_templates() -> Dict[str, Any]:
    """Re-reads the templates file from disk and refreshes the module cache.
    For dev use."""
    global _cache
    _cache = _load_templates()
    return _cache
