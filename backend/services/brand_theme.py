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
import colorsys
from typing import Optional, Dict, Any

from PIL import Image

try:
    import resvg_py
except ImportError:  # requirements.txt pins it; degrade gracefully if somehow absent
    resvg_py = None

logger = logging.getLogger(__name__)

# Supported raster formats (all handled natively by Pillow) plus SVG (rasterized
# below via resvg before Pillow ever sees it — Pillow has no vector support).
SUPPORTED_LOGO_FORMATS = ("PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF", "SVG")
_LOGO_FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "GIF": ".gif",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "SVG": ".svg",
}

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


# Accent fallback: when no accent is explicitly set/extracted, it's derived
# from primary as a vivid variant (modest hue shift + saturation/brightness
# floor) rather than reused from secondary or a hardcoded generic color, so a
# fallback accent still reads as "this brand's accent".
_ACCENT_HUE_SHIFT = 0.08       # ~29 degrees — related to primary, not a clash
_ACCENT_MIN_SATURATION = 0.65
_ACCENT_MIN_VALUE = 0.70
_ACCENT_MAX_VALUE = 0.95       # stays short of washed-out/white


def _vivid_accent_from_primary(primary_hex: str) -> str:
    """Derives a vivid accent related to `primary`: a modest hue shift plus a
    saturation/brightness floor, so an accent that couldn't be reliably
    extracted (or wasn't manually set) is still visibly tied to the brand's
    own primary color instead of an arbitrary fallback."""
    r, g, b = _hex_to_rgb(primary_hex)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h = (h + _ACCENT_HUE_SHIFT) % 1.0
    s = max(s, _ACCENT_MIN_SATURATION)
    v = min(max(v, _ACCENT_MIN_VALUE), _ACCENT_MAX_VALUE)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return _rgb_to_hex(r2 * 255, g2 * 255, b2 * 255)


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
    theme, builds a full theme dict (same keys as REPORT_THEMES entries).
    Primary/secondary fall back to `base` when unset; accent, when unset,
    is instead derived from the resolved primary (_vivid_accent_from_primary)
    rather than reused from secondary or `base` — so a missing accent is
    always visibly tied to this brand's own primary, never a generic or
    unrelated color. Returns None when none of the three colors are
    present/valid, so the caller knows to fall through to the next option in
    its precedence chain."""
    colors = colors or {}
    primary = _normalize_brand_hex(colors.get("primary"))
    secondary = _normalize_brand_hex(colors.get("secondary"))
    accent = _normalize_brand_hex(colors.get("accent"))
    if not primary and not secondary and not accent:
        return None

    p = primary or base["primary"]
    s = secondary or _lighten(p, 0.25)
    a = accent or _vivid_accent_from_primary(p)

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

    Accent is not a user-settable brand_kit field (Brand Kit UI only offers
    primary/secondary), so when manual colors win but lack an accent, one is
    resolved backend-side: a real pixel extraction off the stored logo file
    if it has a sufficiently vivid color (_accent_from_logo), else a vivid
    variant derived from primary (_build_theme_from_colors) — never a
    user-set value.

    `base`, when given, is a (possibly partial) dict using the same 9 slot
    keys as a REPORT_THEMES entry — any slot it doesn't set is filled from
    the report-type theme, so this can never raise a KeyError. Passing
    base=None (the default) is byte-identical to the old 3-arg behavior,
    which is what export_service.py (DOCX) still calls unchanged."""
    report_theme = _get_theme(agent_type)
    resolved_base = report_theme if not base else {**report_theme, **base}

    manual_colors = (brand_kit or {}).get("colors") or {}
    if any(manual_colors.get(k) for k in ("primary", "secondary", "accent")):
        colors = manual_colors
        if not colors.get("accent"):
            # Accent is no longer a user-set field (Brand Kit UI only offers
            # primary/secondary) — try a real extraction off the stored logo
            # file first, so a genuinely vivid brand accent still reaches the
            # export theme; _build_theme_from_colors' derive-from-primary
            # fallback only kicks in when that also finds nothing vivid.
            logo_accent = _accent_from_logo(brand_kit)
            if logo_accent:
                colors = {**colors, "accent": logo_accent}
        theme = _build_theme_from_colors(colors, resolved_base)
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


_SVG_SNIFF_RE = re.compile(rb"<svg[\s>]", re.IGNORECASE)


def _looks_like_svg(data: bytes) -> bool:
    """Sniffs file content for an SVG root tag — format is detected from the
    bytes themselves, not trusted from a filename extension or content-type
    header, since both can lie."""
    head = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    return bool(_SVG_SNIFF_RE.search(head))


def _rasterize_svg(data: bytes) -> bytes:
    """Rasterizes SVG bytes to PNG bytes via resvg — a Rust-based renderer that
    ships as a prebuilt pip wheel on both Windows and manylinux (no system
    cairo/pango required, unlike cairosvg), so it installs cleanly on Windows
    local dev and on Render's Linux deploy alike."""
    if resvg_py is None:
        raise RuntimeError("resvg-py is not installed; cannot rasterize SVG logos")
    svg_text = data.decode("utf-8", errors="replace")
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text))


