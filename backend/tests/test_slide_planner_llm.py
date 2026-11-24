"""Tests for Slice 4a — LLM content-planner logic (classify + extract +
validate + fallback). Run with:
cd backend && python -m pytest tests/test_slide_planner_llm.py -v

No real LLM is ever called: plan_report_llm takes an injected `llm` callable,
so every test here supplies a fake. Production wiring (_default_llm_completion)
is exercised only insofar as it is constructed correctly; it is not invoked
over the network."""
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import backend.services.slide_planner as slide_planner
from backend.services.slide_planner import (
    COMPONENT_BULLETS,
    COMPONENT_CHART,
    COMPONENT_STAT_ROW,
    COMPONENT_TABLE,
    COMPONENT_TIMELINE,
    SectionPlan,
    SlideBlock,
    _is_grounded,
    _resolve_planner_provider_and_model,
    _takeaway_is_valid,
    plan_report_llm,
    validate_block,
)
from backend.services.template_service import DEFAULT_TEMPLATE


# ─────────────────────────────────────────────────────────────────────────────
# validate_block
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_block_bullets_ok_and_rejects_missing_fields():
    ok, _ = validate_block(COMPONENT_BULLETS, {"title": "T", "items": [{"text": "a"}]})
    assert ok
    assert validate_block(COMPONENT_BULLETS, {"title": "", "items": [{"text": "a"}]})[0] is False
    assert validate_block(COMPONENT_BULLETS, {"title": "T", "items": []})[0] is False
    assert validate_block(COMPONENT_BULLETS, {"title": "T", "items": [{"text": "  "}]})[0] is False


def test_validate_block_table_requires_header_plus_row():
    assert validate_block(COMPONENT_TABLE, {"title": "T", "rows": [["A", "B"], ["1", "2"]]})[0] is True
    assert validate_block(COMPONENT_TABLE, {"title": "T", "rows": [["A", "B"]]})[0] is False
    assert validate_block(COMPONENT_TABLE, {"title": "T", "rows": []})[0] is False
    assert validate_block(COMPONENT_TABLE, {"title": "T", "rows": [["A"], []]})[0] is False


def test_validate_block_chart_requires_title_and_chart_json_data():
    ok, _ = validate_block(COMPONENT_CHART, {"title": "T", "chart_json": {"type": "bar", "data": []}})
    assert ok
    assert validate_block(COMPONENT_CHART, {"title": "T", "chart_json": {"type": "bar"}})[0] is False
    assert validate_block(COMPONENT_CHART, {"title": "", "chart_json": {"data": []}})[0] is False


def test_validate_block_stat_row_enforces_2_to_4_stats():
    good = {"heading": "H", "stats": [{"value": "$1M", "label": "A"}, {"value": "2%", "label": "B"}]}
    assert validate_block(COMPONENT_STAT_ROW, good)[0] is True
    too_few = {"heading": "H", "stats": [{"value": "$1M", "label": "A"}]}
    assert validate_block(COMPONENT_STAT_ROW, too_few)[0] is False
    too_many = {"heading": "H", "stats": [{"value": "1", "label": "A"}] * 5}
    assert validate_block(COMPONENT_STAT_ROW, too_many)[0] is False
    missing_label = {"heading": "H", "stats": [{"value": "1", "label": "A"}, {"value": "2", "label": ""}]}
    assert validate_block(COMPONENT_STAT_ROW, missing_label)[0] is False


def test_validate_block_timeline_enforces_3_to_6_phases():
    good = {"heading": "H", "phases": [{"label": f"Phase {i}", "title": "T"} for i in range(1, 4)]}
    assert validate_block(COMPONENT_TIMELINE, good)[0] is True
    too_few = {"heading": "H", "phases": [{"label": "Phase 1", "title": "T"}]}
    assert validate_block(COMPONENT_TIMELINE, too_few)[0] is False
    too_many = {"heading": "H", "phases": [{"label": "P", "title": "T"}] * 7}
    assert validate_block(COMPONENT_TIMELINE, too_many)[0] is False
    missing_title = {"heading": "H", "phases": [{"label": "P1", "title": "T"}, {"label": "P2", "title": ""},
                                                 {"label": "P3", "title": "T"}]}
    assert validate_block(COMPONENT_TIMELINE, missing_title)[0] is False


