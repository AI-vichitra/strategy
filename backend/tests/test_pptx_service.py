"""Tests for pptx_service.generate_pptx() — run with:
cd backend && python -m pytest tests/test_pptx_service.py -v

Plain sync test functions (each driving the async service via asyncio.run)
rather than pytest-asyncio, since this repo doesn't otherwise depend on it.
"""
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Inches

from backend.services.pptx_service import (
    generate_pptx,
    REPORT_THEMES,
    _get_theme,
    _theme_from_brand_kit,
    _readable_text,
    CONTENT_SAFE_BOTTOM_IN,
    CONTENT_BODY_TOP_IN,
    CONTENT_BODY_HEIGHT_IN,
)

_STATIC_LOGOS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "logos")


def _run(coro):
    return asyncio.run(coro)


def _slide_text(slide) -> str:
    chunks = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            chunks.append(shape.text_frame.text)
    return "\n".join(chunks)


def test_generate_pptx_returns_valid_pptx_bytes():
    data = _run(generate_pptx({"title": "Minimal Report", "content": "### Only Section\nSome body text."}))
    assert isinstance(data, bytes)
    assert len(data) > 0
    # PPTX is a ZIP container — ZIP files start with the "PK" magic bytes.
    assert data[:2] == b"PK"


def test_cover_slide_title_prefers_brand_name_over_report_title():
    # Intentional: the cover's big title shows the brand name, not
    # report.title (which is derived from the first section heading) —
    # report.title is still used elsewhere (filenames/TOC/etc.), just not
    # rendered as the cover title.
    data = _run(generate_pptx({
        "title": "Executive Summary",
        "content": "### Executive Summary\nSummary text.",
        "brand_name": "Cog Culture",
        "agent_name": "Brand Positioning",
    }))
    prs = Presentation(io.BytesIO(data))
    cover_text = _slide_text(prs.slides[0])
    assert "Cog Culture" in cover_text
    assert "Executive Summary" not in cover_text
    assert "BRAND POSITIONING REPORT" in cover_text


def test_cover_slide_title_falls_back_to_report_title_without_brand_name():
    data = _run(generate_pptx({
        "title": "Cog Culture Brand Strategy",
        "content": "### Executive Summary\nSummary text.",
        "agent_name": "Brand Positioning",
    }))
    prs = Presentation(io.BytesIO(data))
    cover_text = _slide_text(prs.slides[0])
    assert "Cog Culture Brand Strategy" in cover_text


def test_cover_slide_title_falls_back_to_art_default_without_title_or_brand():
    data = _run(generate_pptx({
        "content": "### Executive Summary\nSummary text.",
    }))
    prs = Presentation(io.BytesIO(data))
    cover_text = _slide_text(prs.slides[0])
    assert "Strategic Intelligence Report" in cover_text


def test_heading_and_bullets_produce_multiple_slides():
    # Each H4 has >=3 bullets and >=50 words so neither subsection is "sparse"
    # (fewer than 3 bullets OR fewer than 50 words) and gets merged away.
    filler = "with a reasonably long explanation that pushes the word count well past the fifty word minimum threshold for this test"
    content = f"""### Market Overview

#### Key Findings
- Finding one {filler}
- Finding two {filler}
- Finding three {filler}

#### Sub Trends
- Sub trend one {filler}
- Sub trend two {filler}
- Sub trend three {filler}
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))
    # cover + toc + section-divider + content(Key Findings) + content(Sub Trends) + closing
    assert len(prs.slides) >= 6

    all_text = "\n".join(_slide_text(s) for s in prs.slides)
    assert "Market Overview" in all_text
    assert "Key Findings" in all_text
    assert "Sub Trends" in all_text
    assert "Finding one" in all_text
    assert "Sub trend one" in all_text


def test_sparse_subsection_does_not_get_its_own_empty_slide():
    # A thin H4 (1 short bullet) must not produce a separate title-only
    # divider slide — it should merge onto the next (substantial) subsection.
    content = """### Market Overview

