"""Tests for the agent-extracted brand palette — the LLM-inferred fallback
theme used when the client skipped manual Brand Kit colors. Run with:
cd backend && python -m pytest tests/test_brand_palette.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services import output_validator
from backend.services.pptx_service import _resolve_theme, _get_theme


def test_brandpalette_block_is_stripped_from_content():
    content = (
        "### Executive Summary\nSome strategic text.\n\n"
        '```brandpalette\n{"primary":"#8E24AA","secondary":"#AB47BC","accent":"#FFB300"}\n```\n'
    )
    stripped = output_validator.strip_brand_palette_block(content)
    assert "brandpalette" not in stripped
    assert "#8E24AA" not in stripped
    assert "Executive Summary" in stripped  # rest of the content survives


def test_extracted_palette_used_when_no_manual_colors():
    palette = {"primary": "#8E24AA", "secondary": "#AB47BC", "accent": "#FFB300"}
    theme = _resolve_theme(None, palette, "default")
    assert theme["primary"] == "8E24AA"
    assert theme != _get_theme("default")


def test_manual_colors_win_over_extracted():
    manual = {"colors": {"primary": "#2C5F8A"}}
    extracted = {"primary": "#8E24AA", "secondary": "#AB47BC", "accent": "#FFB300"}
    theme = _resolve_theme(manual, extracted, "default")
    assert theme["primary"] == "2C5F8A"


def test_no_palette_no_brandkit_uses_report_theme():
    assert _resolve_theme(None, None, "seo-strategy") == _get_theme("seo-strategy")
    assert _resolve_theme({"colors": {}}, None, "seo-strategy") == _get_theme("seo-strategy")


def test_malformed_brandpalette_falls_back():
    content = "### Section\nText.\n\n```brandpalette\nnot valid json at all\n```\n"
    palette = output_validator.extract_brand_palette(content)
    assert palette is None

    stripped = output_validator.strip_brand_palette_block(content)
    assert "brandpalette" not in stripped

    theme = _resolve_theme(None, palette, "seo-strategy")
    assert theme == _get_theme("seo-strategy")
