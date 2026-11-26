"""
Slide Planner — the IR seam between markdown parsing and PPTX rendering
=========================================================================
Slice 1: a deterministic, behavior-preserving wrapper. It runs the existing
parse/cluster/pack logic in pptx_service and re-shapes each resulting slide
spec as a SlideBlock, so renderers can dispatch on `component` instead of the
parser's ad-hoc `type` string. Same blocks, same order as before.

Slice-1 components: "bullets" (the old "content"), "table", "chart".
Section dividers stay structural in pptx_service._create_section_slides.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

COMPONENT_BULLETS = "bullets"
COMPONENT_TABLE = "table"
COMPONENT_CHART = "chart"
COMPONENT_STAT_ROW = "stat_row"
COMPONENT_TIMELINE = "timeline"

_SPEC_TYPE_TO_COMPONENT = {
    "content": COMPONENT_BULLETS,
    "table": COMPONENT_TABLE,
    "chart": COMPONENT_CHART,
}


@dataclass(frozen=True)
class SlideBlock:
    """One planned slide. `data` is the old slide spec's payload minus its
    "type": bullets -> {title, items}; table -> {title, rows, trailing_items?};
    chart -> {title, chart_json, trailing_items?}."""
    component: str
    data: Dict[str, Any] = field(default_factory=dict)
    source_section: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# stat_row detector (Slice 2) — deliberately conservative: a false stat_row is
# worse than a missed one. data shape: {heading, context?, stats: [{value,
# label, sublabel?}, ...]} with 2-4 stats.
#
# Fires only when a content slide consists SOLELY of 2-4 level-0 bullets, each
# <= 8 words, each carrying exactly one prominent number that sits at the start
# or end of the item (or of one side of a "value — label" / "label: value"
# split), and at least one of them is a "strong" number (currency, percent,
# magnitude suffix, rank). A bare number ("12 key players") only counts as a
# supporting item next to a strong one, so "3 phases" style prose never fires.
# ─────────────────────────────────────────────────────────────────────────────
_NUM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_STRONG_RE = re.compile(
    rf"[$₹€£]\s?{_NUM}(?:\s?(?:bn|mn|million|billion|thousand|crore|lakh|[MBK])\b)?"
    rf"|(?<![\w]){_NUM}\s?%"
    rf"|(?<![\w]){_NUM}\s(?:million|billion|thousand|crore|lakh)\b"
    rf"|(?<![\w]){_NUM}(?:bn|mn|[MBK])\b"
    r"|(?<![\w])#\d+\b|(?<![\w])No\.\s?\d+\b|(?<![\w])Thứ\s?\d+\b",
    re.IGNORECASE,
)
_BARE_LEAD_RE = re.compile(rf"^({_NUM})\s+(\S.*)$")
_BARE_ONLY_RE = re.compile(rf"^{_NUM}$")
_SEP_RE = re.compile(r"\s+[—–-]\s+|\s*:\s+")
_PAREN_TAIL_RE = re.compile(r"\s*\(([^()]+)\)\s*$")
_LEADING_LINK_RE = re.compile(r"^(?:of|in|for|from)\s+", re.IGNORECASE)

MAX_ITEM_WORDS = 8
MAX_LABEL_WORDS = 6
MAX_VALUE_CHARS = 9


def _strip_md(text: str) -> str:
    return re.sub(r"\*\*|__|\*|`", "", text or "").strip()


def _clean(text: str, links: bool = True) -> str:
    text = text.strip(" \t.,;:-—–")
    return (_LEADING_LINK_RE.sub("", text) if links else text).strip()


def _is_year(token: str) -> bool:
    return token.isdigit() and 1900 <= int(token) <= 2100


def _bare_number(text: str) -> Optional[str]:
    t = text.strip()
    return t if _BARE_ONLY_RE.match(t) and not _is_year(t) else None


def _at_edge(token: str, side: str) -> bool:
    s = side.strip()
    return s.startswith(token) or s.rstrip(" .,;").endswith(token)


def _extract_stat(text: str) -> Optional[Tuple[Dict[str, str], bool]]:
    """Returns ({value, label, sublabel?}, is_strong) or None when the item is
    not a clear metric."""
    t = _strip_md(text)
    if not t or len(t.split()) > MAX_ITEM_WORDS:
        return None

    sub: Optional[str] = None
    pm = _PAREN_TAIL_RE.search(t)
    if pm:
        sub = pm.group(1).strip()
        t = t[:pm.start()].strip()
    if not t:
        return None

    left, right = t, ""
    sm = _SEP_RE.search(t)
    if sm and t[:sm.start()].strip() and t[sm.end():].strip():
        left, right = t[:sm.start()].strip(), t[sm.end():].strip()

    sides = [("left", left)] + ([("right", right)] if right else [])
    hits = [(name, m) for name, s in sides for m in _STRONG_RE.finditer(s)]
    value = label = sublabel = None
    strong = False

    if len(hits) > 1:
        return None
    if len(hits) == 1:
        name, m = hits[0]
        side_text = left if name == "left" else right
        other = right if name == "left" else left
        if not _at_edge(m.group(0), side_text):
            return None
        value, strong = m.group(0).strip(), True
        rest = _clean(side_text[:m.start()] + " " + side_text[m.end():], links=False)
        # The token's own side supplies the label when it has words besides the
        # token; otherwise the other side does. Leftover clause + trailing
        # parenthetical become the sublabel.
        if name == "left":
            label, clause = (rest, other) if rest else (other, "")
        else:
            label, clause = other, rest
        sublabel = " ".join(p for p in (clause, f"({sub})" if sub and clause else sub) if p) or None
        if not label:
            label, sublabel = _clean(sub or ""), None
    else:
        if right:
            lb, rb = _bare_number(left), _bare_number(right)
            if lb:
                value, label = lb, right
            elif rb:
                value, label = rb, left
        else:
            bm = _BARE_LEAD_RE.match(left)
            if bm and not _is_year(bm.group(1)):
                value, label = bm.group(1), bm.group(2)
        if value is None:
            return None
        sublabel = sub

    is_rank = bool(re.match(r"(?:#|no\.|thứ)", value or "", re.IGNORECASE))
    label = _clean(label or "", links=not is_rank)
    if not value or not label or len(label.split()) > MAX_LABEL_WORDS or len(value) > MAX_VALUE_CHARS:
        return None
    stat = {"value": value, "label": label}
    if sublabel and _clean(sublabel):
        stat["sublabel"] = _clean(sublabel)
    return stat, strong


def detect_stat_row(spec: Dict[str, Any], section_title: str) -> Optional["SlideBlock"]:
    """Returns a stat_row SlideBlock for a parsed "content" spec that is
    clearly a short metric list, else None (caller keeps it as bullets)."""
    items = spec.get("items") or []
    if not 2 <= len(items) <= 4:
        return None
    for it in items:
        if not it.get("bullet") or it.get("level", 0) != 0 or it.get("is_subsection_label"):
            return None
    parsed = [_extract_stat(it.get("text", "")) for it in items]
    if any(p is None for p in parsed) or not any(strong for _, strong in parsed):
        return None
    stats = [stat for stat, _ in parsed]
    if not 2 <= len(stats) <= 4:
        return None
    return SlideBlock(
        component=COMPONENT_STAT_ROW,
        data={"heading": spec.get("title") or section_title, "stats": stats},
        source_section=section_title,
    )


# ─────────────────────────────────────────────────────────────────────────────
# timeline detector (Slice 3) — fires ONLY on 3-6 sequential level-0 bullets
# that all start with the same phase-cue family (Phase N, Step N, Stage N,
# Q1-Q4, H1/H2, Month/Week/Year N, First..Sixth). One trailing non-cue
# bullet may become footer_note. Children provide description/deliverable.
# ─────────────────────────────────────────────────────────────────────────────
_ORDINAL_MAP = {
    "first": 1, "second": 2, "third": 3,
    "fourth": 4, "fifth": 5, "sixth": 6,
}

_CUE_PATTERNS: List[Tuple[str, "re.Pattern"]] = [
    ("phase", re.compile(r"Phase\s+(\d+)", re.IGNORECASE)),
    ("step", re.compile(r"Step\s+(\d+)", re.IGNORECASE)),
    ("stage", re.compile(r"Stage\s+(\d+)", re.IGNORECASE)),
    ("quarter", re.compile(r"(Q[1-4])\b", re.IGNORECASE)),
    ("half", re.compile(r"(H[12])\b", re.IGNORECASE)),
    ("month", re.compile(r"Month\s+(\d+)", re.IGNORECASE)),
    ("week", re.compile(r"Week\s+(\d+)", re.IGNORECASE)),
    ("year", re.compile(r"Year\s+(\d+)", re.IGNORECASE)),
    ("ordinal", re.compile(r"(First|Second|Third|Fourth|Fifth|Sixth)\b", re.IGNORECASE)),
]


def _match_phase_cue(text: str) -> Optional[Dict[str, Any]]:
    for family, pattern in _CUE_PATTERNS:
        m = pattern.match(text)
        if not m:
            continue
        if family in ("quarter", "half"):
            tok = m.group(1).upper()
            return {"family": family, "seq": int(tok[-1]), "label": tok, "end": m.end()}
        if family == "ordinal":
            seq = _ORDINAL_MAP.get(m.group(1).lower())
            if seq is None:
                continue
            return {"family": family, "seq": seq, "label": m.group(1).capitalize(), "end": m.end()}
        seq = int(m.group(1))
        label = f"{family.capitalize()} {seq}"
        return {"family": family, "seq": seq, "label": label, "end": m.end()}
    return None


_DELIVERABLE_RE = re.compile(r"(?:Deliverable:\s*|→\s*)(.*)", re.IGNORECASE)


def _extract_phase(group: Dict[str, Any], cue: Dict[str, Any]) -> Dict[str, str]:
    text = _strip_md(group["parent"].get("text", ""))
    rest = text[cue["end"]:].strip()

    period: Optional[str] = None
    pm = re.match(r"\(([^)]+)\)\s*", rest)
    if pm:
        period = pm.group(1).strip()
        rest = rest[pm.end():].strip()

    rest = re.sub(r"^[:\-—–]\s*", "", rest).strip()

    title = rest
    description: Optional[str] = None
    deliverable: Optional[str] = None

    dm = _DELIVERABLE_RE.search(rest)
    if dm:
        deliverable = dm.group(1).strip()
        title = rest[: dm.start()].rstrip(" \t—–-:")

    if " — " in title:
        parts = title.split(" — ", 1)
        title, description = parts[0].strip(), parts[1].strip()

    for child in group.get("children", []):
        ct = _strip_md(child.get("text", ""))
        if not ct:
            continue
        cdm = _DELIVERABLE_RE.match(ct)
        if cdm:
            deliverable = cdm.group(1).strip() or deliverable
        else:
            description = (description + ". " + ct) if description else ct

    phase: Dict[str, str] = {"label": cue["label"], "title": title or cue["label"]}
    if period:
        phase["period"] = period
    if description:
        phase["description"] = description
    if deliverable:
        phase["deliverable"] = deliverable
    return phase


def detect_timeline(spec: Dict[str, Any], section_title: str) -> Optional[SlideBlock]:
    items = spec.get("items") or []
    if not items:
        return None

    groups: List[Dict[str, Any]] = []
    for it in items:
        if it.get("level", 0) == 0 and it.get("bullet"):
            groups.append({"parent": it, "children": []})
        elif groups and it.get("level", 0) > 0:
            groups[-1]["children"].append(it)
        else:
            return None

    if len(groups) < 3:
        return None

    cues = [_match_phase_cue(_strip_md(g["parent"].get("text", ""))) for g in groups]

    footer_note: Optional[str] = None
    phase_groups, phase_cues = groups, cues
    if cues[-1] is None and len(groups) >= 4:
        parts = [_strip_md(groups[-1]["parent"].get("text", ""))]
        for ch in groups[-1].get("children", []):
            t = _strip_md(ch.get("text", ""))
            if t:
                parts.append(t)
        footer_note = " ".join(parts)
        phase_groups, phase_cues = groups[:-1], cues[:-1]

    if not 3 <= len(phase_groups) <= 6:
        return None
    if any(c is None for c in phase_cues):
        return None
    families = set(c["family"] for c in phase_cues)
    if len(families) != 1:
        return None
    seqs = [c["seq"] for c in phase_cues]
    for j in range(1, len(seqs)):
        if seqs[j] <= seqs[j - 1]:
            return None

    phases = [_extract_phase(g, c) for g, c in zip(phase_groups, phase_cues)]
    data: Dict[str, Any] = {
        "heading": spec.get("title") or section_title,
        "phases": phases,
    }
    if footer_note:
        data["footer_note"] = footer_note.strip()
    return SlideBlock(component=COMPONENT_TIMELINE, data=data, source_section=section_title)


def plan_section(section_markdown: str, section_title: str, tpl) -> List[SlideBlock]:
    """Plans one H3 section's body into SlideBlocks. `tpl` (a TemplateSpec)
    supplies the fit model (chars_per_line / max_lines) and table/chart note
    geometry the packer needs — they are derived from it exactly as before,
    not passed separately."""
    # Imported lazily: pptx_service imports this module at load time.
    from backend.services.pptx_service import _parse_markdown_to_slides

    blocks: List[SlideBlock] = []
    for spec in _parse_markdown_to_slides(section_markdown, tpl, default_title=section_title):
        component = _SPEC_TYPE_TO_COMPONENT.get(spec["type"])
        if component is None:
            continue
        if component == COMPONENT_BULLETS:
            timeline_block = detect_timeline(spec, section_title)
            if timeline_block is not None:
                blocks.append(timeline_block)
                continue
            stat_block = detect_stat_row(spec, section_title)
            if stat_block is not None:
                blocks.append(stat_block)
                continue
        data = {k: v for k, v in spec.items() if k != "type"}
        blocks.append(SlideBlock(component=component, data=data, source_section=section_title))
    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Slice 4a — LLM content-planner logic (classify + extract + validate +
# fallback). No export wiring yet: this only builds plan_report_llm() and the
# SLIDE_PLANNER_LLM flag; pptx_service's export path is untouched until 4b.
# ─────────────────────────────────────────────────────────────────────────────

#: Env flag 4b will read to switch export over to the LLM planner. Default OFF.
SLIDE_PLANNER_LLM = os.environ.get("SLIDE_PLANNER_LLM", "").strip().lower() in (
    "1", "true", "yes", "on",
)


@dataclass(frozen=True)
class SectionPlan:
    """One section's planned blocks, as produced by plan_report_llm."""
    section_title: str
    blocks: List[SlideBlock] = field(default_factory=list)


