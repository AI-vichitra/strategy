"""Tests for template_service.py — run with:
cd backend && python -m pytest tests/test_template_service.py -v

Behavioral asserts rather than a byte snapshot — python-pptx zip output isn't
byte-stable run to run (timestamps/zip metadata), so these check that the
`default` TemplateSpec reproduces pptx_service's OLD module constants exactly,
and that generate_pptx still runs cleanly and renders every text run in
"Calibri" with no template_id given.
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, MSO_SHAPE

import backend.services.pptx_service as pptx_service_module
import backend.services.template_service as template_service_module
from backend.services.template_service import (
    get_template,
    get_templates,
    get_registry,
    DEFAULT_TEMPLATE,
    TemplateSpec,
    _max_lines_per_slide,
)
from backend.services.pptx_service import (
    generate_pptx,
    _resolve_theme,
    _get_theme,
    _logo_box_size,
    MAX_LINES_PER_SLIDE,
    TITLE_BAR_HEIGHT_IN,
    CONTENT_BODY_TOP_IN,
    CONTENT_BODY_HEIGHT_IN,
)
from backend.services.brand_theme import logo_fit_dimensions, _luminance
from fastapi.testclient import TestClient
from backend.main import app

_STATIC_LOGOS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos")

# The values pptx_service's module-level *_FONT_SIZE constants held before
# this change — see pptx_service.py lines ~91-100. DEFAULT_TEMPLATE must
# match these exactly so an unset/unknown template_id reproduces today's
# deck exactly.
_OLD_CONSTANTS = {
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
}


def _run(coro):
    return asyncio.run(coro)


def test_default_template_fonts_and_type_scale_match_old_constants():
    # type_scale has since grown (Step 4a added the remaining inline-literal
    # sizes), so this checks the original 10 keys are still exactly the old
    # values, not full dict equality.
    assert DEFAULT_TEMPLATE.fonts == {"heading": "Calibri", "body": "Calibri"}
    for key, value in _OLD_CONSTANTS.items():
        assert DEFAULT_TEMPLATE.type_scale[key] == value


def test_get_template_with_none_returns_default():
    tpl = get_template(None)
    assert tpl is DEFAULT_TEMPLATE


def test_get_template_with_empty_string_returns_default():
    tpl = get_template("")
    assert tpl is DEFAULT_TEMPLATE


def test_get_template_with_nonexistent_id_returns_default():
    tpl = get_template("this-template-does-not-exist")
    assert tpl is DEFAULT_TEMPLATE


def test_get_template_with_known_default_id_matches_default():
    # The JSON registry's own "default" entry should resolve to the same
    # values as the frozen Python DEFAULT_TEMPLATE (not necessarily the same
    # object, since this one goes through _entry_to_spec).
    tpl = get_template("default")
    assert tpl.fonts == DEFAULT_TEMPLATE.fonts
    assert tpl.type_scale == DEFAULT_TEMPLATE.type_scale


def test_get_templates_returns_a_list_with_default_entry():
    # "default" is disabled in the picker (it stays the code fallback via
    # get_template(None)/get_template("default") directly) — enabled_only
    # excludes it, but it's still present in the full, unfiltered registry.
    templates = get_templates(enabled_only=True)
    assert isinstance(templates, list)
    assert not any(t.get("id") == "default" for t in templates)
    assert any(t.get("id") == "default" for t in get_templates(enabled_only=False))


def test_get_registry_returns_templates_key():
    registry = get_registry()
    assert "templates" in registry
    assert isinstance(registry["templates"], list)


def test_template_spec_is_frozen():
    import dataclasses
    assert dataclasses.is_dataclass(TemplateSpec)
    try:
        DEFAULT_TEMPLATE.id = "changed"
        assert False, "TemplateSpec should be frozen"
    except dataclasses.FrozenInstanceError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test: generate_pptx still runs end-to-end with no template_id, and
# every text run's font family resolves to "Calibri" (DEFAULT_TEMPLATE).
# ─────────────────────────────────────────────────────────────────────────────
def test_generate_pptx_smoke_with_no_template_id_uses_calibri_everywhere():
    content = """### Market Overview

#### Key Findings
- Finding one with enough words to clear the sparse-merge threshold entirely
- Finding two with enough words to clear the sparse-merge threshold entirely
- Finding three with enough words to clear the sparse-merge threshold entirely

| Metric | Value |
| --- | --- |
| Revenue | $1.2B |
| Users | 5M |
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    assert isinstance(data, bytes)
    assert len(data) > 0
    assert data[:2] == b"PK"

    prs = Presentation(io.BytesIO(data))
    checked_runs = 0
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    assert run.font.name == "Calibri", f"unexpected font {run.font.name!r} on run {run.text!r}"
                    checked_runs += 1
            # Tables aren't text_frame shapes at the slide-shape level — walk
            # their cells separately below.
        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    for cell in row.cells:
                        for paragraph in cell.text_frame.paragraphs:
                            for run in paragraph.runs:
                                assert run.font.name == "Calibri"
                                checked_runs += 1
    assert checked_runs > 0


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — base palette + per-slide-kind backgrounds
# ─────────────────────────────────────────────────────────────────────────────
def test_default_template_backgrounds_match_old_hardcoded_mapping():
    assert DEFAULT_TEMPLATE.palette is None
    assert DEFAULT_TEMPLATE.backgrounds == {
        "cover": "bg_dark",
        "divider": "bg_dark",
        "closing": "bg_dark",
        "toc": "bg_light",
        "content": "bg_white",
        "table": "bg_white",
        "chart": "bg_white",
    }


def test_resolve_theme_with_base_none_matches_get_theme():
    # base=None (the default) must be byte-identical to the old 3-arg call —
    # this is exactly what export_service.py (DOCX) still calls.
    for agent in ("seo-strategy", "brand-positioning", "default", "some-unknown-agent"):
        assert _resolve_theme(None, None, agent) == _get_theme(agent)
        assert _resolve_theme(None, None, agent, base=None) == _get_theme(agent)


def test_resolve_theme_base_partial_fills_missing_slots_from_report_theme():
    partial_base = {"primary": "ABCDEF"}
    theme = _resolve_theme(None, None, "seo-strategy", base=partial_base)
    assert theme["primary"] == "ABCDEF"
    report_theme = _get_theme("seo-strategy")
    for key in ("secondary", "accent", "bg_dark", "bg_light", "bg_white", "text_dark", "text_light", "text_muted"):
        assert theme[key] == report_theme[key]


