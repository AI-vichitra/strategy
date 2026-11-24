"""
Brand Brief Service
====================
Generates the structured 6-field Brand Brief (schemas.brand.BRAND_BRIEF_KEYS)
from whatever onboarding-time evidence is available. Built on
slide_planner's one-shot completion pattern (_default_llm_completion /
_resolve_planner_provider_and_model) and its _extract_json parser — but with
its OWN provider/model override pair (BRAND_BRIEF_PROVIDER / BRAND_BRIEF_MODEL)
and no Anthropic/haiku default when that override isn't fully set: unlike
the slide planner, this always defers to the app-wide resolver instead.

IMPORTANT CEILING: at the point onboarding calls this, the richer Tavily
research pipeline (web_scrape / deep_dive / risk / depth research, run only
after pipeline_service's background task completes) does NOT exist yet.
The only evidence available here is:
  - website_text        — a direct fetch of the brand's own site (see
                           social_links_service.extract_page_text)
  - reference_docs_text  — text already extracted from user-uploaded docs
  - tavily_context       — the same two Tavily search queries
                           brand_context_service already runs
  - category / target_market / additional_notes — onboarding form fields
The brief is only as grounded as these inputs. It does not retroactively
gain the pipeline's evidence, and the generation prompt is written to say
"Not available" per-field rather than invent when they don't support a claim.

Never raises: a missing LLM key, a completion failure, or an unparseable
response all degrade to the all-"Not available" 6-key shape (logging why),
so this can never block onboarding. NOT yet threaded into
ai_service.build_system_prompt — storage/generation only in this change.
"""
import json
import logging
import os
from typing import Dict, List, Optional

from backend.schemas.brand import BRAND_BRIEF_KEYS

logger = logging.getLogger(__name__)

#   Two distinct "nothing" shapes, both valid, meaning different things:
#   - "" per field (_EMPTY_BRIEF)       -> generation never produced a
#     judgment at all (no evidence to even try, a completion error, or an
#     unparseable response). Matches schemas.brand.normalize_brand_brief's
#     own default shape for an unset/legacy row.
#   - "Not available" per field         -> the LLM DID run and evidence WAS
#     considered, but that specific field wasn't supported by it. This is a
#     deliberate, field-level judgment call the system prompt asks for, not
#     a failure — e.g. a thin-evidence run may correctly return this for
#     positioning/differentiators while still filling what_we_do.
_EMPTY_BRIEF: Dict[str, str] = {key: "" for key in BRAND_BRIEF_KEYS}

# Headroom for effort="xhigh" (see _brief_llm_completion): that effort spends
# output budget on internal reasoning BEFORE emitting the JSON, and a brief
# grounded in a brand's full website copy legitimately runs long (e.g. a real
# products_services list). At 2048 the combined reasoning+JSON intermittently
# truncated mid-object, failing the parse on some runs and not others — the
# instability this budget removes. 4096 fits both comfortably on every run
# measured.
_MAX_TOKENS = 4096
_TEMPERATURE = 0.2

_SYSTEM_PROMPT = (
    "You are a brand strategist producing a structured Brand Brief from ONLY the evidence "
    "blocks provided below. Output a single JSON object with exactly these six string keys: "
    "what_we_do, positioning, target_audience, differentiators, products_services, "
    "tone_of_voice.\n\n"
    "EVIDENCE PRIORITY:\n"
    "- The brand's OWN WEBSITE text and its UPLOADED REFERENCE DOCUMENTS are the PRIMARY "
    "evidence and outrank everything else. They are the authoritative source for "
    "positioning, target_audience and tone_of_voice in particular: infer the brand's voice "
    "and audience from how its own copy actually reads and whom it addresses.\n"
    "- Third-party WEB RESEARCH is CORROBORATION only — use it to confirm or add facts "
    "(products, numbers, markets), not to override how the brand describes itself. When the "
    "brand's own copy and a third-party source conflict, prefer the brand's own copy.\n\n"
    "RULES:\n"
    "- For any field the evidence does not support, set its value to the literal string "
    "\"Not available\". Do not guess, do not invent, and do not pad a thin field with "
    "generic industry language just to fill it.\n"
    "- positioning and differentiators are the fields most prone to fabrication: only fill "
    "them when the evidence names a SPECIFIC claim, fact, product, number, or quote that "
    "supports them. A category-generic sentence (e.g. \"a trusted leader in its industry\" "
    "or \"known for quality and innovation\") is NOT evidence and must not be produced — use "
    "\"Not available\" instead.\n"
    "- Every other field follows the same rule: only state what the evidence actually "
    "supports, in your own words; never fabricate a product, audience segment, or tone claim "
    "the evidence doesn't contain.\n"
    "- Output ONLY the JSON object. No prose, no markdown fence, nothing before or after it."
)


