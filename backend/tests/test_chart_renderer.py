"""Tests for chart_renderer.render_chart_image() — run with:
cd backend && python -m pytest tests/test_chart_renderer.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.utils.chart_renderer import render_chart_image

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