def test_default_deck_background_colors_unchanged():
    # No template_id -> DEFAULT_TEMPLATE -> per-kind backgrounds must still
    # read the same report-type theme slots as before this step.
    content = """### Market Overview

#### Key Findings
- Finding one with enough words to clear the sparse-merge threshold entirely
- Finding two with enough words to clear the sparse-merge threshold entirely
- Finding three with enough words to clear the sparse-merge threshold entirely
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))
    theme = _get_theme("default")

    cover, toc, divider = prs.slides[0], prs.slides[1], prs.slides[2]
    closing = prs.slides[-1]
    assert cover.background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_dark"])
    assert toc.background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_light"])
    assert divider.background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_dark"])
    assert closing.background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_dark"])

    content_slides = list(prs.slides)[3:-1]
    assert any(
        s.background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_white"])
        for s in content_slides
    )


# A throwaway TemplateSpec used ONLY by these tests (never written to the
# shipped backend/data/pptx_templates.json, never marked enabled) — it has a
# distinct palette and an INVERTED divider background slot ("bg_light"
# instead of DEFAULT_TEMPLATE's "bg_dark") so precedence can be checked
# against a mapping that's actually different from today's.
_THROWAWAY_TEMPLATE_ID = "throwaway-test-template-step2"
_THROWAWAY_TPL = TemplateSpec(
    id=_THROWAWAY_TEMPLATE_ID,
    name="Throwaway Test Template",
    fonts=DEFAULT_TEMPLATE.fonts,
    type_scale=DEFAULT_TEMPLATE.type_scale,
    palette={
        "primary": "112233",
        "secondary": "223344",
        "accent": "334455",
        "bg_dark": "000011",
        "bg_light": "EEEEFF",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "778899",
    },
    backgrounds={
        "cover": "bg_dark",
        "divider": "bg_light",  # inverted from DEFAULT_TEMPLATE's "bg_dark"
        "closing": "bg_dark",
        "toc": "bg_light",
        "content": "bg_white",
        "table": "bg_white",
        "chart": "bg_white",
    },
    geometry=DEFAULT_TEMPLATE.geometry,
    fit=DEFAULT_TEMPLATE.fit,
    slots=DEFAULT_TEMPLATE.slots,
    art=DEFAULT_TEMPLATE.art,
)


def _patch_get_template(monkeypatch):
    """Makes pptx_service.generate_pptx resolve _THROWAWAY_TPL for
    _THROWAWAY_TEMPLATE_ID while delegating every other id to the real
    template_service.get_template — so default/unknown-id behavior is
    untouched by the patch."""
    real_get_template = template_service_module.get_template

    def fake_get_template(template_id):
        if template_id == _THROWAWAY_TEMPLATE_ID:
            return _THROWAWAY_TPL
        return real_get_template(template_id)

    monkeypatch.setattr(pptx_service_module, "get_template", fake_get_template)


def test_template_palette_and_backgrounds_take_effect_with_no_brand_or_extracted(monkeypatch):
    _patch_get_template(monkeypatch)

    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "template_id": _THROWAWAY_TEMPLATE_ID,
    }))
    prs = Presentation(io.BytesIO(data))
    cover, toc, divider = prs.slides[0], prs.slides[1], prs.slides[2]

    # Cover/TOC read the throwaway palette's own bg_dark/bg_light, not the
    # per-agent report theme's.
    assert cover.background.fill.fore_color.rgb == RGBColor.from_string(_THROWAWAY_TPL.palette["bg_dark"])
    assert toc.background.fill.fore_color.rgb == RGBColor.from_string(_THROWAWAY_TPL.palette["bg_light"])
    assert _THROWAWAY_TPL.palette["bg_dark"] != _get_theme("default")["bg_dark"]

    # Divider's background SLOT is inverted to "bg_light" in this template
    # (vs. DEFAULT_TEMPLATE's "bg_dark") -> it must differ from the cover's
    # background and match the palette's bg_light.
    assert divider.background.fill.fore_color.rgb == RGBColor.from_string(_THROWAWAY_TPL.palette["bg_light"])
    assert divider.background.fill.fore_color.rgb != cover.background.fill.fore_color.rgb


def test_brand_kit_colors_override_template_palette(monkeypatch):
    _patch_get_template(monkeypatch)

    brand_kit = {"colors": {"primary": "#6A1B9A", "secondary": "#AB47BC", "accent": "#FFB300"}}
    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "template_id": _THROWAWAY_TEMPLATE_ID,
        "brand_kit": brand_kit,
    }))
    prs = Presentation(io.BytesIO(data))
    cover = prs.slides[0]

    expected_theme = _resolve_theme(brand_kit, None, "default", base=_THROWAWAY_TPL.palette)
    assert cover.background.fill.fore_color.rgb == RGBColor.from_string(expected_theme["bg_dark"])
    # Must differ from the throwaway palette's own bg_dark — brand_kit actually won.
    assert expected_theme["bg_dark"] != _THROWAWAY_TPL.palette["bg_dark"]


def test_extracted_palette_overrides_template_palette(monkeypatch):
    _patch_get_template(monkeypatch)

    extracted_palette = {"primary": "#204060", "secondary": "#4080A0", "accent": "#C0A040"}
    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "template_id": _THROWAWAY_TEMPLATE_ID,
        "extracted_palette": extracted_palette,
    }))
    prs = Presentation(io.BytesIO(data))
    cover = prs.slides[0]

    expected_theme = _resolve_theme(None, extracted_palette, "default", base=_THROWAWAY_TPL.palette)
    assert cover.background.fill.fore_color.rgb == RGBColor.from_string(expected_theme["bg_dark"])
    # Must differ from the throwaway palette's own bg_dark — extracted_palette actually won.
    assert expected_theme["bg_dark"] != _THROWAWAY_TPL.palette["bg_dark"]


def test_throwaway_template_not_in_shipped_registry():
    # Sanity check that this test's fixture template was never written to
    # the real, shipped pptx_templates.json.
    ids = [t.get("id") for t in get_registry().get("templates", [])]
    assert _THROWAWAY_TEMPLATE_ID not in ids


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — geometry + fit values
# ─────────────────────────────────────────────────────────────────────────────
def test_max_lines_per_slide_for_default_equals_old_constant():
    assert _max_lines_per_slide(DEFAULT_TEMPLATE) == MAX_LINES_PER_SLIDE
    assert _max_lines_per_slide(DEFAULT_TEMPLATE) == 17


def test_default_geometry_round_trips_to_old_literals():
    geo = DEFAULT_TEMPLATE.geometry
    assert geo["canvas"] == {"width": 13.333, "height": 7.5}

    assert geo["title_bar"]["height"] == TITLE_BAR_HEIGHT_IN == 0.7
    assert geo["title_bar"]["accent_bar"] == {"on": True, "width": 0.18, "side": "left"}
    assert geo["title_bar"]["title_box"] == {"x": 0.6, "y": 0.35, "w": 12.0}
    assert geo["title_bar"]["subtitle_box"] == {"x": 0.6, "y": 1.0, "w": 12.0, "h": 0.5}

    assert geo["slide_number"] == {
        "on": True, "w": 0.8, "h": 0.35,
        "x_from_right": 1.0, "y_from_bottom": 0.45, "align": "right",
    }

    assert geo["content_body"]["x"] == 0.8
    assert geo["content_body"]["top"] == CONTENT_BODY_TOP_IN == 1.40
    assert geo["content_body"]["w"] == 11.5
    assert geo["content_body"]["height"] == CONTENT_BODY_HEIGHT_IN == 5.20
    assert geo["content_body"]["safe_bottom"] == 6.7

    # Step 7 — content-slide chrome (eyebrow/kicker, heading, hairline rule,
    # source footer), shared by bullets/table/chart/stat_row/timeline.
    assert geo["chrome"]["eyebrow"] == {"x": 0.8, "y": 0.45, "w": 11.5, "h": 0.22}
    assert geo["chrome"]["heading"] == {"x": 0.8, "y": 0.70, "w": 11.5, "h": 0.5}
    assert geo["chrome"]["rule"] == {"x": 0.8, "y": 1.25, "w": 11.5, "thickness_pt": 1}
    assert geo["chrome"]["footer"] == {"x": 0.8, "y": 7.05, "w": 9.0, "h": 0.3}

    assert geo["bullets"] == {"indent_step": 0.3, "max_level": 2, "hanging_indent": -0.25}
    assert geo["spacing"] == {
        "label": {"space_after": 10, "line": 1.2},
        "bullet": {"space_after": 8, "line": 1.2},
        "paragraph": {"space_after": 10, "line": 1.2},
    }
    assert geo["table"] == {
        "x": 0.8, "top": 1.7, "w": 11.7,
        "row_height": 0.5, "max_height": 5.1,
        "cell_margin_h": 0.1, "cell_margin_v": 0.05,
    }
    assert geo["chart"] == {
        "width": 8.0, "top": 1.6, "figsize": [9, 5],
        "takeaway": {"x": 1.2, "y": 6.7, "w": 10.9, "h": 0.6},
    }
    assert DEFAULT_TEMPLATE.fit == {"chars_per_line": 98, "line_height": 0.3}


def test_default_deck_content_body_emu_matches_spec_literals():
    # The rendered content-body box's actual EMU geometry — not just the
    # spec's own values — must equal DEFAULT_TEMPLATE.geometry["content_body"]
    # (shifted slightly in Step 7 to make room for the chrome frame above it;
    # see test_default_geometry_round_trips_to_old_literals).
    data = _run(generate_pptx({"title": "Report", "content": "### Section\n- A bullet.\n"}))
    prs = Presentation(io.BytesIO(data))

    found = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if (
                shape.has_text_frame
                and shape.width == Inches(11.5)
                and round(shape.height / Inches(1), 2) == 5.20
                and round(shape.top / Inches(1), 2) == 1.40
                and round(shape.left / Inches(1), 2) == 0.8
            ):
                found = True
    assert found


# A throwaway TemplateSpec used ONLY by the liveness test below — identical
# to DEFAULT_TEMPLATE except for a much taller `fit.line_height`, which
# lowers the derived max_lines ceiling sharply. Never written to the shipped
# pptx_templates.json, never marked enabled.
_SHRUNK_FIT_TEMPLATE_ID = "throwaway-test-template-step3-shrunk-fit"
_SHRUNK_FIT_TPL = TemplateSpec(
    id=_SHRUNK_FIT_TEMPLATE_ID,
    name="Throwaway Shrunk-Fit Test Template",
    fonts=DEFAULT_TEMPLATE.fonts,
    type_scale=DEFAULT_TEMPLATE.type_scale,
    palette=None,
    backgrounds=DEFAULT_TEMPLATE.backgrounds,
    geometry=DEFAULT_TEMPLATE.geometry,
    fit={"chars_per_line": 98, "line_height": 2.0},  # vs. DEFAULT_TEMPLATE's 0.3
    slots=DEFAULT_TEMPLATE.slots,
    art=DEFAULT_TEMPLATE.art,
)


def test_shrunk_fit_template_has_a_different_max_lines_than_default():
    default_max_lines = _max_lines_per_slide(DEFAULT_TEMPLATE)
    shrunk_max_lines = _max_lines_per_slide(_SHRUNK_FIT_TPL)
    assert shrunk_max_lines != default_max_lines
    assert default_max_lines == 17
    assert shrunk_max_lines == 2


def test_liveness_smaller_fit_model_produces_more_slides(monkeypatch):
    def fake_get_template(template_id):
        if template_id == _SHRUNK_FIT_TEMPLATE_ID:
            return _SHRUNK_FIT_TPL
        return template_service_module.get_template(template_id)

    monkeypatch.setattr(pptx_service_module, "get_template", fake_get_template)

    # 5 short, distinct-labeled bullets — each is 1 wrapped line regardless of
    # template (well under chars_per_line=98), so under DEFAULT_TEMPLATE's
    # max_lines=17 they all combine onto ONE content slide, but under the
    # shrunk template's max_lines=2 the packer must flush every ~2 bullets.
    bullets = "\n".join(f"- Point-{chr(ord('A') + i)}: a short line of text here" for i in range(5))
    content = f"### Section\n{bullets}\n"

    data_default = _run(generate_pptx({"title": "Report", "content": content}))
    data_shrunk = _run(generate_pptx({
        "title": "Report",
        "content": content,
        "template_id": _SHRUNK_FIT_TEMPLATE_ID,
    }))

    slide_count_default = len(list(Presentation(io.BytesIO(data_default)).slides))
    slide_count_shrunk = len(list(Presentation(io.BytesIO(data_shrunk)).slides))

    assert slide_count_shrunk > slide_count_default, (
        f"expected the shrunk-fit template to force MORE slides than default "
        f"(default={slide_count_default}, shrunk={slide_count_shrunk})"
    )


def test_shrunk_fit_template_not_in_shipped_registry():
    ids = [t.get("id") for t in get_registry().get("templates", [])]
    assert _SHRUNK_FIT_TEMPLATE_ID not in ids


# ─────────────────────────────────────────────────────────────────────────────
# Step 4a — remaining font sizes + per-element color slots
# ─────────────────────────────────────────────────────────────────────────────
def _find_run(slide, text_substring):
    """Returns the first run on `slide` whose text contains `text_substring`,
    or None."""
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for p in shape.text_frame.paragraphs:
            for run in p.runs:
                if text_substring in run.text:
                    return run
    return None


def test_default_cover_and_divider_title_sizes_unchanged():
    content = "### A Section Title\nSome body text to make a content slide.\n"
    data = _run(generate_pptx({"title": "A Cover Title", "content": content}))
    prs = Presentation(io.BytesIO(data))

    cover_run = _find_run(prs.slides[0], "A Cover Title")
    assert cover_run is not None
    assert cover_run.font.size == Pt(32)

    divider_run = _find_run(prs.slides[2], "A Section Title")
    assert divider_run is not None
    assert divider_run.font.size == Pt(40)


def test_default_table_colors_unchanged():
    content = """### Comparison
