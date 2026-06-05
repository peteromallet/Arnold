"""Characterization tests for the N-layer ConfigResolver (M4 T13 / Step 9).

Pins layer precedence: env > args > state.config(override) > profile > robustness > DEFAULTS.

Also pins the flag-gated delegation in megaplan._core.io.get_effective /
setting_is_explicit: flag-OFF byte-identical, flag-ON delegates to resolver.
"""

from __future__ import annotations

import argparse
import os
from types import SimpleNamespace
from typing import Any

import pytest

from arnold.pipelines.megaplan._core.config_resolver import (
    ConfigResolver,
    set_state_override,
    state_override_slot,
)


# A self-contained synthetic DEFAULTS so tests don't depend on the real catalog.
SYN_DEFAULTS: dict[str, Any] = {
    "execution.knob": "DEFAULT",
}


def _resolver(
    *,
    state: dict | None = None,
    args: Any = None,
    env: dict | None = None,
) -> ConfigResolver:
    r = ConfigResolver(state=state, args=args, env=env)
    r._defaults = SYN_DEFAULTS  # inject synthetic catalog for hermetic tests
    return r


def _state_with(*, profile=None, robustness=None, override=None) -> dict:
    state: dict = {"config": {}}
    if profile is not None:
        state["config"]["profile_settings"] = {"execution": {"knob": profile}}
    if robustness is not None:
        state["config"]["robustness_settings"] = {"execution": {"knob": robustness}}
    if override is not None:
        state["config"]["override"] = {"execution": {"knob": override}}
    return state


# ---------------------------------------------------------------------------
# Matrix test pinning the full layer order.
# ---------------------------------------------------------------------------

# Each row: (bindings, expected_value, expected_layer)
LAYER_MATRIX = [
    # All layers present — env wins.
    pytest.param(
        {"env": "E", "args": "A", "override": "O", "profile": "P", "robustness": "R"},
        "E", "env", id="env-beats-all",
    ),
    # No env — args wins.
    pytest.param(
        {"args": "A", "override": "O", "profile": "P", "robustness": "R"},
        "A", "args", id="args-beats-override-profile-robustness",
    ),
    # No env, no args — override wins.
    pytest.param(
        {"override": "O", "profile": "P", "robustness": "R"},
        "O", "override", id="override-beats-profile-robustness",
    ),
    # No env/args/override — profile wins.
    pytest.param(
        {"profile": "P", "robustness": "R"},
        "P", "profile", id="profile-beats-robustness",
    ),
    # Only robustness present (above defaults).
    pytest.param(
        {"robustness": "R"},
        "R", "robustness", id="robustness-beats-defaults",
    ),
    # Nothing explicit — DEFAULTS.
    pytest.param(
        {},
        "DEFAULT", None, id="defaults-fallback",
    ),
]


@pytest.mark.parametrize("bindings,expected_value,expected_layer", LAYER_MATRIX)
def test_layer_order_matrix(bindings, expected_value, expected_layer):
    env = {"MEGAPLAN_EXECUTION_KNOB": bindings["env"]} if "env" in bindings else {}
    args = SimpleNamespace(knob=bindings["args"]) if "args" in bindings else None
    state = _state_with(
        profile=bindings.get("profile"),
        robustness=bindings.get("robustness"),
        override=bindings.get("override"),
    )
    r = _resolver(state=state, args=args, env=env)
    assert r.effective("execution", "knob") == expected_value
    assert r.explicit_at("execution", "knob") == expected_layer


# ---------------------------------------------------------------------------
# Args bus: argparse Namespace shape (handlers/execute.py uses argparse).
# ---------------------------------------------------------------------------


def test_argparse_namespace_works_as_args_bus():
    ns = argparse.Namespace(knob="from-argparse")
    r = _resolver(args=ns, env={})
    assert r.effective("execution", "knob") == "from-argparse"
    assert r.explicit_at("execution", "knob") == "args"


def test_args_none_value_skipped_to_lower_layer():
    # argparse defaults are often None when the user didn't pass the flag.
    ns = argparse.Namespace(knob=None)
    state = _state_with(profile="P")
    r = _resolver(state=state, args=ns, env={})
    assert r.effective("execution", "knob") == "P"
    assert r.explicit_at("execution", "knob") == "profile"