#### Tiny Note
- short

#### Real Content
- Point one with plenty of real substantive words to avoid the sparse threshold entirely
- Point two with plenty of real substantive words to avoid the sparse threshold entirely
- Point three with plenty of real substantive words to avoid the sparse threshold entirely
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    # The old bug: every H4 got its own near-empty title-only slide before
    # its content slide even landed. With the fix there's exactly one
    # section-divider (title-only, by design) and no stray extras.
    all_text = "\n".join(_slide_text(s) for s in prs.slides)
    assert "Tiny Note" in all_text  # context preserved as a lead-in label
    assert "Real Content" in all_text
    assert "short" in all_text
    # cover + toc + section-divider + ONE merged content slide + closing == 5
    assert len(prs.slides) == 5


def test_theme_colors_applied_to_cover_background():
    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "agent_type": "seo-strategy",
    }))
    prs = Presentation(io.BytesIO(data))
    cover = prs.slides[0]
    theme = _get_theme("seo-strategy")
    assert cover.background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_dark"])
    assert theme["bg_dark"] == REPORT_THEMES["seo-strategy"]["bg_dark"]


def test_markdown_bold_renders_as_bold_run_not_literal_asterisks():
    content = "### Section\n\nThis has a **bold phrase** and a *italic phrase* inside it.\n"
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    found_bold_run = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for p in shape.text_frame.paragraphs:
                for run in p.runs:
                    assert "**" not in run.text and "*" not in run.text
                    if run.text == "bold phrase" and run.font.bold:
                        found_bold_run = True
    assert found_bold_run


def test_table_markdown_produces_table_slide():
    content = """### Comparison
| Brand | Score |
| --- | --- |
| Brand A | 9 |
| Brand B | 6 |
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    table_slides = [s for s in prs.slides if any(shape.has_table for shape in s.shapes)]
    assert len(table_slides) == 1

    table = next(shape.table for shape in table_slides[0].shapes if shape.has_table)
    assert table.cell(0, 0).text == "Brand"
    assert table.cell(1, 0).text == "Brand A"
    assert table.cell(1, 1).text == "9"


def test_chart_block_produces_chart_slide():
    content = """### Pricing
```recharts
{"type": "bar", "title": "Pricing Index", "data": [{"name": "Brand A", "value": 9}, {"name": "Brand B", "value": 6}]}
```
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    picture_slides = [s for s in prs.slides if any(shape.shape_type == 13 for shape in s.shapes)]
    assert len(picture_slides) == 1


def test_horizontal_rule_produces_no_slide():
    content = """### Section One
Some intro text here.

---

### Section Two
#### Details
- Point one with enough real words to avoid the sparse-merge threshold entirely
- Point two with enough real words to avoid the sparse-merge threshold entirely
- Point three with enough real words to avoid the sparse-merge threshold entirely
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))
    for slide in prs.slides:
        assert _slide_text(slide).strip() != "---"
        assert "---" not in _slide_text(slide)


def test_table_with_short_trailing_note_stays_one_slide():
    content = """### Market Data

#### Pricing
| Metric | Value |
| --- | --- |
| Revenue | $1.2B |
| Users | 5M |

Data not available for Q4.
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    table_slides = [s for s in prs.slides if any(sh.has_table for sh in s.shapes)]
    assert len(table_slides) == 1
    assert "Data not available for Q4." in _slide_text(table_slides[0])

    # The note must not also appear on some OTHER, separate slide.
    other_slides_with_note = [
        s for s in prs.slides
        if s is not table_slides[0] and "Data not available" in _slide_text(s)
    ]
    assert other_slides_with_note == []