| Metric | A | B |
| --- | --- | --- |
| Row1 | 1 | 2 |
| Row2 | 3 | 4 |
| Row3 | 5 | 6 |
"""
    data = _run(generate_pptx({"title": "Report", "content": content, "agent_type": "default"}))
    prs = Presentation(io.BytesIO(data))
    theme = _get_theme("default")

    table_slide = next(s for s in prs.slides if any(sh.has_table for sh in s.shapes))
    table = next(sh.table for sh in table_slide.shapes if sh.has_table)

    assert table.cell(0, 0).fill.fore_color.rgb == RGBColor.from_string(theme["primary"])
    # Row 1 (first body row, r=1, odd) -> slots["table_row_b"] -> "bg_white" (== FFFFFF).
    assert theme["bg_white"] == "FFFFFF"
    assert table.cell(1, 0).fill.fore_color.rgb == RGBColor.from_string(theme["bg_white"])
    # Row 2 (second body row, r=2, even) -> slots["table_row_a"] -> "bg_light".
    assert table.cell(2, 0).fill.fore_color.rgb == RGBColor.from_string(theme["bg_light"])


def test_default_bullet_marker_and_slide_number_colors_unchanged():
    content = "### Section\n- A bullet point with enough words to render normally here\n"
    data = _run(generate_pptx({"title": "Report", "content": content, "agent_type": "default"}))
    prs = Presentation(io.BytesIO(data))
    theme = _get_theme("default")

    found_marker = False
    found_number = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for p in shape.text_frame.paragraphs:
                for run in p.runs:
                    if run.text == "•  ":
                        assert run.font.color.rgb == RGBColor.from_string(theme["accent"])
                        found_marker = True
                    elif run.text.strip().isdigit() and run.font.size == Pt(9):
                        # Pt(9) singles out the slide-number run specifically —
                        # the TOC/divider "NN" index runs are Pt(16).
                        assert run.font.color.rgb == RGBColor.from_string(theme["text_muted"])
                        found_number = True
    assert found_marker, "expected to find the bullet marker glyph run"
    assert found_number, "expected to find a slide-number run"


# A throwaway TemplateSpec used ONLY by the liveness test below — remaps the
# cover title's own slot ("cover_title") to "accent" and bumps its size via
# type_scale["cover_title"], proving both the size and the color are spec-
# driven. Never written to the shipped pptx_templates.json, never enabled.
_RECOLORED_COVER_TITLE_ID = "throwaway-test-template-step4a-recolored-cover-title"
_RECOLORED_COVER_TITLE_TPL = TemplateSpec(
    id=_RECOLORED_COVER_TITLE_ID,
    name="Throwaway Recolored Cover Title Test Template",
    fonts=DEFAULT_TEMPLATE.fonts,
    type_scale={**DEFAULT_TEMPLATE.type_scale, "cover_title": 44},
    palette=None,
    backgrounds=DEFAULT_TEMPLATE.backgrounds,
    geometry=DEFAULT_TEMPLATE.geometry,
    fit=DEFAULT_TEMPLATE.fit,
    slots={**DEFAULT_TEMPLATE.slots, "cover_title": "accent"},
    art=DEFAULT_TEMPLATE.art,
)


def test_liveness_cover_title_size_and_color_are_spec_driven(monkeypatch):
    def fake_get_template(template_id):
        if template_id == _RECOLORED_COVER_TITLE_ID:
            return _RECOLORED_COVER_TITLE_TPL
        return template_service_module.get_template(template_id)

    monkeypatch.setattr(pptx_service_module, "get_template", fake_get_template)

    data = _run(generate_pptx({
        "title": "Recolored Cover",
        "content": "### Section\nSome text.",
        "template_id": _RECOLORED_COVER_TITLE_ID,
        "agent_type": "default",
    }))
    prs = Presentation(io.BytesIO(data))
    theme = _get_theme("default")

    run = _find_run(prs.slides[0], "Recolored Cover")
    assert run is not None
    assert run.font.size == Pt(44)
    assert run.font.color.rgb == RGBColor.from_string(theme["accent"])


def test_recolored_cover_title_template_not_in_shipped_registry():
    ids = [t.get("id") for t in get_registry().get("templates", [])]
    assert _RECOLORED_COVER_TITLE_ID not in ids


# ─────────────────────────────────────────────────────────────────────────────
# Step 4b — cover/divider/closing/TOC art geometry + logo boxes + copy strings
# ─────────────────────────────────────────────────────────────────────────────
def _shape_at(slide, x_in, y_in, w_in=None, h_in=None):
    """Finds a shape on `slide` whose left/top (and, if given, width/height)
    exactly match the given inch values."""
    for shape in slide.shapes:
        if shape.left != Inches(x_in) or shape.top != Inches(y_in):
            continue
        if w_in is not None and shape.width != Inches(w_in):
            continue
        if h_in is not None and shape.height != Inches(h_in):
            continue
        return shape
    return None


def test_default_cover_chrome_geometry_and_copy_unchanged():
    # No agent_name/agent_type -> badge falls back to its configured label
    # instead of "{AGENT} REPORT".
    data = _run(generate_pptx({"title": "A Cover Title", "content": "### Section\nSome text."}))
    prs = Presentation(io.BytesIO(data))
    cover = prs.slides[0]

    badge = _shape_at(cover, 0.6, 1.7, 3.8, 0.5)
    assert badge is not None
    assert badge.auto_shape_type == MSO_SHAPE.ROUNDED_RECTANGLE
    assert "EXECUTIVE STRATEGY DOCUMENT" in badge.text_frame.text

    rule = _shape_at(cover, 0.0, 3.0)
    assert rule is not None
    assert rule.width == Inches(13.333)
    assert rule.height == Pt(4)

    title_box = _shape_at(cover, 0.6, 3.3, 11.5, 1.6)
    assert title_box is not None
    assert "A Cover Title" in title_box.text_frame.text

    all_text = "\n".join(sh.text_frame.text for sh in cover.shapes if sh.has_text_frame)
    assert "StratAI" in all_text
    assert "STRATEGIC MARKET INTELLIGENCE" in all_text
    assert "Powered by StratAI Multi-Agent Strategy Engine" in all_text


def test_default_divider_chrome_geometry_unchanged():
    data = _run(generate_pptx({"title": "Report", "content": "### A Divider Section\nSome text.", "agent_type": "default"}))
    prs = Presentation(io.BytesIO(data))
    divider = prs.slides[2]

    title_box = _shape_at(divider, 0.6, 3.0, 12.1, 1.4)
    assert title_box is not None
    assert "A Divider Section" in title_box.text_frame.text

    expected_bar_left = (Inches(13.333) - Inches(1.6)) // 2
    bar = _shape_at(divider, expected_bar_left / Inches(1), 4.5, 1.6)
    assert bar is not None
    assert bar.height == Pt(4)


def test_default_closing_chrome_geometry_and_copy_unchanged():
    data = _run(generate_pptx({"title": "Report", "content": "### Section\nSome text.", "agent_type": "default"}))
    prs = Presentation(io.BytesIO(data))
    closing = prs.slides[-1]

    box = _shape_at(closing, 1.0, 3.0, 11.3, 1.5)
    assert box is not None
    assert "Generated by StratAI" in box.text_frame.text


def test_default_toc_chrome_geometry_unchanged():
    data = _run(generate_pptx({"title": "Report", "content": "### Section\nSome text.", "agent_type": "default"}))
    prs = Presentation(io.BytesIO(data))
    toc = prs.slides[1]

    list_box = _shape_at(toc, 1.0, 1.8, 11.3, 5.0)
    assert list_box is not None


def test_default_logo_max_boxes_unchanged():
    fake_asset = {"width": 400, "height": 100}

    expected_cover_w, expected_cover_h = logo_fit_dimensions(fake_asset, 1.2, 4.0)
    cover_w, cover_h = _logo_box_size(fake_asset, DEFAULT_TEMPLATE, "cover")
    assert cover_w == Inches(expected_cover_w)
    assert cover_h == Inches(expected_cover_h)

    expected_divider_w, expected_divider_h = logo_fit_dimensions(fake_asset, 0.6, 2.0)
    divider_w, divider_h = _logo_box_size(fake_asset, DEFAULT_TEMPLATE, "divider")
    assert divider_w == Inches(expected_divider_w)
    assert divider_h == Inches(expected_divider_h)


# A throwaway TemplateSpec used ONLY by the liveness tests below — moves the
# cover title down, shrinks the cover logo's max width, changes the badge's
# fallback label, and blanks the tagline. Never written to the shipped
# pptx_templates.json, never enabled.
_MOVED_COVER_ART_ID = "throwaway-test-template-step4b-moved-cover-art"
_MOVED_COVER_ART_TPL = TemplateSpec(
    id=_MOVED_COVER_ART_ID,
    name="Throwaway Moved Cover Art Test Template",
    fonts=DEFAULT_TEMPLATE.fonts,
    type_scale=DEFAULT_TEMPLATE.type_scale,
    palette=None,
    backgrounds=DEFAULT_TEMPLATE.backgrounds,
    geometry=DEFAULT_TEMPLATE.geometry,
    fit=DEFAULT_TEMPLATE.fit,
    slots=DEFAULT_TEMPLATE.slots,
    art={
        **DEFAULT_TEMPLATE.art,
        "cover": {
            **DEFAULT_TEMPLATE.art["cover"],
            "logo": {**DEFAULT_TEMPLATE.art["cover"]["logo"], "max_w": 1.0},
            "tagline": {**DEFAULT_TEMPLATE.art["cover"]["tagline"], "text": ""},
            "badge": {**DEFAULT_TEMPLATE.art["cover"]["badge"], "label": "CUSTOM BADGE TEXT"},
            "title": {**DEFAULT_TEMPLATE.art["cover"]["title"], "y": 5.0},
        },
    },
)


def _write_test_logo(filename="_test_step4b_logo.png"):
    os.makedirs(_STATIC_LOGOS_DIR, exist_ok=True)
    path = os.path.join(_STATIC_LOGOS_DIR, filename)
    Image.new("RGB", (400, 100), (0, 128, 255)).save(path, "PNG")
    return f"/static/uploads/logos/{filename}", path


def _patch_moved_cover_art(monkeypatch):
    def fake_get_template(template_id):
        if template_id == _MOVED_COVER_ART_ID:
            return _MOVED_COVER_ART_TPL
        return template_service_module.get_template(template_id)

    monkeypatch.setattr(pptx_service_module, "get_template", fake_get_template)


def test_liveness_moved_title_shrunk_logo_and_new_badge_text(monkeypatch):
    _patch_moved_cover_art(monkeypatch)

    logo_url, path = _write_test_logo()
    try:
        data = _run(generate_pptx({
            "title": "Report",
            "content": "### Section\nSome text.",
            "template_id": _MOVED_COVER_ART_ID,
            "brand_kit": {"logo_url": logo_url},
        }))
        prs = Presentation(io.BytesIO(data))
        cover = prs.slides[0]

        # Title moved from y=3.3in (default) to y=5.0in.
        moved_title = _shape_at(cover, 0.6, 5.0, 11.5, 1.6)
        assert moved_title is not None
        assert _shape_at(cover, 0.6, 3.3, 11.5, 1.6) is None

        # Logo shrunk to max_w=1.0in (vs. default 4.0in).
        logo_pic = next(sh for sh in cover.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE)
        assert logo_pic.width <= Inches(1.0)

        # Badge fallback label changed (no agent_name passed -> uses the label).
        all_text = "\n".join(sh.text_frame.text for sh in cover.shapes if sh.has_text_frame)
        assert "CUSTOM BADGE TEXT" in all_text
        assert "EXECUTIVE STRATEGY DOCUMENT" not in all_text
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_liveness_blanked_tagline_has_no_text(monkeypatch):
    _patch_moved_cover_art(monkeypatch)

    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "template_id": _MOVED_COVER_ART_ID,
    }))
    prs = Presentation(io.BytesIO(data))
    cover = prs.slides[0]
    all_text = "\n".join(sh.text_frame.text for sh in cover.shapes if sh.has_text_frame)

    assert "STRATEGIC MARKET INTELLIGENCE" not in all_text
    assert "StratAI" in all_text  # the wordmark itself is untouched — only the tagline was blanked


def test_moved_cover_art_template_not_in_shipped_registry():
    ids = [t.get("id") for t in get_registry().get("templates", [])]
    assert _MOVED_COVER_ART_ID not in ids


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — the first two real templates ("executive", "bold") + contrast guard
# ─────────────────────────────────────────────────────────────────────────────
_SHIPPED_TEMPLATE_IDS = ("default", "executive", "bold", "corporate-blue", "midnight-tech", "minimalist-mono", "warm-editorial")
# Step 7 — the chrome pass disabled 3 of the 7 shipped templates in the
# picker ("default" stays the code fallback via get_template(None)/
# get_template("default") directly; minimalist-mono/warm-editorial are just
# off for now). _SHIPPED_TEMPLATE_IDS above still drives every
# render/contrast loop in this file — the chrome frame must work for EVERY
# template, not only the ones currently shown in the picker.
_ENABLED_TEMPLATE_IDS = ("executive", "bold", "corporate-blue", "midnight-tech")


def test_executive_and_bold_load_from_shipped_json():
    executive = get_template("executive")
    assert executive.id == "executive"
    assert executive.fonts["heading"] == "Georgia"
    assert executive.fonts["body"] == "Calibri"  # keeps the fit model identical
    assert executive.type_scale["title"] == 28
    assert executive.type_scale["cover_title"] == 36
    assert executive.type_scale["divider_title"] == 34
    assert executive.backgrounds["cover"] == "bg_white"

    bold = get_template("bold")
    assert bold.id == "bold"
    assert bold.fonts["heading"] == "Trebuchet MS"
    assert bold.fonts["body"] == "Calibri"
    assert bold.type_scale["title"] == 28
    assert bold.type_scale["cover_title"] == 44
    assert bold.type_scale["divider_title"] == 44
    assert bold.backgrounds["cover"] == "bg_dark"
    assert bold.art["cover"]["rule"]["thickness_pt"] == 6
    assert bold.art["divider"]["bar"]["length"] == 2.4
    assert bold.art["divider"]["bar"]["thickness_pt"] == 6
    # Deep-merge must have preserved the sibling fields default's bar/rule set
    # (e.g. divider.bar.y, divider.bar.align, cover.rule.y) alongside bold's
    # overridden thickness_pt/length.
    assert bold.art["divider"]["bar"]["y"] == DEFAULT_TEMPLATE.art["divider"]["bar"]["y"]
    assert bold.art["divider"]["bar"]["align"] == DEFAULT_TEMPLATE.art["divider"]["bar"]["align"]
    assert bold.art["cover"]["rule"]["y"] == DEFAULT_TEMPLATE.art["cover"]["rule"]["y"]


def test_batch1_templates_load_from_shipped_json():
    cb = get_template("corporate-blue")
    assert cb.id == "corporate-blue"
    assert cb.fonts == {"heading": "Arial", "body": "Calibri"}
    assert cb.type_scale["cover_title"] == 34
    assert cb.type_scale["divider_title"] == 38
    assert cb.backgrounds["cover"] == "bg_white"
    assert cb.backgrounds["divider"] == "bg_dark"
    assert cb.slots["cover_title"] == "primary"
    assert cb.slots["cover_badge_text"] == "text_dark"
    assert cb.chart_palette == ["1F3A5F", "2E8BC0", "7FB0D9", "5B7A9D", "A9C4DE", "1A2330"]

    mt = get_template("midnight-tech")
    assert mt.id == "midnight-tech"
    assert mt.fonts == {"heading": "Trebuchet MS", "body": "Calibri"}
    assert mt.type_scale["cover_title"] == 44
    assert mt.backgrounds["cover"] == "bg_dark"
    assert mt.slots["cover_meta"] == "text_muted"
    assert mt.slots["cover_date"] == "text_muted"
    assert mt.slots["cover_badge_text"] == "text_dark"
    assert mt.chart_palette == ["22D3EE", "0E7490", "67E8F9", "155E75", "38BDF8", "0B1220"]

    mm = get_template("minimalist-mono")
    assert mm.id == "minimalist-mono"
    assert mm.fonts == {"heading": "Arial", "body": "Calibri"}
    assert mm.type_scale["cover_title"] == 40
    assert mm.backgrounds["cover"] == "bg_white"
    assert mm.backgrounds["divider"] == "bg_light"
    assert mm.backgrounds["closing"] == "bg_white"
    assert mm.slots["cover_title"] == "primary"
    assert mm.slots["divider_title"] == "primary"
    assert mm.slots["closing_headline"] == "primary"
    assert mm.chart_palette == ["111111", "666666", "999999", "CCCCCC", "444444", "7F7F7F"]

    we = get_template("warm-editorial")
    assert we.id == "warm-editorial"
    assert we.fonts == {"heading": "Georgia", "body": "Calibri"}
    assert we.type_scale["cover_title"] == 36
    assert we.backgrounds["cover"] == "bg_light"
    assert we.backgrounds["divider"] == "bg_dark"
    assert we.slots["cover_title"] == "primary"
    assert we.slots["cover_badge_text"] == "text_dark"
    assert we.slots["divider_title"] == "text_light"
    assert we.chart_palette == ["6B3A2A", "C8743F", "D9A066", "8A7A6B", "A6705E", "E0C097"]


def test_shipped_registry_returns_all_enabled_templates():
    ids = {t["id"] for t in get_templates(enabled_only=True)}
    assert ids == set(_ENABLED_TEMPLATE_IDS)


def test_pptx_templates_endpoint_lists_all_shipped():
    client = TestClient(app)
    body = client.get("/api/pptx-templates").json()
    ids = {t["id"] for t in body}
    assert ids == set(_ENABLED_TEMPLATE_IDS)


def test_all_shipped_templates_fit_model_unchanged_from_default():
    # Every template keeps body font = Calibri, so the line-wrap fit model
    # (chars_per_line/line_height and its derived max_lines) must be
    # byte-identical to default's — none should ever reflow a deck's
    # slide count differently just from picking a different look.
    for template_id in _SHIPPED_TEMPLATE_IDS:
        if template_id == "default":
            continue
        tpl = get_template(template_id)
        assert tpl.fonts["body"] == "Calibri", f"{template_id} body font != Calibri"
        assert tpl.fit == DEFAULT_TEMPLATE.fit, f"{template_id} fit model differs"
        assert tpl.geometry == DEFAULT_TEMPLATE.geometry, f"{template_id} geometry differs"
        assert _max_lines_per_slide(tpl) == _max_lines_per_slide(DEFAULT_TEMPLATE), f"{template_id} max_lines differs"


def test_default_template_is_unchanged_by_this_step():
    # The two new entries must not have perturbed the default entry itself.
    assert get_template(None) is DEFAULT_TEMPLATE
    assert get_template("default").fonts == DEFAULT_TEMPLATE.fonts
    assert get_template("default").palette == DEFAULT_TEMPLATE.palette
    assert get_template("default").slots == DEFAULT_TEMPLATE.slots


# ─────────────────────────────────────────────────────────────────────────────
# Contrast self-check — a WCAG-style guard against a mis-mapped slot putting
# near-invisible text on its slide's own background. One pair per (template,
# slide kind): the kind's background slot vs. that kind's main text/title
# slot, both resolved through the SAME theme-resolution path pptx_service
# actually uses (brand_kit=None, extracted_palette=None, base=tpl.palette).
# ─────────────────────────────────────────────────────────────────────────────
def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio between two hex colors: (L_lighter + 0.05) /
    (L_darker + 0.05), using brand_theme's own relative-luminance formula."""
    l_a, l_b = _luminance(hex_a), _luminance(hex_b)
    lighter, darker = max(l_a, l_b), min(l_a, l_b)
    return (lighter + 0.05) / (darker + 0.05)


