"""Unit tests for pipeline-local profile resolution and inheritance."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.profiles import (
    SYSTEM_DEFAULT_PROFILE,
    _flatten_profile_keys,
    _load_pipeline_local_profiles,
    _resolve_with_inheritance,
    load_profile_metadata,
    load_profiles,
    resolve_pipeline_profile,
)
from arnold.pipelines.megaplan.types import CliError


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
            from arnold.pipelines.megaplan.types import parse_agent_spec
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
    """System default profile is driven by the module constant, not TOML."""

    def test_system_default_profile_constant_is_partnered(self) -> None:
        """The module constant is the single source of truth."""
        assert SYSTEM_DEFAULT_PROFILE == "partnered"

    def test_system_default_profile_is_in_system_profiles(self) -> None:
        """The constant must name a profile that actually exists."""
        profiles = load_profiles()
        assert SYSTEM_DEFAULT_PROFILE in profiles

    def test_layer4_falls_back_to_system_default_profile(self) -> None:
        """When system_metadata has no 'default' key, Layer 4 uses the constant."""
        system_profiles = load_profiles()
        # Strip all 'default' keys from metadata — simulating shipped TOMLs
        # that no longer carry the key, with no user/project override.
        raw_metadata = load_profile_metadata()
        stripped_metadata = {
            name: {k: v for k, v in meta.items() if k != "default"}
            for name, meta in raw_metadata.items()
        }
        profile = resolve_pipeline_profile(
            None,
            pipeline_name="no-pipeline-local-profiles",
            system_profiles=system_profiles,
            system_metadata=stripped_metadata,
            pipeline_local_profiles={},
            pipeline_local_metadata={},
            default_profile=None,
        )
        assert isinstance(profile, dict)
        # Resolved profile must be the SYSTEM_DEFAULT_PROFILE ("partnered").
        # partnered uses symbolic premium specs for author phases and DeepSeek
        # for mechanical/critique phases.
        assert profile.get("plan") == "premium:low", (
            f"expected partnered plan=premium:low, got {profile.get('plan')!r}"
        )
        assert "deepseek" in profile.get("critique", "").lower(), (
            f"expected partnered critique=DeepSeek, got {profile.get('critique')!r}"
        )

    def test_user_project_default_override_wins_over_constant(self) -> None:
        """A metadata 'default' field (e.g., from user/project TOML) overrides
        the SYSTEM_DEFAULT_PROFILE constant at Layer 4."""
        system_profiles = load_profiles()
        raw_metadata = load_profile_metadata()

        # Simulate a user/project override: inject 'default = "solo"'
        # on partnered's metadata (partnered retains adaptive_critique
        # after the TOML cleanup, so it's still present in metadata).
        assert "partnered" in raw_metadata, (
            "partnered must still have metadata after TOML cleanup"
        )
        overridden_metadata = {
            name: dict(meta) for name, meta in raw_metadata.items()
        }
        overridden_metadata["partnered"]["default"] = "solo"

        profile = resolve_pipeline_profile(
            None,
            pipeline_name="no-pipeline-local-profiles",
            system_profiles=system_profiles,
            system_metadata=overridden_metadata,
            pipeline_local_profiles={},
            pipeline_local_metadata={},
            default_profile=None,
        )
        # The override "solo" should resolve, not the constant "partnered".
        # solo uses DeepSeek for author phases (plan, revise) — partnered
        # uses Claude for those.  solo does have feedback=claude:low, so
        # we check the author phases specifically.
        assert isinstance(profile, dict)
        assert "deepseek" in profile.get("plan", "").lower()
        assert "deepseek" in profile.get("revise", "").lower()

    def test_project_default_overrides_user_default(self) -> None:
        """When user and project metadata both set ``default`` on the same
        profile, the project's value wins because ``load_profile_metadata``
        loads project last (built-in → user → project), overwriting any
        user-level ``default`` for the same profile name."""
        system_profiles = load_profiles()
        raw_metadata = load_profile_metadata()

        assert "partnered" in raw_metadata, (
            "partnered must still have metadata after TOML cleanup"
        )
        assert "apex" in system_profiles
        assert "solo" in system_profiles

        # Simulate the post-merge state of load_profile_metadata:
        #   1. Built-in: partnered metadata (vendor_locked, adaptive_critique,
        #      tier_models — no ``default`` key, per T7 cleanup).
        #   2. User profiles.toml sets [partnered] default = "solo"
        #   3. Project .megaplan/profiles.toml sets [partnered] default = "apex"
        # After merge, project overwrites user: partnered.default = "apex".
        merged_metadata = {
            name: dict(meta) for name, meta in raw_metadata.items()
        }
        merged_metadata["partnered"]["default"] = "apex"

        profile = resolve_pipeline_profile(
            None,
            pipeline_name="no-pipeline-local-profiles",
            system_profiles=system_profiles,
            system_metadata=merged_metadata,
            pipeline_local_profiles={},
            pipeline_local_metadata={},
            default_profile=None,
        )
        assert isinstance(profile, dict)
        # Apex profile distinguishes from partnered:
        #   - critique = "codex" (partnered uses DeepSeek)
        #   - execute = "codex" (partnered uses DeepSeek)
        assert profile.get("critique") == "codex", (
            f"expected apex critique=codex (project override), "
            f"got {profile.get('critique')!r}"
        )
        assert profile.get("execute") == "codex", (
            f"expected apex execute=codex (project override), "
            f"got {profile.get('execute')!r}"
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