def validate_block(component: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    """Structural validator for one (component, data) pair. Enforces required
    fields and caps; does NOT check grounding (see _is_grounded) — callers run
    both. Returns (ok, reason); reason is "" when ok."""
    if not isinstance(data, dict):
        return False, f"{component}: data is not a dict"

    if component == COMPONENT_BULLETS:
        title, items = data.get("title"), data.get("items")
        if not isinstance(title, str) or not title.strip():
            return False, "bullets: missing non-empty title"
        if not isinstance(items, list) or not items:
            return False, "bullets: missing non-empty items"
        for it in items:
            if not isinstance(it, dict) or not isinstance(it.get("text"), str) or not it["text"].strip():
                return False, "bullets: item missing non-empty text"
        return True, ""

    if component == COMPONENT_TABLE:
        title, rows = data.get("title"), data.get("rows")
        if not isinstance(title, str) or not title.strip():
            return False, "table: missing non-empty title"
        if not isinstance(rows, list) or len(rows) < 2:
            return False, "table: needs a header row plus at least one data row"
        if any(not isinstance(r, list) or not r for r in rows):
            return False, "table: malformed row"
        return True, ""

    if component == COMPONENT_CHART:
        title, chart_json = data.get("title"), data.get("chart_json")
        if not isinstance(title, str) or not title.strip():
            return False, "chart: missing non-empty title"
        if not isinstance(chart_json, dict) or "data" not in chart_json:
            return False, "chart: missing chart_json.data"
        return True, ""

    if component == COMPONENT_STAT_ROW:
        heading, stats = data.get("heading"), data.get("stats")
        if not isinstance(heading, str) or not heading.strip():
            return False, "stat_row: missing non-empty heading"
        if not isinstance(stats, list) or not 2 <= len(stats) <= 4:
            return False, "stat_row: needs 2-4 stats"
        for s in stats:
            if (
                not isinstance(s, dict)
                or not isinstance(s.get("value"), str) or not s["value"].strip()
                or not isinstance(s.get("label"), str) or not s["label"].strip()
            ):
                return False, "stat_row: stat missing non-empty value/label"
        return True, ""

    if component == COMPONENT_TIMELINE:
        heading, phases = data.get("heading"), data.get("phases")
        if not isinstance(heading, str) or not heading.strip():
            return False, "timeline: missing non-empty heading"
        if not isinstance(phases, list) or not 3 <= len(phases) <= 6:
            return False, "timeline: needs 3-6 phases"
        for p in phases:
            if (
                not isinstance(p, dict)
                or not isinstance(p.get("label"), str) or not p["label"].strip()
                or not isinstance(p.get("title"), str) or not p["title"].strip()
            ):
                return False, "timeline: phase missing non-empty label/title"
        return True, ""

    return False, f"unknown component: {component!r}"


# Normalized numeric-claim grounding: a value grounds only if its number AND
# unit/scale (M/B/K/%/x, or the spelled-out word) appear as one CONTIGUOUS
# claim in the source — not as scattered digits. "$50M" must find "50M"/
# "50 million" in the source; a lone "50" sitting inside "2050" never counts,
# because the number regex below always captures the FULL digit run at each
# position (so "2050" is read as one token "2050", never as "50").
_NUMERIC_CLAIM_RE = re.compile(
    # "%" needs no trailing word-boundary (it's never part of a following
    # word); the spelled-out/letter units DO need one, or "12 key players"
    # would misread "k" off the front of "key" as a thousand-suffix.
    r"(\d[\d,]*(?:\.\d+)?)\s*(%|(?:percent|million|billion|thousand|crore|lakh|mn|bn|[mbkx])\b)?",
    re.IGNORECASE,
)
_UNIT_CANON = {
    "%": "pct", "percent": "pct",
    "million": "m", "mn": "m", "m": "m",
    "billion": "b", "bn": "b", "b": "b",
    "thousand": "k", "k": "k",
    "crore": "crore", "lakh": "lakh",
    "x": "x",
}
# A hedge/estimation word anywhere in a stat's or phase's text is itself a
# fabrication signal, independent of whether a number is present at all.
_HEDGE_RE = re.compile(
    r"~|\best\.|\b(?:estimate[sd]?|approx(?:imately)?|roughly|about|around)\b",
    re.IGNORECASE,
)


def _numeric_claims(text: str) -> set:
    """Set of normalized "<number><canonical-unit>" tokens found in `text`,
    e.g. "$480M" / "480 million" -> {"480m"}; "Top 10%" -> {"10pct"};
    a bare "12" -> {"12"}. Two claims are the "same" claim only if both their
    number AND their unit/scale match after normalization."""
    claims = set()
    for m in _NUMERIC_CLAIM_RE.finditer(text or ""):
        number = m.group(1).replace(",", "")
        unit_raw = (m.group(2) or "").lower()
        unit = _UNIT_CANON.get(unit_raw, "")
        claims.add(f"{number}{unit}")
    return claims


def _has_hedge(text: str) -> bool:
    return bool(_HEDGE_RE.search(text or ""))


def _is_grounded(component: str, data: Dict[str, Any], source_text: str) -> bool:
    """For stat_row/timeline, EVERY numeric claim in EVERY text field of EVERY
    stat/phase must appear as the same normalized claim in the section's own
    source text (see _numeric_claims) — not just scattered matching digits.
    A hedge/estimation word (estimate, approx, roughly, about, around, ~,
    "est.") anywhere in a stat's or phase's fields is rejected outright, since
    it signals the LLM inferred rather than copied a figure. Any single
    stat/phase failing either check fails the WHOLE block (the caller
    degrades it entirely to bullets, never drops just one stat/phase). Other
    components pass through (bullets/table/chart text is free-form prose,
    not a quantitative claim)."""
    if component == COMPONENT_STAT_ROW:
        items = [s for s in data.get("stats", []) if isinstance(s, dict)]
        field_names = ("value", "label", "sublabel")
    elif component == COMPONENT_TIMELINE:
        items = [p for p in data.get("phases", []) if isinstance(p, dict)]
        field_names = ("label", "title", "period", "description", "deliverable")
    else:
        return True

    source_claims = _numeric_claims(source_text)
    for item in items:
        for field_name in field_names:
            field_text = item.get(field_name) or ""
            if not isinstance(field_text, str):
                continue
            if _has_hedge(field_text):
                return False
            if not _numeric_claims(field_text) <= source_claims:
                return False
    return True


# Prompt target for a takeaway is <=15 words; this cap is deliberately a bit
# more generous (catches a wildly long one, not an off-by-one) rather than
# rejecting an otherwise-good takeaway over a couple extra words.
_TAKEAWAY_MAX_WORDS = 20


def _takeaway_is_valid(takeaway: Any, source_text: str) -> bool:
    """A takeaway (the slide's one-line "so what") is valid only if it's a
    non-empty string under the word cap, has no hedge word, and every numeric
    claim in it already appears in the section's own source text — the same
    contiguous-normalized-claim check _is_grounded uses for stat_row/
    timeline, since a takeaway is exactly the kind of place a model might
    quietly round or invent a number while summarizing."""
    if not isinstance(takeaway, str) or not takeaway.strip():
        return False
    if len(takeaway.split()) > _TAKEAWAY_MAX_WORDS:
        return False
    if _has_hedge(takeaway):
        return False
    return _numeric_claims(takeaway) <= _numeric_claims(source_text)


def _bullets_items_grounded(data: Dict[str, Any], source_text: str) -> bool:
    """Tightened/compressed bullets items are still prose, not a quantitative
    claim like a stat_row value — EXCEPT compression itself is a new risk the
    deterministic planner never had: the model could round or invent a number
    while condensing a sentence. So, unlike bullets' normal free pass through
    _is_grounded, every item's text here must carry no hedge word and no
    numeric claim absent from the section's own source text."""
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        if _has_hedge(text):
            return False
        if not _numeric_claims(text) <= _numeric_claims(source_text):
            return False
    return True


def _degrade_to_bullets(component: str, data: Dict[str, Any], section_title: str) -> SlideBlock:
    """Un-grounded stat_row/timeline blocks degrade to a plain bullets block
    carrying the same extracted text, rather than being discarded outright."""
    heading = data.get("heading") or section_title
    items: List[Dict[str, Any]] = []
    if component == COMPONENT_STAT_ROW:
        for s in data.get("stats", []):
            if not isinstance(s, dict):
                continue
            parts = [s.get("value", ""), s.get("label", "")]
            if s.get("sublabel"):
                parts.append(f"({s['sublabel']})")
            text = " ".join(p for p in parts if p).strip()
            if text:
                items.append({"bullet": True, "text": text, "level": 0, "is_subsection_label": False})
    elif component == COMPONENT_TIMELINE:
        for p in data.get("phases", []):
            if not isinstance(p, dict):
                continue
            bits = [p.get("label", ""), p.get("period", ""), p.get("title", "")]
            text = " ".join(b for b in bits if b).strip(" -")
            if text:
                items.append({"bullet": True, "text": text, "level": 0, "is_subsection_label": False})
            for key in ("description", "deliverable"):
                if p.get(key):
                    items.append({"bullet": True, "text": p[key], "level": 1, "is_subsection_label": False})
    if not items:
        items = [{"bullet": True, "text": heading, "level": 0, "is_subsection_label": False}]
    return SlideBlock(
        component=COMPONENT_BULLETS,
        data={"title": heading, "items": items},
        source_section=section_title,
    )


_SYSTEM_PROMPT = """You are a slide-content classifier for a PPTX report generator.

You will be given ONE section of a report (its title + markdown body) — \
sections are classified one at a time, each in its own call, so a problem \
with one section's output never affects any other section. Split this \
section's content into an ordered list of slide "blocks", choosing the \
best-fitting component for each:

- "bullets": a heading plus a flat/nested list of talking points.
- "table": a heading plus tabular rows (first row is the header).
- "chart": a slide that shows a chart. Leave "data" as {} — the real chart \
  data is injected separately from the source markdown's own chart blocks; \
  never invent chart_json yourself.
- "stat_row": ONLY for a short list of 2-4 standout metrics/KPIs, each with a \
  value and a label (e.g. "$480M — market size").
- "timeline": ONLY for a clearly sequential roadmap of 3-6 phases/steps/\
  stages/quarters, each with a label and title (e.g. "Phase 1 — Research").

STRICT GROUNDING RULES (critical):
- Every number, currency figure, percentage, date, or named figure you put in \
  a block's "data" MUST appear verbatim in THIS section's own source text. \
  Never invent, round, estimate, or carry a figure over from another section.
- NEVER estimate, compute, derive, round, or infer a number. Use a metric \
  ONLY if it appears verbatim in the section text. Never add a unit or scale \
  (M, B, K, %, x) that is not already in the source. Do not turn a \
  qualitative claim ("growing fast") into a number. If this section has no \
  verbatim metrics, DO NOT make a stat_row — use bullets instead.
- Never hedge a figure with words like "estimated", "approximately", \
  "roughly", "about", "around", or "~" — if you are not quoting the source \
  exactly, leave the claim out and use bullets for that content instead.
- When unsure whether this section fits stat_row or timeline, use "bullets" \
  instead and keep the original wording — never drop content.
- Preserve the source's own bullet hierarchy: peer items (findings, drivers, \
  options) stay peers at the same level — never nest one sibling finding \
  underneath another as if it were a sub-point of the first.
- Keep one block per logical sub-topic already implied by the source \
  markdown's structure (one table stays one table block, one chart stays one \
  chart block).

SLIDE SHAPING (the deck should read like a deck, not a document):
- For each slide, produce a "takeaway": one assertive sentence (the \
  slide's "so what"), <=15 words, stating only what this section's own text \
  supports — never a new fact or number, never a hedge word. Omit \
  "takeaway" entirely if you cannot state one without adding or hedging \
  anything. Applies to bullets/stat_row/timeline/chart.
- For "bullets", write each item as a short, scannable point (<=14 words), \
  COMPRESSED from the source wording — never a full paragraph copied \
  verbatim. Keep EVERY distinct point from the source as its own item: \
  never merge two separate claims into one item, and never drop a point \
  because it seems minor. Compression must not change meaning or introduce/\
  round a number — if you cannot compress a point without altering a figure \
  in it, keep that one point closer to its original wording instead.

Respond with ONLY a single JSON object (no prose, no markdown fences), \
exactly matching this shape — blocks for THIS section only ("takeaway" is \
optional on every component):

{"blocks": [
  {"component": "bullets", "data": {"title": str, "takeaway": str (optional), "items": [
     {"text": str, "level": 0 or 1, "bullet": true, "is_subsection_label": false}
  ]}},
  {"component": "table", "data": {"title": str, "rows": [[str, ...], ...]}},
  {"component": "chart", "data": {"takeaway": str (optional)}},
  {"component": "stat_row", "data": {"heading": str, "takeaway": str (optional), "stats": [
     {"value": str, "label": str, "sublabel": str (optional)}
  ]}},
  {"component": "timeline", "data": {"heading": str, "takeaway": str (optional), "phases": [
     {"label": str, "title": str, "period": str (optional),
      "description": str (optional), "deliverable": str (optional)}
  ]}}
]}
"""


def _build_section_user_prompt(title: str, body: str) -> str:
    return f"Plan the slide blocks for this report section.\n\n=== SECTION: {title} ===\n{body.strip()}\n"


def _extract_json(text: str) -> Any:
    """Robust single-JSON-object extraction: strips a ```json fence if
    present, otherwise scans for the OUTERMOST balanced {...} (tolerating
    leading/trailing prose the model may add around it) and parses that.
    Brace-counting tracks string state so a "}" inside a quoted value never
    closes the object early. Raises (any exception) when nothing usable is
    found — callers treat every failure here the same way."""
    text = (text or "").strip()

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))

    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in response")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON object in response")


_PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
}
_PROVIDER_CHEAP_MODEL_ENV = {
    "openai": ("OPENAI_PLANNER_MODEL", "gpt-4o-mini"),
    "groq": ("GROQ_PLANNER_MODEL", "openai/gpt-oss-120b"),
    "anthropic": ("ANTHROPIC_PLANNER_MODEL", "claude-haiku-5-5"),
}


_PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_DEFAULT_ANTHROPIC_PLANNER_MODEL = "claude-haiku-5-5"


def _provider_key_present(provider: str) -> bool:
    env_name = _PROVIDER_KEY_ENV.get(provider)
    return bool(env_name and os.environ.get(env_name, "").strip())


_UNEXPECTED_KWARG_RE = re.compile(r"unexpected keyword argument '([^']+)'")


# ── GPT-5/6 reasoning-model compatibility for OpenAI-compatible calls ────────
# These models (gpt-5*, gpt-6*, e.g. "gpt-6-luna") reject a non-default
# temperature and require max_completion_tokens instead of max_tokens on
# chat.completions.create. Every other model/provider on the OpenAI-compatible
# branches (gpt-4o, groq's openai-compatible endpoint, etc.) is unaffected —
# this only changes behavior for a model id starting with one of these
# prefixes.
_REASONING_MODEL_PREFIXES = ("gpt-5", "gpt-6")


