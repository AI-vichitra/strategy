"""Tests for slide_planner (Slice 1 IR seam) and pptx_service._render_block —
run with: cd backend && python -m pytest tests/test_slide_planner.py -v

Slice 1 is a no-op: the regression proof is that the existing layout tests in
test_pptx_service.py / test_template_service.py pass unmodified, plus the
equivalence checks here (planner output == the old parser's output, and the
rendered deck equals one built by the pre-IR loop)."""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pptx import Presentation

import backend.services.pptx_service as pptx_service_module
from backend.services.pptx_service import (
    generate_pptx,
    _parse_markdown_to_slides,
    _render_block,
    _resolve_theme,
)
from backend.services.slide_planner import SlideBlock, plan_section
from backend.services.template_service import get_template, DEFAULT_TEMPLATE
from backend.scripts.render_template_previews import SAMPLE_CONTENT

_SECTION = """
#### Key Findings
- Finding one with enough words to clear the sparse-merge threshold entirely and read naturally here
- Finding two with enough words to clear the sparse-merge threshold entirely and read naturally here
- Finding three with enough words to clear the sparse-merge threshold entirely and read naturally here

#### Market Size
| Metric | 2023 | 2024 |
| --- | --- | --- |
| Revenue | $1.2B | $1.6B |

#### Pricing
```recharts
{"type": "bar", "title": "Pricing Index", "data": [{"name": "A", "value": 9}, {"name": "B", "value": 6}]}
```
"""


def _run(coro):
    return asyncio.run(coro)


def test_plan_section_returns_slideblocks_with_known_components_and_source_section():
    blocks = plan_section(_SECTION, "Market Overview", DEFAULT_TEMPLATE)
    assert [b.component for b in blocks] == ["bullets", "table", "chart"]
    assert all(isinstance(b, SlideBlock) for b in blocks)
    assert all(b.source_section == "Market Overview" for b in blocks)
    assert "items" in blocks[0].data and "rows" in blocks[1].data and "chart_json" in blocks[2].data
    assert all("type" not in b.data for b in blocks)


def test_plan_section_matches_the_existing_parser_block_for_block():
    for template_id in (None, "bold"):
        tpl = get_template(template_id)
        specs = _parse_markdown_to_slides(_SECTION, tpl, default_title="Market Overview")
        blocks = plan_section(_SECTION, "Market Overview", tpl)
        assert len(blocks) == len(specs)
        to_component = {"content": "bullets", "table": "table", "chart": "chart"}
        for spec, block in zip(specs, blocks):
            assert block.component == to_component[spec["type"]]
            assert block.data == {k: v for k, v in spec.items() if k != "type"}


# Step 7 removed the byte-identical-to-the-legacy-loop regression test that
# used to live here (test_ir_rendering_is_slide_xml_identical_to_the_legacy_
# loop, plus its _legacy_section_slides fixture). That test's whole premise —
# the Slice 1 IR refactor was a pure no-op, provable by re-running a frozen
# pre-IR rendering path and diffing slide XML — stopped being the goal
# starting with Slice 2 (stat_row) and every slice since, and the chrome pass
# (every _render_*_block now calls _add_content_chrome instead of the bare
# _add_title_bar, with a per-section eyebrow) is explicitly NOT byte-identical
# by design. test_render_block_routes_each_component_to_its_renderer below
# still proves IR dispatch itself is correct (right block -> right renderer);
# test_full_deck_slide_count_and_text_unchanged_across_templates still proves
# cross-template consistency of what IS still shared (slide count, body text).


def test_full_deck_slide_count_and_text_unchanged_across_templates():
    # Same sample the preview script uses; every template keeps the same
    # slide count (fit model identical) and the same non-cover text content.
    def deck_signature(template_id):
        data = _run(generate_pptx({"title": "T", "content": SAMPLE_CONTENT, "template_id": template_id}))
        prs = Presentation(io.BytesIO(data))
        return [
            "\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            for s in list(prs.slides)[1:]  # skip the cover (layout-specific)
        ]

    default_sig = deck_signature(None)
    assert len(default_sig) >= 8
    for template_id in ("bold", "executive", "corporate-blue"):
        sig = deck_signature(template_id)
        assert len(sig) == len(default_sig)
        assert sig == default_sig


def _block(component, **data):
    return SlideBlock(component=component, data=data, source_section="S")


def test_render_block_routes_each_component_to_its_renderer(monkeypatch):
    calls = []
    sentinel = object()
    for name in ("_render_bullets_block", "_render_table_block", "_render_chart_block"):
        monkeypatch.setattr(pptx_service_module, name, lambda *a, _n=name, **k: (calls.append(_n), sentinel)[1])

    tpl = DEFAULT_TEMPLATE
    for component, expected in (
        ("bullets", "_render_bullets_block"),
        ("table", "_render_table_block"),
        ("chart", "_render_chart_block"),
    ):
        calls.clear()
        assert _render_block(None, _block(component), {}, tpl) is sentinel
        assert calls == [expected]


def test_unknown_component_falls_back_to_bullets_renderer_without_error():
    prs = Presentation()
    tpl = DEFAULT_TEMPLATE
    theme = _resolve_theme(None, None, "default", base=tpl.palette)
    items = [{"bullet": True, "text": "Hello", "level": 0, "is_subsection_label": False}]
    slide = _render_block(prs, _block("sparkline", title="Future Component", items=items), theme, tpl)
    text = "\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
    assert "Future Component" in text and "Hello" in text
    assert len(prs.slides) == 1