def _resolved_theme_for(tpl: TemplateSpec) -> dict:
    return _resolve_theme(None, None, "default", base=tpl.palette)


# slide kind -> the slot holding that kind's main text/title, rendered
# directly on the slide's own background (never on an intermediate shape
# fill like a badge or table-header rectangle).
_REQUIRED_CONTRAST_CHECKS = {
    "cover": "cover_title",
    "divider": "divider_title",
    "closing": "closing_headline",
    "toc": "title",
    "content": "title",
    "table": "title",
    "chart": "title",
}


def test_contrast_background_vs_main_text_slot_for_every_template_and_kind():
    """REQUIRED guard: every shipped template, every slide kind, contrast
    ratio of (background, main text/title slot) >= 3.0 (WCAG AA for large
    text) — flagged via a descriptive assertion message, not silently
    skipped. Also covers the cover's secondary text (cover_meta/cover_date),
    on the cover background — the "Bold" meta/date bug (dark-on-dark, ratio
    ~1.22) slipped through the first pass because only the cover's main
    title was checked."""
    failures = []
    for template_id in _SHIPPED_TEMPLATE_IDS:
        tpl = get_template(template_id)
        theme = _resolved_theme_for(tpl)
        for kind, slot_name in _REQUIRED_CONTRAST_CHECKS.items():
            bg_slot = tpl.backgrounds[kind]
            text_hex = theme[tpl.slots[slot_name]]
            bg_hex = theme[bg_slot]
            ratio = _contrast_ratio(text_hex, bg_hex)
            if ratio < 3.0:
                failures.append(
                    f"{template_id}/{kind}: slots['{slot_name}']={text_hex} on "
                    f"backgrounds['{kind}']='{bg_slot}'={bg_hex} -> contrast {ratio:.2f} < 3.0"
                )
            if kind == "cover":
                cover_bg_hex = bg_hex
                for extra_slot in ("cover_meta", "cover_date"):
                    extra_hex = theme[tpl.slots[extra_slot]]
                    extra_ratio = _contrast_ratio(extra_hex, cover_bg_hex)
                    if extra_ratio < 3.0:
                        failures.append(
                            f"{template_id}/cover: slots['{extra_slot}']={extra_hex} on "
                            f"backgrounds['cover']='{bg_slot}'={cover_bg_hex} -> contrast {extra_ratio:.2f} < 3.0"
                        )
    assert not failures, "\n".join(failures)