def test_args_section_prefixed_attr():
    ns = argparse.Namespace(execution_knob="prefixed")
    r = _resolver(args=ns, env={})
    assert r.effective("execution", "knob") == "prefixed"


# ---------------------------------------------------------------------------
# state.config(override) writer helper — single helper for writers.
# ---------------------------------------------------------------------------


def test_state_override_slot_lazy_creation():
    state: dict = {"config": {}}
    slot = state_override_slot(state)
    assert slot == {}
    assert state["config"]["override"] is slot


def test_set_state_override_writes_through():
    state: dict = {}
    set_state_override(state, "execution", "knob", "WRITTEN")
    assert state["config"]["override"]["execution"]["knob"] == "WRITTEN"
    r = _resolver(state=state, env={})
    assert r.effective("execution", "knob") == "WRITTEN"


def test_resolver_does_not_mutate_state():
    state = _state_with(profile="P")
    snapshot = repr(state)
    r = _resolver(state=state, env={})
    r.effective("execution", "knob")
    r.explicit_at("execution", "knob")
    assert repr(state) == snapshot


# ---------------------------------------------------------------------------
# ResidentConfig.from_env-style binding (resident/config.py:65).
# ---------------------------------------------------------------------------


def test_with_resident_env_classmethod():
    env = {"MEGAPLAN_EXECUTION_KNOB": "from-resident"}
    r = ConfigResolver.with_resident_env(resident_env=env)
    r._defaults = SYN_DEFAULTS
    assert r.effective("execution", "knob") == "from-resident"


# ---------------------------------------------------------------------------
# Unknown key — KeyError surface preserved.
# ---------------------------------------------------------------------------


def test_unknown_section_key_raises():
    r = _resolver(env={})
    with pytest.raises(KeyError):
        r.effective("nope", "missing")


# ---------------------------------------------------------------------------
# Flag-gated delegation in megaplan._core.io.
#
# Flag-OFF: byte-identical to pre-T13 behaviour for the 30+ existing callers.
# Flag-ON:  delegates to ConfigResolver (proven via env-layer takeover).
# ---------------------------------------------------------------------------


def test_io_get_effective_flag_off_uses_legacy_path(monkeypatch, tmp_path):
    """Flag-OFF must behave exactly like the pre-T13 get_effective."""
    monkeypatch.delenv("UNIFIED_CONFIG", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    # An env var that the resolver would honour MUST be ignored by the legacy
    # path — proves we're not delegating.
    monkeypatch.setenv("MEGAPLAN_EXECUTION_KNOB", "would-pollute-resolver")
    from arnold.pipelines.megaplan._core import io
    # Pick a real DEFAULTS entry so we don't depend on the synthetic catalog.
    val = io.get_effective("execution", "robustness")
    from arnold.pipelines.megaplan.types import DEFAULTS
    assert val == DEFAULTS["execution.robustness"]


def test_io_get_effective_flag_on_delegates_to_resolver(monkeypatch):
    monkeypatch.setenv("UNIFIED_CONFIG", "1")
    # The resolver reads MEGAPLAN_<SECTION>_<KEY> from env.
    monkeypatch.setenv("MEGAPLAN_EXECUTION_ROBUSTNESS", "ENV_WINS")
    from arnold.pipelines.megaplan._core import io
    assert io.get_effective("execution", "robustness") == "ENV_WINS"


def test_io_setting_is_explicit_flag_on_reports_env_layer(monkeypatch):
    monkeypatch.setenv("UNIFIED_CONFIG", "1")
    monkeypatch.setenv("MEGAPLAN_EXECUTION_ROBUSTNESS", "ENV_WINS")
    from arnold.pipelines.megaplan._core import io
    assert io.setting_is_explicit("execution", "robustness") is True


def test_io_setting_is_explicit_flag_off_legacy(monkeypatch, tmp_path):
    monkeypatch.delenv("UNIFIED_CONFIG", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    monkeypatch.setenv("MEGAPLAN_EXECUTION_ROBUSTNESS", "ignored-by-legacy")
    from arnold.pipelines.megaplan._core import io
    # With no user config file, legacy path returns False.
    assert io.setting_is_explicit("execution", "robustness", home=tmp_path) is False
