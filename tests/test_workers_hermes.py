"""Direct Hermes worker tests for megaplan.workers."""

from __future__ import annotations

import sys


def test_is_agent_available_hermes_when_runtime_importable() -> None:
    """_is_agent_available('hermes') is True when megaplan.agent + run_agent + hermes_state import.

    Regression for a path-mismatch bug where the legacy filesystem probe
    pointed at megaplan/workers/agent/run_agent.py — which never existed
    (run_agent.py lives at megaplan/agent/run_agent.py). The probe therefore
    always returned False on every install and the downstream phase wrongly
    raised agent_deps_missing even when the agent runtime was fully present.
    """
    from megaplan.workers import _is_agent_available

    assert _is_agent_available("hermes") is True


def test_is_agent_available_hermes_when_runtime_missing() -> None:
    """_is_agent_available('hermes') is False if the runtime can't be imported.

    Simulates the case where megaplan was installed without the agent runtime
    (e.g. a slim wheel that excludes megaplan/agent/). Patches the import via
    sys.modules to force ImportError on run_agent.
    """
    from megaplan.workers import _is_agent_available

    saved_run_agent = sys.modules.pop("run_agent", None)
    sys.modules["run_agent"] = None  # type: ignore[assignment]  # sentinel: forces ImportError
    try:
        assert _is_agent_available("hermes") is False
    finally:
        if saved_run_agent is not None:
            sys.modules["run_agent"] = saved_run_agent
        else:
            sys.modules.pop("run_agent", None)


def test_hermes_high_token_streaming_matches_fireworks_for_direct_deepseek() -> None:
    from megaplan.workers.hermes import _streaming_run_kwargs

    assert _streaming_run_kwargs("fireworks:accounts/fireworks/models/deepseek-v4-pro", 32768)
    assert _streaming_run_kwargs("deepseek:deepseek-v4-pro", 32768)
    assert not _streaming_run_kwargs("deepseek:deepseek-v4-pro", 4096)

def test_hermes_deepseek_v4_does_not_force_reasoning_disabled() -> None:
    from megaplan.workers.hermes import _reasoning_config_for_model

    assert _reasoning_config_for_model("deepseek-v4-pro") is None
    assert _reasoning_config_for_model("accounts/fireworks/models/deepseek-v4-pro") is None
    assert _reasoning_config_for_model("deepseek/deepseek-r1") == {"enabled": False}

def test_hermes_reasoning_config_maps_profile_depth() -> None:
    from megaplan.workers.hermes import _reasoning_config_for_model

    # Effort maps onto a route-safe reasoning budget.
    assert _reasoning_config_for_model("deepseek-v4-pro", "low") == {
        "enabled": True,
        "effort": "low",
    }
    assert _reasoning_config_for_model("deepseek-v4-pro", "high") == {
        "enabled": True,
        "effort": "high",
    }
    # xhigh/max pass through unchanged — DeepSeek-direct accepts max and maps
    # xhigh→max itself; the OpenRouter-only clamp lives in the request builder.
    assert _reasoning_config_for_model("deepseek-v4-pro", "xhigh") == {
        "enabled": True,
        "effort": "xhigh",
    }
    assert _reasoning_config_for_model("deepseek-v4-pro", "max") == {
        "enabled": True,
        "effort": "max",
    }
    # minimal disables thinking entirely.
    assert _reasoning_config_for_model("deepseek-v4-pro", "minimal") == {"enabled": False}
    # Unknown token leaves the provider default untouched.
    assert _reasoning_config_for_model("deepseek-v4-pro", "bogus") is None
    # Family override wins over requested depth.
    assert _reasoning_config_for_model("deepseek/deepseek-r1", "high") == {"enabled": False}