def _decode_logo_image(data: bytes) -> Image.Image:
    """Single chokepoint turning raw logo bytes — any supported format — into a
    Pillow Image. SVGs are rasterized to PNG first (Pillow has no vector
    support); every raster format Pillow understands (png/jpg/jpeg/webp/gif/
    bmp/tiff/...) is opened directly. Raises on anything unreadable; callers
    decide how to handle that (skip-with-warning at export time, reject-with-
    message at upload time) — this helper never swallows errors itself."""
    if _looks_like_svg(data):
        data = _rasterize_svg(data)
    img = Image.open(io.BytesIO(data))
    img.load()  # force full decode now so truncated/corrupt data raises here
    return img


def _load_logo_asset(
    brand_kit: Optional[dict],
    logo_data: Optional[bytes] = None,
    logo_mime: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Reads the brand logo and returns {"bytes": <PNG bytes>, "width": px,
    "height": px}, or None if there's no logo or it's unreadable (skipped
    gracefully rather than crashing the export).

    `logo_data`/`logo_mime` (Project.logo_data/logo_mime — the DB source of
    truth) are used when given. Falls back to reading brand_kit["logo_url"]
    off disk only when logo_data is None (project predates these columns, or
    the caller didn't pass them)."""
    if logo_data:
        try:
            img = _decode_logo_image(logo_data)
            width, height = img.size
            buf = io.BytesIO()
            img.convert("RGBA").save(buf, format="PNG")
            return {"bytes": buf.getvalue(), "width": width, "height": height}
        except Exception:
            logger.warning("Could not decode brand logo from DB (mime=%s) for export — skipping logo", logo_mime, exc_info=True)
            return None

    logo_url = (brand_kit or {}).get("logo_url")
    path = _resolve_logo_path(logo_url)
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
        img = _decode_logo_image(data)
        width, height = img.size
        buf = io.BytesIO()
        img.convert("RGBA").save(buf, format="PNG")
        return {"bytes": buf.getvalue(), "width": width, "height": height}
    except Exception:
        logger.warning("Could not read brand logo at %s for export — skipping logo", path, exc_info=True)
        return None


def _color_distance(a: tuple, b: tuple) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _hsv(rgb: tuple) -> tuple:
    r, g, b = rgb
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


# Accent candidate thresholds: a brand's accent is usually a small but VIVID
# element (e.g. a gold highlight), which a frequency-only pick loses to larger
# grey edge-blends/midtones — so accent is chosen by saturation instead, among
# the same background-filtered, de-duped candidate pool primary/secondary use.
_ACCENT_CANDIDATE_MIN_SATURATION = 0.25
_ACCENT_CANDIDATE_MIN_VALUE = 0.20  # avoid a near-black pixel reading as "vivid"


def extract_palette_from_logo(logo_url: Optional[str]) -> Optional[Dict[str, str]]:
    """Best-effort auto-palette from an uploaded logo, as {"primary"/
    "secondary"/"accent": "#RRGGBB"} (fewer keys if fewer survive, or None if
    the logo can't be loaded or nothing survives the background filter).

    Primary/secondary are the 2 most frequent, reasonably-distinct
    non-background colors — unchanged from before. Accent is NOT the
    3rd-most-frequent color: it's the MOST SATURATED remaining candidate (same
    background/de-dup filters), so a small vivid highlight can win the slot
    over a larger but duller color. If nothing clears the saturation/
    brightness floor, accent is simply omitted here — callers (via
    _build_theme_from_colors) derive it from primary instead of defaulting to
    an unrelated color. Pure function — no I/O beyond the existing guarded
    logo load."""
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

        candidates = []
        picked = []  # primary, secondary — by frequency, same as before
        for _, idx in counts:
            rgb = tuple(palette[idx * 3:idx * 3 + 3])
            if all(c > 240 for c in rgb) or all(c < 15 for c in rgb):
                continue  # near-white / near-black background or text
            candidates.append(rgb)
            if len(picked) < 2 and not any(_color_distance(rgb, p) < 30 for p in picked):
                picked.append(rgb)

        if not picked:
            return None
        result = {"primary": _rgb_to_hex(*picked[0])}
        if len(picked) > 1:
            result["secondary"] = _rgb_to_hex(*picked[1])

        accent_pool = [rgb for rgb in candidates if not any(_color_distance(rgb, p) < 30 for p in picked)]
        if accent_pool:
            best = max(accent_pool, key=lambda rgb: _hsv(rgb)[1])
            h, s, v = _hsv(best)
            if s >= _ACCENT_CANDIDATE_MIN_SATURATION and v >= _ACCENT_CANDIDATE_MIN_VALUE:
                result["accent"] = _rgb_to_hex(*best)

        return result
    except Exception:
        logger.warning("Could not extract palette from logo %s", logo_url, exc_info=True)
        return None


def _accent_from_logo(brand_kit: Optional[dict]) -> Optional[str]:
    """Best-effort: pulls just the accent hex out of a fresh pixel extraction
    of the brand kit's stored logo file. Used by _resolve_theme so a genuinely
    vivid accent color in the logo still reaches the export theme even though
    accent is no longer a user-settable Brand Kit field. Never raises — a
    missing logo or extraction failure just means no logo-derived accent."""
    logo_url = (brand_kit or {}).get("logo_url")
    if not logo_url:
        return None
    palette = extract_palette_from_logo(logo_url)
    return (palette or {}).get("accent")


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
