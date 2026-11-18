"""Renders bullets/stat_row/timeline slides carrying a headline takeaway
(Step 8 — planner slide-shaping) for the corporate-blue and midnight-tech
templates, for visual review of _add_content_chrome's takeaway band and the
content-shift it causes.

Run with:
cd backend && python scripts/render_takeaway_previews.py
(or: python -m backend.scripts.render_takeaway_previews from the repo root)

Builds SlideBlocks directly (bypassing the LLM) so the takeaway text is
fixed and reviewable, rather than depending on a live model call.
"""
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
_REPO_ROOT = os.path.dirname(_BACKEND_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pptx import Presentation
from pptx.util import Inches

from backend.services.pptx_service import _render_block, _resolve_theme, _add_slide_number  # noqa: E402
from backend.services.slide_planner import SlideBlock, COMPONENT_BULLETS, COMPONENT_STAT_ROW, COMPONENT_TIMELINE  # noqa: E402
from backend.services.template_service import get_template  # noqa: E402

_OUT_DIR = os.path.join(_BACKEND_ROOT, "tmp_template_preview")

_BLOCKS = [
    SlideBlock(COMPONENT_BULLETS, {
        "title": "Key Findings",
        "takeaway": "Price and quality now decide purchase intent across every surveyed segment",
        "items": [
            {"text": "Price sensitivity is the single largest factor in this category", "level": 0, "bullet": True, "is_subsection_label": False},
            {"text": "Peer recommendations carry outsized weight among younger buyers", "level": 0, "bullet": True, "is_subsection_label": False},
            {"text": "Mobile browsing dominates the discovery phase this year", "level": 0, "bullet": True, "is_subsection_label": False},
        ],
    }, "Market Overview"),
    SlideBlock(COMPONENT_STAT_ROW, {
        "heading": "Key Metrics",
        "takeaway": "A $480M market is compounding fast with 12 active players",
        "stats": [
            {"value": "$480M", "label": "Market size"},
            {"value": "15%", "label": "CAGR growth"},
            {"value": "12", "label": "Key players", "sublabel": "tracked"},
        ],
    }, "Key Metrics"),
    SlideBlock(COMPONENT_TIMELINE, {
        "heading": "Delivery Plan",
        "takeaway": "Four phases carry the platform from research to a scaled launch",
        "phases": [
            {"label": "Phase 1", "title": "Research", "period": "Q1 2025"},
            {"label": "Phase 2", "title": "Strategy", "period": "Q2 2025"},
            {"label": "Phase 3", "title": "Build", "period": "Q3 2025"},
            {"label": "Phase 4", "title": "Scale", "period": "Q4 2025"},
        ],
    }, "Delivery Plan"),
]


def _render_one(template_id, filename):
    tpl = get_template(template_id)
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    prs = Presentation()
    prs.slide_width = Inches(tpl.geometry["canvas"]["width"])
    prs.slide_height = Inches(tpl.geometry["canvas"]["height"])

    for i, block in enumerate(_BLOCKS, 1):
        slide = _render_block(prs, block, theme, tpl, section_index=i)
        _add_slide_number(slide, i, theme, tpl)

    os.makedirs(_OUT_DIR, exist_ok=True)
    path = os.path.join(_OUT_DIR, filename)
    try:
        prs.save(path)
    except PermissionError:
        path = os.path.join(_OUT_DIR, filename.replace(".pptx", ".NEW.pptx"))
        prs.save(path)
    return path


def main():
    paths = [
        _render_one("corporate-blue", "chrome-corporate-blue-takeaway.pptx"),
        _render_one("midnight-tech", "chrome-midnight-tech-takeaway.pptx"),
    ]
    print("Rendered takeaway previews:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