def test_long_bullet_list_splits_across_slides():
    # Distinct letter-labeled bullets avoid "Point 1" vs "Point 10" substring
    # collisions when checking which slide each bullet landed on.
    labels = [f"Bullet-{chr(ord('A') + i)}" for i in range(12)]
    bullets = "\n".join(f"- {label}" for label in labels)
    content = f"### Big Section\n{bullets}\n"
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    all_text = [_slide_text(s) for s in prs.slides]
    slide_of = {label: next(i for i, t in enumerate(all_text) if label in t) for label in labels}

    # 12 bullets at a max of 6/slide must span at least 2 slides.
    assert len(set(slide_of.values())) >= 2
    # First bullet must land on an earlier (or equal, never later) slide than the last.
    assert slide_of[labels[0]] <= slide_of[labels[-1]]


def _write_test_logo(filename="_test_brand_kit_logo.png"):
    os.makedirs(_STATIC_LOGOS_DIR, exist_ok=True)
    path = os.path.join(_STATIC_LOGOS_DIR, filename)
    Image.new("RGB", (300, 120), (255, 0, 0)).save(path, "PNG")
    return f"/static/uploads/logos/{filename}", path


def test_brand_kit_colors_override_theme():
    brand_kit = {"colors": {"primary": "#6A1B9A", "secondary": "#AB47BC", "accent": "#FFB300"}}
    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "agent_type": "seo-strategy",
        "brand_kit": brand_kit,
    }))
    prs = Presentation(io.BytesIO(data))
    cover = prs.slides[0]
    expected_theme = _theme_from_brand_kit(brand_kit, "seo-strategy")
    assert cover.background.fill.fore_color.rgb == RGBColor.from_string(expected_theme["bg_dark"])
    # Must differ from the plain report-type theme's cover bg — brand colors actually took effect.
    assert expected_theme["bg_dark"] != REPORT_THEMES["seo-strategy"]["bg_dark"]


def test_empty_brand_kit_uses_report_theme():
    assert _theme_from_brand_kit(None, "seo-strategy") == _get_theme("seo-strategy")
    assert _theme_from_brand_kit({"colors": {}}, "seo-strategy") == _get_theme("seo-strategy")

    data_none = _run(generate_pptx({"title": "Report", "content": "### Section\nText.", "agent_type": "seo-strategy", "brand_kit": None}))
    prs = Presentation(io.BytesIO(data_none))
    theme = _get_theme("seo-strategy")
    assert prs.slides[0].background.fill.fore_color.rgb == RGBColor.from_string(theme["bg_dark"])


def test_readable_text_on_dark_brand_bg():
    assert _readable_text("1B0033") == "FFFFFF"
    assert _readable_text("F5F0E6") == "1A1A1A"


def test_malformed_brand_color_is_ignored():
    theme = _theme_from_brand_kit({"colors": {"primary": "not-a-color", "secondary": "#AB47BC"}}, "default")
    base = _get_theme("default")
    assert theme["primary"] == base["primary"]  # malformed primary dropped -> base theme's primary
    assert theme["secondary"] == "AB47BC"


def test_missing_logo_file_does_not_crash():
    data = _run(generate_pptx({
        "title": "Report",
        "content": "### Section\nSome text.",
        "brand_kit": {"logo_url": "/static/uploads/logos/does-not-exist.png"},
    }))
    assert data[:2] == b"PK"


def test_brand_kit_logo_is_embedded_on_cover():
    logo_url, path = _write_test_logo()
    try:
        data = _run(generate_pptx({
            "title": "Report",
            "content": "### Section\nSome text.",
            "brand_kit": {"logo_url": logo_url},
        }))
        prs = Presentation(io.BytesIO(data))
        cover = prs.slides[0]
        assert any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in cover.shapes)
    finally:
        if os.path.exists(path):
            os.remove(path)


# ─────────────────────────────────────────────────────────────────────────────
# Bullet styling + mid-list-split fix
# ─────────────────────────────────────────────────────────────────────────────
DARK_TEXT = RGBColor.from_string("1A1A1A")