def _is_reasoning_model(model: Optional[str]) -> bool:
    return (model or "").strip().lower().startswith(_REASONING_MODEL_PREFIXES)


_reasoning_effort_supported: Optional[bool] = None  # lazily cached feature-detection result


def _sdk_supports_reasoning_effort() -> bool:
    """Static, installed-SDK-version feature detection (not a per-call
    unsupported-kwarg retry) — reasoning_effort is only ever added for a
    model that already wants it (_is_reasoning_model), so a 400 from the
    MODEL rejecting it should still surface as a real error, not be
    swallowed; this only skips the param when the installed openai package
    itself doesn't know about it at all."""
    global _reasoning_effort_supported
    if _reasoning_effort_supported is None:
        try:
            import inspect
            from openai.resources.chat.completions import Completions
            _reasoning_effort_supported = "reasoning_effort" in inspect.signature(Completions.create).parameters
        except Exception:
            _reasoning_effort_supported = False
    return _reasoning_effort_supported


def openai_completion_kwargs(
    model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float,
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """Builds the kwargs for an OpenAI-compatible chat.completions.create call,
    branching ONLY on the model id:
    - gpt-5/gpt-6 reasoning model: max_completion_tokens (not max_tokens), no
      temperature (the API only accepts its default), and reasoning_effort
      when the caller asked for one AND the installed SDK supports it.
    - every other model (gpt-4o, groq's models, ...): today's exact shape —
      max_tokens + temperature, unchanged.
    """
    kwargs: Dict[str, Any] = {"model": model, "stream": False, "messages": messages}
    if _is_reasoning_model(model):
        kwargs["max_completion_tokens"] = max_tokens
        if reasoning_effort and _sdk_supports_reasoning_effort():
            kwargs["reasoning_effort"] = reasoning_effort
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
    return kwargs


# ── Shared automatic fallback for non-streaming JSON-completion call sites ──
# Used by task_classifier_service/checkpoint_service/brand_brief_service's
# own completion functions when their primary provider call raises (e.g. the
# Anthropic 400 "credit balance too low" error) — a single retry against a
# second provider instead of degrading straight to each service's empty/
# Other fail-safe. Configurable via LLM_FALLBACK_PROVIDER/LLM_FALLBACK_MODEL;
# defaults (openai/gpt-4o-mini) mean no .env change is required.
_DEFAULT_FALLBACK_PROVIDER = "openai"
_DEFAULT_FALLBACK_MODEL = "gpt-4o-mini"


def resolve_llm_fallback() -> Tuple[str, str]:
    provider = os.environ.get("LLM_FALLBACK_PROVIDER", _DEFAULT_FALLBACK_PROVIDER).strip().lower()
    model = os.environ.get("LLM_FALLBACK_MODEL", _DEFAULT_FALLBACK_MODEL).strip()
    return provider, model


def llm_fallback_available(primary_provider: str) -> bool:
    """Whether the automatic fallback can run for this primary failure: the
    fallback provider differs from the one that just failed, and its API key
    is present. With the defaults, this is exactly OPENAI_API_KEY present
    and primary_provider != "openai"."""
    fallback_provider, _ = resolve_llm_fallback()
    return primary_provider != fallback_provider and _provider_key_present(fallback_provider)


def llm_fallback_completion(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float = 0.2) -> Tuple[str, str, str]:
    """Runs ONE fallback completion via the OpenAI-compatible dispatch path
    (same shape as every service's own non-Anthropic branch). Returns
    (text, fallback_provider, fallback_model). Raises on failure — callers
    fall through to their existing fail-safe."""
    from backend.services.ai_service import _get_llm_provider
    from openai import OpenAI

    provider, model = resolve_llm_fallback()
    _, api_key = _get_llm_provider(provider)
    client = OpenAI(api_key=api_key, base_url=_PROVIDER_BASE_URLS.get(provider))
    resp = client.chat.completions.create(**openai_completion_kwargs(
        model, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens, temperature,
    ))
    text = resp.choices[0].message.content or ""
    return text, provider, model


def _resolve_planner_provider_and_model() -> Tuple[Optional[str], Optional[str]]:
    """Dedicated-model resolution for the slide planner, independent of the
    global generation resolver's priority order:
    (a) SLIDE_PLANNER_PROVIDER + SLIDE_PLANNER_MODEL both set, AND that
        provider's own API key is present -> use them as given.
    (b) else, if an Anthropic key is present -> default to Claude (using
        SLIDE_PLANNER_MODEL as the model id if set, else a sensible default).
    (c) else -> (None, None): caller falls back to the existing global
        `_get_llm_provider()` resolver untouched."""
    override_provider = os.environ.get("SLIDE_PLANNER_PROVIDER", "").strip().lower()
    override_model = os.environ.get("SLIDE_PLANNER_MODEL", "").strip()

    if override_provider and override_model and _provider_key_present(override_provider):
        return override_provider, override_model

    if _provider_key_present("anthropic"):
        return "anthropic", override_model or _DEFAULT_ANTHROPIC_PLANNER_MODEL

    return None, None


def _default_llm_completion(system_prompt: str, user_prompt: str) -> str:
    """Production llm callable for plan_report_llm: a thin, single
    NON-streaming completion at temperature 0.1. Resolves a DEDICATED
    planner model first (see _resolve_planner_provider_and_model) — Claude by
    default when an Anthropic key is configured, so the planner doesn't
    silently ride whatever provider the main report-generation resolver
    happens to pick — and only falls back to that global multi-provider
    resolver (`ai_service._get_llm_provider`) when neither an explicit
    override nor an Anthropic key is available. Tests inject a fake callable
    instead of this; any error here propagates to plan_report_llm's
    try/except, which degrades to the deterministic planner rather than
    letting export crash."""
    from backend.services.ai_service import _get_llm_provider

    forced_provider, forced_model = _resolve_planner_provider_and_model()
    if forced_provider:
        provider = forced_provider
        _, api_key = _get_llm_provider(forced_provider)
        model = forced_model
    else:
        provider, api_key = _get_llm_provider()
        model_env, default_model = _PROVIDER_CHEAP_MODEL_ENV.get(provider, (None, "gpt-4o-mini"))
        model = os.environ.get(model_env, default_model) if model_env else default_model
    logger.info("[slide_planner] resolved provider=%s model=%s", provider, model)

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            # temperature is gone from this API entirely — not just absent
            # from the SDK's typed create() signature (TypeError), but
            # actively rejected server-side even via extra_body (400
            # "Extra inputs are not permitted"). There is no sampling knob
            # left to ask for determinism with; output_config.effort="low"
            # is the closest available lever (least exploratory/most
            # literal), so extraction passes use that instead of silently
            # running at an uncontrolled default via the strip-and-retry
            # path below.
            "output_config": {"effort": "low"},
        }
        stripped: List[str] = []
        while True:
            try:
                resp = client.messages.create(**kwargs)
                break
            except TypeError as exc:
                m = _UNEXPECTED_KWARG_RE.search(str(exc))
                if not m or m.group(1) not in kwargs:
                    raise
                del kwargs[m.group(1)]
                stripped.append(m.group(1))
        if stripped:
            logger.warning(
                "[slide_planner] retried anthropic call without unsupported kwarg(s): %s",
                ", ".join(stripped),
            )
        text = "".join(getattr(b, "text", "") for b in resp.content)
        logger.info("[slide_planner] provider=%s completion received, length=%d chars", provider, len(text))
        return text

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=_PROVIDER_BASE_URLS.get(provider))
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        stream=False,
        max_tokens=4096,  # generous per-section budget so one section can't get truncated
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = resp.choices[0].message.content or ""
    logger.info("[slide_planner] provider=%s completion received, length=%d chars", provider, len(text))
    return text


