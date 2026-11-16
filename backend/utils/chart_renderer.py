"""
Chart Renderer — recharts JSON → PNG bytes (matplotlib, headless)
===================================================================
Extracted from export_service.py so both the DOCX and PPTX export services
render charts identically (same colors, same chart-type dispatch) instead of
maintaining two copies of the same matplotlib logic.
"""

import io
import logging
from typing import Optional, List, Dict, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backend.services.output_validator import _resolve_chart_type

logger = logging.getLogger(__name__)

# Same order as EXECUTIVE_COLORS in frontend/src/components/ReportRenderer.tsx
EXECUTIVE_COLORS = [
    "#2D2A26",  # Deep Charcoal
    "#D4A843",  # Warm StratAI Gold
    "#3B82F6",  # Corporate Blue
    "#10B981",  # Emerald
    "#8B5CF6",  # Purple
    "#EC4899",  # Rose
    "#F59E0B",  # Amber
    "#06B6D4",  # Cyan
    "#6366F1",  # Indigo
]


def _chart_color(idx: int) -> str:
    return EXECUTIVE_COLORS[idx % len(EXECUTIVE_COLORS)]


def _to_num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _infer_numeric_keys(data: List[Dict[str, Any]], exclude: set) -> List[str]:
    keys: List[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            if k in exclude or k in keys:
                continue
            if isinstance(v, (int, float)):
                keys.append(k)
    return keys


def _render_bar(ax, data, keys, x_label, y_label):
    names = [str(d.get("name", "")) for d in data]
    if isinstance(keys, list) and keys:
        n = len(keys)
        width = 0.8 / max(n, 1)
        x = list(range(len(names)))
        for i, k in enumerate(keys):
            vals = [_to_num(d.get(k)) for d in data]
            offset = (i - (n - 1) / 2) * width
            ax.bar([xi + offset for xi in x], vals, width=width, label=str(k), color=_chart_color(i))
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right")
        ax.legend()
    else:
        vals = [_to_num(d.get("value")) for d in data]
        x = list(range(len(names)))
        colors = [_chart_color(i) for i in range(len(names))]
        ax.bar(x, vals, color=colors)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right")
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)


def _render_line(ax, data, keys, x_label, y_label, filled):
    names = [str(d.get("name", "")) for d in data]
    x = list(range(len(names)))
    series_keys = keys if isinstance(keys, list) and keys else _infer_numeric_keys(data, exclude={"name"})
    for i, k in enumerate(series_keys):
        vals = [_to_num(d.get(k)) for d in data]
        color = _chart_color(i)
        ax.plot(x, vals, marker="o", label=str(k), color=color)
        if filled:
            ax.fill_between(x, vals, alpha=0.3, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right")
    if len(series_keys) > 1:
        ax.legend()
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)


def _render_radar(ax, data, keys):
    import math

    subjects = [str(d.get("subject", "")) for d in data]
    n = len(subjects)
    if n == 0:
        return
    angles = [i / n * 2 * math.pi for i in range(n)]
    angles += angles[:1]
    series_keys = keys if isinstance(keys, list) and keys else _infer_numeric_keys(data, exclude={"subject"})
    for i, k in enumerate(series_keys):
        vals = [_to_num(d.get(k)) for d in data]
        vals += vals[:1]
        color = _chart_color(i)
        ax.plot(angles, vals, label=str(k), color=color)
        ax.fill(angles, vals, alpha=0.1, color=color)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(subjects)
    if series_keys:
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))


def _render_scatter(ax, data, x_label, y_label):
    """Positioning-map style scatter: one labeled point per (x, y) data item,
    plus quadrant reference lines at the domain midpoint — mirrors the
    frontend's ScatterChart in ReportRenderer.tsx (same 0-10 default domain,
    expanded to fit the data; same quadrant-line placement)."""
    names = [str(d.get("name", "")) for d in data]
    xs = [_to_num(d.get("x")) for d in data]
    ys = [_to_num(d.get("y")) for d in data]
    colors = [_chart_color(i) for i in range(len(names))]
    ax.scatter(xs, ys, c=colors, s=90, zorder=3)

    # Alternate the label offset direction so adjacent points don't stack
    # their text directly on top of one another — a simple, not exhaustive,
    # overlap mitigation.
    for i, (name, x, y) in enumerate(zip(names, xs, ys)):
        offset = (6, 8) if i % 2 == 0 else (6, -12)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=offset, fontsize=8)

    x_min, x_max = min([0.0] + xs), max([10.0] + xs)
    y_min, y_max = min([0.0] + ys), max([10.0] + ys)
    ax.axhline((y_min + y_max) / 2, color="#D4A843", linestyle="--", linewidth=1, zorder=1)
    ax.axvline((x_min + x_max) / 2, color="#D4A843", linestyle="--", linewidth=1, zorder=1)
    ax.set_xlim(x_min - 0.5, x_max + 0.5)
    ax.set_ylim(y_min - 0.5, y_max + 0.5)
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)


def _render_pie(ax, data):
    names = [str(d.get("name", "")) for d in data]
    vals = [_to_num(d.get("value")) for d in data]
    colors = [_chart_color(i) for i in range(len(names))]
    ax.pie(vals, labels=names, autopct="%1.0f%%", colors=colors)
    ax.axis("equal")


def render_chart_image(chart_json: Optional[dict], figsize: Optional[tuple] = None) -> Optional[bytes]:
    """Renders a single recharts JSON block to a PNG via matplotlib. Never raises.
    `figsize` overrides the default (6, 4.5)/(6, 4) sizing — PPTX slides want a
    wider aspect ratio than the DOCX's portrait-page default."""
    try:
        if not isinstance(chart_json, dict):
            return None

        data = chart_json.get("data")
        data = data if isinstance(data, list) else []
        if not data:
            return None

        keys = chart_json.get("keys")
        title = chart_json.get("title", "")
        x_label = chart_json.get("x_label", "")
        y_label = chart_json.get("y_label", "")
        chart_type = _resolve_chart_type(chart_json, data)

        if chart_type == "radar":
            fig = plt.figure(figsize=figsize or (6, 4.5))
            ax = fig.add_subplot(111, polar=True)
            _render_radar(ax, data, keys)
        else:
            fig, ax = plt.subplots(figsize=figsize or (6, 4))
            if chart_type == "bar":
                _render_bar(ax, data, keys, x_label, y_label)
            elif chart_type == "line":
                _render_line(ax, data, keys, x_label, y_label, filled=False)
            elif chart_type == "area":
                _render_line(ax, data, keys, x_label, y_label, filled=True)
            elif chart_type == "pie":
                _render_pie(ax, data)
            elif chart_type == "scatter":
                _render_scatter(ax, data, x_label, y_label)
            else:
                plt.close(fig)
                return None

        if title:
            ax.set_title(title, pad=16 if chart_type == "radar" else None)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"[chart_renderer] render_chart_image failed (non-fatal): {type(e).__name__}: {e}")
        try:
            plt.close("all")
        except Exception:
            pass
        return None
