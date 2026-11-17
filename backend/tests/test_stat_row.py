"""Tests for Slice 2: the stat_row detector (slide_planner) and renderer
(pptx_service._render_stat_row_block) — run with:
cd backend && python -m pytest tests/test_stat_row.py -v
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches, Pt

from backend.services.brand_theme import _luminance
from backend.services.pptx_service import (
    generate_pptx,
    _parse_markdown_to_slides,
    _render_block,
    _resolve_theme,
)
from backend.services.slide_planner import SlideBlock, plan_section, _extract_stat
from backend.services.template_service import get_template, get_templates, DEFAULT_TEMPLATE

_METRICS = "- $480M market size\n- 15% CAGR growth\n- 12 key players\n"


def _run(coro):
    return asyncio.run(coro)


def _plan(markdown):
    return plan_section(markdown, "S", DEFAULT_TEMPLATE)


# ── detector ─────────────────────────────────────────────────────────────────
def test_detector_fires_on_a_crafted_metrics_section():
    blocks = plan_section(_METRICS, "Key Metrics", DEFAULT_TEMPLATE)
    assert [b.component for b in blocks] == ["stat_row"]
    data = blocks[0].data
    assert data["heading"] == "Key Metrics"
    assert data["stats"] == [
        {"value": "$480M", "label": "market size"},
        {"value": "15%", "label": "CAGR growth"},
        {"value": "12", "label": "key players"},
    ]
    assert blocks[0].source_section == "Key Metrics"


def test_detector_handles_both_value_label_forms_ranks_and_sublabels():
    assert _extract_stat("$480M — market size")[0] == {"value": "$480M", "label": "market size"}
    assert _extract_stat("Market size: $480M")[0] == {"value": "$480M", "label": "Market size"}
    assert _extract_stat("**$1.2B** TAM (by 2029)")[0] == {"value": "$1.2B", "label": "TAM", "sublabel": "by 2029"}
    assert _extract_stat("Market size: $480M by 2029")[0]["sublabel"] == "by 2029"
    assert _extract_stat("#1 brand in category")[0]["value"] == "#1"
    assert _extract_stat("No. 2 in category")[0] == {"value": "No. 2", "label": "in category"}
    assert _extract_stat("Thứ 2 về thị phần")[0]["value"] == "Thứ 2"
    assert _extract_stat("₹90 crore — annual revenue")[0]["value"] == "₹90 crore"
    assert _extract_stat("5.5bn users")[0] == {"value": "5.5bn", "label": "users"}


def test_detector_rejects_ambiguous_or_prose_items():
    for text in (
        "Revenue grew 15% annually",
        "$5M to $10M budget",
        "Launched in 2024",
        "2024 was a big year",
        "Focus on 5 priorities",
        "Consumers weigh price and quality heavily before every purchase they make",
        "$480M",
        "$480 million market size",  # value wider than the 9-char cap (would not fit a 4-column row)
    ):
        assert _extract_stat(text) is None, text


def test_detector_does_not_fire_on_normal_bullets_or_wrong_shapes():
    prose = (
        "- Consumers weigh price and quality heavily before committing to a purchase decision\n"
        "- Peer recommendations carry outsized weight among younger buyers in digital channels\n"
        "- Mobile browsing dominates the discovery phase across the entire category\n"
    )
    assert [b.component for b in _plan(prose)] == ["bullets"]
    # only bare numbers -> no strong anchor
    assert [b.component for b in _plan("- 3 phases to rollout\n- 12 key players\n- 5 priority markets\n")] == ["bullets"]
    # one item / five items
    assert [b.component for b in _plan("- $480M market size\n")] == ["bullets"]
    five = "".join(f"- ${i}M segment {i}\n" for i in range(1, 6))
    assert [b.component for b in _plan(five)] == ["bullets"]
    # one non-metric item poisons the group
    assert [b.component for b in _plan("- $480M market size\n- 15% CAGR growth\n- Strong brand awareness\n")] == ["bullets"]
    # nested children / paragraphs are never converted
    assert [b.component for b in _plan("- $480M market size\n  - driven by mobile\n- 15% CAGR growth\n")] == ["bullets"]
    assert [b.component for b in _plan("$480M market size and 15% CAGR growth overall.\n")] == ["bullets"]


def test_declined_bullets_keep_their_exact_payload():
    prose = "- Consumers weigh price and quality heavily before committing to a purchase decision\n- Peer recommendations carry outsized weight\n"
    specs = _parse_markdown_to_slides(prose, DEFAULT_TEMPLATE, default_title="S")
    blocks = _plan(prose)
    assert len(specs) == len(blocks) == 1
    assert blocks[0].component == "bullets"
    assert blocks[0].data == {k: v for k, v in specs[0].items() if k != "type"}


# ── renderer ─────────────────────────────────────────────────────────────────
def _stat_block(n, context=None, sublabels=True):
    pool = [
        {"value": "$480M", "label": "market size", "sublabel": "by 2029"},
        {"value": "15%", "label": "CAGR growth", "sublabel": "2024-2029"},
        {"value": "12", "label": "key players", "sublabel": "tracked"},
        {"value": "#1", "label": "category rank", "sublabel": "since 2022"},
    ][:n]
    if not sublabels:
        pool = [{k: v for k, v in s.items() if k != "sublabel"} for s in pool]
    data = {"heading": "Key Metrics", "stats": pool}
    if context:
        data["context"] = context
    return SlideBlock(component="stat_row", data=data, source_section="Key Metrics")


def _new_prs(tpl):
    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])
    return prs


def _slide_text(slide):
    return "\n".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)


def test_stat_row_renders_2_3_and_4_tiles_inside_the_content_body_safe_area():
    for template_id in (None, "bold", "executive", "midnight-tech"):
        tpl = get_template(template_id)
        theme = _resolve_theme(None, None, "default", base=tpl.palette)
        cb = tpl.geometry["content_body"]
        for n in (2, 3, 4):
            for context in (None, "Snapshot of the category"):
                slide = _render_block(_new_prs(tpl), _stat_block(n, context=context), theme, tpl)
                text = _slide_text(slide)
                assert "Key Metrics" in text
                assert "$480M" in text and "MARKET SIZE" in text
                if context:
                    assert "Snapshot of the category" in text
                body = [s for s in slide.shapes if s.top >= Inches(cb["top"]) - 10]
                assert body
                for s in body:
                    assert s.left >= Inches(cb["x"]) - 10, (template_id, n)
                    assert s.left + s.width <= Inches(cb["x"] + cb["w"]) + 10, (template_id, n)
                    assert s.top + s.height <= Inches(cb["safe_bottom"]), (template_id, n, context)
                tiles = [s for s in body if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and s.width > Inches(1.0)]
                assert len(tiles) == n, (template_id, n)


def test_stat_row_renders_without_sublabels():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    slide = _render_block(_new_prs(tpl), _stat_block(3, sublabels=False), theme, tpl)
    text = _slide_text(slide)
    assert "by 2029" not in text and "$480M" in text and "MARKET SIZE" in text


def test_stat_row_uses_spec_sizes_and_colors():
    tpl = get_template("bold")
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    slide = _render_block(_new_prs(tpl), _stat_block(3), theme, tpl)
    runs = {r.text: r for s in slide.shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs}
    hero_color = RGBColor.from_string(theme[tpl.slots["stat_hero_text"]])
    assert runs["$480M"].font.size == Pt(tpl.type_scale["stat_value"])
    assert runs["$480M"].font.bold is True
    assert runs["$480M"].font.color.rgb == hero_color
    assert runs["MARKET SIZE"].font.size == Pt(tpl.type_scale["stat_label"])
    assert runs["MARKET SIZE"].font.color.rgb == hero_color
    assert runs["by 2029"].font.size == Pt(tpl.type_scale["stat_sublabel"])
    assert runs["by 2029"].font.color.rgb == hero_color
    non_hero_val = RGBColor.from_string(theme[tpl.slots["stat_value"]])
    assert runs["15%"].font.color.rgb == non_hero_val
    assert runs["CAGR GROWTH"].font.color.rgb == RGBColor.from_string(theme[tpl.slots["stat_label"]])


def test_stat_row_tile_contrast_for_every_template():
    def ratio(a, b):
        la, lb = _luminance(a), _luminance(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    failures = []
    for entry in get_templates(enabled_only=False):
        tpl = get_template(entry["id"])
        theme = _resolve_theme(None, None, "default", base=tpl.palette)
        hero_bg = theme[tpl.slots["stat_hero_bg"]]
        hero_text = theme[tpl.slots["stat_hero_text"]]
        r = ratio(hero_text, hero_bg)
        if r < 3.0:
            failures.append(f"{entry['id']}: hero text {hero_text} on {hero_bg} = {r:.2f}")
        tile_bg = theme[tpl.slots["stat_tile_bg"]]
        for slot in ("stat_value", "stat_label", "stat_sublabel"):
            r = ratio(theme[tpl.slots[slot]], tile_bg)
            if r < 3.0:
                failures.append(f"{entry['id']}: {slot} {theme[tpl.slots[slot]]} on tile {tile_bg} = {r:.2f}")
    assert not failures, "\n".join(failures)


def test_generate_pptx_emits_a_stat_row_slide_and_leaves_other_slides_alone():
    content = (
        "### Key Metrics\n" + _METRICS
        + "\n### Other\n- Consumers weigh price and quality heavily before committing to a purchase decision today\n"
    )
    data = _run(generate_pptx({"title": "T", "content": content, "template_id": "bold"}))
    prs = Presentation(io.BytesIO(data))
    texts = [_slide_text(s) for s in prs.slides]
    assert len([t for t in texts if "$480M" in t and "CAGR GROWTH" in t]) == 1
    assert any("Consumers weigh price" in t for t in texts)


def test_unknown_component_fallback_still_works_after_stat_row():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    prs = Presentation()
    items = [{"bullet": True, "text": "Hello", "level": 0, "is_subsection_label": False}]
    slide = _render_block(prs, SlideBlock("sparkline", {"title": "Future", "items": items}, "S"), theme, tpl)
    assert "Hello" in _slide_text(slide)