def test_validate_block_unknown_component_rejected():
    ok, reason = validate_block("sparkline", {})
    assert ok is False and "unknown component" in reason


# ─────────────────────────────────────────────────────────────────────────────
# plan_report_llm — happy path, validation fallback, grounding degrade,
# unparseable-response fallback, chart substitution.
# ─────────────────────────────────────────────────────────────────────────────

_SECTIONS = [
    ("Key Metrics", "- $480M market size\n- 15% CAGR growth\n- 12 key players (tracked)\n"),
]


def _fake_llm(response_obj):
    """A fake llm that returns the SAME per-section {"blocks": [...]} payload
    no matter which section is asked — fine when a test only has one section
    in play. For multi-section isolation tests, see _fake_llm_by_title."""
    def _llm(system_prompt, user_prompt):
        return json.dumps(response_obj)
    return _llm


def _fake_llm_by_title(responses: Dict[str, Any]):
    """A fake llm keyed by section title: plan_report_llm now calls the llm
    ONCE PER SECTION, so each call's user_prompt embeds exactly one
    "=== SECTION: <title> ===" marker — used here to route to that section's
    own canned response (a dict, serialized to JSON, OR a raw string to
    return as-is, e.g. to simulate garbage/truncated output for one section)."""
    def _llm(system_prompt, user_prompt):
        for title, resp in responses.items():
            if f"=== SECTION: {title} ===" in user_prompt:
                return resp if isinstance(resp, str) else json.dumps(resp)
        raise AssertionError(f"no fake response configured for prompt: {user_prompt[:200]!r}")
    return _llm