def test_bullets_are_not_bold_and_use_dark_text():
    content = "### Section\n- A plain bullet point with several words that is not a label and has no markdown emphasis at all\n"
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    found = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for p in shape.text_frame.paragraphs:
                for run in p.runs:
                    if "plain bullet point" in run.text:
                        found = True
                        assert run.font.bold is not True
                        assert run.font.color.rgb == DARK_TEXT
    assert found


def test_lead_in_label_bullet_is_bold():
    content = "### Section\n- Decision Drivers:\n  - A sub bullet explaining the driver in more depth with several words\n"
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    found = False
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for p in shape.text_frame.paragraphs:
                for run in p.runs:
                    if run.text == "Decision Drivers:":
                        found = True
                        assert run.font.bold is True
                        assert run.font.color.rgb == DARK_TEXT  # bold, but still dark — never the accent color
    assert found


def test_nested_list_not_split_across_slides():
    # ~250 words: two lead-in-label bullets ("Decision Drivers:",
    # "Channel Preferences:"), each with 3 sub-bullets — the S13/S14-style
    # case that used to split mid-list.
    content = """### Consumer Insights

#### Consumer Behavior
- Decision Drivers: Consumers in this category weigh price, perceived quality, and peer recommendations heavily before committing to a purchase, often comparing at least three alternatives online.
  - Price sensitivity remains the single largest factor across all surveyed segments, with nearly two-thirds citing cost as their primary concern when evaluating available options.
  - Peer and influencer recommendations carry outsized weight among younger buyers, who are significantly more likely to trust social proof over traditional advertising claims and messaging.
  - Perceived brand quality, built through consistent product performance and transparent communication, continues to anchor long-term loyalty even when meaningful price gaps exist.
- Channel Preferences: Shopping behavior increasingly favors mobile-first discovery followed by a desktop or in-store purchase, reflecting a fragmented multi-device purchase journey.
  - Mobile browsing dominates the discovery phase, accounting for the large majority of initial product research sessions across the entire category.
  - In-store visits remain important for final validation, particularly for higher-ticket purchases where consumers want to physically inspect the product beforehand.
  - Marketplace platforms are gaining share as a trusted intermediary, especially among first-time buyers unfamiliar with a given brand or retailer.
"""
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    # cover + toc + section-divider + ONE content slide + closing == 5
    assert len(prs.slides) == 5

    content_slide_text = _slide_text(prs.slides[3])
    assert "Decision Drivers" in content_slide_text
    assert "Channel Preferences" in content_slide_text
    assert "Price sensitivity" in content_slide_text
    assert "Marketplace platforms" in content_slide_text

    # Nothing from this subsection's sub-bullets leaked onto another slide —
    # i.e. no slide starts with an orphaned level-1 bullet whose parent
    # landed on a different slide.
    for idx, slide in enumerate(prs.slides):
        if idx == 3:
            continue
        text = _slide_text(slide)
        assert "Price sensitivity" not in text
        assert "Marketplace platforms" not in text


# ─────────────────────────────────────────────────────────────────────────────
# Overflow / geometry fix — fixed-size content boxes + line-based splitting
# ─────────────────────────────────────────────────────────────────────────────
_FILLER_WORDS = (
    "the market continues to shift toward digital first discovery while "
    "consumer loyalty remains fragile across the category and competitors "
    "sharpen their pricing and messaging every single quarter this year"
).split()


def _filler_paragraph(n_words: int) -> str:
    import itertools
    words = list(itertools.islice(itertools.cycle(_FILLER_WORDS), n_words))
    text = " ".join(words)
    return text[0].upper() + text[1:] + "."