def _build_user_prompt(
    brand_name: str,
    category: str,
    target_market: Optional[dict],
    additional_notes: str,
    website_text: str,
    reference_docs_text: str,
    tavily_context: str,
    tavily_sources: Optional[List[str]],
) -> str:
    meta_lines = [f"Brand: {brand_name}"]
    if category:
        meta_lines.append(f"Category: {category}")
    if target_market:
        meta_lines.append(f"Target Market: {json.dumps(target_market)}")
    if additional_notes.strip():
        meta_lines.append(f"User-provided notes/guardrails: {additional_notes.strip()}")

    # Primary evidence (brand's own copy, then uploaded docs) is emitted FIRST
    # and labelled PRIMARY; third-party research is labelled CORROBORATING —
    # mirroring the EVIDENCE PRIORITY rule in _SYSTEM_PROMPT so the ranking is
    # explicit in the payload itself, not only in the instructions.
    evidence_blocks = []
    if website_text.strip():
        evidence_blocks.append(f"[PRIMARY — Brand's own website]\n{website_text.strip()}")
    if reference_docs_text.strip():
        evidence_blocks.append(f"[PRIMARY — Uploaded reference documents]\n{reference_docs_text.strip()}")
    if tavily_context.strip():
        src_note = f" (sources: {', '.join(tavily_sources)})" if tavily_sources else ""
        evidence_blocks.append(f"[CORROBORATING — Third-party web research{src_note}]\n{tavily_context.strip()}")

    if not evidence_blocks:
        evidence_blocks.append("[No evidence available — every field must be \"Not available\".]")

    return "\n".join(meta_lines) + "\n\n" + "\n\n".join(evidence_blocks)


# ── Model resolution: BRAND_BRIEF_PROVIDER / BRAND_BRIEF_MODEL, own pair ─────
# Mirrors slide_planner._resolve_planner_provider_and_model's STRUCTURE (an
# explicit override pair, else defer to the app-wide resolver) but drops its
# "default to Anthropic/haiku when no override is set" branch entirely —
# with no override, this always falls through to whatever the app-wide
# resolver picks, using a cheap default model for that provider.
_PROVIDER_CHEAP_MODEL_ENV = {
    "openai": ("BRAND_BRIEF_OPENAI_MODEL", "gpt-4o-mini"),
    "groq": ("BRAND_BRIEF_GROQ_MODEL", "openai/gpt-oss-120b"),
    "anthropic": ("BRAND_BRIEF_ANTHROPIC_MODEL", "claude-haiku-5-5"),
}


def _resolve_brief_provider_and_model():
    from backend.services.slide_planner import _provider_key_present

    provider = os.environ.get("BRAND_BRIEF_PROVIDER", "").strip().lower()
    model = os.environ.get("BRAND_BRIEF_MODEL", "").strip()
    if provider and model and _provider_key_present(provider):
        return provider, model
    return None, None


