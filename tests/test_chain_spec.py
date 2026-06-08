"""Tests for megaplan.chain.spec — parsing and validation edge cases.

These tests exercise ``megaplan.chain.spec`` directly to ensure that
old validation behavior remains intact through the extracted spec
module before supervisor chain routing is introduced.

All tests go through ``megaplan.chain.spec`` imports so they verify
parity with the re-exported surface in ``megaplan.chain.__init__``.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from arnold.pipelines.megaplan.chain import spec as chain_spec
from arnold.pipelines.megaplan.chain.spec import (
    APEX_EXTREME_RETRY_CAP,
    BLOCKED_EXECUTE_OUTCOME_STATUSES,
    DEFAULT_MILESTONE_RETRY_CAP,
    DEPTH_BUMP_ORDER,
    PROFILE_BUMP_ORDER,
    ROBUSTNESS_BUMP_ORDER,
    VALID_CLEAN_MILESTONE_PR_POLICIES,
    VALID_FAILURE_ACTIONS,
    VALID_PREREQUISITE_POLICIES,
    VALID_VALIDATION_POLICIES,
    ChainSpec,
    ChainState,
    FailurePolicy,
    MilestoneSpec,
    _bump_one_tier,
    _legacy_state_path_for,
    _optional_bool,
    _optional_choice,
    _runtime_policy_path_for,
    _state_path_for,
    _warn_chain_fallback,
    effective_chain_policy,
    load_chain_state,
    load_runtime_policy,
    load_spec,
    save_chain_state,
    save_runtime_policy,
    validate_paths,
)
from arnold.pipelines.megaplan.types import CliError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_spec(tmp_path: Path, spec_dict: dict, *, name: str = "chain.yaml") -> Path:
    spec_path = tmp_path / name
    spec_path.write_text(yaml.safe_dump(spec_dict), encoding="utf-8")
    return spec_path


def _write_yaml_text(tmp_path: Path, text: str, *, name: str = "chain.yaml") -> Path:
    spec_path = tmp_path / name
    spec_path.write_text(text, encoding="utf-8")
    return spec_path


def _touch_idea(tmp_path: Path, name: str, body: str = "an idea") -> Path:
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir(exist_ok=True)
    path = ideas_dir / name
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Constants and module-level contracts (parity)
# ---------------------------------------------------------------------------

class TestModuleConstants:
    """Constants exported from spec.py are stable and match expected values."""

    def test_valid_failure_actions_is_correct(self) -> None:
        assert VALID_FAILURE_ACTIONS == (
            "stop_chain",
            "skip_milestone",
            "resume_milestone",
            "retry_milestone",
            "bump_profile",
            "bump_robustness",
        )

    def test_profile_bump_order_is_correct(self) -> None:
        assert PROFILE_BUMP_ORDER == ("premium", "apex")

    def test_robustness_bump_order_is_correct(self) -> None:
        assert ROBUSTNESS_BUMP_ORDER == ("thorough", "extreme")

    def test_depth_bump_order_is_correct(self) -> None:
        assert DEPTH_BUMP_ORDER == ("high", "max")

    def test_default_milestone_retry_cap(self) -> None:
        assert DEFAULT_MILESTONE_RETRY_CAP == 2

    def test_apex_extreme_retry_cap(self) -> None:
        assert APEX_EXTREME_RETRY_CAP == 1

    def test_valid_prerequisite_policies(self) -> None:
        assert VALID_PREREQUISITE_POLICIES == ("none", "required")

    def test_valid_validation_policies(self) -> None:
        assert VALID_VALIDATION_POLICIES == ("none", "required")

    def test_valid_clean_milestone_pr_policies(self) -> None:
        assert VALID_CLEAN_MILESTONE_PR_POLICIES == ("auto", "manual")

    def test_blocked_execute_outcome_statuses(self) -> None:
        assert BLOCKED_EXECUTE_OUTCOME_STATUSES == {"blocked", "worker_blocked"}


# ---------------------------------------------------------------------------
# _bump_one_tier edge cases
# ---------------------------------------------------------------------------

class TestBumpOneTier:
    """Edge cases for the autonomy-ladder bump helper."""

    def test_none_bumps_to_second_rung(self) -> None:
        # None = unset baseline below the first explicit tier.
        # Bump moves to the *second* rung (the first explicit escalation tier).
        val, bumped = _bump_one_tier(None, PROFILE_BUMP_ORDER)
        assert val == "apex"  # order[1], not order[0]
        assert bumped is True

    def test_none_with_single_element_tuple_returns_only_element(self) -> None:
        val, bumped = _bump_one_tier(None, ("only",))
        assert val == "only"
        assert bumped is False

    def test_none_with_empty_tuple_raises(self) -> None:
        with pytest.raises(IndexError):
            _bump_one_tier(None, ())

    def test_bump_from_first_to_second(self) -> None:
        val, bumped = _bump_one_tier("premium", PROFILE_BUMP_ORDER)
        assert val == "apex"
        assert bumped is True

    def test_at_top_is_noop(self) -> None:
        val, bumped = _bump_one_tier("apex", PROFILE_BUMP_ORDER)
        assert val == "apex"
        assert bumped is False

    def test_unknown_tier_is_noop(self) -> None:
        val, bumped = _bump_one_tier("custom", PROFILE_BUMP_ORDER)
        assert val == "custom"
        assert bumped is False

    def test_robustness_bump_none_bumps_to_extreme(self) -> None:
        # None → order[1] = "extreme" (the first explicit escalation tier)
        val, bumped = _bump_one_tier(None, ROBUSTNESS_BUMP_ORDER)
        assert val == "extreme"
        assert bumped is True

    def test_robustness_bump_thorough_to_extreme(self) -> None:
        val, bumped = _bump_one_tier("thorough", ROBUSTNESS_BUMP_ORDER)
        assert val == "extreme"
        assert bumped is True

    def test_depth_bump_none_bumps_to_max(self) -> None:
        # None → order[1] = "max" (the first explicit escalation tier)
        val, bumped = _bump_one_tier(None, DEPTH_BUMP_ORDER)
        assert val == "max"
        assert bumped is True

    def test_depth_bump_high_to_max(self) -> None:
        val, bumped = _bump_one_tier("high", DEPTH_BUMP_ORDER)
        assert val == "max"
        assert bumped is True


# ---------------------------------------------------------------------------
# FailurePolicy edge cases
# ---------------------------------------------------------------------------

class TestFailurePolicy:
    """Edge cases for FailurePolicy YAML parsing."""

    def test_none_value_uses_default_abort(self) -> None:
        policy = FailurePolicy.from_yaml(None, "on_failure")
        assert policy.abort == "stop_chain"
        assert policy.retry is None
        assert policy.escalate is None

    def test_none_value_with_custom_default(self) -> None:
        policy = FailurePolicy.from_yaml(None, "on_failure", default_abort="skip_milestone")
        assert policy.abort == "skip_milestone"

    def test_plain_string_abort(self) -> None:
        policy = FailurePolicy.from_yaml("skip_milestone", "on_failure")
        assert policy.abort == "skip_milestone"
        assert policy.retry is None
        assert policy.escalate is None

    def test_plain_string_invalid_action(self) -> None:
        with pytest.raises(CliError) as excinfo:
            FailurePolicy.from_yaml("nonsense", "on_failure")
        assert excinfo.value.code == "invalid_spec"
        assert "on_failure must be one of" in excinfo.value.message

    def test_non_dict_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            FailurePolicy.from_yaml(42, "on_failure")
        assert "must be a string or a mapping" in excinfo.value.message

    def test_structured_with_all_keys(self) -> None:
        policy = FailurePolicy.from_yaml(
            {"retry": "retry_milestone", "escalate": "bump_profile", "abort": "skip_milestone"},
            "on_failure",
        )
        assert policy.retry == "retry_milestone"
        assert policy.escalate == "bump_profile"
        assert policy.abort == "skip_milestone"

    def test_structured_missing_abort_uses_default(self) -> None:
        policy = FailurePolicy.from_yaml(
            {"retry": "retry_milestone", "escalate": "bump_profile"},
            "on_failure",
        )
        assert policy.retry == "retry_milestone"
        assert policy.escalate == "bump_profile"
        assert policy.abort == "stop_chain"

    def test_structured_invalid_retry(self) -> None:
        with pytest.raises(CliError) as excinfo:
            FailurePolicy.from_yaml({"retry": "bad_action"}, "on_failure")
        assert "on_failure.retry" in excinfo.value.message

    def test_structured_invalid_escalate(self) -> None:
        with pytest.raises(CliError) as excinfo:
            FailurePolicy.from_yaml({"escalate": "bad_action"}, "on_failure")
        assert "on_failure.escalate" in excinfo.value.message

    def test_frozen_dataclass(self) -> None:
        policy = FailurePolicy(abort="stop_chain")
        with pytest.raises(Exception):
            policy.abort = "skip_milestone"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MilestoneSpec edge cases
# ---------------------------------------------------------------------------

class TestMilestoneSpecEdgeCases:
    """Edge cases for MilestoneSpec.from_dict."""

    def test_non_dict_milestone_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict(["not", "a", "dict"], 0)
        assert excinfo.value.code == "invalid_spec"
        assert "must be a mapping" in excinfo.value.message

    def test_label_is_required(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"idea": "/tmp/x.txt"}, 0)
        assert excinfo.value.code == "invalid_spec"
        assert "label is required" in excinfo.value.message

    def test_empty_label_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "  ", "idea": "/tmp/x.txt"}, 0)
        assert excinfo.value.code == "invalid_spec"
        assert "label is required" in excinfo.value.message

    def test_non_string_label_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": 42, "idea": "/tmp/x.txt"}, 0)
        assert excinfo.value.code == "invalid_spec"
        assert "label is required" in excinfo.value.message

    def test_idea_is_required(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1"}, 0)
        assert excinfo.value.code == "invalid_spec"
        assert "idea is required" in excinfo.value.message

    def test_empty_idea_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1", "idea": ""}, 0)
        assert excinfo.value.code == "invalid_spec"
        assert "idea is required" in excinfo.value.message

    def test_branch_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt", "branch": 42}, 0)
        assert "branch must be a string" in excinfo.value.message

    def test_profile_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt", "profile": 42}, 0)
        assert "profile must be a string" in excinfo.value.message

    def test_robustness_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt", "robustness": 42}, 0)
        assert "robustness must be a string" in excinfo.value.message

    def test_notes_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt", "notes": 42}, 0)
        assert "notes must be a string" in excinfo.value.message

    def test_bakeoff_non_dict_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt", "bakeoff": "nope"}, 0)
        assert "bakeoff must be a mapping" in excinfo.value.message

    def test_phase_model_string_coerced_to_list(self) -> None:
        ms = MilestoneSpec.from_dict(
            {"label": "m1", "idea": "/tmp/x.txt", "phase_model": "plan=claude:high"}, 0
        )
        assert ms.phase_model == ["plan=claude:high"]

    def test_phase_model_non_string_in_list_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict(
                {"label": "m1", "idea": "/tmp/x.txt", "phase_model": [42]}, 0
            )
        assert "phase_model must be a string or list of strings" in excinfo.value.message

    def test_phase_model_non_list_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict(
                {"label": "m1", "idea": "/tmp/x.txt", "phase_model": 42}, 0
            )
        assert "phase_model must be a string or list of strings" in excinfo.value.message

    def test_depends_on_non_string_items_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict(
                {"label": "m1", "idea": "/tmp/x.txt", "depends_on": [42]}, 0
            )
        assert "depends_on must be a label or list of non-empty labels" in excinfo.value.message

    def test_depends_on_empty_string_item_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict(
                {"label": "m1", "idea": "/tmp/x.txt", "depends_on": ["  "]}, 0
            )
        assert "depends_on must be a label or list of non-empty labels" in excinfo.value.message

    def test_prep_clarify_absent_defaults_true(self) -> None:
        ms = MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt"}, 0)
        assert ms.prep_clarify is True

    def test_prep_clarify_explicit_false(self) -> None:
        ms = MilestoneSpec.from_dict(
            {"label": "m1", "idea": "/tmp/x.txt", "prep_clarify": False}, 0
        )
        assert ms.prep_clarify is False

    def test_prep_clarify_non_bool_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            MilestoneSpec.from_dict(
                {"label": "m1", "idea": "/tmp/x.txt", "prep_clarify": "yes"}, 0
            )
        assert "prep_clarify must be a boolean" in excinfo.value.message

    def test_all_defaults_are_correct(self) -> None:
        ms = MilestoneSpec.from_dict({"label": "m1", "idea": "/tmp/x.txt"}, 0)
        assert ms.branch is None
        assert ms.profile is None
        assert ms.robustness is None
        assert ms.vendor is None
        assert ms.depth is None
        assert ms.critic is None
        assert ms.deepseek_provider is None
        assert ms.with_prep is False
        assert ms.with_feedback is False
        assert ms.prep_clarify is True
        assert ms.prep_direction is None
        assert ms.phase_model == []
        assert ms.bakeoff is None
        assert ms.notes is None
        assert ms.depends_on == []


# ---------------------------------------------------------------------------
# ChainSpec.from_dict edge cases
# ---------------------------------------------------------------------------

class TestChainSpecEdgeCases:
    """Edge cases for ChainSpec.from_dict validation."""

    def test_non_dict_raw_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict(["not", "a", "dict"])
        assert excinfo.value.code == "invalid_spec"
        assert "must be a YAML mapping" in excinfo.value.message

    def test_milestones_is_required_key(self) -> None:
        spec = ChainSpec.from_dict({})
        assert spec.milestones == []

    def test_non_list_milestones_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": "not-a-list"})
        assert "`milestones` must be a list" in excinfo.value.message

    def test_seed_non_dict_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "seed": "not-a-dict"})
        assert "`seed` must be a mapping" in excinfo.value.message

    def test_seed_plan_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "seed": {"plan": 42}})
        assert "`seed.plan` must be a string" in excinfo.value.message

    def test_seed_plan_empty_string_becomes_none(self) -> None:
        spec = ChainSpec.from_dict({"milestones": [], "seed": {"plan": ""}})
        assert spec.seed_plan is None

    def test_seed_plan_whitespace_becomes_none(self) -> None:
        spec = ChainSpec.from_dict({"milestones": [], "seed": {"plan": "   "}})
        assert spec.seed_plan is None

    def test_driver_non_dict_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "driver": "not-a-dict"})
        assert "`driver` must be a mapping" in excinfo.value.message

    def test_driver_on_escalate_invalid(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict(
                {"milestones": [], "driver": {"on_escalate": "nonsense"}}
            )
        assert "driver.on_escalate must be one of" in excinfo.value.message

    def test_driver_robustness_non_string_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict(
                {"milestones": [], "driver": {"robustness": 42}}
            )
        assert "driver.robustness must be a string" in excinfo.value.message

    def test_driver_require_clean_base_non_boolean_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict(
                {"milestones": [], "driver": {"require_clean_base": "yes"}}
            )
        assert "driver.require_clean_base must be a boolean" in excinfo.value.message

    def test_driver_requires_clean_base_true(self) -> None:
        spec = ChainSpec.from_dict(
            {"milestones": [], "driver": {"require_clean_base": True}}
        )
        assert spec.require_clean_base is True

    def test_duplicate_milestone_labels_allowed(self) -> None:
        """Duplicate labels are allowed at the spec level (later validation may catch)."""
        spec = ChainSpec.from_dict({
            "milestones": [
                {"label": "m1", "idea": "/tmp/a.txt"},
                {"label": "m1", "idea": "/tmp/b.txt"},
            ]
        })
        assert len(spec.milestones) == 2
        assert spec.milestones[0].label == "m1"
        assert spec.milestones[1].label == "m1"


# ---------------------------------------------------------------------------
# ChainState edge cases
# ---------------------------------------------------------------------------

class TestChainStateEdgeCases:
    """Edge cases for ChainState serialization / deserialization."""

    def test_default_state(self) -> None:
        state = ChainState()
        assert state.current_milestone_index == -1
        assert state.current_plan_name is None
        assert state.metadata == {}
        assert state.schema_version == 0

    def test_round_trip_to_dict_and_back(self) -> None:
        original = ChainState(
            current_milestone_index=2,
            current_plan_name="my-plan",
            last_state="done",
            pr_number=42,
            pr_state="OPEN",
            completed=[{"label": "m1", "status": "done"}],
            retry_counts={"m1": 1},
            ladder_stage={"m1": "escalate"},
            profile_bumps={"m1": "apex"},
            robustness_bumps={"m1": "extreme"},
            depth_bumps={"m1": "max"},
            metadata={"engine_isolation": {"pinned": True}},
        )
        d = original.to_dict()
        restored = ChainState.from_dict(d)
        assert restored.current_milestone_index == 2
        assert restored.current_plan_name == "my-plan"
        assert restored.last_state == "done"
        assert restored.pr_number == 42
        assert restored.pr_state == "OPEN"
        assert restored.completed == [{"label": "m1", "status": "done"}]
        assert restored.retry_counts == {"m1": 1}
        assert restored.ladder_stage == {"m1": "escalate"}
        assert restored.profile_bumps == {"m1": "apex"}
        assert restored.robustness_bumps == {"m1": "extreme"}
        assert restored.depth_bumps == {"m1": "max"}
        assert restored.metadata == {"engine_isolation": {"pinned": True}}

    def test_from_empty_dict(self) -> None:
        state = ChainState.from_dict({})
        assert state.current_milestone_index == -1

    def test_extra_repos_coercion_non_list(self) -> None:
        state = ChainState.from_dict({"extra_repos": "not-a-list"})
        assert state.extra_repos == []

    def test_extra_repos_coercion_mixed_items(self) -> None:
        state = ChainState.from_dict({"extra_repos": ["ok", 42, ""]})
        assert state.extra_repos == []

    def test_retry_counts_int_coercion(self) -> None:
        state = ChainState.from_dict({"retry_counts": {"m1": "2", "m2": "not-int"}})
        assert state.retry_counts == {"m1": 2}

    def test_ladder_stage_non_dict_coerced(self) -> None:
        state = ChainState.from_dict({"ladder_stage": "not-a-dict"})
        assert state.ladder_stage == {}

    def test_ladder_stage_non_str_values_ignored(self) -> None:
        state = ChainState.from_dict({"ladder_stage": {"m1": 42}})
        assert state.ladder_stage == {}


# ---------------------------------------------------------------------------
# load_spec edge cases
# ---------------------------------------------------------------------------

class TestLoadSpecEdgeCases:
    """Edge cases for load_spec (file-level parsing)."""

    def test_missing_spec_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(CliError) as excinfo:
            load_spec(missing)
        assert excinfo.value.code == "invalid_spec"
        assert "not found" in excinfo.value.message

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        spec_path = _write_yaml_text(tmp_path, ":: bad yaml : [")
        with pytest.raises(CliError) as excinfo:
            load_spec(spec_path)
        assert excinfo.value.code == "invalid_spec"
        assert "YAML parse error" in excinfo.value.message

    def test_empty_yaml_file(self, tmp_path: Path) -> None:
        spec_path = _write_yaml_text(tmp_path, "")
        spec = load_spec(spec_path)
        assert spec.milestones == []
        assert spec.base_branch == "main"

    def test_comment_only_yaml_file(self, tmp_path: Path) -> None:
        spec_path = _write_yaml_text(tmp_path, "# just a comment\n")
        spec = load_spec(spec_path)
        assert spec.milestones == []

    def test_minimal_valid_spec(self, tmp_path: Path) -> None:
        spec_path = _write_spec(
            tmp_path,
            {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
        )
        spec = load_spec(spec_path)
        assert len(spec.milestones) == 1
        assert spec.milestones[0].label == "m1"

    def test_spec_without_milestones_key(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"base_branch": "develop"})
        spec = load_spec(spec_path)
        assert spec.milestones == []
        assert spec.base_branch == "develop"


# ---------------------------------------------------------------------------
# load_chain_state edge cases
# ---------------------------------------------------------------------------

class TestLoadChainStateEdgeCases:
    """Edge cases for load_chain_state."""

    def test_no_state_file_returns_default(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        state = load_chain_state(spec_path)
        assert state.current_milestone_index == -1

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        # Manually write the state file with bad JSON
        state_dir = _state_path_for(spec_path).parent
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = _state_path_for(spec_path)
        state_file.write_text("not json", encoding="utf-8")
        with pytest.raises(CliError) as excinfo:
            load_chain_state(spec_path)
        assert excinfo.value.code == "invalid_chain_state"
        assert "invalid JSON" in excinfo.value.message

    def test_non_object_state_file_raises(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        state_dir = _state_path_for(spec_path).parent
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = _state_path_for(spec_path)
        state_file.write_text('["not", "an", "object"]', encoding="utf-8")
        with pytest.raises(CliError) as excinfo:
            load_chain_state(spec_path)
        assert excinfo.value.code == "invalid_chain_state"
        assert "must be an object" in excinfo.value.message

    def test_valid_round_trip(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        original = ChainState(current_milestone_index=5, current_plan_name="plan-x")
        save_chain_state(spec_path, original)
        loaded = load_chain_state(spec_path)
        assert loaded.current_milestone_index == 5
        assert loaded.current_plan_name == "plan-x"

    def test_legacy_state_path_fallback(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        legacy = _legacy_state_path_for(spec_path)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps({"current_milestone_index": 3, "current_plan_name": "legacy-plan"}),
            encoding="utf-8",
        )
        state = load_chain_state(spec_path)
        assert state.current_milestone_index == 3
        assert state.current_plan_name == "legacy-plan"


# ---------------------------------------------------------------------------
# Runtime policy edge cases
# ---------------------------------------------------------------------------

class TestRuntimePolicy:
    """Edge cases for runtime policy load/save."""

    def test_load_runtime_policy_no_file(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        policy = load_runtime_policy(spec_path)
        assert policy == {}

    def test_load_runtime_policy_corrupt_json(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        policy_path = _runtime_policy_path_for(spec_path)
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text("bad json {{{", encoding="utf-8")
        with patch.object(chain_spec, "_warn_chain_fallback") as mock_warn:
            policy = load_runtime_policy(spec_path)
        assert policy == {}
        mock_warn.assert_called_once()
        # _warn_chain_fallback uses keyword-only args after the token;
        # reason="corrupt_json" is in kwargs.
        assert mock_warn.call_args[1]["reason"] == "corrupt_json"

    def test_load_runtime_policy_non_dict(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        policy_path = _runtime_policy_path_for(spec_path)
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text('["list"]', encoding="utf-8")
        policy = load_runtime_policy(spec_path)
        assert policy == {}

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        spec_path = _write_spec(tmp_path, {"milestones": []})
        overrides = {"prerequisite_policy": "required", "validation_policy": "required"}
        save_runtime_policy(spec_path, overrides)
        loaded = load_runtime_policy(spec_path)
        assert loaded == overrides


# ---------------------------------------------------------------------------
# effective_chain_policy edge cases
# ---------------------------------------------------------------------------

class TestEffectiveChainPolicy:
    """Edge cases for effective_chain_policy."""

    def test_no_overrides_returns_spec_values(self) -> None:
        spec = ChainSpec.from_dict({
            "milestones": [],
            "prerequisite_policy": "required",
            "validation_policy": "required",
            "review_policy": {"clean_milestone_pr": "manual"},
        })
        policy = effective_chain_policy(spec)
        assert policy["prerequisite_policy"] == "required"
        assert policy["validation_policy"] == "required"
        assert policy["review_policy"] == {"clean_milestone_pr": "manual"}
        assert policy["source"] == "chain_yaml"

    def test_overrides_apply(self) -> None:
        spec = ChainSpec.from_dict({"milestones": []})
        overrides = {"prerequisite_policy": "required"}
        policy = effective_chain_policy(spec, overrides)
        assert policy["prerequisite_policy"] == "required"
        assert policy["source"] == "runtime_override"

    def test_overrides_partial(self) -> None:
        spec = ChainSpec.from_dict({
            "milestones": [],
            "validation_policy": "required",
        })
        overrides = {"prerequisite_policy": "required"}
        policy = effective_chain_policy(spec, overrides)
        assert policy["prerequisite_policy"] == "required"
        assert policy["validation_policy"] == "required"
        assert policy["source"] == "runtime_override"

    def test_overrides_review_policy_merge(self) -> None:
        spec = ChainSpec.from_dict({
            "milestones": [],
            "review_policy": {"clean_milestone_pr": "manual"},
        })
        overrides = {"review_policy": {"clean_milestone_pr": "auto"}}
        policy = effective_chain_policy(spec, overrides)
        assert policy["review_policy"] == {"clean_milestone_pr": "auto"}

    def test_overrides_empty_dict(self) -> None:
        spec = ChainSpec.from_dict({"milestones": []})
        policy = effective_chain_policy(spec, {})
        assert policy["source"] == "chain_yaml"


# ---------------------------------------------------------------------------
# validate_paths edge cases
# ---------------------------------------------------------------------------

class TestValidatePaths:
    """Edge cases for validate_paths."""

    def test_valid_paths_does_not_raise(self, tmp_path: Path) -> None:
        idea = _touch_idea(tmp_path, "m1.txt")
        spec = ChainSpec.from_dict({
            "milestones": [{"label": "m1", "idea": str(idea)}]
        })
        # Should not raise
        validate_paths(spec, tmp_path)

    def test_missing_idea_raises(self, tmp_path: Path) -> None:
        spec = ChainSpec.from_dict({
            "milestones": [{"label": "m1", "idea": str(tmp_path / "missing.txt")}]
        })
        with pytest.raises(CliError) as excinfo:
            validate_paths(spec, tmp_path)
        assert excinfo.value.code == "missing_idea_file"
        assert "idea file not found" in excinfo.value.message

    def test_missing_seed_plan_raises(self, tmp_path: Path) -> None:
        idea = _touch_idea(tmp_path, "m1.txt")
        spec = ChainSpec.from_dict({
            "milestones": [{"label": "m1", "idea": str(idea)}],
            "seed": {"plan": "no-such-plan"},
        })
        (tmp_path / ".megaplan" / "plans").mkdir(parents=True, exist_ok=True)
        with pytest.raises(CliError) as excinfo:
            validate_paths(spec, tmp_path)
        assert excinfo.value.code == "missing_seed_plan"
        assert "seed plan" in excinfo.value.message

    def test_no_seed_no_error(self, tmp_path: Path) -> None:
        idea = _touch_idea(tmp_path, "m1.txt")
        spec = ChainSpec.from_dict({
            "milestones": [{"label": "m1", "idea": str(idea)}]
        })
        validate_paths(spec, tmp_path)  # Should not raise


# ---------------------------------------------------------------------------
# _state_path_for determinism
# ---------------------------------------------------------------------------

class TestStatePathFor:
    """Tests for _state_path_for path generation."""

    def test_same_spec_produces_same_path(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "chain.yaml"
        spec_path.write_text("milestones: []", encoding="utf-8")
        p1 = _state_path_for(spec_path)
        p2 = _state_path_for(spec_path)
        assert p1 == p2

    def test_different_spec_names_produce_different_paths(self, tmp_path: Path) -> None:
        spec1 = tmp_path / "chain-a.yaml"
        spec2 = tmp_path / "chain-b.yaml"
        spec1.write_text("milestones: []", encoding="utf-8")
        spec2.write_text("milestones: []", encoding="utf-8")
        assert _state_path_for(spec1) != _state_path_for(spec2)

    def test_path_contains_megaplan_plans_chains(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "chain.yaml"
        spec_path.write_text("milestones: []", encoding="utf-8")
        state_path = _state_path_for(spec_path)
        parts = state_path.parts
        assert ".megaplan" in parts
        assert "plans" in parts
        assert ".chains" in parts or state_path.parent.name == ".chains"


# ---------------------------------------------------------------------------
# Export surface parity — verify chain.__init__ and chain.spec agree
# ---------------------------------------------------------------------------

class TestExportSurfaceParity:
    """Verify that symbols exported from chain.__init__ match chain.spec."""

    def test_chain_init_re_exports_store_via_chain_spec(self) -> None:
        """load_spec, load_chain_state, etc. imported from megaplan.chain delegate
        to chain_spec."""
        from arnold.pipelines.megaplan.chain import load_spec as top_load_spec
        from arnold.pipelines.megaplan.chain import load_chain_state as top_load_chain_state
        from arnold.pipelines.megaplan.chain import save_chain_state as top_save_chain_state
        from arnold.pipelines.megaplan.chain import ChainSpec as top_ChainSpec
        from arnold.pipelines.megaplan.chain import ChainState as top_ChainState
        from arnold.pipelines.megaplan.chain import FailurePolicy as top_FailurePolicy
        from arnold.pipelines.megaplan.chain import MilestoneSpec as top_MilestoneSpec

        # All should be the exact same object (module-level assignment)
        assert top_load_spec is chain_spec.load_spec
        assert top_load_chain_state is chain_spec.load_chain_state
        assert top_save_chain_state is chain_spec.save_chain_state
        assert top_ChainSpec is chain_spec.ChainSpec
        assert top_ChainState is chain_spec.ChainState
        assert top_FailurePolicy is chain_spec.FailurePolicy
        assert top_MilestoneSpec is chain_spec.MilestoneSpec

    def test_load_spec_from_chain_init_same_result_as_from_spec(self, tmp_path: Path) -> None:
        """Calling load_spec through chain.__init__ or chain.spec yields the same result."""
        from arnold.pipelines.megaplan.chain import load_spec as top_load_spec

        idea = _touch_idea(tmp_path, "m1.txt")
        spec_path = _write_spec(
            tmp_path,
            {
                "seed": {"plan": "test-plan"},
                "milestones": [
                    {"label": "m1", "idea": str(idea), "prep_direction": "steer"},
                ],
                "on_failure": {"abort": "skip_milestone"},
            },
        )
        spec_via_init = top_load_spec(spec_path)
        spec_via_mod = chain_spec.load_spec(spec_path)
        assert spec_via_init.seed_plan == spec_via_mod.seed_plan
        assert spec_via_init.base_branch == spec_via_mod.base_branch
        assert len(spec_via_init.milestones) == len(spec_via_mod.milestones)
        assert spec_via_init.milestones[0].label == spec_via_mod.milestones[0].label
        assert spec_via_init.milestones[0].prep_direction == spec_via_mod.milestones[0].prep_direction
        assert spec_via_init.on_failure == spec_via_mod.on_failure


# ---------------------------------------------------------------------------
# Edge case: validates warning helper is callable
# ---------------------------------------------------------------------------

class TestWarnChainFallback:
    """Tests for the _warn_chain_fallback warning helper."""

    def test_warn_does_not_raise(self) -> None:
        # _warn_chain_fallback should log a warning, not raise
        _warn_chain_fallback("TEST_TOKEN", reason="test_reason")

    def test_warn_with_path(self) -> None:
        _warn_chain_fallback("TEST_TOKEN", reason="test_reason", path=Path("/tmp/test"))

    def test_warn_with_context(self) -> None:
        _warn_chain_fallback("TEST_TOKEN", reason="test_reason", context={"k": "v"})


# ---------------------------------------------------------------------------
# _optional_choice and _optional_bool edge cases
# ---------------------------------------------------------------------------

class TestOptionalHelpers:
    """Edge cases for _optional_choice and _optional_bool helpers."""

    def test_optional_choice_none_value(self) -> None:
        assert _optional_choice({}, "vendor", ("a", "b"), index=0) is None

    def test_optional_choice_invalid_type(self) -> None:
        with pytest.raises(CliError) as excinfo:
            _optional_choice({"vendor": 42}, "vendor", ("a", "b"), index=0)
        assert "must be a string" in excinfo.value.message

    def test_optional_choice_invalid_choice(self) -> None:
        with pytest.raises(CliError) as excinfo:
            _optional_choice({"vendor": "c"}, "vendor", ("a", "b"), index=0)
        assert "must be one of" in excinfo.value.message

    def test_optional_choice_valid(self) -> None:
        assert _optional_choice({"vendor": "a"}, "vendor", ("a", "b"), index=0) == "a"

    def test_optional_bool_absent_defaults_false(self) -> None:
        assert _optional_bool({}, "with_prep", index=0) is False

    def test_optional_bool_false(self) -> None:
        assert _optional_bool({"with_prep": False}, "with_prep", index=0) is False

    def test_optional_bool_true(self) -> None:
        assert _optional_bool({"with_prep": True}, "with_prep", index=0) is True

    def test_optional_bool_non_bool_rejected(self) -> None:
        with pytest.raises(CliError) as excinfo:
            _optional_bool({"with_prep": "true"}, "with_prep", index=0)
        assert "must be a boolean" in excinfo.value.message


# ---------------------------------------------------------------------------
# Full end-to-end parity: old error messages preserved
# ---------------------------------------------------------------------------

class TestValidationErrorParity:
    """Ensure old validation error codes and messages are preserved through spec.py."""

    def test_missing_label_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [{"idea": "/tmp/x.txt"}]})
        assert excinfo.value.code == "invalid_spec"
        assert "label is required" in excinfo.value.message

    def test_invalid_base_branch_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "base_branch": ""})
        assert excinfo.value.code == "invalid_spec"
        assert "`base_branch` must be" in excinfo.value.message

    def test_depends_on_after_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({
                "milestones": [
                    {"label": "b", "idea": "/tmp/b.txt", "depends_on": ["a"]},
                    {"label": "a", "idea": "/tmp/a.txt"},
                ]
            })
        assert excinfo.value.code == "invalid_spec"
        assert "listed before" in excinfo.value.message

    def test_depends_on_self_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({
                "milestones": [{"label": "a", "idea": "/tmp/a.txt", "depends_on": ["a"]}]
            })
        assert excinfo.value.code == "invalid_spec"
        assert "itself" in excinfo.value.message

    def test_depends_on_unknown_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({
                "milestones": [{"label": "a", "idea": "/tmp/a.txt", "depends_on": ["ghost"]}]
            })
        assert excinfo.value.code == "invalid_spec"
        assert "unknown milestone" in excinfo.value.message

    def test_invalid_merge_policy_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "merge_policy": "later"})
        assert excinfo.value.code == "invalid_spec"
        assert "merge_policy" in excinfo.value.message

    def test_invalid_prerequisite_policy_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "prerequisite_policy": "sometimes"})
        assert excinfo.value.code == "invalid_spec"
        assert "prerequisite_policy" in excinfo.value.message

    def test_invalid_validation_policy_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "validation_policy": "maybe"})
        assert excinfo.value.code == "invalid_spec"
        assert "validation_policy" in excinfo.value.message

    def test_invalid_clean_milestone_pr_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "review_policy": {"clean_milestone_pr": "never"}})
        assert excinfo.value.code == "invalid_spec"
        assert "clean_milestone_pr" in excinfo.value.message

    def test_non_mapping_review_policy_via_spec_direct(self) -> None:
        with pytest.raises(CliError) as excinfo:
            ChainSpec.from_dict({"milestones": [], "review_policy": "auto"})
        assert excinfo.value.code == "invalid_spec"
        assert "review_policy" in excinfo.value.message