def _content_body_boxes(slide):
    """The main fixed-size body textbox _add_content_slide creates, identified
    by its exact (width, height, top) — width 11.5in alone also matches the
    cover slide's title textbox, so height/top must match too."""
    return [
        shape for shape in slide.shapes
        if (
            shape.has_text_frame
            and shape.width == Inches(11.5)
            and round(shape.height / Inches(1), 2) == CONTENT_BODY_HEIGHT_IN
            and round(shape.top / Inches(1), 2) == CONTENT_BODY_TOP_IN
        )
    ]


def _title_bar_text(slide):
    """The slide heading text specifically — width 11.5in AND height 0.5in
    (tpl.geometry["chrome"]["heading"] for DEFAULT_TEMPLATE) distinguishes
    the chrome heading box from the eyebrow/footer textboxes (different
    heights) and from the 0.18in-wide accent bar."""
    for shape in slide.shapes:
        if (
            shape.has_text_frame
            and shape.width == Inches(11.5)
            and round(shape.height / Inches(1), 2) == 0.5
        ):
            return shape.text_frame.text
    return None


def test_content_box_never_overflows_below_safe_area():
    long_prose = "\n\n".join(_filler_paragraph(45) for _ in range(6))
    dense_bullets = "\n".join(
        f"- Dense finding number {i} with enough words in it to matter for slide layout testing here"
        for i in range(1, 11)
    )
    content = f"### Executive Summary\n\n{long_prose}\n\n### Dense Findings\n{dense_bullets}\n"
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    checked = 0
    for slide in prs.slides:
        for shape in _content_body_boxes(slide):
            checked += 1
            bottom_in = (shape.top + shape.height) / Inches(1)
            assert bottom_in <= CONTENT_SAFE_BOTTOM_IN + 1e-6, (
                f"content box bottom {bottom_in:.2f}in exceeds the {CONTENT_SAFE_BOTTOM_IN}in safe area"
            )
    assert checked >= 2  # both sections produced at least one content slide


def test_heading_to_body_gap_reduced():
    """Content slides now carry the chrome frame (eyebrow + heading + rule),
    not the bare title bar — this checks the chrome heading box (w=11.5in,
    h=0.5in, distinct from the TOC's own w=12.0in title box) sits just above
    the content body with a small, deliberate gap (spanning the hairline
    rule), not the old title-bar-to-body gap."""
    data = _run(generate_pptx({"title": "Report", "content": "### Section\n- A bullet.\n"}))
    prs = Presentation(io.BytesIO(data))

    found_heading = found_body = False
    heading_y = None
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            if shape.width == Inches(11.5) and round(shape.height / Inches(1), 2) == 0.5:
                found_heading = True
                heading_y = shape.top / Inches(1)
            if shape.width == Inches(11.5) and round(shape.top / Inches(1), 2) == CONTENT_BODY_TOP_IN:
                found_body = True
    assert found_heading, "expected a chrome heading box (w=11.5in, h=0.5in)"
    assert found_body, f"expected a content body box starting at top {CONTENT_BODY_TOP_IN}in"

    gap_in = CONTENT_BODY_TOP_IN - (heading_y + 0.5)
    assert 0.1 <= gap_in <= 0.4


def test_long_prose_section_splits_across_slides():
    paragraphs = "\n\n".join(_filler_paragraph(47) for _ in range(6))  # ~282 words
    content = f"### Executive Summary\n\n{paragraphs}\n"
    data = _run(generate_pptx({"title": "Report", "content": content}))
    prs = Presentation(io.BytesIO(data))

    content_slides = [slide for slide in prs.slides if _content_body_boxes(slide)]
    assert len(content_slides) == 2, f"expected the ~280-word section to split into 2 slides, got {len(content_slides)}"

    for slide in content_slides:
        for shape in _content_body_boxes(slide):
            bottom_in = (shape.top + shape.height) / Inches(1)
            assert bottom_in <= CONTENT_SAFE_BOTTOM_IN + 1e-6

    titles = [_title_bar_text(slide) for slide in content_slides]
    assert titles[0] == "Executive Summary"
    assert "cont'd" in titles[1]
