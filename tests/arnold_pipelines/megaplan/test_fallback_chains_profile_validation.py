"""Profile validation tests for TOML array acceptance (T3).

Tests that profile validation accepts TOML arrays for phase routes,
tier_models, and prep_models while preserving scalar behavior, rejecting
empty arrays and non-string members with path-specific errors.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.profiles import (
    _validate_prep_models,
    _validate_profile_map,
    _validate_tier_models,
    resolve_profile,
)
from arnold_pipelines.megaplan.profiles.policy import validate_prep_stage_provider
from arnold_pipelines.megaplan.types import CliError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROFILE_PATH = Path("/test/profiles.toml")


def _parse_profile(raw_toml: str) -> dict:
    """Parse a TOML snippet returning the loaded dict."""
    return tomllib.loads(raw_toml)


# ---------------------------------------------------------------------------
# Phase routes: scalar behavior preserved
# ---------------------------------------------------------------------------

class TestPhaseRoutesScalarPreserved:
    """Scalar phase route validation continues to work exactly as before."""

    def test_scalar_phase_spec_accepted(self) -> None:
        result = _validate_profile_map(
            _PROFILE_PATH, "test-profile",
            {"prep": "claude", "plan": "codex:high", "execute": "codex"},
        )
        assert result == {"prep": "claude", "plan": "codex:high", "execute": "codex"}

    def test_scalar_phase_spec_with_premium_placeholder_accepted(self) -> None:
        result = _validate_profile_map(
            _PROFILE_PATH, "test-profile",
            {"prep": "premium", "execute": "premium"},
        )
        assert result == {"prep": "premium", "execute": "premium"}

    def test_scalar_unknown_agent_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown agent"):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": "unknown_agent:model"},
            )

    def test_scalar_unknown_phase_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown phase"):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"not_a_phase": "codex"},
            )

    def test_scalar_non_string_spec_rejected(self) -> None:
        with pytest.raises(CliError):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"prep": 123},
            )


# ---------------------------------------------------------------------------
# Phase routes: TOML arrays
# ---------------------------------------------------------------------------

class TestPhaseRoutesTomlArrays:
    """Phase route validation accepts TOML arrays with element validation."""

    def test_array_phase_spec_accepted(self) -> None:
        result = _validate_profile_map(
            _PROFILE_PATH, "test-profile",
            {"plan": ["codex:high", "claude:sonnet"]},
        )
        assert result == {"plan": ["codex:high", "claude:sonnet"]}

    def test_single_element_array_preserved_as_list(self) -> None:
        result = _validate_profile_map(
            _PROFILE_PATH, "test-profile",
            {"plan": ["codex"]},
        )
        assert result == {"plan": ["codex"]}

    def test_empty_array_rejected(self) -> None:
        with pytest.raises(CliError, match="must not be an empty list"):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": []},
            )

    def test_non_string_array_member_rejected(self) -> None:
        with pytest.raises(CliError, match="must be a string"):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": ["codex", 123]},
            )

    def test_empty_string_array_member_rejected(self) -> None:
        with pytest.raises(CliError, match="must be a non-empty string"):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": ["codex", ""]},
            )

    def test_unknown_agent_in_array_element_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown agent"):
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": ["codex", "unknown_agent:model"]},
            )

    def test_path_specific_error_for_array_element(self) -> None:
        with pytest.raises(CliError) as exc_info:
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": ["codex", "bad_agent:model"]},
            )
        error_msg = str(exc_info.value)
        assert "plan" in error_msg
        assert "test-profile" in error_msg

    def test_array_element_zero_error_path(self) -> None:
        with pytest.raises(CliError) as exc_info:
            _validate_profile_map(
                _PROFILE_PATH, "test-profile",
                {"plan": ["bad_agent:model", "codex"]},
            )
        error_msg = str(exc_info.value)
        assert "plan[0]" in error_msg or "plan" in error_msg

    def test_mixed_scalar_and_array_in_same_profile(self) -> None:
        result = _validate_profile_map(
            _PROFILE_PATH, "test-profile",
            {
                "prep": "claude",
                "plan": "codex:high",
                "execute": ["codex:gpt-5.4", "claude:sonnet"],
            },
        )
        assert result["prep"] == "claude"
        assert result["plan"] == "codex:high"
        assert result["execute"] == ["codex:gpt-5.4", "claude:sonnet"]


# ---------------------------------------------------------------------------
# tier_models: scalar behavior preserved
# ---------------------------------------------------------------------------

class TestTierModelsScalarPreserved:
    """Scalar tier_model specs continue to work as before."""

    def test_scalar_tier_specs_accepted(self) -> None:
        result = _validate_tier_models(
            _PROFILE_PATH, "test-profile",
            {
                "execute": {1: "codex:gpt-5.4", 2: "hermes:deepseek:deepseek-v4-pro"},
                "critique": {1: "claude:sonnet"},
            },
        )
        assert result == {
            "execute": {1: "codex:gpt-5.4", 2: "hermes:deepseek:deepseek-v4-pro"},
            "critique": {1: "claude:sonnet"},
        }

    def test_scalar_premium_placeholder_accepted_in_tiers(self) -> None:
        result = _validate_tier_models(
            _PROFILE_PATH, "test-profile",
            {"execute": {1: "premium"}},
        )
        assert result == {"execute": {1: "premium"}}

    def test_unknown_agent_in_tier_spec_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown agent"):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {1: "bad_agent:model"}},
            )

    def test_non_string_tier_spec_rejected(self) -> None:
        with pytest.raises(CliError):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {1: 123}},
            )

    def test_invalid_tier_key_rejected(self) -> None:
        with pytest.raises(CliError, match="tier key must be an integer"):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {0: "codex"}},
            )

    def test_unknown_phase_in_tier_models_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown phase"):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"not_a_phase": {1: "codex"}},
            )


# ---------------------------------------------------------------------------
# tier_models: TOML arrays
# ---------------------------------------------------------------------------

class TestTierModelsTomlArrays:
    """tier_models validation accepts TOML arrays for tier specs."""

    def test_array_tier_spec_accepted(self) -> None:
        result = _validate_tier_models(
            _PROFILE_PATH, "test-profile",
            {
                "execute": {
                    1: ["codex:gpt-5.4", "hermes:deepseek:deepseek-v4-pro"],
                    2: "claude:sonnet",
                },
            },
        )
        assert result["execute"][1] == ["codex:gpt-5.4", "hermes:deepseek:deepseek-v4-pro"]
        assert result["execute"][2] == "claude:sonnet"

    def test_empty_array_tier_spec_rejected(self) -> None:
        with pytest.raises(CliError, match="must not be an empty list"):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {1: []}},
            )

    def test_non_string_array_member_in_tier_rejected(self) -> None:
        with pytest.raises(CliError, match="must be a string"):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {1: ["codex", 123]}},
            )

    def test_unknown_agent_in_tier_array_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown agent"):
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {1: ["codex", "bad_agent:model"]}},
            )

    def test_path_specific_error_for_tier_array_element(self) -> None:
        with pytest.raises(CliError) as exc_info:
            _validate_tier_models(
                _PROFILE_PATH, "test-profile",
                {"execute": {1: ["codex", "bad_agent:model"]}},
            )
        error_msg = str(exc_info.value)
        assert "tier_models.execute.1" in error_msg


# ---------------------------------------------------------------------------
# prep_models: scalar behavior preserved
# ---------------------------------------------------------------------------

class TestPrepModelsScalarPreserved:
    """Scalar prep_model specs continue to work as before."""

    def test_scalar_prep_accepted(self) -> None:
        result = _validate_prep_models(
            _PROFILE_PATH, "test-profile",
            {"triage": "hermes:deepseek:deepseek-v4-pro"},
        )
        assert result == {"triage": "hermes:deepseek:deepseek-v4-pro"}

    def test_scalar_prep_with_claude_accepted(self) -> None:
        result = _validate_prep_models(
            _PROFILE_PATH, "test-profile",
            {"triage": "claude:sonnet"},
        )
        assert result == {"triage": "claude:sonnet"}

    def test_non_readonly_agent_in_prep_rejected(self) -> None:
        with pytest.raises(CliError, match="read-only providers"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": "premium"},
            )

    def test_unknown_agent_in_prep_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown agent"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": "bad_agent:model"},
            )

    def test_unknown_prep_stage_rejected_via_provider(self) -> None:
        with pytest.raises(CliError, match="unknown prep stage"):
            validate_prep_stage_provider(
                "claude",
                stage="not_a_stage",
                path=_PROFILE_PATH,
                profile_name="test-profile",
            )

    def test_non_string_scalar_prep_spec_rejected(self) -> None:
        with pytest.raises(CliError, match="expected a non-empty string agent spec or list"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": 123},
            )


# ---------------------------------------------------------------------------
# prep_models: TOML arrays
# ---------------------------------------------------------------------------

class TestPrepModelsTomlArrays:
    """prep_models validation accepts TOML arrays with read-only agent checks."""

    def test_array_prep_spec_accepted(self) -> None:
        result = _validate_prep_models(
            _PROFILE_PATH, "test-profile",
            {"triage": ["hermes:deepseek:deepseek-v4-pro", "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"]},
        )
        assert result == {
            "triage": ["hermes:deepseek:deepseek-v4-pro", "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"],
        }

    def test_array_with_claude_accepted(self) -> None:
        result = _validate_prep_models(
            _PROFILE_PATH, "test-profile",
            {"triage": ["claude:sonnet", "hermes:deepseek:deepseek-v4-pro"]},
        )
        assert result == {"triage": ["claude:sonnet", "hermes:deepseek:deepseek-v4-pro"]}

    def test_empty_array_prep_spec_rejected(self) -> None:
        with pytest.raises(CliError, match="must not be empty"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": []},
            )

    def test_non_string_array_member_in_prep_rejected(self) -> None:
        with pytest.raises(CliError, match="must be a string"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": ["claude:sonnet", 123]},
            )

    def test_empty_string_array_member_in_prep_rejected(self) -> None:
        with pytest.raises(CliError, match="must be a non-empty string"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": ["claude:sonnet", ""]},
            )

    def test_non_readonly_agent_in_prep_array_rejected(self) -> None:
        with pytest.raises(CliError, match="read-only providers"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": ["claude:sonnet", "premium"]},
            )

    def test_unknown_agent_in_prep_array_rejected(self) -> None:
        with pytest.raises(CliError, match="unknown agent"):
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": ["claude:sonnet", "bad_agent:model"]},
            )

    def test_path_specific_error_for_prep_array_element(self) -> None:
        with pytest.raises(CliError) as exc_info:
            _validate_prep_models(
                _PROFILE_PATH, "test-profile",
                {"triage": ["claude:sonnet", "bad_agent:model"]},
            )
        error_msg = str(exc_info.value)
        assert "prep_models.triage" in error_msg

    def test_mixed_scalar_and_array_prep_models(self) -> None:
        result = _validate_prep_models(
            _PROFILE_PATH, "test-profile",
            {
                "triage": ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"],
                "fanout": "hermes:deepseek:deepseek-v4-pro",
            },
        )
        assert result["triage"] == ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"]
        assert result["fanout"] == "hermes:deepseek:deepseek-v4-pro"


# ---------------------------------------------------------------------------
# validate_prep_stage_provider: direct function tests
# ---------------------------------------------------------------------------

class TestValidatePrepStageProvider:
    """Direct tests for validate_prep_stage_provider with arrays."""

    def test_returns_scalar_for_string_input(self) -> None:
        result = validate_prep_stage_provider(
            "hermes:deepseek:deepseek-v4-pro",
            stage="triage",
        )
        assert isinstance(result, str)
        assert result == "hermes:deepseek:deepseek-v4-pro"

    def test_returns_list_for_array_input(self) -> None:
        result = validate_prep_stage_provider(
            ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"],
            stage="triage",
        )
        assert isinstance(result, list)
        assert result == ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"]

    def test_rejects_empty_array(self) -> None:
        with pytest.raises(CliError, match="must not be empty"):
            validate_prep_stage_provider(
                [],
                stage="triage",
            )

    def test_rejects_non_string_elements(self) -> None:
        with pytest.raises(CliError, match="must be a string"):
            validate_prep_stage_provider(
                ["claude:sonnet", 456],
                stage="triage",
            )

    def test_rejects_non_readonly_in_array(self) -> None:
        with pytest.raises(CliError, match="read-only providers"):
            validate_prep_stage_provider(
                ["claude:sonnet", "premium"],
                stage="triage",
            )

    def test_strips_whitespace_from_scalar(self) -> None:
        result = validate_prep_stage_provider(
            "  hermes:deepseek:deepseek-v4-pro  ",
            stage="triage",
        )
        assert result == "hermes:deepseek:deepseek-v4-pro"

    def test_strips_whitespace_from_array_elements(self) -> None:
        result = validate_prep_stage_provider(
            ["  hermes:deepseek:deepseek-v4-pro  ", " claude:sonnet "],
            stage="triage",
        )
        assert result == ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"]


# ---------------------------------------------------------------------------
# End-to-end: TOML parsing with arrays
# ---------------------------------------------------------------------------

class TestTomlProfileParsingWithArrays:
    """End-to-end tests verifying TOML arrays survive profile parsing."""

    def test_phase_route_array_in_toml_profile(self) -> None:
        toml_content = """\
