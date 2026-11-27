"""
Task Classifier Service
========================
Classifies a user's first-message prompt (and, optionally, their uploaded
Brand Brief text) into the single closest-matching task from the closed
task list in backend/data/task_groups.json, via task_service.

Mirrors brand_brief_service.py's LLM-call pattern verbatim (same provider
resolution shape, same Anthropic vs. OpenAI-compatible dispatch, same
output_config/effort usage on Anthropic with no temperature there, same
_extract_json-based parse), with its own env override pair
(TASK_CLASSIFIER_PROVIDER / TASK_CLASSIFIER_MODEL) that — unlike
brand_brief_service's own cheap-model-per-provider default — falls back to
whatever provider+model brand_brief_service itself resolves to when unset,
so an unconfigured classifier never silently lands on a weaker model than
the brief generation it sits next to.

Never raises: a missing LLM key, a completion failure, an unparseable
response, or a task name outside the closed list all degrade to the
Other-group / unmatched result (logging why), exactly like
brand_brief_service degrading to its all-"Not available" shape — intake
must never block on this.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from backend.services import task_service

logger = logging.getLogger(__name__)

_MAX_TOKENS = 512
_TEMPERATURE = 0.2

_SYSTEM_PROMPT = (
    "You classify a user's request into one task from the provided TASK LIST for a "
    "brand-strategy tool. Choose the single closest task, or null if none fits. Return "
    "strict JSON: {\"task\": string|null, \"confidence\": 0..1, \"reasoning\": short string}."
)


def _build_task_list_block() -> str:
    """Renders every group's tasks under its group name, so the LLM picks
    from the SAME closed list task_service.list_all_tasks() validates
    against afterward."""
    lines = []
    for group in task_service.load_task_groups().get("groups", []):
        tasks = group.get("tasks", [])
        if not tasks:
            continue
        lines.append(f"{group.get('name', group.get('id', ''))}:")
        for t in tasks:
            lines.append(f"- {t}")
    return "\n".join(lines)


def _build_user_prompt(prompt_text: str, brief_text: Optional[str]) -> str:
    parts = [
        "TASK LIST (choose exactly one task string from this list, verbatim, or null):",
        _build_task_list_block(),
        "",
        f"User request: {prompt_text.strip()}",
    ]
    if brief_text and brief_text.strip():
        parts.append(f"\nUploaded brief:\n{brief_text.strip()}")
    return "\n".join(parts)


# ── Model resolution: TASK_CLASSIFIER_PROVIDER / TASK_CLASSIFIER_MODEL ───────
# Mirrors brand_brief_service._resolve_brief_provider_and_model's STRUCTURE
# (an explicit override pair, else fall through) — but the fallback here is
# brand_brief_service's OWN resolved provider+model, not a second independent
# cheap-default table, so an unconfigured classifier rides on whatever this
# app already trusts for structured-JSON brief generation.
def _resolve_classifier_provider_and_model():
    from backend.services.slide_planner import _provider_key_present

    provider = os.environ.get("TASK_CLASSIFIER_PROVIDER", "").strip().lower()
    model = os.environ.get("TASK_CLASSIFIER_MODEL", "").strip()
    if provider and model and _provider_key_present(provider):
        return provider, model

    from backend.services.brand_brief_service import _resolve_brief_provider_and_model
    forced_provider, forced_model = _resolve_brief_provider_and_model()
    if forced_provider:
        return forced_provider, forced_model

    from backend.services.ai_service import _get_llm_provider
    from backend.services.brand_brief_service import _PROVIDER_CHEAP_MODEL_ENV
    provider, _ = _get_llm_provider()
    model_env, default_model = _PROVIDER_CHEAP_MODEL_ENV.get(provider, (None, "gpt-4o-mini"))
    model = os.environ.get(model_env, default_model) if model_env else default_model
    return provider, model


def _classifier_llm_completion(system_prompt: str, user_prompt: str) -> str:
    """One-shot, non-streaming completion for the classifier — identical
    dispatch shape to brand_brief_service._brief_llm_completion (Anthropic
    vs. OpenAI-compatible branches, same unexpected-kwarg retry), driven by
    _resolve_classifier_provider_and_model's own env pair instead."""
    from backend.services.ai_service import _get_llm_provider
    from backend.services.slide_planner import (
        _PROVIDER_BASE_URLS, _UNEXPECTED_KWARG_RE, openai_completion_kwargs,
        llm_fallback_available, llm_fallback_completion,
    )

    provider, model = _resolve_classifier_provider_and_model()
    _, api_key = _get_llm_provider(provider)
    logger.info(f"[TaskClassifier] resolved provider={provider} model={model}")

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            kwargs = {
                "model": model,
                "max_tokens": _MAX_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                # No temperature here — the Anthropic API rejects it (even via
                # extra_body, a 400) on the models this app targets; effort is
                # the replacement knob. "low" is enough for a closed-list pick
                # with a short reasoning string, unlike the brief's "xhigh".
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
                logger.warning(f"[TaskClassifier] retried anthropic call without unsupported kwarg(s): {', '.join(stripped)}")
            text = "".join(getattr(b, "text", "") for b in resp.content)
            logger.info(f"[TaskClassifier] provider={provider} completion received, length={len(text)} chars")
            return text

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=_PROVIDER_BASE_URLS.get(provider))
        # Closed-set extraction needs no deep reasoning — "low" effort when the
        # model is a gpt-5/6 reasoning model and the installed SDK supports it;
        # a no-op for every other model (see openai_completion_kwargs).
        resp = client.chat.completions.create(**openai_completion_kwargs(
            model, [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ], _MAX_TOKENS, _TEMPERATURE, reasoning_effort="low",
        ))
        text = resp.choices[0].message.content or ""
        logger.info(f"[TaskClassifier] provider={provider} completion received, length={len(text)} chars")
        return text
    except Exception as primary_exc:
        if not llm_fallback_available(provider):
            raise
        try:
            text, fb_provider, fb_model = llm_fallback_completion(system_prompt, user_prompt, _MAX_TOKENS, _TEMPERATURE)
        except Exception as fallback_exc:
            logger.warning(f"[TaskClassifier] primary provider={provider} failed ({primary_exc}); fallback also failed: {fallback_exc}")
            raise primary_exc
        logger.warning(f"[TaskClassifier] primary provider={provider} failed ({primary_exc}); fell back to provider={fb_provider} model={fb_model}")
        return text


