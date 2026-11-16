"""Tests for the brand_kit schema round-trip — run with:
cd backend && python -m pytest tests/test_brand_kit.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import pytest
from pydantic import ValidationError

from backend.schemas.project import BrandKit, ProjectResponse


def _base_response_kwargs(brand_kit):
    return dict(
        id="proj-1",
        user_id="user-1",
        brand_config_id="brand-1",
        agent_type="brand-positioning",
        title="Test Project",
        created_at="2026-01-01T00:00:00",
        brand_kit=brand_kit,
    )


def test_valid_brand_kit_serializes_and_parses_back():
    brand_kit = BrandKit(
        logo_url="/static/uploads/logos/abc123.png",
        colors={"primary": "#2C5F8A", "secondary": "#FFF", "accent": "#A1B2C3"},
    )
    stored = json.dumps(brand_kit.model_dump())

    response = ProjectResponse(**_base_response_kwargs(stored))

    assert response.brand_kit.logo_url == "/static/uploads/logos/abc123.png"
    assert response.brand_kit.colors.primary == "#2C5F8A"
    assert response.brand_kit.colors.secondary == "#FFF"
    assert response.brand_kit.colors.accent == "#A1B2C3"


def test_invalid_hex_color_rejected():
    with pytest.raises(ValidationError):
        BrandKit(colors={"primary": "not-a-color"})


def test_none_brand_kit_is_allowed():
    response = ProjectResponse(**_base_response_kwargs(None))
    assert response.brand_kit is None


def test_empty_string_brand_kit_is_allowed():
    response = ProjectResponse(**_base_response_kwargs(""))
    assert response.brand_kit is None
