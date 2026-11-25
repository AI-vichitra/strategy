"""
Task Service
============
Loads and caches the static task-group taxonomy from
backend/data/task_groups.json (7 task groups + an "Other" catch-all, each
with its own checkpoints and task list, plus a task -> agent title map and
a shared set of core checkpoints every task goes through).

Mirrors registry_service.py's loader pattern exactly: a module-level cache,
loaded once on first use; any load failure (missing file, malformed JSON,
wrong root shape) is logged as a single warning and degrades to a safe,
empty structure — this must never raise and never block a caller.

Phase 1 (this module): pure data access, no FastAPI route, not imported by
any router. Wiring a task classifier / checkpoint flow on top of this is
phase 2.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TASK_GROUPS_PATH = Path(__file__).resolve().parent.parent / "data" / "task_groups.json"

_EMPTY_TASK_GROUPS: Dict[str, Any] = {
    "version": 0,
    "core_checkpoints": [],
    "groups": [],
    "other_group": {"id": "OTHER", "name": "Other", "note": "", "group_checkpoints": [], "step3_modules": []},
    "task_to_agent": {},
}

_cache: Optional[Dict[str, Any]] = None


def _load_task_groups_from_disk() -> Dict[str, Any]:
    """Reads and parses the task_groups.json file. Never raises — falls back
    to an empty-but-well-shaped structure, mirroring registry_service's
    _load_registry()."""
    try:
        with open(TASK_GROUPS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("task_groups.json root must be a JSON object")
        data.setdefault("core_checkpoints", [])
        data.setdefault("groups", [])
        data.setdefault("other_group", dict(_EMPTY_TASK_GROUPS["other_group"]))
        data.setdefault("task_to_agent", {})
        return data
    except Exception as e:
        logger.warning(f"[task_service] Failed to load {TASK_GROUPS_PATH}: {e}")
        return dict(_EMPTY_TASK_GROUPS)


def _get_cache() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _load_task_groups_from_disk()
    return _cache


def load_task_groups() -> Dict[str, Any]:
    """Returns the full task-groups dict (cached)."""
    return _get_cache()


def reload_task_groups() -> Dict[str, Any]:
    """Re-reads task_groups.json from disk and refreshes the module cache. For dev use."""
    global _cache
    _cache = _load_task_groups_from_disk()
    return _cache


def list_groups() -> List[Dict[str, Any]]:
    """Returns the 7 task groups plus the Other catch-all, as one flat list."""
    data = _get_cache()
    return list(data.get("groups", [])) + [data.get("other_group", {})]


def get_group(group_id: str) -> Optional[Dict[str, Any]]:
    """Returns the group dict whose "id" matches group_id (including "OTHER"),
    or None if no group has that id."""
    if not group_id:
        return None
    for group in list_groups():
        if group.get("id") == group_id:
            return group
    return None


def get_task_group(task_name: str) -> Dict[str, Any]:
    """Returns the group dict the given task belongs to (case-insensitive,
    trimmed match against each group's "tasks" list), or the Other group
    when no task matches."""
    data = _get_cache()
    other = data.get("other_group", {})
    if not task_name:
        return other
    needle = task_name.strip().lower()
    for group in data.get("groups", []):
        for task in group.get("tasks", []):
            if isinstance(task, str) and task.strip().lower() == needle:
                return group
    return other


def get_core_checkpoints() -> List[Dict[str, Any]]:
    """Returns the shared core checkpoints (C1..C6) every task goes through."""
    return _get_cache().get("core_checkpoints", [])


def get_group_checkpoints(group_id: str) -> List[Dict[str, Any]]:
    """Returns the group-specific checkpoints for group_id, or [] if the
    group isn't found or has none (e.g. the Other group)."""
    group = get_group(group_id)
    if not group:
        return []
    return group.get("group_checkpoints", [])


def resolve_agent_for_task(task_name: str) -> Optional[str]:
    """Returns the agent title task_to_agent maps task_name to (case-insensitive,
    trimmed), or None when unmapped or the task isn't in the taxonomy at all."""
    if not task_name:
        return None
    task_to_agent = _get_cache().get("task_to_agent", {})
    needle = task_name.strip().lower()
    for task, agent_title in task_to_agent.items():
        if isinstance(task, str) and task.strip().lower() == needle:
            return agent_title
    return None


def list_all_tasks() -> List[str]:
    """Returns a flat list of every task name across all 7 groups (not
    including the Other group, which has no fixed task list)."""
    data = _get_cache()
    tasks: List[str] = []
    for group in data.get("groups", []):
        tasks.extend(group.get("tasks", []))
    return tasks