def plan_report_llm(
    sections: List[Tuple[str, str]],
    chart_blocks: Dict[str, List[SlideBlock]],
    llm: Callable[[str, str], str],
    tpl: Any = None,
) -> List[SectionPlan]:
    """LLM-assisted planner for a whole report — ONE call PER SECTION (Slice
    4e), not one call for the whole report. A large/malformed response for
    one section therefore only ever degrades THAT section; every other
    section still gets its own independent LLM plan. The system prompt is
    identical across calls (prompt-cache friendly); only the user prompt
    (one section's title + body) changes per call.

    `sections` is an ordered list of (section_title, section_markdown).
    `chart_blocks` maps section_title -> the deterministically pre-extracted
    chart SlideBlocks for that section (the LLM never invents chart_json;
    "chart" blocks it proposes are swapped for these in order). `llm` is
    `(system_prompt, user_prompt) -> str`, a single non-streaming completion
    per call — production uses `_default_llm_completion`; tests inject a fake
    (optionally keyed by section title, since each section gets its own call).

    On ANY failure for a section (the call raising, an unparseable response,
    an invalid block) that section falls back to the existing deterministic
    `plan_section` — logged, and isolated to that section only. stat_row/
    timeline blocks that fail the grounding check (a number not present in
    the section's own text) degrade to a bullets block instead of a full
    section fallback.
    """
    from backend.services.template_service import DEFAULT_TEMPLATE
    tpl = tpl or DEFAULT_TEMPLATE

    results: List[SectionPlan] = []

    for title, body in sections:
        det_blocks = plan_section(body, title, tpl)

        try:
            raw = llm(_SYSTEM_PROMPT, _build_section_user_prompt(title, body))
            logger.info("[slide_planner] %s: llm call ok, response length=%d chars", title, len(raw or ""))
        except Exception as exc:
            logger.warning(
                "[slide_planner] %s: llm call FAILED: %s: %s -> deterministic fallback for section",
                title, type(exc).__name__, exc,
            )
            results.append(SectionPlan(section_title=title, blocks=det_blocks))
            continue

        try:
            parsed = _extract_json(raw)
            raw_blocks = parsed.get("blocks", [])
            if not isinstance(raw_blocks, list):
                raise ValueError("'blocks' is not a list")
        except Exception as exc:
            preview = (raw or "")[:120]
            logger.warning(
                "[slide_planner] %s: response did NOT parse as JSON (%s: %s) -> deterministic fallback for "
                "section; first 120 chars: %r", title, type(exc).__name__, exc, preview,
            )
            results.append(SectionPlan(section_title=title, blocks=det_blocks))
            continue

        chart_iter = iter(chart_blocks.get(title, []))
        final_blocks: List[SlideBlock] = []
        section_failed = False
        fail_reason = ""

        for raw_block in raw_blocks:
            if not isinstance(raw_block, dict):
                section_failed, fail_reason = True, f"malformed block entry: {raw_block!r}"
                break
            component = raw_block.get("component")
            data = raw_block.get("data", {})
            if not isinstance(data, dict):
                section_failed, fail_reason = True, f"{component}: data is not a dict"
                break

            if component == COMPONENT_CHART:
                nxt = next(chart_iter, None)
                if nxt is not None:
                    takeaway = data.get("takeaway")
                    if takeaway is not None:
                        if _takeaway_is_valid(takeaway, body):
                            nxt = SlideBlock(component=nxt.component, data={**nxt.data, "takeaway": takeaway},
                                              source_section=nxt.source_section)
                        else:
                            logger.info("[slide_planner] %s: dropping invalid/ungrounded chart takeaway", title)
                    final_blocks.append(nxt)
                continue

            ok, reason = validate_block(component, data)
            if not ok:
                section_failed, fail_reason = True, reason
                break

            # Tightened bullets items carry their own grounding risk (a model
            # could round/invent a number while compressing a sentence) that
            # validate_block's structural checks don't cover — unlike
            # stat_row/timeline, an ungrounded item here fails the WHOLE
            # block (there is no narrower "degrade to bullets" for bullets
            # itself), same as any other validate_block failure.
            if component == COMPONENT_BULLETS and not _bullets_items_grounded(data, body):
                section_failed, fail_reason = True, "bullets: a tightened item is hedged or contains an ungrounded number"
                break

            if component in (COMPONENT_STAT_ROW, COMPONENT_TIMELINE) and not _is_grounded(component, data, body):
                logger.info("[slide_planner] %s: ungrounded %s block -> degraded to bullets", title, component)
                final_blocks.append(_degrade_to_bullets(component, data, title))
                continue

            # The takeaway is a pure annotation on an otherwise-valid block —
            # unlike every check above, a bad takeaway only drops the
            # takeaway itself, never the block it's attached to.
            takeaway = data.get("takeaway")
            if takeaway is not None and not _takeaway_is_valid(takeaway, body):
                logger.info("[slide_planner] %s: dropping invalid/ungrounded %s takeaway", title, component)
                data = {k: v for k, v in data.items() if k != "takeaway"}

            final_blocks.append(SlideBlock(component=component, data=data, source_section=title))

        if section_failed:
            logger.info("[slide_planner] %s: invalid block (%s) -> deterministic fallback for section",
                        title, fail_reason)
            results.append(SectionPlan(section_title=title, blocks=det_blocks))
            continue

        # Never silently drop a chart the deterministic parser already found,
        # even if the LLM's block list didn't mention it.
        final_blocks.extend(chart_iter)

        if not final_blocks:
            logger.info("[slide_planner] %s: no usable blocks -> deterministic fallback for section", title)
            final_blocks = det_blocks
        else:
            counts: Dict[str, int] = {}
            for b in final_blocks:
                counts[b.component] = counts.get(b.component, 0) + 1
            logger.info("[slide_planner] %s: %s", title, counts)
        results.append(SectionPlan(section_title=title, blocks=final_blocks))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Slice 4b — render-time pagination. plan_report_llm's bullets blocks carry an
