"""Tests for the deliberation pipeline package skeleton (T5).

Covers:
- Manifest fields (name, description, default_profile, supported_modes, driver,
  entrypoint bare symbol, arnold_api_version, capabilities)
- SKILL.md sibling presence
- build_pipeline bare symbol importable and callable
- abstraction_level_validator (string, dict, and error cases)
- Profile validator integration with stage_value_validators
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipeline.discovery import Manifest, ManifestError, read_manifest
from arnold.pipeline.profiles import (
    ProfileLoadError,
    load_profiles,
)
from arnold.pipelines.deliberation.profile import abstraction_level_validator


# ── Paths ──────────────────────────────────────────────────────────────────

_DELIBERATION_INIT = Path(__file__).parents[4] / "arnold" / "pipelines" / "deliberation" / "__init__.py"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _write_profiles(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── Manifest tests ──────────────────────────────────────────────────────────


class TestDeliberationManifest:
    """The deliberation package manifest is readable and correct."""

    def test_read_manifest_returns_manifest_not_error(self) -> None:
        result = read_manifest(_DELIBERATION_INIT)
        assert isinstance(result, Manifest), f"Expected Manifest, got {type(result).__name__}: {getattr(result, 'reason', '')}"

    def test_manifest_name(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert manifest.name == "deliberation"

    def test_manifest_description(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert isinstance(manifest.description, str)
        assert len(manifest.description) > 0

    def test_manifest_default_profile_is_none(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert manifest.default_profile is None

    def test_manifest_supported_modes(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert manifest.supported_modes == ("default",)

    def test_manifest_driver(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert manifest.driver == "in_process"

    def test_manifest_entrypoint_is_bare_symbol(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        # entrypoint must be a bare symbol name, not "module:symbol"
        assert manifest.entrypoint == "build_pipeline"
        assert ":" not in manifest.entrypoint

    def test_manifest_arnold_api_version(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert manifest.arnold_api_version == "1.0"

    def test_manifest_capabilities(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert "deliberation" in manifest.capabilities
        assert "layered-critique" in manifest.capabilities

    def test_manifest_hash_present(self) -> None:
        manifest = read_manifest(_DELIBERATION_INIT)
        assert isinstance(manifest, Manifest)
        assert manifest.manifest_hash.startswith("sha256:")
        assert len(manifest.manifest_hash) > 7


# ── SKILL.md tests ──────────────────────────────────────────────────────────


class TestSkillMd:
    """The deliberation package has a sibling SKILL.md."""

    def test_skill_md_exists(self) -> None:
        skill_path = _DELIBERATION_INIT.parent / "SKILL.md"
        assert skill_path.is_file(), f"SKILL.md missing at {skill_path}"

    def test_skill_md_not_empty(self) -> None:
        skill_path = _DELIBERATION_INIT.parent / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8").strip()
        assert len(content) > 0, "SKILL.md is empty"

    def test_skill_md_referenced_by_manifest(self) -> None:
        """read_manifest requires SKILL.md sibling — success proves it's present."""
        result = read_manifest(_DELIBERATION_INIT)
        assert isinstance(result, Manifest), (
            f"read_manifest failed: {getattr(result, 'reason', result)}"
        )


# ── build_pipeline symbol tests ─────────────────────────────────────────────


class TestBuildPipelineSymbol:
    """The build_pipeline bare symbol is importable and callable."""

    def test_build_pipeline_importable(self) -> None:
        from arnold.pipelines.deliberation import build_pipeline
        assert callable(build_pipeline)

    def test_build_pipeline_is_callable(self) -> None:
        """Placeholder pipeline raises because no stages are wired yet.
        Downstream tasks (T6-T10) add the full DAG; the callable exists."""
        from arnold.pipelines.deliberation import build_pipeline
        import inspect
        assert callable(build_pipeline)
        sig = inspect.signature(build_pipeline)
        assert "name" in sig.parameters

    def test_build_pipeline_accepts_name_kwarg(self) -> None:
        """The placeholder raises ValueError (no stages), but accepts 'name'."""
        from arnold.pipelines.deliberation import build_pipeline
        with pytest.raises(ValueError, match="no stages"):
            build_pipeline(name="custom_deliberation")


# ── abstraction_level_validator tests ───────────────────────────────────────


class TestAbstractionLevelValidator:
    """The abstraction_level_validator handles strings, dicts, and errors."""

    # ── String inputs ──────────────────────────────────────────────────

    def test_accepts_high_string(self) -> None:
        assert abstraction_level_validator("high") == "high"

    def test_accepts_mid_string(self) -> None:
        assert abstraction_level_validator("mid") == "mid"

    def test_accepts_low_string(self) -> None:
        assert abstraction_level_validator("low") == "low"

    def test_accepts_string_with_whitespace(self) -> None:
        assert abstraction_level_validator("  high  ") == "high"

    def test_rejects_unknown_string(self) -> None:
        with pytest.raises(ValueError, match="unknown abstraction level"):
            abstraction_level_validator("extreme")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="unknown abstraction level"):
            abstraction_level_validator("")

    # ── Dict inputs ────────────────────────────────────────────────────

    def test_accepts_dict_with_abstraction_level_high(self) -> None:
        result = abstraction_level_validator({"abstraction_level": "high"})
        assert result == "high"

    def test_accepts_dict_with_abstraction_level_mid(self) -> None:
        result = abstraction_level_validator({"abstraction_level": "mid"})
        assert result == "mid"

    def test_accepts_dict_with_abstraction_level_low(self) -> None:
        result = abstraction_level_validator({"abstraction_level": "low"})
        assert result == "low"

    def test_dict_with_extra_keys_preserves_them(self) -> None:
        result = abstraction_level_validator({
            "abstraction_level": "high",
            "critics": 5,
            "model": "opus",
        })
        assert result == "high:critics=5,model=opus"

    def test_dict_extra_keys_sorted(self) -> None:
        result = abstraction_level_validator({
            "abstraction_level": "mid",
            "z_key": "last",
            "a_key": "first",
        })
        assert result == "mid:a_key=first,z_key=last"

    # ── Dict error cases ───────────────────────────────────────────────

    def test_dict_without_abstraction_level_key_raises(self) -> None:
        with pytest.raises(ValueError, match="missing valid 'abstraction_level'"):
            abstraction_level_validator({"critics": 3})

    def test_dict_with_invalid_level_raises(self) -> None:
        with pytest.raises(ValueError, match="missing valid 'abstraction_level'"):
            abstraction_level_validator({"abstraction_level": "extreme"})

    def test_dict_with_non_string_level_raises(self) -> None:
        with pytest.raises(ValueError, match="missing valid 'abstraction_level'"):
            abstraction_level_validator({"abstraction_level": 5})

    # ── Other type errors ──────────────────────────────────────────────

    def test_rejects_int(self) -> None:
        with pytest.raises(ValueError, match="expected str or dict"):
            abstraction_level_validator(42)

    def test_rejects_list(self) -> None:
        with pytest.raises(ValueError, match="expected str or dict"):
            abstraction_level_validator(["high"])

    def test_rejects_none(self) -> None:
        with pytest.raises(ValueError, match="expected str or dict"):
            abstraction_level_validator(None)