def _brief_llm_completion(system_prompt: str, user_prompt: str) -> str:
    """One-shot, non-streaming completion for the brief — built on the same
    dispatch shape as slide_planner._default_llm_completion (Anthropic vs.
    OpenAI-compatible branches, same unexpected-kwarg retry), but driven by
    _resolve_brief_provider_and_model's own env pair instead."""
    from backend.services.ai_service import _get_llm_provider
    from backend.services.slide_planner import _PROVIDER_BASE_URLS, _UNEXPECTED_KWARG_RE

    forced_provider, forced_model = _resolve_brief_provider_and_model()
    if forced_provider:
        provider = forced_provider
        _, api_key = _get_llm_provider(forced_provider)
        model = forced_model
    else:
        provider, api_key = _get_llm_provider()
        model_env, default_model = _PROVIDER_CHEAP_MODEL_ENV.get(provider, (None, "gpt-4o-mini"))
        model = os.environ.get(model_env, default_model) if model_env else default_model
    logger.info(f"[BrandBrief] resolved provider={provider} model={model}")

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        kwargs = {
            "model": model,
            "max_tokens": _MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            # temperature is gone from this API (rejected even via
            # extra_body with a 400); output_config.effort is the
            # replacement knob. effort="xhigh" chosen on OUTPUT QUALITY,
            # not variance: tested live at all five accepted values
            # (low|medium|high|xhigh|max) against the Emaar India brief.
            # low/medium/high filled 4/6 fields; "xhigh" uniquely and
            # reproducibly recovered a grounded `positioning` (the
            # inference-dependent field that is this brief's known
            # failure mode) for 5/6, with no fabrication. "max" is
            # unusable here: it spends the whole max_tokens budget on
            # internal reasoning and returns EMPTY content
            # (stop_reason=max_tokens), degrading every brief to
            # all-"Not available". tone_of_voice stays "Not available"
            # at every level — correct, as third-party research text
            # carries no brand copy to infer voice from.
            "output_config": {"effort": "xhigh"},
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
            logger.warning(f"[BrandBrief] retried anthropic call without unsupported kwarg(s): {', '.join(stripped)}")
        text = "".join(getattr(b, "text", "") for b in resp.content)
        logger.info(f"[BrandBrief] provider={provider} completion received, length={len(text)} chars")
        return text

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=_PROVIDER_BASE_URLS.get(provider))
    resp = client.chat.completions.create(
        model=model,
        temperature=_TEMPERATURE,
        stream=False,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = resp.choices[0].message.content or ""
    logger.info(f"[BrandBrief] provider={provider} completion received, length={len(text)} chars")
    return text


def generate_brand_brief(
    brand_name: str,
    category: str = "",
    target_market: Optional[dict] = None,
    additional_notes: str = "",
    website_text: str = "",
    reference_docs_text: str = "",
    tavily_context: str = "",
    tavily_sources: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Generates the 6-key structured Brand Brief. Every evidence input is
    optional; an all-empty call still returns the canonical shape (every
    value "Not available") without ever calling the LLM. NEVER raises.
    """
    user_prompt = _build_user_prompt(
        brand_name, category, target_market, additional_notes,
        website_text, reference_docs_text, tavily_context, tavily_sources,
    )

    has_evidence = any(s.strip() for s in (website_text, reference_docs_text, tavily_context))
    if not has_evidence:
        logger.info(f"[BrandBrief] No evidence available for '{brand_name}' — skipping the LLM call.")
        return dict(_EMPTY_BRIEF)

    try:
        raw = _brief_llm_completion(_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning(f"[BrandBrief] Completion failed for '{brand_name}': {e}")
        return dict(_EMPTY_BRIEF)

    try:
        from backend.services.slide_planner import _extract_json
        parsed = _extract_json(raw)
    except Exception as e:
        logger.warning(f"[BrandBrief] Unparseable response for '{brand_name}': {e}")
        return dict(_EMPTY_BRIEF)

    if not isinstance(parsed, dict):
        logger.warning(f"[BrandBrief] Parsed response for '{brand_name}' was not a JSON object.")
        return dict(_EMPTY_BRIEF)

    result: Dict[str, str] = {}
    for key in BRAND_BRIEF_KEYS:
        value = parsed.get(key)
        result[key] = value.strip() if isinstance(value, str) and value.strip() else "Not available"
    return result
