"""Unit tests for pipeline-local profile resolution and inheritance."""

from __future__ import annotations

from pathlib import Path

import pytest

from megaplan.profiles import (
    _flatten_profile_keys,
    _load_pipeline_local_profiles,
    _resolve_with_inheritance,
    load_profile_metadata,
    load_profiles,
    resolve_pipeline_profile,
)
from megaplan.types import CliError


# ── Pipeline-local profile loading ────────────────────────────────────


class TestPipelineLocalProfiles:
    """Pipeline-local profiles load correctly."""

    def test_writing_panel_standard_profile(self) -> None:
        profiles = _load_pipeline_local_profiles("writing-panel-strict")
        assert "standard" in profiles
        std = profiles["standard"]
        assert "synth" in std
        assert "revise" in std
        # Dotted keys are flattened
        assert "panel_review.pessimist" in std
        assert "panel_review.optimist" in std
        assert "panel_review.structuralist" in std

    def test_pipeline_local_profiles_only_known_agents(self) -> None:
        """Pipeline-local profiles only validate agent specs, not phase keys."""
        profiles = _load_pipeline_local_profiles("writing-panel-strict")
        std = profiles.get("standard", {})
        # All slots should be valid agent specs
        for slot, spec in std.items():
            # Should not raise
            from megaplan.types import parse_agent_spec
            agent, model = parse_agent_spec(spec)
            assert agent in ("claude", "codex", "hermes", "shannon")

    def test_unknown_pipeline_returns_empty(self) -> None:
        profiles = _load_pipeline_local_profiles("nonexistent-pipeline")
        assert profiles == {}


# ── Key flattening ────────────────────────────────────────────────────


class TestFlattenKeys:
    """Dotted TOML keys are flattened into compound keys."""

    def test_flatten_nested_dict(self) -> None:
        d = {
            "panel_review": {
                "pessimist": "claude:low",
                "optimist": "claude:low",
            },
            "synth": "claude:medium",
        }
        out: dict[str, str] = {}
        _flatten_profile_keys(d, "", out)
        assert out == {
            "panel_review.pessimist": "claude:low",
            "panel_review.optimist": "claude:low",
            "synth": "claude:medium",
        }

    def test_flatten_scalar_only(self) -> None:
        d = {"a": "1", "b": "2"}
        out: dict[str, str] = {}
        _flatten_profile_keys(d, "", out)
        assert out == {"a": "1", "b": "2"}


# ── System profile defaults ───────────────────────────────────────────


class TestSystemProfileDefaults:
    """System profiles have 'default' metadata fields."""

    def test_partnered_has_default_field(self) -> None:
        metadata = load_profile_metadata()
        assert "partnered" in metadata
        assert metadata["partnered"].get("default") == "partnered"

    def test_system_profiles_have_default_field(self) -> None:
        """Every shipped system profile should have a 'default' field."""
        profiles = load_profiles()
        metadata = load_profile_metadata()
        for name in profiles:
            if name in metadata:
                assert "default" in metadata[name], (
                    f"Profile '{name}' missing 'default' metadata field"
                )


# ── 4-layer profile resolution ────────────────────────────────────────


class TestProfileResolution:
    """Profile resolution follows the locked 4-layer order."""

    def test_layer2_pipeline_local(self) -> None:
        """When no CLI flag, pipeline-local profiles are found."""
        profile = resolve_pipeline_profile(
            None,  # no CLI flag
            pipeline_name="writing-panel-strict",
        )
        assert isinstance(profile, dict)
        assert len(profile) > 0

    def test_layer1_cli_flag_with_at_syntax(self) -> None:
        """CLI flag with @pipeline:profile syntax."""
        profile = resolve_pipeline_profile(
            "@writing-panel-strict:standard",
            pipeline_name="writing-panel-strict",
        )
        assert "synth" in profile
        assert "revise" in profile

    def test_layer3_system_profile(self) -> None:
        """System profiles are matched by name."""
        # Use a pipeline that has no pipeline-local profiles
        profile = resolve_pipeline_profile(
            "partnered",  # CLI flag with system profile name
            pipeline_name="planning",
        )
        assert isinstance(profile, dict)

    def test_layer4_fails_loud(self) -> None:
        """When no profile can be resolved, raise CliError."""
        with pytest.raises(CliError, match="Cannot resolve profile"):
            resolve_pipeline_profile(
                None,
                pipeline_name="no-profiles-exist",
                system_profiles={},
                system_metadata={},
                pipeline_local_profiles={},
                pipeline_local_metadata={},
                default_profile=None,
            )

    def test_at_syntax_with_cross_pipeline(self) -> None:
        """@<other-pipeline>:<profile> loads that pipeline's profiles."""
        # writing-panel-strict's standard profile should be loadable
        # via cross-pipeline reference
        profile = resolve_pipeline_profile(
            "@writing-panel-strict:standard",
            pipeline_name="planning",  # different pipeline
        )
        assert isinstance(profile, dict)
        assert "synth" in profile


# ── Inheritance ───────────────────────────────────────────────────────


class TestInheritance:
    """Profile inheritance with cycle detection."""

    def test_extends_system_profile(self) -> None:
        """Pipeline-local profile extending a system profile."""
        local_profiles = _load_pipeline_local_profiles("writing-panel-strict")
        system_profiles = load_profiles()
        system_metadata = load_profile_metadata()

        resolved = _resolve_with_inheritance(
            "standard",
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            pipeline_local_profiles=local_profiles,
            pipeline_local_metadata={},
        )
        assert isinstance(resolved, dict)
        # Child keys override parent
        assert "synth" in resolved

    def test_extends_cycle_detection(self) -> None:
        """Self-referencing extends should be caught."""
        system_profiles = {
            "cycle": {"plan": "claude:low"},
        }
        system_metadata = {
            "cycle": {"extends": "system:cycle"},
        }
        with pytest.raises(CliError, match="Cycle detected"):
            _resolve_with_inheritance(
                "cycle",
                system_profiles=system_profiles,
                system_metadata=system_metadata,
                pipeline_local_profiles={},
                pipeline_local_metadata={},
            )

    def test_child_overrides_parent(self) -> None:
        """Child profile keys take precedence over parent."""
        system_profiles = {
            "parent": {"plan": "claude:low", "critique": "claude:low"},
            "child": {"plan": "codex:high", "extends": "system:parent"},
        }
        system_metadata = {
            "parent": {},
            "child": {"extends": "system:parent"},
        }
        resolved = _resolve_with_inheritance(
            "child",
            system_profiles=system_profiles,
            system_metadata=system_metadata,
            pipeline_local_profiles={},
            pipeline_local_metadata={},
        )
        assert resolved["plan"] == "codex:high"  # child override
        assert resolved["critique"] == "claude:low"  # inherited