def test_happy_path_well_formed_grounded_response_is_used_verbatim():
    response = {
        "blocks": [
            {
                "component": "stat_row",
                "data": {
                    "heading": "Key Metrics",
                    "stats": [
                        {"value": "$480M", "label": "Market size"},
                        {"value": "15%", "label": "CAGR growth"},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(_SECTIONS, {}, _fake_llm(response))
    assert len(plans) == 1
    assert isinstance(plans[0], SectionPlan)
    assert plans[0].section_title == "Key Metrics"
    assert len(plans[0].blocks) == 1
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_STAT_ROW
    assert block.data["stats"][0]["value"] == "$480M"


def test_invalid_block_falls_back_to_deterministic_plan_for_section():
    response = {
        "blocks": [
            {"component": "stat_row", "data": {"heading": "Key Metrics", "stats": [{"value": "$480M", "label": "Market size"}]}},
        ]
    }
    plans = plan_report_llm(_SECTIONS, {}, _fake_llm(response))
    assert len(plans) == 1
    # The deterministic planner should fire its own stat_row detector here,
    # since the fallback source data is a clean 3-stat list.
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW
    assert len(plans[0].blocks[0].data["stats"]) == 3


def test_ungrounded_stat_value_degrades_just_that_block_to_bullets():
    response = {
        "blocks": [
            {
                "component": "stat_row",
                "data": {
                    "heading": "Key Metrics",
                    "stats": [
                        {"value": "$999M", "label": "Market size"},  # 999 not in source text
                        {"value": "15%", "label": "CAGR growth"},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(_SECTIONS, {}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_BULLETS
    text = " ".join(it["text"] for it in block.data["items"])
    assert "$999M" in text and "Market size" in text


def test_ungrounded_timeline_period_degrades_to_bullets():
    sections = [("Delivery Plan", "- Phase 1 (Q1 2025): Research\n- Phase 2 (Q2 2025): Build\n- Phase 3 (Q3 2025): Launch\n")]
    response = {
        "blocks": [
            {
                "component": "timeline",
                "data": {
                    "heading": "Delivery Plan",
                    "phases": [
                        {"label": "Phase 1", "title": "Research", "period": "Q1 2099"},
                        {"label": "Phase 2", "title": "Build", "period": "Q2 2025"},
                        {"label": "Phase 3", "title": "Launch", "period": "Q3 2025"},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(sections, {}, _fake_llm(response))
    assert plans[0].blocks[0].component == COMPONENT_BULLETS


def test_unparseable_llm_response_falls_back_to_deterministic_for_that_section():
    def _broken_llm(system_prompt, user_prompt):
        return "not json at all {{"
    plans = plan_report_llm(_SECTIONS, {}, _broken_llm)
    assert len(plans) == 1
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW


def test_llm_raising_exception_falls_back_to_deterministic():
    def _raising_llm(system_prompt, user_prompt):
        raise RuntimeError("network error")
    plans = plan_report_llm(_SECTIONS, {}, _raising_llm)
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW


def test_missing_blocks_key_in_response_falls_back_to_deterministic():
    response = {}  # no "blocks" key at all
    plans = plan_report_llm(_SECTIONS, {}, _fake_llm(response))
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW


def test_chart_block_is_substituted_with_preextracted_chart_never_llm_data():
    sections = [("Competitive Landscape", "Some prose about pricing.\n")]
    real_chart = SlideBlock(
        component=COMPONENT_CHART,
        data={"title": "Pricing Index", "chart_json": {"type": "bar", "data": [{"name": "A", "value": 9}]}},
        source_section="Competitive Landscape",
    )
    response = {
        "blocks": [{"component": "chart", "data": {"title": "Hallucinated", "chart_json": {"data": [{"name": "X", "value": 1}]}}}],
    }
    plans = plan_report_llm(sections, {"Competitive Landscape": [real_chart]}, _fake_llm(response))
    assert len(plans[0].blocks) == 1
    assert plans[0].blocks[0] is real_chart


def test_chart_not_mentioned_by_llm_is_still_appended_not_dropped():
    sections = [("Competitive Landscape", "Some prose about pricing.\n")]
    real_chart = SlideBlock(
        component=COMPONENT_CHART,
        data={"title": "Pricing Index", "chart_json": {"type": "bar", "data": [{"name": "A", "value": 9}]}},
        source_section="Competitive Landscape",
    )
    response = {
        "blocks": [{"component": "bullets", "data": {"title": "Pricing", "items": [{"text": "Prices vary by brand"}]}}],
    }
    plans = plan_report_llm(sections, {"Competitive Landscape": [real_chart]}, _fake_llm(response))
    components = [b.component for b in plans[0].blocks]
    assert components == [COMPONENT_BULLETS, COMPONENT_CHART]
    assert plans[0].blocks[1] is real_chart


def test_malformed_block_entry_falls_back_whole_section():
    response = {"blocks": ["not-a-dict"]}
    plans = plan_report_llm(_SECTIONS, {}, _fake_llm(response))
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW


# ─────────────────────────────────────────────────────────────────────────────
# Slice 4e — per-section calls: one bad section must never affect its
# neighbors (this is the fix for the JSONDecodeError-on-real-reports failure,
# where one section's large/malformed output used to take down the whole
# report's LLM plan).
# ─────────────────────────────────────────────────────────────────────────────

_MULTI_SECTIONS = [
    ("Key Metrics", "- $480M market size\n- 15% CAGR growth\n- 12 key players (tracked)\n"),
    ("Delivery Plan", "- Phase 1 (Q1 2025): Research\n- Phase 2 (Q2 2025): Build\n- Phase 3 (Q3 2025): Launch\n"),
    ("Competitive Landscape", "Prices vary by brand and region across the category.\n"),
]


def test_all_sections_valid_are_all_llm_planned():
    responses = {
        "Key Metrics": {"blocks": [{"component": "stat_row", "data": {
            "heading": "Key Metrics",
            "stats": [{"value": "$480M", "label": "Market size"}, {"value": "15%", "label": "Growth"}],
        }}]},
        "Delivery Plan": {"blocks": [{"component": "timeline", "data": {
            "heading": "Delivery Plan",
            "phases": [
                {"label": "Phase 1", "title": "Research", "period": "Q1 2025"},
                {"label": "Phase 2", "title": "Build", "period": "Q2 2025"},
                {"label": "Phase 3", "title": "Launch", "period": "Q3 2025"},
            ],
        }}]},
        "Competitive Landscape": {"blocks": [{"component": "bullets", "data": {
            "title": "Competitive Landscape",
            "items": [{"text": "Prices vary by brand and region", "level": 0, "bullet": True, "is_subsection_label": False}],
        }}]},
    }
    plans = plan_report_llm(_MULTI_SECTIONS, {}, _fake_llm_by_title(responses))
    assert [p.section_title for p in plans] == [t for t, _ in _MULTI_SECTIONS]
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW
    assert plans[1].blocks[0].component == COMPONENT_TIMELINE
    assert plans[2].blocks[0].component == COMPONENT_BULLETS


def test_one_section_garbage_json_is_isolated_others_still_llm_planned():
    # This is the real-report failure this slice fixes: previously a single
    # bad/truncated section response took down the WHOLE report's LLM plan.
    responses = {
        "Key Metrics": {"blocks": [{"component": "stat_row", "data": {
            "heading": "Key Metrics",
            "stats": [{"value": "$480M", "label": "Market size"}, {"value": "15%", "label": "Growth"}],
        }}]},
        "Delivery Plan": "{\"blocks\": [truncated garbage not valid json",  # the real-report failure mode
        "Competitive Landscape": {"blocks": [{"component": "bullets", "data": {
            "title": "Competitive Landscape",
            "items": [{"text": "Prices vary by brand and region", "level": 0, "bullet": True, "is_subsection_label": False}],
        }}]},
    }
    plans = plan_report_llm(_MULTI_SECTIONS, {}, _fake_llm_by_title(responses))

    # Key Metrics and Competitive Landscape: LLM-planned, unaffected.
    assert plans[0].blocks[0].component == COMPONENT_STAT_ROW
    assert plans[2].blocks[0].component == COMPONENT_BULLETS
    assert plans[2].blocks[0].data["items"][0]["text"] == "Prices vary by brand and region"

    # Delivery Plan: isolated failure -> deterministic fallback for THAT
    # section only (its own deterministic plan detects the timeline here).
    assert plans[1].section_title == "Delivery Plan"
    assert plans[1].blocks[0].component == COMPONENT_TIMELINE


def test_one_section_ungrounded_block_degrades_neighbors_unaffected():
    responses = {
        "Key Metrics": {"blocks": [{"component": "stat_row", "data": {
            "heading": "Key Metrics",
            "stats": [{"value": "$999M", "label": "Market size"}, {"value": "15%", "label": "Growth"}],  # 999 ungrounded
        }}]},
        "Delivery Plan": {"blocks": [{"component": "timeline", "data": {
            "heading": "Delivery Plan",
            "phases": [
                {"label": "Phase 1", "title": "Research", "period": "Q1 2025"},
                {"label": "Phase 2", "title": "Build", "period": "Q2 2025"},
                {"label": "Phase 3", "title": "Launch", "period": "Q3 2025"},
            ],
        }}]},
        "Competitive Landscape": {"blocks": [{"component": "bullets", "data": {
            "title": "Competitive Landscape",
            "items": [{"text": "Prices vary by brand and region", "level": 0, "bullet": True, "is_subsection_label": False}],
        }}]},
    }
    plans = plan_report_llm(_MULTI_SECTIONS, {}, _fake_llm_by_title(responses))

    # Key Metrics: ungrounded stat_row degrades to bullets (not a crash, not
    # a whole-report fallback).
    assert plans[0].blocks[0].component == COMPONENT_BULLETS

    # Neighbors: still their own clean LLM plan.
    assert plans[1].blocks[0].component == COMPONENT_TIMELINE
    assert plans[2].blocks[0].component == COMPONENT_BULLETS
    assert plans[2].blocks[0].data["items"][0]["text"] == "Prices vary by brand and region"


# ─────────────────────────────────────────────────────────────────────────────
# config flag
# ─────────────────────────────────────────────────────────────────────────────

def test_slide_planner_llm_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("SLIDE_PLANNER_LLM", raising=False)
    import importlib
    import backend.services.slide_planner as sp
    importlib.reload(sp)
    try:
        assert sp.SLIDE_PLANNER_LLM is False
    finally:
        importlib.reload(sp)


def test_slide_planner_llm_flag_true_when_env_set(monkeypatch):
    monkeypatch.setenv("SLIDE_PLANNER_LLM", "true")
    import importlib
    import backend.services.slide_planner as sp
    importlib.reload(sp)
    try:
        assert sp.SLIDE_PLANNER_LLM is True
    finally:
        monkeypatch.delenv("SLIDE_PLANNER_LLM", raising=False)
        importlib.reload(sp)


# ─────────────────────────────────────────────────────────────────────────────
# Slice 4d — hardened grounding (contiguous normalized match + hedge rejection)
# ─────────────────────────────────────────────────────────────────────────────

def test_grounding_accepts_480m_when_480m_is_in_source():
    data = {"heading": "H", "stats": [{"value": "$480M", "label": "Market size"},
                                       {"value": "15%", "label": "Growth"}]}
    source = "Our market reached $480M in size with 15% growth this year."
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is True


def test_grounding_bare_number_not_corrupted_by_a_following_word_starting_with_a_unit_letter():
    # Regression: "12 key players" must NOT be misread as "12k" (treating the
    # "k" off the front of "key" as a thousand-suffix) — a bare "12" in the
    # source must still ground a bare "12" value.
    data = {"heading": "H", "stats": [
        {"value": "$480M", "label": "Market size"},
        {"value": "15%", "label": "Growth"},
        {"value": "12", "label": "Key players", "sublabel": "tracked"},
    ]}
    source = "- $480M market size\n- 15% CAGR growth\n- 12 key players (tracked)\n"
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is True


def test_grounding_rejects_50m_plus_when_source_lacks_50m_or_50_million():
    data = {"heading": "H", "stats": [{"value": "$50M+", "label": "Market size"},
                                       {"value": "15%", "label": "Growth"}]}
    source = "Our market reached $480M in size with 15% growth this year."
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is False


def test_grounding_scattered_digit_inside_another_number_does_not_ground():
    data = {"heading": "H", "stats": [{"value": "$50M", "label": "Target"},
                                       {"value": "15%", "label": "Growth"}]}
    # "50" appears only embedded inside "2050" — must NOT ground "$50M".
    source = "Our forecast targets the year 2050, with 15% growth projected."
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is False


def test_grounding_rejects_hedged_sublabel():
    data = {
        "heading": "H",
        "stats": [
            {"value": "$480M", "label": "Market size", "sublabel": "Estimated total addressable market"},
            {"value": "15%", "label": "Growth"},
        ],
    }
    source = "Our market reached $480M in size with 15% growth this year."
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is False


def test_grounding_rejects_hedge_words_tilde_and_est_abbreviation():
    for hedge_value in ("~$480M", "$480M (est.)", "approximately $480M", "around 15%"):
        data = {"heading": "H", "stats": [{"value": hedge_value, "label": "Market size"},
                                           {"value": "15%", "label": "Growth"}]}
        source = "Our market reached $480M in size with 15% growth this year."
        assert _is_grounded(COMPONENT_STAT_ROW, data, source) is False, hedge_value


def test_grounding_percent_word_form_equivalence():
    data = {"heading": "H", "stats": [{"value": "Top 10%", "label": "Segment"},
                                       {"value": "5", "label": "Count"}]}
    source = "The top 10 percent of users account for most of the 5 purchases."
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is True


def test_grounding_fails_whole_block_when_any_single_stat_is_ungrounded():
    data = {
        "heading": "H",
        "stats": [
            {"value": "$480M", "label": "Market size"},  # grounded
            {"value": "99%", "label": "Fabricated"},       # NOT grounded
        ],
    }
    source = "Our market reached $480M in size this year."
    assert _is_grounded(COMPONENT_STAT_ROW, data, source) is False


# ─────────────────────────────────────────────────────────────────────────────
# Slice 4d — dedicated planner model resolution (Claude by default)
# ─────────────────────────────────────────────────────────────────────────────

def _clear_planner_env(monkeypatch):
    for name in ("SLIDE_PLANNER_PROVIDER", "SLIDE_PLANNER_MODEL", "ANTHROPIC_API_KEY",
                 "MISTRAL_API_KEY", "QWEN_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_resolve_planner_model_override_respected_when_key_present(monkeypatch):
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("SLIDE_PLANNER_PROVIDER", "groq")
    monkeypatch.setenv("SLIDE_PLANNER_MODEL", "my-groq-model")
    monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
    assert _resolve_planner_provider_and_model() == ("groq", "my-groq-model")


def test_resolve_planner_model_override_ignored_when_its_key_is_missing(monkeypatch):
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("SLIDE_PLANNER_PROVIDER", "groq")
    monkeypatch.setenv("SLIDE_PLANNER_MODEL", "my-groq-model")
    # GROQ_API_KEY intentionally not set -> override must not be trusted blindly.
    assert _resolve_planner_provider_and_model() == (None, None)


def test_resolve_planner_defaults_to_anthropic_when_key_present_and_no_override(monkeypatch):
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    provider, model = _resolve_planner_provider_and_model()
    assert provider == "anthropic"
    assert model == slide_planner._DEFAULT_ANTHROPIC_PLANNER_MODEL


def test_resolve_planner_anthropic_default_honors_model_override_without_provider(monkeypatch):
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    monkeypatch.setenv("SLIDE_PLANNER_MODEL", "claude-custom-model")
    assert _resolve_planner_provider_and_model() == ("anthropic", "claude-custom-model")


def test_resolve_planner_falls_back_to_none_when_nothing_configured(monkeypatch):
    _clear_planner_env(monkeypatch)
    assert _resolve_planner_provider_and_model() == (None, None)


def test_invalid_model_string_falls_back_to_deterministic_without_crashing(monkeypatch):
    """Simulates a provider call that errors because of a bad model id (e.g. a
    typo'd SLIDE_PLANNER_MODEL): the exception must propagate out of
    _default_llm_completion (never be swallowed there) so plan_report_llm's
    own try/except is what catches it and degrades to the deterministic
    planner — export must never crash."""
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-mistral-key")  # global resolver path (c)

    import backend.services.ai_service as ai_service
    monkeypatch.setattr(ai_service, "_get_llm_provider", lambda requested=None: ("mistral", "fake-mistral-key"))

    class _FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError(f"model not found: {kwargs.get('model')}")

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *a, **k):
            self.chat = _FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", _FakeClient)

    sections = [("Key Metrics", "- $480M market size\n- 15% CAGR growth\n- 12 key players (tracked)\n")]
    results = plan_report_llm(sections, {}, slide_planner._default_llm_completion)
    assert len(results) == 1
    assert results[0].blocks[0].component == COMPONENT_STAT_ROW  # deterministic fallback, not a crash


# ─────────────────────────────────────────────────────────────────────────────
# Hotfix 4d.1 — tolerate an installed anthropic SDK that rejects a kwarg by
# stripping it and retrying, instead of failing out to the deterministic
# planner. `temperature` itself is no longer sent at all (the installed SDK
# dropped it from messages.create()'s signature entirely, and the API
# rejects it even via extra_body with a 400) — _default_llm_completion sends
# output_config={"effort": "low"} instead, so this test exercises the retry
# loop against THAT kwarg to prove it still protects against a future
# SDK/API change, without resurrecting the removed `temperature` kwarg.
# ─────────────────────────────────────────────────────────────────────────────

def test_anthropic_call_retries_without_unsupported_kwarg_and_succeeds(monkeypatch, caplog):
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")

    import backend.services.ai_service as ai_service
    monkeypatch.setattr(ai_service, "_get_llm_provider", lambda requested=None: ("anthropic", "fake-anthropic-key"))

    calls = []

    class _FakeTextBlock:
        def __init__(self, text):
            self.text = text

    class _FakeResponse:
        content = [_FakeTextBlock('{"sections": []}')]

    class _FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise TypeError("Messages.create() got an unexpected keyword argument 'output_config'")
            return _FakeResponse()

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)

    import logging
    caplog.set_level(logging.WARNING, logger="backend.services.slide_planner")

    text = slide_planner._default_llm_completion("sys", "user")

    assert text == '{"sections": []}'
    assert len(calls) == 2  # first call failed, retried once, succeeded
    assert "temperature" not in calls[0]  # never sent at all any more
    assert "temperature" not in calls[1]
    assert "output_config" in calls[0]  # the original call DID try it first
    assert "output_config" not in calls[1]  # stripped on retry
    assert any(
        "retried anthropic call without unsupported kwarg(s): output_config" in r.message
        for r in caplog.records
    )


def test_anthropic_retry_reraises_non_matching_type_error(monkeypatch):
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")

    import backend.services.ai_service as ai_service
    monkeypatch.setattr(ai_service, "_get_llm_provider", lambda requested=None: ("anthropic", "fake-anthropic-key"))

    class _FakeMessages:
        def create(self, **kwargs):
            raise TypeError("some unrelated type error")

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)

    import pytest
    with pytest.raises(TypeError, match="some unrelated type error"):
        slide_planner._default_llm_completion("sys", "user")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — per-slide headline takeaway + tightened bullets items
# ─────────────────────────────────────────────────────────────────────────────

_VERBOSE_SECTION = [
    (
        "Market Overview",
        "Our market reached $480M in size this year, growing at a 15% compound "
        "annual rate, and the competitive field now tracks 12 key players who "
        "are actively investing in differentiation to defend share.",
    )
]


def test_verbose_section_yields_tightened_bullets_with_a_grounded_takeaway():
    response = {
        "blocks": [
            {
                "component": "bullets",
                "data": {
                    "title": "Market Overview",
                    "takeaway": "The $480M market is growing fast with 12 active players",
                    "items": [
                        {"text": "Market reached $480M this year", "level": 0, "bullet": True, "is_subsection_label": False},
                        {"text": "Growing at a 15% compound annual rate", "level": 0, "bullet": True, "is_subsection_label": False},
                        {"text": "12 key players are investing in differentiation", "level": 0, "bullet": True, "is_subsection_label": False},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(_VERBOSE_SECTION, {}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_BULLETS
    assert block.data["takeaway"] == "The $480M market is growing fast with 12 active players"
    assert len(block.data["items"]) == 3
    for item in block.data["items"]:
        assert len(item["text"].split()) <= 14


def test_takeaway_with_an_ungrounded_number_is_dropped_but_the_bullets_block_survives():
    response = {
        "blocks": [
            {
                "component": "bullets",
                "data": {
                    "title": "Market Overview",
                    "takeaway": "The market is on track to reach $999M next year",  # 999 not in source
                    "items": [
                        {"text": "Market reached $480M this year", "level": 0, "bullet": True, "is_subsection_label": False},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(_VERBOSE_SECTION, {}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_BULLETS
    assert "takeaway" not in block.data
    assert block.data["items"][0]["text"] == "Market reached $480M this year"


def test_takeaway_with_a_hedge_word_is_dropped_but_the_stat_row_block_survives():
    response = {
        "blocks": [
            {
                "component": "stat_row",
                "data": {
                    "heading": "Market Overview",
                    "takeaway": "The market is approximately $480M and growing steadily",  # hedge word
                    "stats": [
                        {"value": "$480M", "label": "Market size"},
                        {"value": "15%", "label": "CAGR"},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(_VERBOSE_SECTION, {}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_STAT_ROW
    assert "takeaway" not in block.data
    assert block.data["stats"][0]["value"] == "$480M"


def test_chart_takeaway_dropped_when_ungrounded_chart_itself_still_substituted():
    sections = [("Competitive Landscape", "Some prose about pricing across brands.\n")]
    real_chart = SlideBlock(
        component=COMPONENT_CHART,
        data={"title": "Pricing Index", "chart_json": {"type": "bar", "data": [{"name": "A", "value": 9}]}},
        source_section="Competitive Landscape",
    )
    response = {
        "blocks": [{"component": "chart", "data": {"takeaway": "Brand A leads at a $999M valuation"}}],
    }
    plans = plan_report_llm(sections, {"Competitive Landscape": [real_chart]}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_CHART
    assert "takeaway" not in block.data
    assert block.data["chart_json"] == real_chart.data["chart_json"]


def test_chart_takeaway_kept_when_grounded():
    sections = [("Competitive Landscape", "Brand A commands a $480M share of pricing across the category.\n")]
    real_chart = SlideBlock(
        component=COMPONENT_CHART,
        data={"title": "Pricing Index", "chart_json": {"type": "bar", "data": [{"name": "A", "value": 9}]}},
        source_section="Competitive Landscape",
    )
    response = {
        "blocks": [{"component": "chart", "data": {"takeaway": "Brand A commands a $480M share"}}],
    }
    plans = plan_report_llm(sections, {"Competitive Landscape": [real_chart]}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert block.component == COMPONENT_CHART
    assert block.data["takeaway"] == "Brand A commands a $480M share"


def test_takeaway_is_valid_rejects_over_cap_hedged_and_ungrounded():
    source = "Our market reached $480M in size with 15% growth this year."
    assert _takeaway_is_valid("The $480M market is growing fast", source) is True
    assert _takeaway_is_valid("approximately $480M and growing", source) is False  # hedge
    assert _takeaway_is_valid("The market will reach $999M next year", source) is False  # ungrounded
    assert _takeaway_is_valid("word " * 25, source) is False  # over the word cap
    assert _takeaway_is_valid("", source) is False
    assert _takeaway_is_valid(None, source) is False


def test_bullets_items_tightening_preserves_every_distinct_point():
    # A tightened bullets block must keep one item per distinct source claim
    # — never merge two separate findings into one item.
    response = {
        "blocks": [
            {
                "component": "bullets",
                "data": {
                    "title": "Market Overview",
                    "items": [
                        {"text": "Market reached $480M this year", "level": 0, "bullet": True, "is_subsection_label": False},
                        {"text": "Growing at a 15% compound annual rate", "level": 0, "bullet": True, "is_subsection_label": False},
                        {"text": "12 key players invest in differentiation", "level": 0, "bullet": True, "is_subsection_label": False},
                    ],
                },
            }
        ]
    }
    plans = plan_report_llm(_VERBOSE_SECTION, {}, _fake_llm(response))
    block = plans[0].blocks[0]
    assert len(block.data["items"]) == 3
