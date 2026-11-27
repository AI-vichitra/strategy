"""
Checkpoint Service
==================
Computes the task-brief intake state for a classified task: which of the
core (C1-C6) and group-specific checkpoints are already answered by the
prompt/brief/brand context, and which still need to be asked about.

The one LLM call here (for the checkpoints that aren't resolved by simple
field lookups) mirrors task_classifier_service.py's/brand_brief_service.py's
completion-call pattern exactly (SDK-safe, no temperature on Anthropic,
output_config.effort instead; temperature kept on the OpenAI-compatible
branch) and reuses slide_planner._extract_json for parsing — the one
genuinely shared, reusable piece across this whole family of services (see
DIAGNOSE: task_classifier_service.py has no single call+parse helper to
import directly, since its own completion function is hardcoded to its own
provider-resolution pair).

Never raises: a missing LLM key, a completion failure, or an unparseable
response all degrade every LLM-extracted checkpoint to "missing" (C6 to
"optional_missing"), logging why — intake must never block on this, exactly
like brand_brief_service/task_classifier_service's own failure modes.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from backend.services import task_service

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1024
_TEMPERATURE = 0.2

# Core checkpoints handled by direct field lookups, never sent to the LLM.
_DIRECT_CORE_IDS = ("C1", "C4")
# Core checkpoints resolved via the one LLM extraction call, alongside every
# group checkpoint.
_LLM_CORE_IDS = ("C2", "C3", "C5", "C6")

_SYSTEM_PROMPT = (
    "You extract short factual values for a set of checkpoints from a user's request and, "
    "optionally, their uploaded brand brief, for a brand-strategy tool. For EACH checkpoint, "
    "extract a short value ONLY if it is explicitly stated in the text — never infer, never "
    "guess, never invent. If a checkpoint isn't explicitly addressed, its value is null. "
    "Return strict JSON: {\"<checkpoint id>\": {\"value\": string|null, \"source\": "
    "\"prompt\"|\"brief\"|null}, ...} — one entry per checkpoint id given, nothing else."
)


def _build_checkpoint_defs_block(checkpoints: List[Dict[str, Any]]) -> str:
    lines = []
    for cp in checkpoints:
        lines.append(f"- {cp['id']} ({cp.get('name', '')}): {cp.get('meaning', '')}")
    return "\n".join(lines)


def _build_user_prompt(checkpoints: List[Dict[str, Any]], prompt_text: str, brief_text: Optional[str]) -> str:
    parts = [
        "CHECKPOINTS (extract a value for each id below, or null):",
        _build_checkpoint_defs_block(checkpoints),
        "",
        f"User request: {prompt_text.strip()}",
    ]
    if brief_text and brief_text.strip():
        parts.append(f"\nUploaded brief:\n{brief_text.strip()}")
    return "\n".join(parts)


# ── Model resolution: CHECKPOINT_PROVIDER / CHECKPOINT_MODEL ─────────────────
# Mirrors task_classifier_service._resolve_classifier_provider_and_model's
# STRUCTURE (an explicit override pair, else fall through) — the fallback
# here is the classifier's OWN resolution (which itself falls back to
# brand_brief_service's, then the app-wide resolver), so an unconfigured
# checkpoint extractor rides on the same chain the classifier already trusts.
def _resolve_checkpoint_provider_and_model():
    from backend.services.slide_planner import _provider_key_present

    provider = os.environ.get("CHECKPOINT_PROVIDER", "").strip().lower()
    model = os.environ.get("CHECKPOINT_MODEL", "").strip()
    if provider and model and _provider_key_present(provider):
        return provider, model

    from backend.services.task_classifier_service import _resolve_classifier_provider_and_model
    return _resolve_classifier_provider_and_model()


def _checkpoint_llm_completion(system_prompt: str, user_prompt: str) -> str:
    """One-shot, non-streaming completion for checkpoint extraction —
    identical dispatch shape to task_classifier_service._classifier_llm_completion
    (Anthropic vs. OpenAI-compatible branches, same unexpected-kwarg retry),
    driven by _resolve_checkpoint_provider_and_model's own env pair instead."""
    from backend.services.ai_service import _get_llm_provider
    from backend.services.slide_planner import (
        _PROVIDER_BASE_URLS, _UNEXPECTED_KWARG_RE, openai_completion_kwargs,
        llm_fallback_available, llm_fallback_completion,
    )

    provider, model = _resolve_checkpoint_provider_and_model()
    _, api_key = _get_llm_provider(provider)
    logger.info(f"[Checkpoint] resolved provider={provider} model={model}")

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            kwargs = {
                "model": model,
                "max_tokens": _MAX_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                # No temperature here — the Anthropic API rejects it on the
                # models this app targets; effort is the replacement knob. "low"
                # is enough for short, explicitly-stated-only extraction.
                "output_config": {"effort": "low"},
            }
            stripped = []
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
                logger.warning(f"[Checkpoint] retried anthropic call without unsupported kwarg(s): {', '.join(stripped)}")
            text = "".join(getattr(b, "text", "") for b in resp.content)
            logger.info(f"[Checkpoint] provider={provider} completion received, length={len(text)} chars")
            return text

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=_PROVIDER_BASE_URLS.get(provider))
        # Explicitly-stated-only extraction needs no deep reasoning — "low"
        # effort when the model is a gpt-5/6 reasoning model and the installed
        # SDK supports it; a no-op for every other model (see
        # openai_completion_kwargs).
        resp = client.chat.completions.create(**openai_completion_kwargs(
            model, [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ], _MAX_TOKENS, _TEMPERATURE, reasoning_effort="low",
        ))
        text = resp.choices[0].message.content or ""
        logger.info(f"[Checkpoint] provider={provider} completion received, length={len(text)} chars")
        return text
    except Exception as primary_exc:
        if not llm_fallback_available(provider):
            raise
        try:
            text, fb_provider, fb_model = llm_fallback_completion(system_prompt, user_prompt, _MAX_TOKENS, _TEMPERATURE)
        except Exception as fallback_exc:
            logger.warning(f"[Checkpoint] primary provider={provider} failed ({primary_exc}); fallback also failed: {fallback_exc}")
            raise primary_exc
        logger.warning(f"[Checkpoint] primary provider={provider} failed ({primary_exc}); fell back to provider={fb_provider} model={fb_model}")
        return text


