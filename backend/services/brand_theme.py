"""
Brand theming — shared by pptx_service.py and export_service.py so the DOCX
and PPTX exports always agree on the same brand colors, logo, and bullet
label-bold rule.

Lives in its own module rather than inside either exporter because
pptx_service.py already imports from export_service.py (for _split_segments);
export_service.py importing back from pptx_service.py would be circular.

Dimensions here are returned as plain floats (inches) rather than either
library's own Length type, since python-pptx's Inches and python-docx's
Inches are different classes — each caller wraps the float with its own.
"""
import os
import re
import io
import logging
from typing import Optional, Dict, Any

from PIL import Image

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Per-agent-type color themes
# ─────────────────────────────────────────────────────────────────────────────
REPORT_THEMES = {
    "brand-positioning": {
        "primary": "2C5F8A",      # Deep blue
        "secondary": "4A90D9",    # Medium blue
        "accent": "C8A951",       # Gold
        "bg_dark": "1B3A5C",      # Dark navy for cover/dividers
        "bg_light": "EDF3F9",     # Light blue tint for content
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "6B7B8D",
    },
    "competition-analysis": {
        "primary": "8B2252",      # Deep magenta
        "secondary": "C44D7B",
        "accent": "E8A838",       # Amber
        "bg_dark": "5C1636",
        "bg_light": "FDF0F4",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "8D6B7B",
    },
    "seo-strategy": {
        "primary": "2E7D32",      # Forest green
        "secondary": "4CAF50",
        "accent": "FF9800",       # Orange
        "bg_dark": "1B5E20",
        "bg_light": "E8F5E9",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "6B8D6B",
    },
    "social-media-strategy": {
        "primary": "7B1FA2",      # Purple
        "secondary": "AB47BC",
        "accent": "FF5722",       # Deep orange
        "bg_dark": "4A148C",
        "bg_light": "F3E5F5",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "8D6B9F",
    },
    "market-entry-strategy": {
        "primary": "E65100",      # Deep orange
        "secondary": "FF8F00",
        "accent": "1565C0",       # Blue accent
        "bg_dark": "BF360C",
        "bg_light": "FFF3E0",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "8D7B6B",
    },
    "content-calendar": {
        "primary": "00695C",      # Teal
        "secondary": "26A69A",
        "accent": "FFB300",       # Gold amber
        "bg_dark": "004D40",
        "bg_light": "E0F2F1",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "6B8D87",
    },
    "default": {
        "primary": "37474F",      # Blue grey
        "secondary": "607D8B",
        "accent": "C8A951",       # StratAI gold
        "bg_dark": "263238",
        "bg_light": "ECEFF1",
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": "FFFFFF",
        "text_muted": "78716C",
    },
}


def _get_theme(agent_type: str) -> dict:
    """Get color theme for agent type. Normalizes key format."""
    key = (agent_type or "").lower().replace(" ", "-").replace("_", "-")
    return REPORT_THEMES.get(key, REPORT_THEMES["default"])


# ─────────────────────────────────────────────────────────────────────────────
# Brand-kit theming — derives a full theme (same shape as REPORT_THEMES
# entries) from a client's logo_url/colors so an exported deck/doc can theme
# to the CLIENT's brand instead of the fixed report-type palette.
# ─────────────────────────────────────────────────────────────────────────────
_BRAND_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{3}$|^#?[0-9a-fA-F]{6}$")


def _hex_to_rgb(h: str) -> tuple:
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    clamp = lambda v: max(0, min(255, int(round(v))))
    return f"{clamp(r):02X}{clamp(g):02X}{clamp(b):02X}"


