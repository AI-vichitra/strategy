"""
Blueprint service — loads report section templates and builds
structured prompts for the LLM so reports follow a consistent
section layout per agent type.
"""

import os
import re
import json
from functools import lru_cache
from typing import Any, Dict, List

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "config", "report_blueprints.json"
)


@lru_cache(maxsize=1)
def load_blueprints() -> Dict[str, Any]:
    """Loads and caches report_blueprints.json for the lifetime of the process."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_agent_key(agent_key: str) -> str:
    """
    agent_type arrives in whichever format the caller has on hand — the registry's
    hyphenated id ("brand-positioning"), the display title build_system_prompt
    actually receives ("Brand Positioning"), or snake_case ("brand_positioning").
    Lowercasing and collapsing spaces/underscores to hyphens maps all three onto
    the hyphenated keys report_blueprints.json's agent_blueprints is keyed by.
    """
    return re.sub(r"[\s_]+", "-", agent_key.strip().lower())


def get_blueprint_for_agent(agent_key: str) -> List[Dict[str, Any]]:
    """
    Returns the merged, order-sorted list of section dicts for agent_key:
    common_sections + (that agent's type_specific_sections, or
    default_blueprint's if agent_key isn't recognized).
    """
    blueprints = load_blueprints()
    normalized = _normalize_agent_key(agent_key)

    agent_blueprint = blueprints["agent_blueprints"].get(normalized)
    type_specific = (
        agent_blueprint["type_specific_sections"]
        if agent_blueprint is not None
        else blueprints["default_blueprint"]["type_specific_sections"]
    )

    merged = list(blueprints["common_sections"]) + list(type_specific)
    return sorted(merged, key=lambda section: section["order"])


def build_section_prompt(agent_key: str) -> str:
    """Formats the agent's blueprint into a section-structure prompt block."""
    sections = get_blueprint_for_agent(agent_key)

    lines = ["## REPORT STRUCTURE — Follow this exact section order:", ""]
    for section in sections:
        lines.append(f"### {section['title']}")
        subsections = section.get("subsections")
        if subsections:
            lines.append(f"Subsections: {' | '.join(subsections)}")
        lines.append(f"Content: {section['content_guidance']}")
        lines.append("")

    lines.extend([
        "CRITICAL FORMATTING RULES:",
        "- Use ### (H3) for each main section heading — the system parses these as report sections",
        "- Use #### (H4) for subsections within each section",
        "- Include markdown TABLEs where the content guidance specifies tables",
        "- Maintain the exact section order above — do not skip, merge, or reorder sections",
        '- Every section must have substantive, detailed content — no placeholders or "to be completed" text',
        "- Keep section titles EXACTLY as specified above (the section editor relies on consistent H3 titles)",
    ])

    return "\n".join(lines)
