"""Tests for Step 7 — the shared content-slide chrome (_add_content_chrome):
an eyebrow/kicker ("<NN> · <SECTION>"), the heading with a hairline rule
beneath it, and a source-footer slot, used by every content-kind renderer
(bullets/table/chart/stat_row/timeline) in place of the bare title bar. Run
with: cd backend && python -m pytest tests/test_content_chrome.py -v
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from backend.services.brand_theme import _luminance
from backend.services.pptx_service import (
    generate_pptx,
    _render_block,
    _resolve_theme,
    _add_content_slide,
    _content_shift_for_takeaway,
)
from backend.services.slide_planner import (
    SlideBlock,
    COMPONENT_BULLETS,
    COMPONENT_TABLE,
    COMPONENT_CHART,
    COMPONENT_STAT_ROW,
    COMPONENT_TIMELINE,
)
from backend.services.template_service import get_template, DEFAULT_TEMPLATE

# The 4 templates kept enabled in the picker after Step 7 (see
# test_template_service.py's _ENABLED_TEMPLATE_IDS) — the contrast guard is
# checked specifically for these.
_FOUR_KEPT_TEMPLATE_IDS = ("executive", "bold", "corporate-blue", "midnight-tech")


def _run(coro):
    return asyncio.run(coro)


def _new_prs(tpl):
    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])
    return prs


def _eyebrow_box(slide, tpl):
    eb = tpl.geometry["chrome"]["eyebrow"]
    for s in slide.shapes:
        if (
            s.has_text_frame
            and s.width == Inches(eb["w"])
            and round(s.height / Inches(1), 2) == eb["h"]
            and round(s.top / Inches(1), 2) == eb["y"]
        ):
            return s
    return None


def _heading_box(slide, tpl):
    hd = tpl.geometry["chrome"]["heading"]
    for s in slide.shapes:
        if (
            s.has_text_frame
            and s.width == Inches(hd["w"])
            and round(s.height / Inches(1), 2) == hd["h"]
            and round(s.top / Inches(1), 2) == hd["y"]
        ):
            return s
    return None


def _rule_shape(slide, tpl):
    rl = tpl.geometry["chrome"]["rule"]
    for s in slide.shapes:
        if (
            s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
            and round(s.top / Inches(1), 2) == rl["y"]
            and s.width == Inches(rl["w"])
        ):
            return s
    return None


def _footer_box(slide, tpl):
    ft = tpl.geometry["chrome"]["footer"]
    for s in slide.shapes:
        if (
            s.has_text_frame
            and s.width == Inches(ft["w"])
            and round(s.top / Inches(1), 2) == ft["y"]
        ):
            return s
    return None


_BLOCKS_BY_COMPONENT = {
    COMPONENT_BULLETS: lambda: SlideBlock(COMPONENT_BULLETS, {
        "title": "Key Findings",
        "items": [{"bullet": True, "text": "A finding", "level": 0, "is_subsection_label": False}],
    }, "Market Overview"),
    COMPONENT_TABLE: lambda: SlideBlock(COMPONENT_TABLE, {
        "title": "Market Size & Growth",
        "rows": [["Metric", "2023", "2024"], ["Revenue", "$1.2B", "$1.6B"]],
    }, "Market Overview"),
    COMPONENT_CHART: lambda: SlideBlock(COMPONENT_CHART, {
        "title": "Pricing Comparison",
        "chart_json": {"type": "bar", "title": "Pricing Index",
                        "data": [{"name": "A", "value": 9}, {"name": "B", "value": 6}]},
    }, "Market Overview"),
    COMPONENT_STAT_ROW: lambda: SlideBlock(COMPONENT_STAT_ROW, {
        "heading": "Key Metrics",
        "stats": [{"value": "$480M", "label": "market size"}, {"value": "15%", "label": "growth"}],
    }, "Key Metrics"),
    COMPONENT_TIMELINE: lambda: SlideBlock(COMPONENT_TIMELINE, {
        "heading": "Delivery Plan",
        "phases": [
            {"label": "Phase 1", "title": "Research"},
            {"label": "Phase 2", "title": "Build"},
            {"label": "Phase 3", "title": "Launch"},
        ],
    }, "Delivery Plan"),
}


def test_every_content_kind_renders_eyebrow_heading_rule_and_footer():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    for component, make_block in _BLOCKS_BY_COMPONENT.items():
        block = make_block()
        slide = _render_block(_new_prs(tpl), block, theme, tpl, section_index=3)

        eyebrow = _eyebrow_box(slide, tpl)
        assert eyebrow is not None, f"{component}: missing eyebrow"
        assert eyebrow.text_frame.text == f"03  ·  {block.source_section.upper()}", component

        heading = _heading_box(slide, tpl)
        assert heading is not None, f"{component}: missing heading box"

        rule = _rule_shape(slide, tpl)
        assert rule is not None, f"{component}: missing hairline rule"

        footer = _footer_box(slide, tpl)
        assert footer is not None, f"{component}: missing footer slot"
        assert footer.text_frame.text == "", f"{component}: footer should be blank (no source given)"


def test_chrome_shapes_above_content_body_never_overflow_into_it():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    cb = tpl.geometry["content_body"]
    for component, make_block in _BLOCKS_BY_COMPONENT.items():
        slide = _render_block(_new_prs(tpl), make_block(), theme, tpl, section_index=1)
        for getter in (_eyebrow_box, _heading_box, _rule_shape):
            shape = getter(slide, tpl)
            bottom_in = (shape.top + shape.height) / Inches(1)
            assert bottom_in <= cb["top"] + 1e-6, (component, getter.__name__)


def test_footer_slot_never_horizontally_overlaps_the_slide_number():
    # The footer (bottom-left) and the slide number (bottom-right) intentionally
    # share the same vertical band (chrome.footer.y == canvas_h - slide_number
    # geometry) — they must never overlap horizontally.
    tpl = DEFAULT_TEMPLATE
    canvas_w = tpl.geometry["canvas"]["width"]
    sn = tpl.geometry["slide_number"]
    ft = tpl.geometry["chrome"]["footer"]
    slide_number_left = canvas_w - sn["x_from_right"]
    footer_right = ft["x"] + ft["w"]
    assert footer_right <= slide_number_left


def test_eyebrow_shows_section_number_and_title_from_section_order():
    content = (
        "### First Section\n- Alpha point one here for content purposes.\n"
        "### Second Section\n- Beta point one here for content purposes.\n"
        "### Third Section\n- Gamma point one here for content purposes.\n"
    )
    data = _run(generate_pptx({"title": "T", "content": content}))
    prs = Presentation(io.BytesIO(data))
    tpl = DEFAULT_TEMPLATE

    found = []
    for slide in prs.slides:
        eb = _eyebrow_box(slide, tpl)
        if eb is not None:
            found.append(eb.text_frame.text)

    assert found == [
        "01  ·  FIRST SECTION",
        "02  ·  SECOND SECTION",
        "03  ·  THIRD SECTION",
    ]


def _contrast_ratio(hex_a, hex_b):
    la, lb = _luminance(hex_a), _luminance(hex_b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_eyebrow_and_footer_contrast_at_least_3_across_the_four_kept_templates():
    for template_id in _FOUR_KEPT_TEMPLATE_IDS:
        tpl = get_template(template_id)
        theme = _resolve_theme(None, None, "default", base=tpl.palette)
        content_bg = theme[tpl.backgrounds["content"]]
        eyebrow_hex = theme[tpl.slots["eyebrow"]]
        footer_hex = theme[tpl.slots["footer"]]
        assert _contrast_ratio(eyebrow_hex, content_bg) >= 3.0, (template_id, "eyebrow")
        assert _contrast_ratio(footer_hex, content_bg) >= 3.0, (template_id, "footer")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — per-slide headline takeaway, rendered in the chrome
# (_add_content_chrome's optional `takeaway` line directly under the rule).
# ─────────────────────────────────────────────────────────────────────────────
_TAKEAWAY_TEXT = "This is the slide's one-line so-what headline"
_TAKEAWAY_COMPONENTS = (COMPONENT_BULLETS, COMPONENT_STAT_ROW, COMPONENT_TIMELINE, COMPONENT_CHART)


def _takeaway_box(slide, tpl):
    tk = tpl.geometry["chrome"]["takeaway"]
    for s in slide.shapes:
        if (
            s.has_text_frame
            and s.width == Inches(tk["w"])
            and round(s.height / Inches(1), 2) == tk["h"]
            and round(s.top / Inches(1), 2) == tk["y"]
        ):
            return s
    return None


def _block_with_takeaway(component):
    block = _BLOCKS_BY_COMPONENT[component]()
    return SlideBlock(component, {**block.data, "takeaway": _TAKEAWAY_TEXT}, block.source_section)


def test_takeaway_renders_for_every_component_that_supports_it():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    for component in _TAKEAWAY_COMPONENTS:
        slide = _render_block(_new_prs(tpl), _block_with_takeaway(component), theme, tpl, section_index=1)
        box = _takeaway_box(slide, tpl)
        assert box is not None, component
        assert box.text_frame.text == _TAKEAWAY_TEXT, component


def test_table_never_renders_a_takeaway_even_if_data_carried_one():
    # table isn't in the planner's "applies to" list for takeaway; _render_table_block
    # never reads block.data["takeaway"], so a stray key there is simply ignored.
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    block = _BLOCKS_BY_COMPONENT[COMPONENT_TABLE]()
    block = SlideBlock(COMPONENT_TABLE, {**block.data, "takeaway": _TAKEAWAY_TEXT}, block.source_section)
    slide = _render_block(_new_prs(tpl), block, theme, tpl, section_index=1)
    assert _takeaway_box(slide, tpl) is None


def test_no_takeaway_box_when_block_carries_none():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    for component, make_block in _BLOCKS_BY_COMPONENT.items():
        slide = _render_block(_new_prs(tpl), make_block(), theme, tpl, section_index=1)
        assert _takeaway_box(slide, tpl) is None, component


def test_takeaway_sits_below_the_rule_never_colliding_with_it():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    for component in _TAKEAWAY_COMPONENTS:
        slide = _render_block(_new_prs(tpl), _block_with_takeaway(component), theme, tpl, section_index=1)
        rule = _rule_shape(slide, tpl)
        takeaway = _takeaway_box(slide, tpl)
        rule_bottom_in = (rule.top + rule.height) / Inches(1)
        takeaway_top_in = takeaway.top / Inches(1)
        assert takeaway_top_in >= rule_bottom_in - 1e-6, component


def _bullets_body_box(slide):
    for s in slide.shapes:
        if s.has_text_frame and "A finding" in s.text_frame.text:
            return s
    return None


def test_bullets_content_body_shifts_down_and_shrinks_when_takeaway_present_no_overflow():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    items = [{"bullet": True, "text": "A finding", "level": 0, "is_subsection_label": False}]
    cb = tpl.geometry["content_body"]

    no_tk_slide = _add_content_slide(_new_prs(tpl), "T", items, theme, tpl, 1, "Sec")
    tk_slide = _add_content_slide(_new_prs(tpl), "T", items, theme, tpl, 1, "Sec", takeaway=_TAKEAWAY_TEXT)

    box_no_tk = _bullets_body_box(no_tk_slide)
    box_tk = _bullets_body_box(tk_slide)
    shift = _content_shift_for_takeaway(tpl, _TAKEAWAY_TEXT)
    assert shift > 0

    assert round(box_no_tk.top / Inches(1), 4) == cb["top"]
    assert round(box_tk.top / Inches(1), 4) == round(cb["top"] + shift, 4)
    assert round(box_tk.height / Inches(1), 4) == round(cb["height"] - shift, 4)

    # The box's bottom edge (top + height) never moves past the original
    # safe floor — shrinking exactly offsets the downward shift.
    no_tk_bottom = (box_no_tk.top + box_no_tk.height) / Inches(1)
    tk_bottom = (box_tk.top + box_tk.height) / Inches(1)
    assert round(tk_bottom, 4) == round(no_tk_bottom, 4)
    assert tk_bottom <= cb["safe_bottom"] + 1e-6


def test_content_shift_for_takeaway_zero_when_no_takeaway():
    tpl = DEFAULT_TEMPLATE
    assert _content_shift_for_takeaway(tpl, None) == 0.0
    assert _content_shift_for_takeaway(tpl, "") == 0.0


def test_timeline_chevron_row_unaffected_by_takeaway_since_it_starts_well_below_it():
    # Documented in _content_shift_for_takeaway's own docstring: timeline
    # never needs the shift because row_top (2.3in) already clears the
    # takeaway band. Proven here by checking the chevron shapes land at the
    # same top with or without a takeaway.
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    row_top = tpl.geometry.get("timeline", {}).get("row_top", 2.3)

    def _chevron_top(slide):
        for s in slide.shapes:
            if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and round(s.top / Inches(1), 2) == row_top:
                return round(s.top / Inches(1), 2)
        return None

    no_tk = _render_block(_new_prs(tpl), _BLOCKS_BY_COMPONENT[COMPONENT_TIMELINE](), theme, tpl, section_index=1)
    tk = _render_block(_new_prs(tpl), _block_with_takeaway(COMPONENT_TIMELINE), theme, tpl, section_index=1)
    assert _chevron_top(no_tk) == row_top
    assert _chevron_top(tk) == row_top