def test_bold_cover_meta_and_date_now_pass_the_contrast_guard():
    """Pins the fix: Bold's cover_meta/cover_date used to resolve to
    "secondary" (1E293B), nearly invisible on Bold's bg_dark (0F172A,
    ratio ~1.22). They now resolve to "text_muted" (64748B)."""
    tpl = get_template("bold")
    assert tpl.slots["cover_meta"] == "text_muted"
    assert tpl.slots["cover_date"] == "text_muted"
    # cover_meta_brand (the bold brand-name run) stays on the light slot.
    assert tpl.slots.get("cover_meta_brand", DEFAULT_TEMPLATE.slots["cover_meta_brand"]) == "text_light"

    theme = _resolved_theme_for(tpl)
    cover_bg = theme[tpl.backgrounds["cover"]]
    meta_ratio = _contrast_ratio(theme[tpl.slots["cover_meta"]], cover_bg)
    date_ratio = _contrast_ratio(theme[tpl.slots["cover_date"]], cover_bg)
    assert meta_ratio >= 3.0, meta_ratio
    assert date_ratio >= 3.0, date_ratio


def test_contrast_cover_badge_text_on_badge_fill():
    """Extra check beyond the required per-slide-kind table: the cover
    badge's TEXT sits on its own accent-filled shape, not the slide
    background, so it needs its own pairing (slots["cover_badge_text"] vs
    slots["cover_badge_bg"]). Asserted >= 3.0 for executive/bold — the two
    templates this step introduces. default's existing badge (white text on
    its gold accent fill) measures under 3.0 already; that is a pre-existing
    characteristic of the Step 4a default template this step is not
    authorized to change, so it is computed and left for review (see the
    OUTPUT report) rather than asserted here."""
    ratios = {}
    for template_id in _SHIPPED_TEMPLATE_IDS:
        tpl = get_template(template_id)
        theme = _resolved_theme_for(tpl)
        text_hex = theme[tpl.slots["cover_badge_text"]]
        bg_hex = theme[tpl.slots["cover_badge_bg"]]
        ratios[template_id] = _contrast_ratio(text_hex, bg_hex)

    for tid, ratio in ratios.items():
        if tid == "default":
            continue  # pre-existing characteristic — see docstring
        assert ratio >= 3.0, f"{tid}: badge text-on-fill ratio {ratio:.2f} < 3.0"


