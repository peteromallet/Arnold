"""Tests for ``arnold.runtime.settings_resolver`` (T7 / SC7).

Coverage
--------
* Precedence per adjacent pair (4 tests — every adjacent layer pair).
* Source attribution (1 test — winning source recorded on EffectiveSetting).
* Five validation failure modes (1 dedicated test each):
    - unknown_stage_key
    - idle_exceeds_wall_timeout
    - negative_timeout
    - isolation_mode_invalid
    - max_workers_nonpositive
* env-override-wins end-to-end (1 test).
"""

from __future__ import annotations

import pytest

from arnold.runtime.settings import SettingSource
from arnold.runtime.settings_resolver import ResolvedSettings, ValidationError, resolve_settings


# ---------------------------------------------------------------------------
# Precedence: adjacent-pair tests (4 pairs × 1 test each)
# ---------------------------------------------------------------------------


class TestAdjacentPairPrecedence:
    """Each higher-priority layer must beat the one below it."""

    def test_plugin_default_beats_arnold_default(self) -> None:
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 10.0},
            plugin_defaults={"wall_timeout_s": 20.0},
        )
        assert result.effective["wall_timeout_s"].value == 20.0

    def test_profile_beats_plugin_default(self) -> None:
        result = resolve_settings(
            plugin_defaults={"wall_timeout_s": 20.0},
            profile={"wall_timeout_s": 30.0},
        )
        assert result.effective["wall_timeout_s"].value == 30.0

    def test_run_override_beats_profile(self) -> None:
        result = resolve_settings(
            profile={"wall_timeout_s": 30.0},
            run_overrides={"wall_timeout_s": 40.0},
        )
        assert result.effective["wall_timeout_s"].value == 40.0

    def test_env_override_beats_run_override(self) -> None:
        result = resolve_settings(
            run_overrides={"wall_timeout_s": 40.0},
            env_overrides={"wall_timeout_s": 50.0},
        )
        assert result.effective["wall_timeout_s"].value == 50.0


# ---------------------------------------------------------------------------
# Source attribution
# ---------------------------------------------------------------------------


class TestSourceAttribution:
    """The SettingSource on each EffectiveSetting must name the winning layer."""

    def test_source_reflects_winning_layer(self) -> None:
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 10.0, "idle_timeout_s": 5.0},
            run_overrides={"wall_timeout_s": 40.0},
            env_overrides={"max_workers": 4},
        )
        # wall_timeout_s overridden by run_override
        assert result.effective["wall_timeout_s"].source == SettingSource.RUN_OVERRIDE
        # idle_timeout_s only in arnold_default
        assert result.effective["idle_timeout_s"].source == SettingSource.ARNOLD_DEFAULT
        # max_workers only in env_override
        assert result.effective["max_workers"].source == SettingSource.ENV_OVERRIDE


# ---------------------------------------------------------------------------
# Validation failure modes — one dedicated test each (5 required)
# ---------------------------------------------------------------------------


