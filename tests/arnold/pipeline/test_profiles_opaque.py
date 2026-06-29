"""Tests for opaque (dict-value) profile validation via stage_value_validators.

Covers the T3 extension: threading ``stage_value_validators`` through the
profile-loading chain and the ``passthrough_keys`` short-circuit in
``_flatten_stage_entries``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.profiles import (
    ProfileLoadError,
    load_profiles,
    load_profile_metadata,
    load_profile_sources,
)


def _write_profiles(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


_STAGE_KEYS = frozenset({"synth", "panel_review", "revise"})
_AGENTS = frozenset({"claude", "codex", "hermes"})


# ---------------------------------------------------------------------------
# Helpers: callable validators
# ---------------------------------------------------------------------------


def _valid_panel_review(value: object) -> str:
    """Accept a dict of reviewer_id → agent_spec and return a canonical string."""
    if not isinstance(value, dict):
        raise ValueError(f"expected dict, got {type(value).__name__}")
    parts = []
    for reviewer, spec in sorted(value.items()):
        parts.append(f"{reviewer}={spec}")
    return ";".join(parts)


def _reject_everything(value: object) -> str:
    raise ValueError("always rejected")


# ---------------------------------------------------------------------------
# No-validator regression: existing behaviour unchanged
# ---------------------------------------------------------------------------


class TestNoValidatorRegression:
    """When ``stage_value_validators`` is ``None``, behaviour is unchanged."""

    def test_string_values_work_without_validator(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"
panel_review.optimist = "codex"
panel_review.pessimist = "hermes:provider:model"
revise = "claude"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
        )
        panel = loaded["panel"]
        assert panel["synth"] == "claude"
        assert panel["panel_review.optimist"] == "codex"
        assert panel["panel_review.pessimist"] == "hermes:provider:model"

    def test_sub_table_flattened_to_strings_without_validator(self, tmp_path: Path) -> None:
        """Without a validator, TOML sub-tables are flattened to dotted string
        keys, and their string values pass normal agent-spec validation."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"

[profiles.panel.panel_review]
optimist = "codex"
pessimist = "hermes:provider:model"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
        )
        # Sub-table flattened into dotted string keys — no error.
        panel = loaded["panel"]
        assert panel["panel_review.optimist"] == "codex"
        assert panel["panel_review.pessimist"] == "hermes:provider:model"

    def test_dotted_keys_still_flatten_without_validator(self, tmp_path: Path) -> None:
        """Inline dotted keys (e.g. panel_review.optimist) still flatten normally."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"
panel_review.optimist = "codex"
revise = "claude"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
        )
        assert loaded["panel"]["panel_review.optimist"] == "codex"

    def test_metadata_keys_unaffected(self, tmp_path: Path) -> None:
        """Metadata extraction works regardless of stage_value_validators."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.standard]
default = true
extends = "base"
synth = "claude"
panel_review.optimist = "codex"
""",
        )
        metadata = load_profile_metadata(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            metadata_keys=frozenset({"default", "extends"}),
        )
        assert metadata["standard"] == {"default": True, "extends": "base"}


# ---------------------------------------------------------------------------
# Dict-value accept: validator is called with the raw dict
# ---------------------------------------------------------------------------


class TestDictValueAccept:
    """When a validator is registered for a stage, dict values are accepted."""

    def test_dict_value_passed_to_validator(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"
revise = "claude"

[profiles.panel.panel_review]
optimist = "codex"
pessimist = "hermes:provider:model"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            stage_value_validators={"panel_review": _valid_panel_review},
        )
        panel = loaded["panel"]
        # The validator returns a canonical string from the dict.
        assert "optimist=codex" in panel["panel_review"]
        assert "pessimist=hermes:provider:model" in panel["panel_review"]
        # String keys still validated normally.
        assert panel["synth"] == "claude"

    def test_validator_can_reject_dict(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"

[profiles.panel.panel_review]
optimist = "codex"
""",
        )
        with pytest.raises(ProfileLoadError, match="stage value validator rejected dict value"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=_STAGE_KEYS,
                known_agents=_AGENTS,
                stage_value_validators={"panel_review": _reject_everything},
            )

    def test_validator_skips_string_values_for_registered_key(self, tmp_path: Path) -> None:
        """A validator is only consulted for dict values.  String values for
        other keys (including dotted sub-keys of a registered stage) still go
        through normal agent-spec validation when the TOML uses dotted syntax
        that produces dicts — the dict is short-circuited to the validator.
        This test confirms that string keys without dict values are unaffected."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"
revise = "claude"

[profiles.panel.panel_review]
optimist = "codex"
pessimist = "hermes:provider:model"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            stage_value_validators={"panel_review": _valid_panel_review},
        )
        # panel_review dict was short-circuited to the validator.
        panel = loaded["panel"]
        assert "panel_review" in panel
        assert "optimist=codex" in panel["panel_review"]
        # synth and revise are plain strings — validator not called for those.
        assert panel["synth"] == "claude"
        assert panel["revise"] == "claude"

    def test_validator_not_called_for_unregistered_stage(self, tmp_path: Path) -> None:
        """When a validator is registered for a DIFFERENT stage, a sub-table
        for an unregistered stage is still flattened to dotted string keys
        (no rejection — the strings pass agent-spec validation)."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"