def test_executive_badge_now_uses_text_dark_and_clears_4_point_4():
    """Pins the fix: executive's cover badge now maps cover_badge_text to
    "text_dark" (1A1A1A) instead of inheriting the default's "text_light"
    (white), which only cleared 3.95 against the gold accent fill (9A7B4F).
    text_dark on that same accent measures ~4.41 — a solid improvement, and
    comfortably above the 3.0 AA-large-text floor, but NOTE: it lands just
    under the 4.5 AA-normal-text target because 1A1A1A (not pure black) is
    the darkest literal the executive palette's 9 slots offer; reaching 4.5
    exactly would require darkening the palette's text_dark/accent hex
    values themselves, which is out of this change's scope (slot remapping
    only, no new hex values)."""
    tpl = get_template("executive")
    assert tpl.slots["cover_badge_text"] == "text_dark"

    theme = _resolved_theme_for(tpl)
    ratio = _contrast_ratio(theme["text_dark"], theme["accent"])
    assert 4.0 <= ratio < 4.5, ratio


# ─────────────────────────────────────────────────────────────────────────────
# chart_palette — per-template ordered series color list threaded into
# render_chart_image(palette=...). default must equal EXECUTIVE_COLORS
# verbatim (byte-identical default charts); executive/bold ship their own.
# ─────────────────────────────────────────────────────────────────────────────
def test_default_chart_palette_equals_executive_colors():
    from backend.utils.chart_renderer import EXECUTIVE_COLORS

    assert DEFAULT_TEMPLATE.chart_palette == EXECUTIVE_COLORS
    assert get_template(None).chart_palette == EXECUTIVE_COLORS
    assert get_template("default").chart_palette == EXECUTIVE_COLORS