# ── Profile integration tests ───────────────────────────────────────────────


class TestProfileIntegration:
    """The abstraction_level_validator works as a stage_value_validator."""

    _DELIBERATION_STAGES = frozenset({
        "question_gen",
        "draft_plan",
        "layer_high_critique",
        "layer_high_synth",
        "layer_mid_critique",
        "layer_mid_synth",
        "layer_low_critique",
        "layer_low_synth",
        "final_report",
    })
    _KNOWN_AGENTS = frozenset({"claude", "codex", "hermes"})

    def test_string_abstraction_level_in_profile(self, tmp_path: Path) -> None:
        """A string abstraction level passes through the validator chain."""
        built_in = tmp_path / "profiles.toml"
        _write_profiles(
            built_in,
            """\
[profiles.quick]
layer_high_critique = "claude"
layer_high_synth = "claude"
layer_low_critique = "codex"
final_report = "claude"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=self._DELIBERATION_STAGES,
            known_agents=self._KNOWN_AGENTS,
        )
        assert loaded["quick"]["layer_high_critique"] == "claude"

    def test_dict_abstraction_level_in_profile(self, tmp_path: Path) -> None:
        """A dict abstraction level is short-circuited to the validator."""
        built_in = tmp_path / "profiles.toml"
        _write_profiles(
            built_in,
            """\
[profiles.deep]
question_gen = "claude"
final_report = "codex"

[profiles.deep.layer_high_critique]
abstraction_level = "high"
critics = 10
model = "opus"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=self._DELIBERATION_STAGES,
            known_agents=self._KNOWN_AGENTS,
            stage_value_validators={
                "layer_high_critique": abstraction_level_validator,
            },
        )
        deep = loaded["deep"]
        # The dict was short-circuited and passed to the validator.
        assert "layer_high_critique" in deep
        assert "high" in deep["layer_high_critique"]
        assert "critics=10" in deep["layer_high_critique"]
        assert "model=opus" in deep["layer_high_critique"]
        # String keys still validated normally.
        assert deep["question_gen"] == "claude"
        # Dotted sub-keys should NOT exist — the dict was short-circuited.
        assert "layer_high_critique.abstraction_level" not in deep
        assert "layer_high_critique.critics" not in deep

    def test_unregistered_layer_still_flattened(self, tmp_path: Path) -> None:
        """Without a validator, sub-tables are flattened to dotted keys."""
        built_in = tmp_path / "profiles.toml"
        _write_profiles(
            built_in,
            """\
[profiles.simple]
question_gen = "claude"

[profiles.simple.layer_high_critique]
critic_a = "codex"
critic_b = "hermes:model"
""",
        )
        # No stage_value_validators — dict is flattened to dotted string keys.
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=self._DELIBERATION_STAGES,
            known_agents=self._KNOWN_AGENTS,
        )
        simple = loaded["simple"]
        assert simple["layer_high_critique.critic_a"] == "codex"
        assert simple["layer_high_critique.critic_b"] == "hermes:model"

    def test_validator_rejects_invalid_level_in_profile(self, tmp_path: Path) -> None:
        """The validator rejects invalid dict values in profile context."""
        built_in = tmp_path / "profiles.toml"
        _write_profiles(
            built_in,
            """\
[profiles.bad]
question_gen = "claude"

[profiles.bad.layer_high_critique]
abstraction_level = "extreme"
""",
        )
        with pytest.raises(ProfileLoadError, match="stage value validator rejected dict value"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=self._DELIBERATION_STAGES,
                known_agents=self._KNOWN_AGENTS,
                stage_value_validators={
                    "layer_high_critique": abstraction_level_validator,
                },
            )

    def test_validator_rejects_missing_abstraction_level_in_profile(self, tmp_path: Path) -> None:
        """The validator rejects dicts without abstraction_level."""
        built_in = tmp_path / "profiles.toml"
        _write_profiles(
            built_in,
            """\
[profiles.bad]
question_gen = "claude"

[profiles.bad.layer_high_critique]
critics = 10
""",
        )
        with pytest.raises(ProfileLoadError, match="stage value validator rejected dict value"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=self._DELIBERATION_STAGES,
                known_agents=self._KNOWN_AGENTS,
                stage_value_validators={
                    "layer_high_critique": abstraction_level_validator,
                },
            )