[profiles.panel.panel_review]
optimist = "codex"
""",
        )
        # Register a validator for synth, not panel_review.
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            stage_value_validators={"synth": _valid_panel_review},
        )
        # panel_review sub-table is still flattened to dotted string keys.
        panel = loaded["panel"]
        assert panel["panel_review.optimist"] == "codex"
        # synth is a string, not a dict — validator is not called.
        assert panel["synth"] == "claude"


# ---------------------------------------------------------------------------
# Flatten short-circuit: passthrough_keys preserves registered dicts
# ---------------------------------------------------------------------------


class TestFlattenPassthrough:
    """The flatten step short-circuits on keys registered in passthrough_keys."""

    def test_registered_dict_key_not_flattened(self, tmp_path: Path) -> None:
        """When panel_review has a validator, its sub-table is not flattened
        into dotted keys — the whole dict is preserved."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"
revise = "claude"

[profiles.panel.panel_review]
optimist = "codex"
pessimist = "hermes:provider:model"
""",
        )
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            stage_value_validators={"panel_review": _valid_panel_review},
        )
        panel = loaded["panel"]
        # panel_review should be a single key with the validator result, not
        # panel_review.optimist / panel_review.pessimist dotted keys.
        assert "panel_review" in panel
        assert "panel_review.optimist" not in panel
        assert "panel_review.pessimist" not in panel

    def test_unregistered_dict_still_flattened(self, tmp_path: Path) -> None:
        """When no validator is registered, sub-tables are still flattened to
        dotted string keys, and those strings pass agent-spec validation."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"

[profiles.panel.panel_review]
optimist = "codex"
""",
        )
        # Without a validator, flattening produces panel_review.optimist string
        # keys — they pass normal agent-spec validation.
        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
        )
        panel = loaded["panel"]
        assert panel["panel_review.optimist"] == "codex"

    def test_passthrough_via_load_profile_sources(self, tmp_path: Path) -> None:
        """The passthrough also works through load_profile_sources."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"

[profiles.panel.panel_review]
optimist = "codex"
pessimist = "hermes:provider:model"
""",
        )
        sources = load_profile_sources(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            stage_value_validators={"panel_review": _valid_panel_review},
        )
        assert len(sources) == 1
        source_label, profile_name, stage_map = sources[0]
        assert source_label == "built-in"
        assert profile_name == "panel"
        assert "panel_review" in stage_map
        assert "optimist=codex" in stage_map["panel_review"]

    def test_passthrough_via_load_profile_metadata(self, tmp_path: Path) -> None:
        """Metadata loading still works alongside stage_value_validators."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
default = true
synth = "claude"

[profiles.panel.panel_review]
optimist = "codex"
""",
        )
        metadata = load_profile_metadata(
            built_in_paths=(built_in,),
            declared_stage_keys=_STAGE_KEYS,
            known_agents=_AGENTS,
            metadata_keys=frozenset({"default"}),
            stage_value_validators={"panel_review": _valid_panel_review},
        )
        assert metadata["panel"] == {"default": True}


# ---------------------------------------------------------------------------
# Boundary: no megaplan imports in the opaque test file
# ---------------------------------------------------------------------------


class TestBoundary:
    def test_no_megaplan_imports(self) -> None:
        import ast
        source = Path(__file__)
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "megaplan":
                        violations.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None and node.module.split(".")[0] == "megaplan":
                    violations.append(node.module)
        assert not violations