def test_executive_and_bold_ship_their_own_chart_palette():
    assert get_template("executive").chart_palette == [
        "1A1A2E", "9A7B4F", "6B6B7B", "4E6E5D", "A8755C", "8A8AA0",
    ]
    assert get_template("bold").chart_palette == [
        "2563EB", "F59E0B", "10B981", "EF4444", "8B5CF6", "06B6D4",
    ]
    # Distinct from default's — proves the per-template override actually
    # took effect rather than silently falling back.
    assert get_template("executive").chart_palette != DEFAULT_TEMPLATE.chart_palette
    assert get_template("bold").chart_palette != DEFAULT_TEMPLATE.chart_palette


def test_pptx_service_passes_template_chart_palette_into_chart_rendering(monkeypatch):
    captured_palettes = []
    real_render = pptx_service_module.render_chart_image

    def spy_render(data, figsize=None, palette=None):
        captured_palettes.append(palette)
        return real_render(data, figsize=figsize, palette=palette)

    monkeypatch.setattr(pptx_service_module, "render_chart_image", spy_render)

    content = """### Section
#### Chart
```recharts
{"type": "bar", "data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]}
```
"""
    for template_id, expected in (
        (None, DEFAULT_TEMPLATE.chart_palette),
        ("executive", get_template("executive").chart_palette),
        ("bold", get_template("bold").chart_palette),
    ):
        captured_palettes.clear()
        _run(generate_pptx({"title": "T", "content": content, "template_id": template_id}))
        assert captured_palettes, f"render_chart_image was never called for template_id={template_id!r}"
        assert all(p == expected for p in captured_palettes)


