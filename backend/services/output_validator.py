"""
Output Validator
=================
Mirrors frontend/src/components/builder/MainContent.tsx's RechartsBlock resolution
logic exactly, so "invalid" here means precisely "would hit a fallback card on the
frontend" — not a stricter standard than the UI actually enforces.

Non-blocking / observability-only: every public function here is safe to call from
anywhere without risk — nothing raises, and nothing here mutates its input. Reusable
by a future repair pass, which is why the chart-level resolution logic is split out
into validate_recharts_block() rather than being inlined into validate_output().
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_CHART_TYPES = {"bar", "line", "area", "radar", "pie"}

# Tolerant of leading/trailing whitespace around the language tag and the fence itself.
_RECHARTS_FENCE_RE = re.compile(r"```recharts[ \t]*\r?\n(.*?)```", re.DOTALL)
_BRANDPALETTE_FENCE_RE = re.compile(r"```brandpalette[ \t]*\r?\n(.*?)```", re.DOTALL)
_HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{3}$|^#?[0-9a-fA-F]{6}$")
_H2_HEADING_RE = re.compile(r"^##[ \t]+", re.MULTILINE)


def extract_recharts_blocks(text: str) -> List[str]:
    """Extracts the raw JSON string inside each ```recharts ... ``` fence, in order."""
    if not text:
        return []
    try:
        return [m.group(1).strip() for m in _RECHARTS_FENCE_RE.finditer(text)]
    except Exception as e:
        logger.warning(f"[output_validator] extract_recharts_blocks failed: {type(e).__name__}: {e}")
        return []


def _normalize_hex(value: Any) -> Optional[str]:
    if not value or not isinstance(value, str) or not _HEX_COLOR_RE.match(value.strip()):
        return None
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return v.upper()


def extract_brand_palette(text: str) -> Optional[Dict[str, str]]:
    """Extracts + validates the {"primary"/"secondary"/"accent": "#RRGGBB"} palette
    the agent is instructed to emit in a trailing ```brandpalette ... ``` fence.
    Returns None if the fence is missing, isn't valid JSON, or has no usable hex
    color in it — callers then fall back to the report-type theme."""
    if not text:
        return None
    m = _BRANDPALETTE_FENCE_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    palette = {k: _normalize_hex(data.get(k)) for k in ("primary", "secondary", "accent")}
    palette = {k: v for k, v in palette.items() if v}
    return palette or None


def strip_brand_palette_block(text: str) -> str:
    """Removes the trailing ```brandpalette ... ``` fence so it never reaches the
    chat UI, a Report snapshot, or any export (DOCX/PPTX/public share) — the
    palette itself is captured separately via extract_brand_palette() first."""
    if not text:
        return text or ""
    return _BRANDPALETTE_FENCE_RE.sub("", text).rstrip()


def _resolve_chart_type(data: Dict[str, Any], chart_data: List[Any]) -> str:
    """Same alias-normalization + auto-detect-from-shape logic as the frontend's RechartsBlock."""
    chart_type = str(data.get("type") or "").strip().lower()

    if chart_type in ("bar_chart", "column"):
        chart_type = "bar"
    if chart_type in ("line_chart", "trend"):
        chart_type = "line"
    if chart_type == "area_chart":
        chart_type = "area"
    if chart_type in ("radar_chart", "spider"):
        chart_type = "radar"
    if chart_type in ("pie_chart", "donut"):
        chart_type = "pie"

    if not chart_type:
        sample_item = chart_data[0] if chart_data else {}
        if isinstance(sample_item, dict) and "subject" in sample_item:
            chart_type = "radar"
        elif isinstance(data.get("keys"), list) and len(data["keys"]) > 0:
            chart_type = "line"
        else:
            chart_type = "bar"

    return chart_type


def validate_recharts_block(raw: str) -> Dict[str, Any]:
    """
    Resolves a single ```recharts``` block's raw JSON the same way the frontend would,
    and reports whether it would render a real chart or fall back.
    Returns {"valid": bool, "resolved_type": str | None, "reason": str | None}.
    Never raises.
    """
    try:
        data = json.loads(raw)
    except Exception:
        return {"valid": False, "resolved_type": None, "reason": "malformed_json"}

    try:
        if not isinstance(data, dict):
            return {"valid": False, "resolved_type": None, "reason": "malformed_json"}

        data_field = data.get("data")
        chart_data = data_field if isinstance(data_field, list) else []

        chart_type = _resolve_chart_type(data, chart_data)

        if chart_type not in VALID_CHART_TYPES:
            return {"valid": False, "resolved_type": chart_type, "reason": f"unsupported_type:{chart_type}"}

        if len(chart_data) == 0:
            return {"valid": False, "resolved_type": chart_type, "reason": "empty_or_missing_data"}

        return {"valid": True, "resolved_type": chart_type, "reason": None}
    except Exception as e:
        logger.warning(f"[output_validator] validate_recharts_block failed unexpectedly: {type(e).__name__}: {e}")
        return {"valid": False, "resolved_type": None, "reason": "validation_error"}


def validate_output(text: str, agent_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Summarizes a generated response's recharts blocks plus basic structure.
    Returns {"chart_count", "valid_charts", "invalid_charts": [{"index","reason"}],
    "heading_count", "char_count"}. Never raises — returns safe defaults on any error.
    """
    try:
        text = text or ""
        blocks = extract_recharts_blocks(text)

        invalid_charts: List[Dict[str, Any]] = []
        valid_count = 0
        for idx, raw in enumerate(blocks):
            result = validate_recharts_block(raw)
            if result.get("valid"):
                valid_count += 1
            else:
                invalid_charts.append({"index": idx, "reason": result.get("reason")})

        heading_count = len(_H2_HEADING_RE.findall(text))

        return {
            "chart_count": len(blocks),
            "valid_charts": valid_count,
            "invalid_charts": invalid_charts,
            "heading_count": heading_count,
            "char_count": len(text),
        }
    except Exception as e:
        logger.warning(f"[output_validator] validate_output failed unexpectedly: {type(e).__name__}: {e}")
        return {
            "chart_count": 0,
            "valid_charts": 0,
            "invalid_charts": [],
            "heading_count": 0,
            "char_count": len(text) if isinstance(text, str) else 0,
        }
