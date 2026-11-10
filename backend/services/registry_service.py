"""
Registry Service
=================
Loads and caches the static agent catalog from backend/data/agents_registry.json.
Loaded once into a module-level cache on first use; call reload_registry() to
force a re-read from disk (dev use).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "agents_registry.json"

_cache: Optional[Dict[str, Any]] = None


def _load_registry() -> Dict[str, Any]:
    """Reads and parses the registry JSON file. Never raises — falls back to an empty registry."""
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("agents_registry.json root must be a JSON object")
        data.setdefault("categories", [])
        data.setdefault("agents", [])
        return data
    except Exception as e:
        logger.error(f"[registry] Failed to load {REGISTRY_PATH}: {e}")
        return {"categories": [], "agents": []}


def _get_cache() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _load_registry()
    return _cache


def get_registry() -> Dict[str, Any]:
    """Returns the full registry dict: {"categories": [...], "agents": [...]}."""
    return _get_cache()


def get_categories() -> List[Dict[str, Any]]:
    """Returns the list of category dicts."""
    return _get_cache().get("categories", [])


def get_agents(enabled_only: bool = True) -> List[Dict[str, Any]]:
    """Returns the list of agent dicts, optionally filtered to only enabled agents."""
    agents = _get_cache().get("agents", [])
    if enabled_only:
        return [a for a in agents if a.get("enabled", True)]
    return agents


def get_agent(title: str) -> Optional[Dict[str, Any]]:
    """Returns the agent dict whose "title" field exactly matches, or None if not found."""
    for agent in _get_cache().get("agents", []):
        if agent.get("title") == title:
            return agent
    return None


def get_questions(title: str) -> Optional[List[Dict[str, Any]]]:
    """Returns the matching agent's questions list, or None if the title isn't in the registry."""
    agent = get_agent(title)
    if agent is None:
        return None
    return agent.get("questions")


def reload_registry() -> Dict[str, Any]:
    """Re-reads the registry file from disk and refreshes the module cache. For dev use."""
    global _cache
    _cache = _load_registry()
    return _cache
