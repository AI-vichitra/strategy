"""Tests for Slice 4b — wiring plan_report_llm into PPTX export (flag-gated)
plus render-time bullets pagination. Run with:
cd backend && python -m pytest tests/test_pptx_export_llm_flag.py -v

No real LLM is ever called: SLIDE_PLANNER_LLM is monkeypatched on the
slide_planner module (which generate_pptx reads dynamically, so the patch is
visible), and `slide_planner._default_llm_completion` is monkeypatched to a
fake single-completion callable — exactly the seam plan_report_llm expects.
"""
import asyncio
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pptx import Presentation

import backend.services.slide_planner as slide_planner
from backend.services.pptx_service import generate_pptx
from backend.services.template_service import DEFAULT_TEMPLATE


def _run(coro):
    return asyncio.run(coro)


def _slide_texts(pptx_bytes):
    prs = Presentation(io.BytesIO(pptx_bytes))
    return [
        "\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
        for s in prs.slides
    ]


# Prose (not bullet-list-shaped) so the DETERMINISTIC planner would keep each
# of these as a single plain "bullets" paragraph slide — any stat_row/timeline
# slide we find in the flag-ON deck can only have come from the LLM path.
_METRICS_PROSE = (
    "Our market reached $480M in size with growth of 15% year over year, "
    "against a tracked base of 12 key players this year."
)
_ROADMAP_PROSE = (
    "Our roadmap runs through Q1 2025 with research, Q2 2025 with strategy "
    "work, Q3 2025 for building the platform, and Q4 2025 to scale usage."
)
_LONG_LIST_PROSE = "See the fourteen launch-readiness checks below for this release."

_CONTENT = f"""### Key Metrics
{_METRICS_PROSE}

### Delivery Plan
{_ROADMAP_PROSE}

### Long List
{_LONG_LIST_PROSE}
"""

_LONG_LIST_ITEMS = [
    {"text": f"Checklist item number {i} is complete and verified", "level": 0, "bullet": True, "is_subsection_label": False}
    for i in range(1, 15)
]

_LLM_RESPONSES_BY_TITLE = {
    "Key Metrics": {
        "blocks": [
            {
                "component": "stat_row",
                "data": {
                    "heading": "Key Metrics",
                    "stats": [
                        {"value": "$480M", "label": "Market size"},
                        {"value": "15%", "label": "YoY growth"},
                        {"value": "12", "label": "Key players"},
                    ],
                },
            }
        ],
    },
    "Delivery Plan": {
        "blocks": [
            {
                "component": "timeline",
                "data": {
                    "heading": "Delivery Plan",
                    "phases": [
                        {"label": "Phase 1", "title": "Research", "period": "Q1 2025"},
                        {"label": "Phase 2", "title": "Strategy", "period": "Q2 2025"},
                        {"label": "Phase 3", "title": "Build", "period": "Q3 2025"},
                        {"label": "Phase 4", "title": "Scale", "period": "Q4 2025"},
                    ],
                },
            }
        ],
    },
    "Long List": {
        "blocks": [
            {"component": "bullets", "data": {"title": "Long List", "items": _LONG_LIST_ITEMS}},
        ],
    },
}


def _fake_llm_ok(system_prompt, user_prompt):
    # plan_report_llm now calls the llm ONCE PER SECTION (Slice 4e), so route
    # by whichever "=== SECTION: <title> ===" marker is in this call's prompt.
    for title, resp in _LLM_RESPONSES_BY_TITLE.items():
        if f"=== SECTION: {title} ===" in user_prompt:
            return json.dumps(resp)
    raise AssertionError(f"no fake response configured for prompt: {user_prompt[:200]!r}")


def _fake_llm_raises(system_prompt, user_prompt):
    raise RuntimeError("simulated provider outage")


def _report(content=_CONTENT):
    return {"title": "T", "content": content, "template_id": None}


def test_flag_off_default_is_byte_identical_deck(monkeypatch):
    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", False)
    a = _run(generate_pptx(_report()))
    b = _run(generate_pptx(_report()))
    assert a == b  # deterministic path is itself stable/reproducible
    texts = _slide_texts(a)
    assert any("Key Metrics" in t for t in texts)
    # with the flag off, the prose sections stay plain bullets, not stat_row/timeline
    assert not any("MARKET SIZE" in t.upper() and "$480M" in t for t in texts if "PHASE" not in t.upper())


def test_flag_on_fake_llm_failure_falls_back_to_byte_identical_deck(monkeypatch):
    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", False)
    off_bytes = _run(generate_pptx(_report()))

    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", True)
    monkeypatch.setattr(slide_planner, "_default_llm_completion", _fake_llm_raises)
    on_but_failing_bytes = _run(generate_pptx(_report()))

    assert off_bytes == on_but_failing_bytes


def test_flag_on_fake_llm_produces_stat_row_timeline_and_paginated_bullets(monkeypatch):
    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", True)
    monkeypatch.setattr(slide_planner, "_default_llm_completion", _fake_llm_ok)

    data = _run(generate_pptx(_report()))
    texts = _slide_texts(data)

    stat_row_slides = [t for t in texts if "$480M" in t and "MARKET SIZE" in t.upper()]
    assert len(stat_row_slides) == 1

    timeline_slides = [t for t in texts if "PHASE 1" in t.upper() and "PHASE 4" in t.upper()]
    assert len(timeline_slides) == 1
    assert "Q1 2025" in timeline_slides[0] and "Q4 2025" in timeline_slides[0]

    long_list_slides = [t for t in texts if "Checklist item" in t]
    assert len(long_list_slides) == 2  # 14 items, MAX_ITEMS_PER_SLIDE=9 -> 9 + 5
    assert "(cont'd)" in long_list_slides[1]
    all_checklist_text = "\n".join(long_list_slides)
    for i in range(1, 15):
        assert f"Checklist item number {i} is complete" in all_checklist_text


def test_flag_on_paginated_bullets_slides_each_respect_item_cap(monkeypatch):
    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", True)
    monkeypatch.setattr(slide_planner, "_default_llm_completion", _fake_llm_ok)

    data = _run(generate_pptx(_report()))
    prs = Presentation(io.BytesIO(data))
    for slide in prs.slides:
        texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
        joined = "\n".join(texts)
        if "Checklist item" in joined:
            bullet_lines = [l for l in joined.splitlines() if "Checklist item" in l]
            assert len(bullet_lines) <= 9


def test_flag_on_malformed_llm_response_falls_back_to_byte_identical_deck(monkeypatch):
    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", False)
    off_bytes = _run(generate_pptx(_report()))

    monkeypatch.setattr(slide_planner, "SLIDE_PLANNER_LLM", True)
    monkeypatch.setattr(slide_planner, "_default_llm_completion", lambda s, u: "not json {{")
    on_but_broken_bytes = _run(generate_pptx(_report()))

    assert off_bytes == on_but_broken_bytes
