"""Tests for chart_renderer.render_chart_image() — run with:
cd backend && python -m pytest tests/test_chart_renderer.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.utils.chart_renderer import render_chart_image, EXECUTIVE_COLORS

COG_CULTURE_SCATTER = {
    "type": "scatter",
    "title": "Competitive Positioning Map",
    "x_label": "Tech Integration (1-10)",
    "y_label": "Human-Centric Design (1-10)",
    "data": [
        {"name": "Cog Culture", "x": 8, "y": 9},
        {"name": "Wunderman Thompson", "x": 7, "y": 5},
        {"name": "Ogilvy", "x": 6, "y": 4},
        {"name": "Edelman", "x": 3, "y": 2},
        {"name": "The Brand Identity", "x": 4, "y": 9},
    ],
}


def test_scatter_chart_renders_image():
    png_bytes = render_chart_image(COG_CULTURE_SCATTER)

    assert png_bytes is not None
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png_bytes) > 2000


def test_scatter_chart_type_aliases_render():
    for alias in ("scatter_chart", "quadrant", "positioning_map", "xy"):
        aliased = dict(COG_CULTURE_SCATTER, type=alias)
        png_bytes = render_chart_image(aliased)
        assert png_bytes is not None, f"alias {alias!r} did not render"
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_scatter_auto_detected_from_xy_shape_without_type():
    untyped = {k: v for k, v in COG_CULTURE_SCATTER.items() if k != "type"}
    png_bytes = render_chart_image(untyped)
    assert png_bytes is not None
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_unknown_chart_type_still_returns_none():
    png_bytes = render_chart_image({"type": "heatmap", "data": [{"name": "A", "value": 5}]})
    assert png_bytes is None


def test_existing_bar_chart_still_renders():
    png_bytes = render_chart_image({
        "type": "bar",
        "title": "Pricing Index",
        "data": [{"name": "Brand A", "value": 8}, {"name": "Brand B", "value": 5}],
    })
    assert png_bytes is not None
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


# ─────────────────────────────────────────────────────────────────────────────
# palette param — DOCX (export_service) always calls with no palette, so it
# must keep rendering with EXECUTIVE_COLORS exactly, byte-for-byte.
# ─────────────────────────────────────────────────────────────────────────────
_BAR_CHART = {
    "type": "bar",
    "title": "Pricing Index",
    "data": [{"name": "Brand A", "value": 8}, {"name": "Brand B", "value": 5}, {"name": "Brand C", "value": 3}],
}


def test_palette_none_is_byte_identical_to_omitting_the_param():
    with_default_arg = render_chart_image(_BAR_CHART, palette=None)
    without_arg = render_chart_image(_BAR_CHART)
    assert with_default_arg == without_arg


def test_palette_matching_executive_colors_is_byte_identical_to_none():
    # The default PPTX template passes tpl.chart_palette, which equals
    # EXECUTIVE_COLORS verbatim — must render the exact same pixels as the
    # palette=None (DOCX) path.
    explicit = render_chart_image(_BAR_CHART, palette=list(EXECUTIVE_COLORS))
    implicit = render_chart_image(_BAR_CHART, palette=None)
    assert explicit == implicit


def test_custom_palette_renders_without_the_hash_prefix():
    # Template JSON entries store hex strings without a leading '#'
    # (e.g. "2563EB") — render_chart_image must normalize them itself.
    png_bytes = render_chart_image(_BAR_CHART, palette=["2563EB", "F59E0B", "10B981"])
    assert png_bytes is not None
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    # And it must actually be a different image from the default palette.
    assert png_bytes != render_chart_image(_BAR_CHART, palette=None)


def test_custom_palette_applies_to_every_chart_type():
    palette = ["2563EB", "F59E0B", "10B981", "EF4444"]
    charts = [
        {"type": "bar", "data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]},
        {"type": "line", "data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]},
        {"type": "area", "data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]},
        {"type": "radar", "data": [{"subject": "A", "value": 1}, {"subject": "B", "value": 2}]},
        {"type": "pie", "data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]},
        dict(COG_CULTURE_SCATTER),
    ]
    for chart in charts:
        png_bytes = render_chart_image(chart, palette=palette)
        assert png_bytes is not None, f"{chart['type']} failed to render with a custom palette"
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
