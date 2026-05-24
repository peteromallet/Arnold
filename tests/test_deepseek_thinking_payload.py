"""Verify the request payload the agent builds for DeepSeek thinking mode.

Exercises the real run_agent._build_api_kwargs against both routes that
consume profile `--depth`:
  * DeepSeek-direct (api.deepseek.com): thinking toggle in extra_body +
    top-level reasoning_effort, raw token preserved (so `max` survives).
  * OpenRouter (deepseek/*): reasoning in extra_body, xhigh/max clamped to
    high (OpenRouter's vocab is low/medium/high).

Shapes match https://api-docs.deepseek.com/guides/thinking_mode.
"""
from __future__ import annotations

import megaplan.agent  # noqa: F401  (side-effect: sys.path setup)
from run_agent import AIAgent


def _agent(base_url: str, model: str, reasoning_config) -> AIAgent:
    a = AIAgent.__new__(AIAgent)
    a.api_mode = "chat_completions"
    a._base_url_lower = base_url.lower()
    a.model = model
    a.reasoning_config = reasoning_config
    a.tools = None
    a.response_format = None
    a.max_tokens = None
    a.providers_allowed = a.providers_ignored = a.providers_order = None
    a.provider_sort = None
    a.provider_require_parameters = False
    a.provider_data_collection = None
    # Trivial helpers irrelevant to the reasoning payload.
    a._supports_response_format = lambda: False
    a._api_timeout_seconds = lambda: 60
    return a


def test_deepseek_direct_preserves_max():
    a = _agent("https://api.deepseek.com/v1", "deepseek-v4-pro",
               {"enabled": True, "effort": "max"})
    kw = a._build_api_kwargs([])
    assert kw["reasoning_effort"] == "max"
    assert kw["extra_body"]["thinking"] == {"type": "enabled"}
    assert "reasoning" not in kw["extra_body"]


def test_deepseek_direct_xhigh_passes_through():
    # DeepSeek maps xhigh->max server-side, so we forward it raw.
    a = _agent("https://api.deepseek.com/v1", "deepseek-v4-pro",
               {"enabled": True, "effort": "xhigh"})
    kw = a._build_api_kwargs([])
    assert kw["reasoning_effort"] == "xhigh"


def test_deepseek_direct_disabled():
    a = _agent("https://api.deepseek.com/v1", "deepseek-v4-pro",
               {"enabled": False})
    kw = a._build_api_kwargs([])
    assert kw["extra_body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in kw


def test_openrouter_maps_max_to_xhigh():
    # OpenRouter rejects "max" with a 400 but accepts "xhigh" (verified live
    # 2026-05), so max maps to xhigh — OpenRouter's real ceiling — not high.
    a = _agent("https://openrouter.ai/api/v1", "deepseek/deepseek-v3.2",
               {"enabled": True, "effort": "max"})
    kw = a._build_api_kwargs([])
    assert kw["extra_body"]["reasoning"] == {"enabled": True, "effort": "xhigh"}
    assert "reasoning_effort" not in kw


def test_openrouter_keeps_xhigh():
    # xhigh is in OpenRouter's accepted vocab — must pass through untouched.
    a = _agent("https://openrouter.ai/api/v1", "deepseek/deepseek-v3.2",
               {"enabled": True, "effort": "xhigh"})
    kw = a._build_api_kwargs([])
    assert kw["extra_body"]["reasoning"] == {"enabled": True, "effort": "xhigh"}


def test_openrouter_keeps_low():
    a = _agent("https://openrouter.ai/api/v1", "deepseek/deepseek-v3.2",
               {"enabled": True, "effort": "low"})
    kw = a._build_api_kwargs([])
    assert kw["extra_body"]["reasoning"] == {"enabled": True, "effort": "low"}