# arbitrary-length `items` list (the LLM isn't template-aware); this splits
# each one across one-or-more fitted slides using the SAME packer the
# deterministic planner already relies on (_group_into_clusters +
# _pack_clusters_to_slides in pptx_service), so a long LLM-planned bullets
# block fits any template exactly like today's content slides do. The
# deterministic planner's own bullets blocks are already single-slide by
# construction, so re-running this over them is a no-op (same clustering,
# same packer, same input -> same single slide out) — which is what keeps the
# flag-OFF path byte-identical even though pagination runs unconditionally.
# ─────────────────────────────────────────────────────────────────────────────

def paginate_bullets_block(block: SlideBlock, tpl: Any) -> List[SlideBlock]:
    """Splits one bullets SlideBlock's items across one-or-more slides via the
    existing content-slide packer. stat_row/timeline/table/chart blocks are
    already single-slide by construction (validator caps enforce that) and
    are never passed here — see paginate_blocks, which routes only bullets
    blocks through this function.

    A takeaway (the section's "so what") is stated once — if present on the
    original block, it's attached only to the FIRST resulting slide, never
    repeated on a "(cont'd)" continuation slide."""
    from backend.services.pptx_service import _group_into_clusters, _pack_clusters_to_slides
    from backend.services.template_service import _max_lines_per_slide

    items = block.data.get("items") or []
    elements = [dict(it, kind="item") for it in items]
    clusters = _group_into_clusters(elements)
    chars_per_line = tpl.fit["chars_per_line"]
    max_lines = _max_lines_per_slide(tpl)
    specs = _pack_clusters_to_slides(clusters, block.data.get("title", ""), max_lines, chars_per_line)
    takeaway = block.data.get("takeaway")
    result = []
    for i, s in enumerate(specs):
        data = {"title": s["title"], "items": s["items"]}
        if i == 0 and takeaway:
            data["takeaway"] = takeaway
        result.append(SlideBlock(component=COMPONENT_BULLETS, data=data, source_section=block.source_section))
    return result


def paginate_blocks(blocks: List[SlideBlock], tpl: Any) -> List[SlideBlock]:
    """Expands every bullets block in `blocks` into one-or-more fitted bullets
    SlideBlocks (see paginate_bullets_block); every other component passes
    through unchanged, in order."""
    result: List[SlideBlock] = []
    for block in blocks:
        if block.component == COMPONENT_BULLETS:
            result.extend(paginate_bullets_block(block, tpl))
        else:
            result.append(block)
    return result