[profiles.test]
prep = "claude"
plan = ["codex:high", "claude:sonnet"]
execute = "codex"
"""
        from arnold_pipelines.megaplan.profiles import _parse_profiles_doc

        profiles, _metadata = _parse_profiles_doc(
            _PROFILE_PATH, toml_content,
        )
        assert "test" in profiles
        assert profiles["test"]["prep"] == "claude"
        assert profiles["test"]["plan"] == ["codex:high", "claude:sonnet"]
        assert profiles["test"]["execute"] == "codex"

    def test_tier_models_array_in_toml_metadata(self) -> None:
        toml_content = """\
[profiles.test]
prep = "claude"
plan = "codex"
execute = "codex"

[profiles.test.tier_models.execute]
1 = ["codex:gpt-5.4", "hermes:deepseek:deepseek-v4-pro"]
2 = "claude:sonnet"

[profiles.test.tier_models.critique]
1 = "claude:sonnet"
"""
        from arnold_pipelines.megaplan.profiles import _parse_profiles_doc

        _profiles, metadata = _parse_profiles_doc(
            _PROFILE_PATH, toml_content,
        )
        assert "test" in metadata
        tier_models = metadata["test"]["tier_models"]
        assert tier_models["execute"][1] == ["codex:gpt-5.4", "hermes:deepseek:deepseek-v4-pro"]
        assert tier_models["execute"][2] == "claude:sonnet"
        assert tier_models["critique"][1] == "claude:sonnet"

    def test_prep_models_array_in_toml_metadata(self) -> None:
        toml_content = """\