# ─────────────────────────────────────────────────────────────────────────────
# Cover layout recipes — art.cover.layout selects the cover COMPOSITION
# (classic | centered | sidebar | band | hero); "classic" is the original body.
# ─────────────────────────────────────────────────────────────────────────────
_COVER_LAYOUT_NAMES = ("classic", "centered", "sidebar", "band", "hero")
_EXPECTED_COVER_LAYOUTS = {
    "default": "classic",
    "executive": "centered",
    "bold": "band",
    "corporate-blue": "sidebar",
    "midnight-tech": "hero",
    "minimalist-mono": "centered",
    "warm-editorial": "band",
}


def _tpl_with_cover_layout(base: TemplateSpec, layout) -> TemplateSpec:
    from dataclasses import replace

    cover = {k: v for k, v in base.art["cover"].items() if k != "layout"}
    if layout is not None:
        cover["layout"] = layout
    return replace(base, art={**base.art, "cover": cover})


def _render_cover(tpl: TemplateSpec, logo_asset=None):
    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])
    theme = _resolved_theme_for(tpl)
    slide = pptx_service_module._create_cover_slide(
        prs, "Executive Summary", "Cog Culture", "Brand Positioning", theme, tpl,
        date="January 01, 2026", logo_asset=logo_asset,
    )
    return slide


def _sample_logo_asset():
    buf = io.BytesIO()
    Image.new("RGBA", (400, 200), (200, 50, 50, 255)).save(buf, format="PNG")
    return {"bytes": buf.getvalue(), "width": 400, "height": 200}


def test_every_shipped_template_has_its_assigned_cover_layout():
    for template_id, layout in _EXPECTED_COVER_LAYOUTS.items():
        assert get_template(template_id).art["cover"]["layout"] == layout, template_id
    assert DEFAULT_TEMPLATE.art["cover"]["layout"] == "classic"


def test_unknown_or_omitted_cover_layout_falls_back_to_classic():
    from lxml import etree

    classic_xml = etree.tostring(_render_cover(_tpl_with_cover_layout(DEFAULT_TEMPLATE, "classic"))._element)
    for layout in (None, "does-not-exist", ""):
        xml = etree.tostring(_render_cover(_tpl_with_cover_layout(DEFAULT_TEMPLATE, layout))._element)
        assert xml == classic_xml, f"layout={layout!r} did not fall back to classic"


def test_classic_dispatch_is_identical_to_the_original_classic_body():
    from lxml import etree

    tpl = _tpl_with_cover_layout(DEFAULT_TEMPLATE, "classic")
    theme = _resolved_theme_for(tpl)
    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])
    direct = pptx_service_module._cover_classic(
        prs, "Executive Summary", "Cog Culture", "Brand Positioning", theme, tpl, date="January 01, 2026",
    )
    via_dispatch = _render_cover(tpl)
    assert etree.tostring(direct._element) == etree.tostring(via_dispatch._element)


def test_every_cover_recipe_renders_on_a_light_and_a_dark_template_with_and_without_logo():
    # dark cover bg: default / bold; light cover bg: executive / warm-editorial.
    for template_id in ("default", "bold", "executive", "warm-editorial"):
        base = get_template(template_id)
        for layout in _COVER_LAYOUT_NAMES:
            tpl = _tpl_with_cover_layout(base, layout)
            for logo in (None, _sample_logo_asset()):
                slide = _render_cover(tpl, logo_asset=logo)
                text = "\n".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
                assert "Cog Culture" in text, f"{template_id}/{layout}: brand title missing"
                assert "Executive Summary" not in text, f"{template_id}/{layout}: first-heading title leaked"
                assert "BRAND POSITIONING REPORT" in text, f"{template_id}/{layout}: badge missing"
                if logo:
                    assert any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in slide.shapes), f"{template_id}/{layout}: logo missing"


def test_cover_recipes_keep_all_shapes_inside_the_slide():
    for template_id in ("default", "executive"):
        base = get_template(template_id)
        for layout in _COVER_LAYOUT_NAMES:
            tpl = _tpl_with_cover_layout(base, layout)
            for logo in (None, _sample_logo_asset()):
                slide = _render_cover(tpl, logo_asset=logo)
                width, height = Inches(tpl.geometry["canvas"]["width"]), Inches(tpl.geometry["canvas"]["height"])
                for shape in slide.shapes:
                    assert shape.left >= 0 and shape.top >= 0, f"{template_id}/{layout}: shape starts off-slide"
                    assert shape.left + shape.width <= width + 10, f"{template_id}/{layout}: shape overflows right"
                    assert shape.top + shape.height <= height + 10, f"{template_id}/{layout}: shape overflows bottom"


def test_band_and_sidebar_text_contrasts_with_the_band_fill_not_the_slide_background():
    """For sidebar/band covers the title/meta sit on cover_band_fill, so check
    cover_band_text against that fill (>= 3.0) for every template that uses
    one of those layouts — and for every template if it were switched to one."""
    failures = []
    for template_id in _SHIPPED_TEMPLATE_IDS:
        tpl = get_template(template_id)
        theme = _resolved_theme_for(tpl)
        fill_hex = theme[tpl.slots["cover_band_fill"]]
        text_hex = theme[tpl.slots["cover_band_text"]]
        ratio = _contrast_ratio(text_hex, fill_hex)
        if ratio < 3.0:
            failures.append(f"{template_id}: cover_band_text {text_hex} on cover_band_fill {fill_hex} -> {ratio:.2f} < 3.0")
        if tpl.art["cover"]["layout"] in ("band", "sidebar"):
            # the band must also be visible against the cover background it sits on
            bg_hex = theme[tpl.backgrounds["cover"]]
            if fill_hex == bg_hex:
                failures.append(f"{template_id}: band fill {fill_hex} is identical to the cover background")
    assert not failures, "\n".join(failures)


# ─────────────────────────────────────────────────────────────────────────────
# Render harness — all three templates render a shared sample deck without
# exception, producing valid (PK-header) .pptx files.
# ─────────────────────────────────────────────────────────────────────────────
def test_render_harness_produces_valid_pptx_previews_for_all_shipped():
    from backend.scripts import render_template_previews

    paths = _run(render_template_previews.render_all())
    assert len(paths) == len(_SHIPPED_TEMPLATE_IDS)
    for path in paths:
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read(2) == b"PK"


def test_default_deck_unchanged_by_shipping_new_templates():
    # Regression: adding "executive"/"bold" to the registry must not alter
    # what template_id=None (or "default") renders. Reuses the same
    # assertions as the existing cover-background test.
    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "agent_type": "seo-strategy",
    }))
    prs = Presentation(io.BytesIO(data))
    theme = _get_theme("seo-strategy")
    assert prs.slides[0].background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_dark"])