_UNMATCHED_RESULT_BASE: Dict[str, Any] = {
    "task": None,
    "matched": False,
    "agent_type": None,
    "confidence": 0.0,
}


def _unmatched_result(reasoning: str) -> Dict[str, Any]:
    other = task_service.get_group("OTHER") or {"id": "OTHER", "name": "Other"}
    return {
        **_UNMATCHED_RESULT_BASE,
        "group_id": other.get("id", "OTHER"),
        "group_name": other.get("name", "Other"),
        "reasoning": reasoning,
    }


def classify_task(prompt_text: str, brief_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Classifies prompt_text (+ optional brief_text) into the single closest
    task from task_service's closed task list.

    Returns {task, matched, group_id, group_name, agent_type, confidence,
    reasoning}. NEVER raises — any failure (no LLM key, completion error,
    unparseable response, or a returned task outside the closed list)
    degrades to the Other-group/unmatched shape, logging why.
    """
    if not prompt_text or not prompt_text.strip():
        return _unmatched_result("Empty prompt — nothing to classify.")

    user_prompt = _build_user_prompt(prompt_text, brief_text)

    try:
        raw = _classifier_llm_completion(_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning(f"[TaskClassifier] Completion failed: {e}")
        return _unmatched_result(f"Classifier completion failed: {e}")

    try:
        from backend.services.slide_planner import _extract_json
        parsed = _extract_json(raw)
    except Exception as e:
        logger.warning(f"[TaskClassifier] Unparseable response: {e}")
        return _unmatched_result("Classifier response was unparseable.")

    if not isinstance(parsed, dict):
        logger.warning("[TaskClassifier] Parsed response was not a JSON object.")
        return _unmatched_result("Classifier response was not a JSON object.")

    raw_task = parsed.get("task")
    reasoning = parsed.get("reasoning") or ""
    try:
        confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    if not isinstance(raw_task, str) or not raw_task.strip():
        return _unmatched_result(reasoning or "Model returned no matching task.")

    all_tasks = task_service.list_all_tasks()
    needle = raw_task.strip().lower()
    matched_task = next((t for t in all_tasks if t.strip().lower() == needle), None)

    if matched_task is None:
        logger.warning(f"[TaskClassifier] Model returned a task outside the closed list: {raw_task!r}")
        return _unmatched_result(reasoning or f"Model returned an unrecognised task: {raw_task!r}")

    group = task_service.get_task_group(matched_task)
    agent_type = task_service.resolve_agent_for_task(matched_task)

    return {
        "task": matched_task,
        "matched": True,
        "group_id": group.get("id", "OTHER"),
        "group_name": group.get("name", "Other"),
        "agent_type": agent_type,
        "confidence": confidence,
        "reasoning": reasoning,
    }