class TestValidationFailures:
    def test_unknown_stage_key_returns_error(self) -> None:
        """Rule 1: stage_id not in pipeline_stages."""
        result = resolve_settings(
            run_overrides={"wall_timeout_s": 30.0},
            pipeline_stages=frozenset({"stage_a", "stage_b"}),
            stage_local=[{"stage_id": "nonexistent_stage", "overrides": {}}],
        )
        codes = [e.code for e in result.errors]
        assert "unknown_stage_key" in codes

    def test_idle_exceeds_wall_timeout_returns_error(self) -> None:
        """Rule 2: idle_timeout_s must not exceed wall_timeout_s."""
        result = resolve_settings(
            run_overrides={"wall_timeout_s": 10.0, "idle_timeout_s": 20.0},
        )
        codes = [e.code for e in result.errors]
        assert "idle_exceeds_wall_timeout" in codes

    def test_negative_timeout_returns_error(self) -> None:
        """Rule 3: no timeout value may be negative."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": -1.0},
        )
        codes = [e.code for e in result.errors]
        assert "negative_timeout" in codes

    def test_isolation_mode_invalid_returns_error(self) -> None:
        """Rule 4: isolation_mode must be in ISOLATION_MODES."""
        result = resolve_settings(
            run_overrides={"isolation_mode": "docker_container"},
        )
        codes = [e.code for e in result.errors]
        assert "isolation_mode_invalid" in codes

    def test_max_workers_nonpositive_returns_error(self) -> None:
        """Rule 5: max_workers must be >= 1 when provided."""
        result = resolve_settings(
            run_overrides={"max_workers": 0},
        )
        codes = [e.code for e in result.errors]
        assert "max_workers_nonpositive" in codes


# ---------------------------------------------------------------------------
# Additional: no error on valid inputs; env-override end-to-end
# ---------------------------------------------------------------------------


class TestValidInputsProduceNoErrors:
    def test_valid_isolation_mode_produces_no_error(self) -> None:
        for mode in ("in_process", "subprocess_isolated"):
            result = resolve_settings(run_overrides={"isolation_mode": mode})
            assert all(e.code != "isolation_mode_invalid" for e in result.errors)

    def test_valid_timeouts_produce_no_error(self) -> None:
        result = resolve_settings(
            run_overrides={"wall_timeout_s": 30.0, "idle_timeout_s": 10.0},
        )
        assert not result.errors

    def test_valid_max_workers_produces_no_error(self) -> None:
        result = resolve_settings(run_overrides={"max_workers": 1})
        assert not result.errors


class TestEnvOverrideWinsEndToEnd:
    """env_override must beat all five layers for every key it provides."""

    def test_env_override_wins_over_all_layers(self) -> None:
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 1.0, "max_workers": 1},
            plugin_defaults={"wall_timeout_s": 2.0, "max_workers": 2},
            profile={"wall_timeout_s": 3.0, "max_workers": 3},
            run_overrides={"wall_timeout_s": 4.0, "max_workers": 4},
            env_overrides={"wall_timeout_s": 99.0, "max_workers": 99},
        )
        assert result.effective["wall_timeout_s"].value == 99.0
        assert result.effective["wall_timeout_s"].source == SettingSource.ENV_OVERRIDE
        assert result.effective["max_workers"].value == 99
        assert result.effective["max_workers"].source == SettingSource.ENV_OVERRIDE

    def test_errors_not_raised_but_returned(self) -> None:
        """Callers receive errors in the result, no exception is thrown."""
        result = resolve_settings(
            env_overrides={
                "isolation_mode": "invalid",
                "max_workers": -5,
                "wall_timeout_s": -1.0,
            }
        )
        assert len(result.errors) >= 3
        codes = {e.code for e in result.errors}
        assert "isolation_mode_invalid" in codes
        assert "max_workers_nonpositive" in codes
        assert "negative_timeout" in codes


# ---------------------------------------------------------------------------
# T8: Stage inheritance + child-scope overrides (3 tests)
# ---------------------------------------------------------------------------


class TestStageInheritance:
    """Run-level inheritables flow into stage overrides as base values;
    stage-local overrides win for the named stage."""

    def test_run_level_flows_into_stage_as_base(self) -> None:
        """Stage inherits run-level values when no stage-local override exists."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 10.0, "idle_timeout_s": 5.0},
            stage_local=[
                {"stage_id": "build", "overrides": {}},
            ],
        )
        assert "build" in result.stage_effective
        stage = result.stage_effective["build"]
        assert stage["wall_timeout_s"].value == 10.0
        assert stage["idle_timeout_s"].value == 5.0
        # Inherited values keep their original source
        assert stage["wall_timeout_s"].source == SettingSource.ARNOLD_DEFAULT

    def test_stage_local_override_beats_inherited_base(self) -> None:
        """Stage-local override wins over the run-level inherited value."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 10.0, "max_workers": 4},
            stage_local=[
                {"stage_id": "build", "overrides": {"wall_timeout_s": 60.0}},
            ],
        )
        assert "build" in result.stage_effective
        stage = result.stage_effective["build"]
        # wall_timeout_s is overridden by stage-local
        assert stage["wall_timeout_s"].value == 60.0
        assert stage["wall_timeout_s"].source == SettingSource.RUN_OVERRIDE
        # max_workers flows through from run-level unchanged
        assert stage["max_workers"].value == 4
        assert stage["max_workers"].source == SettingSource.ARNOLD_DEFAULT


class TestChildScopeOverrides:
    """child_scope_overrides propagate into named child scopes."""

    def test_child_scope_override_flows_into_named_scope(self) -> None:
        """Child-scope override wins over run-level for the named child scope."""
        result = resolve_settings(
            arnold_defaults={"wall_timeout_s": 10.0, "max_workers": 4},
            child_scope_overrides={
                "panels": {"wall_timeout_s": 120.0},
                "fanouts": {"max_workers": 8},
            },
        )
        # panels scope
        assert "panels" in result.child_scope_effective
        panels = result.child_scope_effective["panels"]
        assert panels["wall_timeout_s"].value == 120.0
        assert panels["wall_timeout_s"].source == SettingSource.RUN_OVERRIDE
        # inherited max_workers flows through
        assert panels["max_workers"].value == 4

        # fanouts scope
        assert "fanouts" in result.child_scope_effective
        fanouts = result.child_scope_effective["fanouts"]
        assert fanouts["max_workers"].value == 8
        assert fanouts["max_workers"].source == SettingSource.RUN_OVERRIDE
        # inherited wall_timeout_s flows through
        assert fanouts["wall_timeout_s"].value == 10.0