def _luminance(h: str) -> float:
    """Relative (WCAG) luminance of a hex color, 0 (black) .. 1 (white)."""
    def chan(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _hex_to_rgb(h)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _darken(h: str, amount: float) -> str:
    """Moves a hex color toward black by `amount` (0..1)."""
    r, g, b = _hex_to_rgb(h)
    return _rgb_to_hex(r * (1 - amount), g * (1 - amount), b * (1 - amount))


def _lighten(h: str, amount: float) -> str:
    """Moves a hex color toward white by `amount` (0..1)."""
    r, g, b = _hex_to_rgb(h)
    return _rgb_to_hex(r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount)


def _readable_text(bg_hex: str) -> str:
    """Picks white or near-black text so it stays readable on `bg_hex`."""
    return "FFFFFF" if _luminance(bg_hex) < 0.5 else "1A1A1A"


def _normalize_brand_hex(value: Optional[str]) -> Optional[str]:
    """Validates a user-supplied hex color; malformed input is dropped (so the
    caller derives it instead of embedding garbage into the export)."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not _BRAND_HEX_RE.match(v):
        return None
    v = v.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return v.upper()


def _build_theme_from_colors(colors: Optional[dict], base: dict) -> Optional[dict]:
    """Shared derivation: given a {"primary"/"secondary"/"accent"} dict (brand_kit
    colors OR an extracted palette — same shape either way) and a fallback base
    theme, builds a full theme dict (same keys as REPORT_THEMES entries). Any
    color slot not set is derived from the ones that are, or falls back to
    `base`. Returns None when none of the three colors are present/valid, so
    the caller knows to fall through to the next option in its precedence chain."""
    colors = colors or {}
    primary = _normalize_brand_hex(colors.get("primary"))
    secondary = _normalize_brand_hex(colors.get("secondary"))
    accent = _normalize_brand_hex(colors.get("accent"))
    if not primary and not secondary and not accent:
        return None

    p = primary or base["primary"]
    s = secondary or _lighten(p, 0.25)
    a = accent or secondary or base["accent"]

    # Dark background for cover/dividers: darken primary until it's dark enough for white text.
    bg_dark = p if _luminance(p) < 0.35 else _darken(p, 0.55)
    # Light tint for content accents / alt rows.
    bg_light = _lighten(p, 0.88)

    return {
        "primary": p,
        "secondary": s,
        "accent": a,
        "bg_dark": bg_dark,
        "bg_light": bg_light,
        "bg_white": "FFFFFF",
        "text_dark": "1A1A1A",
        "text_light": _readable_text(bg_dark),
        "text_muted": base["text_muted"],
    }


def _theme_from_brand_kit(brand_kit: Optional[dict], agent_type: str) -> dict:
    """Builds a full theme dict from a project's brand_kit colors. With no
    brand colors at all, returns the report-type theme unchanged."""
    base = _get_theme(agent_type)
    colors = (brand_kit or {}).get("colors") or {}
    return _build_theme_from_colors(colors, base) or base


def _resolve_theme(brand_kit: Optional[dict], extracted_palette: Optional[dict], agent_type: str,
                    base: Optional[dict] = None) -> dict:
    """Export theme precedence: manual brand_kit colors (if any are set) win
    outright; otherwise an LLM-extracted palette from report generation;
    otherwise a template-supplied `base` palette (if given); otherwise the
    fixed report-type theme. Logo placement is unaffected — it only ever
    comes from brand_kit, never from the extracted palette.

    `base`, when given, is a (possibly partial) dict using the same 9 slot
    keys as a REPORT_THEMES entry — any slot it doesn't set is filled from
    the report-type theme, so this can never raise a KeyError. Passing
    base=None (the default) is byte-identical to the old 3-arg behavior,
    which is what export_service.py (DOCX) still calls unchanged."""
    report_theme = _get_theme(agent_type)
    resolved_base = report_theme if not base else {**report_theme, **base}

    manual_colors = (brand_kit or {}).get("colors") or {}
    if any(manual_colors.get(k) for k in ("primary", "secondary", "accent")):
        theme = _build_theme_from_colors(manual_colors, resolved_base)
        if theme:
            return theme

    if extracted_palette:
        theme = _build_theme_from_colors(extracted_palette, resolved_base)
        if theme:
            return theme

    return resolved_base


# ─────────────────────────────────────────────────────────────────────────────
# Brand-kit logo — reads the uploaded logo off disk and normalizes it to PNG
# bytes so python-pptx's native format whitelist (no webp) never blocks it,
# and so python-docx (which only reads image bytes, not webp-aware) gets a
# format it always understands too.
# ─────────────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATIC_ROOT = os.path.normpath(os.path.join(_BACKEND_ROOT, "static"))


def _resolve_logo_path(logo_url: Optional[str]) -> Optional[str]:
    """Maps a served `/static/...` logo URL back to a filesystem path, under
    backend/static/ only (guards against path traversal via a crafted URL).
    Returns None if the URL doesn't point into /static/ or the file is missing."""
    if not logo_url or not isinstance(logo_url, str) or not logo_url.startswith("/static/"):
        return None
    rel = logo_url[len("/static/"):]
    path = os.path.normpath(os.path.join(_STATIC_ROOT, rel))
    if not (path == _STATIC_ROOT or path.startswith(_STATIC_ROOT + os.sep)):
        return None
    return path if os.path.isfile(path) else None


def _load_logo_asset(brand_kit: Optional[dict]) -> Optional[Dict[str, Any]]:
    """Reads the brand kit's logo file and returns {"bytes": <PNG bytes>,
    "width": px, "height": px}, or None if there's no logo, the file is
    missing/unreadable, or it's an SVG (Pillow can't rasterize SVG, so it's
    skipped gracefully rather than crashing the export)."""
    logo_url = (brand_kit or {}).get("logo_url")
    path = _resolve_logo_path(logo_url)
    if not path:
        return None
    try:
        with Image.open(path) as img:
            width, height = img.size
            import io
            buf = io.BytesIO()
            img.convert("RGBA").save(buf, format="PNG")
            return {"bytes": buf.getvalue(), "width": width, "height": height}
    except Exception:
        logger.warning("Could not read brand logo at %s for export — skipping logo", path, exc_info=True)
        return None


def _color_distance(a: tuple, b: tuple) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def extract_palette_from_logo(logo_url: Optional[str]) -> Optional[Dict[str, str]]:
    """Best-effort auto-palette from an uploaded logo: the 3 most frequent,
    reasonably-distinct non-background colors, as {"primary"/"secondary"/
    "accent": "#RRGGBB"}. Returns fewer keys if fewer than 3 survive, or None
    if the logo can't be loaded (incl. SVG, which Pillow can't rasterize) or
    nothing survives the background filter. Pure function — no I/O beyond the
    existing guarded logo load."""
    asset = _load_logo_asset({"logo_url": logo_url})
    if not asset:
        return None
    try:
        with Image.open(io.BytesIO(asset["bytes"])) as img:
            rgba = img.convert("RGBA")
            rgba.thumbnail((150, 150))
            opaque_pixels = [(r, g, b) for r, g, b, a in rgba.getdata() if a > 0]
        if not opaque_pixels:
            return None

        strip = Image.new("RGB", (len(opaque_pixels), 1))
        strip.putdata(opaque_pixels)
        quantized = strip.convert("P", palette=Image.ADAPTIVE, colors=8)
        counts = quantized.getcolors()
        if not counts:
            return None
        palette = quantized.getpalette()
        counts.sort(key=lambda c: -c[0])

        picked = []
        for _, idx in counts:
            rgb = tuple(palette[idx * 3:idx * 3 + 3])
            if all(c > 240 for c in rgb) or all(c < 15 for c in rgb):
                continue  # near-white / near-black background or text
            if any(_color_distance(rgb, p) < 30 for p in picked):
                continue  # too close to an already-picked color
            picked.append(rgb)
            if len(picked) == 3:
                break

        if not picked:
            return None
        keys = ("primary", "secondary", "accent")
        return {keys[i]: _rgb_to_hex(*picked[i]) for i in range(len(picked))}
    except Exception:
        logger.warning("Could not extract palette from logo %s", logo_url, exc_info=True)
        return None


def logo_fit_dimensions(asset: Dict[str, Any], max_height_in: float, max_width_in: float):
    """Scales a logo to fit within a max height/width box (inches, as plain
    floats), preserving aspect ratio. Each caller wraps the result with its
    own library's Inches() — python-pptx's and python-docx's are different
    classes, so the shared helper stays unit-system-agnostic."""
    aspect = (asset["width"] / asset["height"]) if asset["height"] else 1.0
    height_in = max_height_in
    width_in = height_in * aspect
    if width_in > max_width_in:
        width_in = max_width_in
        height_in = width_in / aspect
    return width_in, height_in


# ─────────────────────────────────────────────────────────────────────────────
# Bullet label-bold rule — shared so a "Decision Drivers:" style lead-in
# bullet renders bold (but still dark, never the accent color) identically in
# both the PPTX and the DOCX, while an LLM-wrapped whole-sentence bullet does
# NOT get stuck bold just because it happens to be wrapped in **markdown**.
# ─────────────────────────────────────────────────────────────────────────────
def _is_lead_in_label(text: str) -> bool:
    """A bullet whose text is a standalone lead-in label (e.g. "Decision
    Drivers:") ending in a colon — rendered bold, but still dark, never the
    accent color, and only the label line itself (not merely containing a
    colon elsewhere in a longer sentence)."""
    return (text or "").rstrip().endswith(":")
