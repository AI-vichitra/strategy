"""Tests for Slice 3: the timeline detector (slide_planner) and renderer
(pptx_service._render_timeline_block) — run with:
cd backend && python -m pytest tests/test_timeline.py -v
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from backend.services.brand_theme import _luminance, _hex_to_rgb
from backend.services.pptx_service import (
    generate_pptx,
    _render_block,
    _resolve_theme,
)
from backend.services.slide_planner import (
    SlideBlock, plan_section, detect_timeline, _match_phase_cue, COMPONENT_TIMELINE,
)
from backend.services.template_service import get_template, get_templates, DEFAULT_TEMPLATE


def _run(coro):
    return asyncio.run(coro)


def _plan(markdown, title="S"):
    return plan_section(markdown, title, DEFAULT_TEMPLATE)


def _slide_text(slide):
    return "\n".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)


# ── cue matching ────────────────────────────────────────────────────────────
def test_cue_matching_all_families():
    assert _match_phase_cue("Phase 1: Research")["family"] == "phase"
    assert _match_phase_cue("Phase 1: Research")["seq"] == 1
    assert _match_phase_cue("Step 3 — Build")["family"] == "step"
    assert _match_phase_cue("Stage 2 (Q2)")["family"] == "stage"
    assert _match_phase_cue("Q3 2025")["family"] == "quarter"
    assert _match_phase_cue("Q3 2025")["label"] == "Q3"
    assert _match_phase_cue("H2 planning")["family"] == "half"
    assert _match_phase_cue("Month 6 review")["family"] == "month"
    assert _match_phase_cue("Week 12 sprint")["family"] == "week"
    assert _match_phase_cue("Year 2 scale")["family"] == "year"
    assert _match_phase_cue("First milestone")["family"] == "ordinal"
    assert _match_phase_cue("Third milestone")["seq"] == 3
    assert _match_phase_cue("No match here") is None
    assert _match_phase_cue("2024 was big") is None


# ── detector fires ──────────────────────────────────────────────────────────
_PHASES_MD = """\
- Phase 1 (Q1 2025): Research — Conduct market analysis
  - Deliverable: Market assessment report
- Phase 2 (Q2 2025): Strategy — Develop positioning plan
  - Deliverable: Strategic roadmap
- Phase 3 (Q3 2025): Build — Implement core features
  - Deliverable: MVP platform
- Phase 4 (Q4 2025): Scale — Expand user acquisition
  - Deliverable: Growth playbook