[profiles.test]
prep = "claude"
plan = "codex"
execute = "codex"

[profiles.test.prep_models]
triage = ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"]
fanout = "hermes:deepseek:deepseek-v4-pro"
"""
        from arnold_pipelines.megaplan.profiles import _parse_profiles_doc

        _profiles, metadata = _parse_profiles_doc(
            _PROFILE_PATH, toml_content,
        )
        assert "test" in metadata
        prep_models = metadata["test"]["prep_models"]
        assert prep_models["triage"] == ["hermes:deepseek:deepseek-v4-pro", "claude:sonnet"]
        assert prep_models["fanout"] == "hermes:deepseek:deepseek-v4-pro"

    def test_empty_array_rejected_in_toml_phase(self) -> None:
        toml_content = """\
[profiles.test]
prep = "claude"
plan = []
execute = "codex"
"""
        from arnold_pipelines.megaplan.profiles import _parse_profiles_doc

        with pytest.raises(CliError, match="must not be an empty list"):
            _parse_profiles_doc(_PROFILE_PATH, toml_content)

    def test_empty_array_rejected_in_toml_prep_models(self) -> None:
        toml_content = """\
[profiles.test]
prep = "claude"
plan = "codex"
execute = "codex"

[profiles.test.prep_models]
triage = []
"""
        from arnold_pipelines.megaplan.profiles import _parse_profiles_doc

        with pytest.raises(CliError, match="must not be empty"):
            _parse_profiles_doc(_PROFILE_PATH, toml_content)

    def test_non_string_element_rejected_in_toml_phase_array(self) -> None:
        toml_content = """\
[profiles.test]
prep = "claude"
plan = ["codex", 123]
execute = "codex"
"""
        from arnold_pipelines.megaplan.profiles import _parse_profiles_doc

        with pytest.raises(CliError, match="must be a string"):
            _parse_profiles_doc(_PROFILE_PATH, toml_content)