def _extract_llm_checkpoints(checkpoints: List[Dict[str, Any]], prompt_text: str, brief_text: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Runs the one extraction call for `checkpoints` (C2/C3/C5/C6 + every
    group checkpoint). Returns {checkpoint_id: {"value":..., "source":...}}
    — an empty dict on ANY failure (logged once), never raising."""
    if not checkpoints:
        return {}
    try:
        user_prompt = _build_user_prompt(checkpoints, prompt_text, brief_text)
        raw = _checkpoint_llm_completion(_SYSTEM_PROMPT, user_prompt)

        from backend.services.slide_planner import _extract_json
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError("checkpoint extraction response was not a JSON object")
        return parsed
    except Exception as e:
        logger.warning(f"[Checkpoint] extraction failed, treating {len(checkpoints)} checkpoint(s) as missing: {e}")
        return {}


def _is_populated(value: Optional[str]) -> bool:
    """Mirrors ai_service._is_brief_field_populated's "not a real value"
    check (empty, or the model's own not-available marker) without importing
    a private helper across an unrelated module boundary — same small rule,
    kept local since it's one line."""
    if not value or not isinstance(value, str):
        return False
    v = value.strip().lower().rstrip(".")
    return bool(v) and v not in ("not available", "n/a", "na", "not applicable")


def _stringify_prefilled(value: Any) -> Optional[str]:
    """A prefilled_checkpoints entry may be a string or a list of strings
    (the form's multi-select questions join to one string already, but the
    request schema allows either) — normalizes to the same comma-joined
    string shape fill_checkpoints' other checkpoint values use, or None if
    there's nothing real in it."""
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(parts) if parts else None
    if isinstance(value, str):
        return value.strip() or None
    return None


def fill_checkpoints(
    task: Optional[str],
    group_id: str,
    prompt_text: str,
    brief_text: Optional[str] = None,
    brand_context: Optional[Dict[str, Any]] = None,
    brand_memory: Optional[Dict[str, Any]] = None,
    prefilled_checkpoints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes the full checkpoint-fill state for a classified task.

    brand_context shape (all optional/nullable): {"brand_brief": {...9 brief
    fields...}, "target_market": {region, cities, custom_region},
    "additional_notes": str}.

    brand_memory: accepted but UNUSED for now — a stub for the deferred
    Brand Memory source, which will slot into the lookup order ahead of
    brand_brief once it exists (e.g. for C4 and the C6 fallback below).

    prefilled_checkpoints: optional {checkpoint_id: value} map (value a
    string or list of strings) for checkpoints already answered outside the
    intake flow. Only applies to checkpoints this task's own LLM-extracted
    set actually includes (C2/C3/C5/C6 + the classified group's own
    checkpoints) — an id for a different group (e.g. G3.1 on a non-G3 task)
    is silently ignored, never an error.

    Returns {task, group_id, group_name, agent_type, checkpoints: [...],
    missing_required: [...]}. Never raises.
    """
    prefilled_checkpoints = prefilled_checkpoints or {}
    brand_context = brand_context or {}
    brief = brand_context.get("brand_brief") or {}
    target_market = brand_context.get("target_market") or {}
    additional_notes = brand_context.get("additional_notes") or ""

    group = task_service.get_group(group_id) or task_service.get_group("OTHER") or {}
    group_name = group.get("name", "Other")
    agent_type = task_service.resolve_agent_for_task(task) if task else None

    core_checkpoints = task_service.get_core_checkpoints()
    group_checkpoints = task_service.get_group_checkpoints(group_id)

    checkpoints: List[Dict[str, Any]] = []

    # ── C1 (Task): direct lookup, never sent to the LLM ─────────────────────
    c1_def = next((c for c in core_checkpoints if c["id"] == "C1"), None)
    if c1_def:
        if task:
            checkpoints.append({"id": "C1", "name": c1_def.get("name", "Task"), "scope": "core", "must": True, "state": "found", "value": task, "source": "prompt"})
        else:
            checkpoints.append({"id": "C1", "name": c1_def.get("name", "Task"), "scope": "core", "must": True, "state": "missing", "value": None, "source": None})

    # ── C4 (Audience and market): direct lookup from brand_context only ─────
    c4_def = next((c for c in core_checkpoints if c["id"] == "C4"), None)
    if c4_def:
        from backend.services.brand_brief_service import _target_market_geography

        audience_parts = []
        target_audience = brief.get("target_audience")
        if _is_populated(target_audience):
            audience_parts.append(target_audience.strip())
        geography = _target_market_geography(target_market)
        if geography:
            audience_parts.append(geography)

        if audience_parts:
            checkpoints.append({"id": "C4", "name": c4_def.get("name", "Audience and market"), "scope": "core", "must": False, "state": "prefilled", "value": " — ".join(audience_parts), "source": "brand_brief"})
        else:
            checkpoints.append({"id": "C4", "name": c4_def.get("name", "Audience and market"), "scope": "core", "must": False, "state": "missing", "value": None, "source": None})

    # ── Remaining checkpoints: ONE LLM extraction call ───────────────────────
    llm_core_defs = [c for c in core_checkpoints if c["id"] in _LLM_CORE_IDS]
    llm_checkpoint_defs = llm_core_defs + list(group_checkpoints)
    extracted = _extract_llm_checkpoints(llm_checkpoint_defs, prompt_text, brief_text)

    for cp_def in llm_checkpoint_defs:
        cp_id = cp_def["id"]
        scope = "core" if cp_id in _LLM_CORE_IDS else "group"
        must = False if cp_id == "C6" else bool(cp_def.get("must", False))

        # A value the user already supplied elsewhere (e.g. the template
        # form's Strategy Preferences tab) wins outright over extraction —
        # skip the LLM result entirely for this checkpoint so build_questions
        # never re-asks it. Blank/absent entries fall through unchanged.
        prefilled_value = _stringify_prefilled(prefilled_checkpoints.get(cp_id))
        if prefilled_value is not None:
            checkpoints.append({
                "id": cp_id, "name": cp_def.get("name", cp_id), "scope": scope, "must": must,
                "state": "found", "value": prefilled_value, "source": "form",
            })
            continue

        entry = extracted.get(cp_id) if isinstance(extracted, dict) else None
        value = entry.get("value") if isinstance(entry, dict) else None
        source = entry.get("source") if isinstance(entry, dict) else None

        if isinstance(value, str) and value.strip():
            state = "found"
            value = value.strip()
            source = source if source in ("prompt", "brief") else "prompt"
        else:
            state = "optional_missing" if cp_id == "C6" else "missing"
            value = None
            source = None

        # C6-only fallback: brand's own onboarding guardrails, independent of
        # whether the LLM call ran at all — a cheap, reliable local source.
        if cp_id == "C6" and state == "optional_missing" and additional_notes.strip():
            state = "found"
            value = additional_notes.strip()
            source = "brand_brief"

        checkpoints.append({"id": cp_id, "name": cp_def.get("name", cp_id), "scope": scope, "must": must, "state": state, "value": value, "source": source})

    # ── missing_required: C1/C2/C3/C5 if missing, + must=true group checkpoints if missing ──
    required_core_ids = {"C1", "C2", "C3", "C5"}
    missing_required = [
        cp["id"] for cp in checkpoints
        if cp["state"] == "missing" and (
            (cp["scope"] == "core" and cp["id"] in required_core_ids)
            or (cp["scope"] == "group" and cp["must"])
        )
    ]

    return {
        "task": task,
        "group_id": group.get("id", group_id),
        "group_name": group_name,
        "agent_type": agent_type,
        "checkpoints": checkpoints,
        "missing_required": missing_required,
    }


def _lookup_checkpoint_def(checkpoint_id: str, group_id: str) -> Dict[str, Any]:
    """Looks the full raw definition (meaning, ask_options, multi_select)
    back up from task_groups.json by id — fill_checkpoints' own per-checkpoint
    output deliberately doesn't carry these UI-only fields."""
    for cp in task_service.get_core_checkpoints():
        if cp["id"] == checkpoint_id:
            return cp
    for cp in task_service.get_group_checkpoints(group_id):
        if cp["id"] == checkpoint_id:
            return cp
    return {}


def _make_question(checkpoint_id: str, group_id: str, options_override: Optional[List[str]] = None) -> Dict[str, Any]:
    cp_def = _lookup_checkpoint_def(checkpoint_id, group_id)
    text = cp_def.get("meaning") or cp_def.get("name") or checkpoint_id
    options = options_override if options_override is not None else (cp_def.get("ask_options") or [])
    return {
        "checkpoint_id": checkpoint_id,
        "text": text,
        "options": options,
        "multi_select": bool(cp_def.get("multi_select", False)),
        "allow_other": True,
        "skippable": True,
    }


_QUESTION_CAP = 5


def build_questions(fill_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Builds the ordered, capped question set from a fill_checkpoints() result,
    per §2.9: C1 first (only if missing) -> missing required core checkpoints
    (C2/C3/C5 — the same required set used by missing_required) in id order
    -> must=true GROUP checkpoints that are missing. Nothing else is ever
    asked: non-must group checkpoints are left to best judgement even when
    missing, C6 is never asked (optional — surfaced only in the brief as an
    assumption when skipped), and C4 is never a question (prefilled or not).
    Hard cap: 5, truncated from the end after ordering.
    """
    group_id = fill_result.get("group_id", "OTHER")
    by_id = {cp["id"]: cp for cp in fill_result.get("checkpoints", [])}

    ordered: List[Dict[str, Any]] = []

    c1 = by_id.get("C1")
    if c1 and c1["state"] == "missing":
        group = task_service.get_group(group_id)
        group_tasks = (group or {}).get("tasks") or []
        options = group_tasks if (group_id and group_id != "OTHER" and group_tasks) else task_service.list_all_tasks()
        ordered.append(_make_question("C1", group_id, options_override=options))

    for cid in ("C2", "C3", "C5"):
        cp = by_id.get(cid)
        if cp and cp["state"] == "missing":
            ordered.append(_make_question(cid, group_id))

    group_missing_must = [cp for cp in fill_result.get("checkpoints", []) if cp["scope"] == "group" and cp["must"] and cp["state"] == "missing"]
    for cp in group_missing_must:
        ordered.append(_make_question(cp["id"], group_id))

    return ordered[:_QUESTION_CAP]
