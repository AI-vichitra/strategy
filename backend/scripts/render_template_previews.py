"""
Renders the same sample report three times — once per PPTX template
(default, executive, bold) — to backend/tmp_template_preview/*.pptx, for
visual review of Step 6's two new templates.

Run with:
cd backend && python scripts/render_template_previews.py
(or: python -m backend.scripts.render_template_previews from the repo root)

The sample content mirrors what the existing pptx_service tests use: a
section with bullets, a table, and a recharts chart block, plus a second
section with a nested bullet list — enough to exercise cover/TOC/divider/
content/table/chart/closing slides in one deck.
"""
import asyncio
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
_REPO_ROOT = os.path.dirname(_BACKEND_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.pptx_service import generate_pptx  # noqa: E402

_OUT_DIR = os.path.join(_BACKEND_ROOT, "tmp_template_preview")

SAMPLE_CONTENT = """### Market Overview

#### Key Findings
- Finding one with enough words to clear the sparse-merge threshold entirely and read naturally
- Finding two with enough words to clear the sparse-merge threshold entirely and read naturally
- Finding three with enough words to clear the sparse-merge threshold entirely and read naturally

#### Market Size & Growth
| Metric | 2023 | 2024 |
| --- | --- | --- |
| Revenue | $1.2B | $1.6B |
| Users | 5M | 7M |

### Key Metrics
- $480M market size
- 15% CAGR growth
- 12 key players (tracked)

### Delivery Plan
- Phase 1 (Q1 2025): Research — Conduct market analysis and competitive benchmarking
  - Deliverable: Market assessment report
- Phase 2 (Q2 2025): Strategy — Develop positioning and go-to-market plan
  - Deliverable: Strategic roadmap
- Phase 3 (Q3 2025): Build — Implement core platform features and integrations
  - Deliverable: MVP platform launch
- Phase 4 (Q4 2025): Scale — Expand user acquisition and optimize retention
  - Deliverable: Growth playbook
- What StratAI provides: continuous monitoring, competitive alerts, quarterly strategy reviews

### Competitive Landscape

#### Pricing Comparison
```recharts
{"type": "bar", "title": "Pricing Index", "data": [{"name": "Brand A", "value": 9}, {"name": "Brand B", "value": 6}, {"name": "Brand C", "value": 7}]}
```

#### Strategic Recommendations
- Decision Drivers: Consumers weigh price and quality heavily before committing to a purchase decision
  - Price sensitivity remains the single largest factor across all surveyed segments in this category
  - Peer recommendations carry outsized weight among younger buyers in digital-first channels today
- Channel Preferences: Shopping behavior increasingly favors mobile-first discovery before an in-store visit
  - Mobile browsing dominates the discovery phase across the entire category this year
"""


async def _render_one(template_id, filename):
    report_data = {
        "title": "Strategic Market Intelligence Report",
        "content": SAMPLE_CONTENT,
        "brand_name": "Acme Corp",
        "agent_name": "Brand Positioning",
        "template_id": template_id,
    }
    pptx_bytes = await generate_pptx(report_data)
    os.makedirs(_OUT_DIR, exist_ok=True)
    path = os.path.join(_OUT_DIR, filename)
    try:
        with open(path, "wb") as f:
            f.write(pptx_bytes)
    except PermissionError:
        alt = os.path.join(_OUT_DIR, filename.replace(".pptx", ".NEW.pptx"))
        with open(alt, "wb") as f:
            f.write(pptx_bytes)
        path = alt
    return path


async def render_all():
    paths = []
    for template_id, filename in (
        (None, "default.pptx"),
        ("executive", "executive.pptx"),
        ("bold", "bold.pptx"),
        ("corporate-blue", "corporate-blue.pptx"),
        ("midnight-tech", "midnight-tech.pptx"),
        ("minimalist-mono", "minimalist-mono.pptx"),
        ("warm-editorial", "warm-editorial.pptx"),
    ):
        path = await _render_one(template_id, filename)
        paths.append(path)
    return paths


def main():
    paths = asyncio.run(render_all())
    print("Rendered template previews:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