- What StratAI provides: continuous monitoring and alerts
"""


def test_detector_fires_on_phased_section():
    blocks = _plan(_PHASES_MD, "Delivery Plan")
    assert len(blocks) == 1
    assert blocks[0].component == COMPONENT_TIMELINE
    data = blocks[0].data
    assert data["heading"] == "Delivery Plan"
    assert len(data["phases"]) == 4
    p1 = data["phases"][0]
    assert p1["label"] == "Phase 1"
    assert p1["period"] == "Q1 2025"
    assert p1["title"] == "Research"
    assert "market analysis" in p1.get("description", "").lower()
    assert p1["deliverable"] == "Market assessment report"
    assert "monitoring" in data.get("footer_note", "").lower()


def test_detector_fires_on_step_cues():
    md = "- Step 1: Discovery\n- Step 2: Ideation\n- Step 3: Validation\n"
    blocks = _plan(md, "Process")
    assert blocks[0].component == COMPONENT_TIMELINE
    assert len(blocks[0].data["phases"]) == 3


def test_detector_fires_on_quarter_cues():
    md = "- Q1 Launch campaign\n- Q2 Scale operations\n- Q3 Optimize funnel\n"
    blocks = _plan(md, "Roadmap")
    assert blocks[0].component == COMPONENT_TIMELINE
    assert blocks[0].data["phases"][0]["label"] == "Q1"


def test_detector_fires_on_ordinal_cues():
    md = "- First: Assess the landscape\n- Second: Build the strategy\n- Third: Execute the plan\n"
    blocks = _plan(md, "Approach")
    assert blocks[0].component == COMPONENT_TIMELINE


def test_detector_fires_on_six_phases():
    md = "".join(f"- Phase {i}: Task {i}\n" for i in range(1, 7))
    blocks = _plan(md, "Long Plan")
    assert blocks[0].component == COMPONENT_TIMELINE
    assert len(blocks[0].data["phases"]) == 6


# ── detector does NOT fire ──────────────────────────────────────────────────
def test_detector_does_not_fire_on_normal_bullets():
    prose = (
        "- Consumers weigh price and quality heavily before purchase\n"
        "- Peer recommendations carry outsized weight among buyers\n"
        "- Mobile browsing dominates the discovery phase\n"
    )
    blocks = _plan(prose)
    assert all(b.component != COMPONENT_TIMELINE for b in blocks)


def test_detector_does_not_fire_on_two_items():
    md = "- Phase 1: Research\n- Phase 2: Build\n"
    blocks = _plan(md, "Short")
    assert all(b.component != COMPONENT_TIMELINE for b in blocks)


def test_detector_does_not_fire_on_mixed_families():
    md = "- Phase 1: Research\n- Step 2: Build\n- Stage 3: Launch\n"
    blocks = _plan(md, "Mixed")
    assert all(b.component != COMPONENT_TIMELINE for b in blocks)


def test_detector_does_not_fire_on_non_sequential():
    md = "- Phase 3: Late\n- Phase 1: Early\n- Phase 2: Middle\n"
    blocks = _plan(md, "Shuffled")
    assert all(b.component != COMPONENT_TIMELINE for b in blocks)


def test_detector_does_not_fire_on_seven_phases():
    md = "".join(f"- Phase {i}: Task {i}\n" for i in range(1, 8))
    blocks = _plan(md, "Too Long")
    assert all(b.component != COMPONENT_TIMELINE for b in blocks)


# ── existing detectors still work ──────────────────────────────────────────
def test_stat_row_still_detects():
    md = "- $480M market size\n- 15% CAGR growth\n- 12 key players\n"
    blocks = _plan(md, "Metrics")
    assert blocks[0].component == "stat_row"


def test_normal_bullets_still_work():
    prose = "- Long prose bullet one here and more words to fill it out properly\n- Long prose bullet two here and more words to fill it out\n- Another bullet\n"
    blocks = _plan(prose)
    assert blocks[0].component == "bullets"


# ── renderer ────────────────────────────────────────────────────────────────
def _timeline_block(n, footer=None, deliverables=True):
    pool = [
        {"label": f"Phase {i+1}", "period": f"Q{i+1} 2025", "title": f"Task {i+1}",
         "description": f"Description for phase {i+1}",
         "deliverable": f"Output {i+1}" if deliverables else None}
        for i in range(n)
    ]
    pool = [{k: v for k, v in p.items() if v is not None} for p in pool]
    data = {"heading": "Delivery Plan", "phases": pool}
    if footer:
        data["footer_note"] = footer
    return SlideBlock(component=COMPONENT_TIMELINE, data=data, source_section="Delivery Plan")


def _new_prs(tpl):
    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])
    return prs


def test_timeline_renders_3_4_6_phases_inside_safe_area():
    for template_id in (None, "bold", "executive"):
        tpl = get_template(template_id)
        theme = _resolve_theme(None, None, "default", base=tpl.palette)
        cb = tpl.geometry["content_body"]
        for n in (3, 4, 6):
            for footer in (None, "StratAI provides continuous monitoring"):
                slide = _render_block(_new_prs(tpl), _timeline_block(n, footer=footer), theme, tpl)
                text = _slide_text(slide)
                assert "Delivery Plan" in text
                assert "PHASE 1" in text
                assert "Task 1" in text
                if footer:
                    assert "monitoring" in text.lower()
                # Exclude the chrome footer slot (y=chrome.footer.y, e.g. 7.05in) —
                # it intentionally sits below content_body/safe_bottom, in the
                # slide-number band; it's chrome, not timeline body content.
                footer_y = tpl.geometry["chrome"]["footer"]["y"]
                body = [
                    s for s in slide.shapes
                    if s.top >= Inches(cb["top"]) - 10 and round(s.top / Inches(1), 2) != footer_y
                ]
                for s in body:
                    assert s.left >= Inches(cb["x"]) - 10, (template_id, n)
                    assert s.left + s.width <= Inches(cb["x"] + cb["w"]) + 20, (template_id, n)
                    assert s.top + s.height <= Inches(cb["safe_bottom"]) + 10, (template_id, n, footer)
                chevrons = [s for s in body if s.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
                            and s.height == Inches(tpl.geometry.get("timeline", {}).get("chevron_height", 0.7))]
                assert len(chevrons) == n, (template_id, n)


def test_timeline_chevron_text_contrast_across_ramp_for_every_template():
    def ratio(a, b):
        la, lb = _luminance(a), _luminance(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    failures = []
    for entry in get_templates(enabled_only=False):
        tpl = get_template(entry["id"])
        theme = _resolve_theme(None, None, "default", base=tpl.palette)
        start_rgb = _hex_to_rgb(theme[tpl.slots["timeline_start"]])
        end_rgb = _hex_to_rgb(theme[tpl.slots["timeline_end"]])
        for n in (3, 6):
            for i in range(n):
                t = i / max(n - 1, 1)
                fr = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
                fg = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
                fb = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
                fill = f"{fr:02X}{fg:02X}{fb:02X}"
                l_fill = _luminance(fill)
                l_lt = _luminance(theme["text_light"])
                l_dk = _luminance(theme["text_dark"])
                r_lt = (max(l_fill, l_lt) + 0.05) / (min(l_fill, l_lt) + 0.05)
                r_dk = (max(l_fill, l_dk) + 0.05) / (min(l_fill, l_dk) + 0.05)
                best = max(r_lt, r_dk)
                if best < 3.0:
                    failures.append(f"{entry['id']}: chev {i+1}/{n} fill={fill} best_ratio={best:.2f}")
    assert not failures, "\n".join(failures)


def test_timeline_renders_without_deliverables():
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    slide = _render_block(_new_prs(tpl), _timeline_block(4, deliverables=False), theme, tpl)
    text = _slide_text(slide)
    assert "DELIVERABLE" not in text
    assert "Task 1" in text


def test_generate_pptx_emits_timeline_slide():
    content = (
        "### Delivery Plan\n"
        "- Phase 1 (Q1): Research — Market analysis\n"
        "  - Deliverable: Report\n"
        "- Phase 2 (Q2): Strategy — Positioning\n"
        "  - Deliverable: Roadmap\n"
        "- Phase 3 (Q3): Build — Implementation\n"
        "  - Deliverable: MVP\n"
        "\n### Other\n- Normal bullets here for regression check\n"
    )
    data = _run(generate_pptx({"title": "T", "content": content, "template_id": "bold"}))
    prs = Presentation(io.BytesIO(data))
    texts = [_slide_text(s) for s in prs.slides]
    assert len([t for t in texts if "PHASE 1" in t and "PHASE 3" in t]) == 1
    assert any("Normal bullets" in t for t in texts)
