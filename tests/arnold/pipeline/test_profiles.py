"""Tests for neutral profile loading in ``arnold_pipelines.megaplan.profiles``."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.profiles import (
    ProfileLoadError,
    load_profile_metadata,
    load_profiles,
    load_profile_sources,
    parse_agent_spec_shape,
    resolve_default_profile,
    validate_declared_stage_keys,
)


def _write_profiles(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestGenericProfileLoading:
    def test_load_profiles_merges_built_in_user_and_project_layers(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        user = tmp_path / "user.toml"
        project = tmp_path / "project.toml"
        _write_profiles(
            built_in,
            """
            [profiles.base]
            draft = "claude"
            review = "codex"

            [profiles.shared]
            draft = "claude:low"
            review = "codex"
            """,
        )
        _write_profiles(
            user,
            """
            [profiles.shared]
            draft = "claude:medium"
            review = "codex"

            [profiles.user_only]
            draft = "hermes:provider:model"
            review = "codex"
            """,
        )
        _write_profiles(
            project,
            """
            [profiles.shared]
            draft = "codex:gpt-5.4"
            review = "codex"

            [profiles.project_only]
            draft = "claude:high"
            review = "codex"
            """,
        )

        loaded = load_profiles(
            built_in_paths=(built_in,),
            user_path=user,
            project_path=project,
            declared_stage_keys=frozenset({"draft", "review"}),
            known_agents=frozenset({"claude", "codex", "hermes"}),
        )

        assert loaded["base"]["draft"] == "claude"
        assert loaded["shared"]["draft"] == "codex:gpt-5.4"
        assert loaded["user_only"]["draft"] == "hermes:provider:model"
        assert loaded["project_only"]["draft"] == "claude:high"

    def test_load_profile_sources_keeps_layer_order(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        user = tmp_path / "user.toml"
        project = tmp_path / "project.toml"
        for path, spec in (
            (built_in, "claude"),
            (user, "codex"),
            (project, "hermes:provider:model"),
        ):
            _write_profiles(
                path,
                f"""
                [profiles.shared]
                draft = "{spec}"
                review = "codex"
                """,
            )

        sources = load_profile_sources(
            built_in_paths=(built_in,),
            user_path=user,
            project_path=project,
            declared_stage_keys=frozenset({"draft", "review"}),
            known_agents=frozenset({"claude", "codex", "hermes"}),
        )

        assert [(source, name) for source, name, _profile in sources] == [
            ("built-in", "shared"),
            ("user", "shared"),
            ("project", "shared"),
        ]

    def test_load_profile_metadata_preserves_declared_metadata_keys(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        project = tmp_path / "project.toml"
        _write_profiles(
            built_in,
            """
            [profiles.shared]
            default = "baseline"
            extends = "system:base"
            draft = "claude"
            review = "codex"
            """,
        )
        _write_profiles(
            project,
            """
            [profiles.shared]
            default = "project-default"
            extends = "project:base"
            draft = "codex"
            review = "codex"
            """,
        )

        metadata = load_profile_metadata(
            built_in_paths=(built_in,),
            project_path=project,
            declared_stage_keys=frozenset({"draft", "review"}),
            known_agents=frozenset({"claude", "codex", "hermes"}),
            metadata_keys=frozenset({"default", "extends"}),
        )

        assert metadata["shared"] == {
            "default": "project-default",
            "extends": "project:base",
        }

    def test_dotted_stage_keys_validate_by_declared_prefix_only(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """
            [profiles.panel]
            synth = "claude"
            [profiles.panel.panel_review]
            optimist = "codex"
            pessimist = "hermes:provider:model"
            """,
        )

        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=frozenset({"synth", "panel_review"}),
            known_agents=frozenset({"claude", "codex", "hermes"}),
        )

        assert loaded["panel"]["panel_review.optimist"] == "codex"
        assert loaded["panel"]["panel_review.pessimist"] == "hermes:provider:model"

    def test_unknown_declared_stage_prefix_is_rejected(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """
            [profiles.bad]
            unknown_stage.slot = "claude"
            """,
        )

        with pytest.raises(ProfileLoadError, match="unknown declared stage prefix 'unknown_stage'"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=frozenset({"synth", "panel_review"}),
                known_agents=frozenset({"claude", "codex", "hermes"}),
            )

    def test_unknown_agent_is_rejected_when_allowlist_is_supplied(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """
            [profiles.bad]
            draft = "bogus:model"
            review = "codex"
            """,
        )

        with pytest.raises(ProfileLoadError, match="Unknown agent 'bogus'"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=frozenset({"draft", "review"}),
                known_agents=frozenset({"claude", "codex", "hermes"}),
            )

    def test_structured_stage_values_require_explicit_validator(self) -> None:
        with pytest.raises(ProfileLoadError, match="expected a string agent spec"):
            validate_declared_stage_keys(
                "profiles.toml",
                "structured",
                {"plan": {"agent": "claude", "model": "sonnet"}},
                declared_stage_keys=frozenset({"plan", "review"}),
                known_agents=frozenset({"claude", "codex"}),
            )

    def test_structured_stage_validator_normalizes_dict_value(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """
            [profiles.structured]
            plan = { agent = "claude", model = "sonnet" }
            review = "codex"
            """,
        )

        def normalize_plan(raw: object) -> str:
            assert isinstance(raw, dict)
            return f"{raw['agent']}:{raw['model']}"

        loaded = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=frozenset({"plan", "review"}),
            known_agents=frozenset({"claude", "codex"}),
            stage_value_validators={"plan": normalize_plan},
        )

        assert loaded["structured"] == {
            "plan": "claude:sonnet",
            "review": "codex",
        }

    def test_structured_stage_validator_errors_are_profile_errors(self, tmp_path: Path) -> None:
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """
            [profiles.bad]
            plan = { agent = "claude" }
            review = "codex"
            """,
        )

        def reject(_raw: object) -> str:
            raise ValueError("missing model")

        with pytest.raises(ProfileLoadError, match="missing model"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=frozenset({"plan", "review"}),
                known_agents=frozenset({"claude", "codex"}),
                stage_value_validators={"plan": reject},
            )


class TestAgentSpecShape:
    def test_parse_premium_agent_variants(self) -> None:
        assert parse_agent_spec_shape("claude").agent == "claude"
        assert parse_agent_spec_shape("claude:low").effort == "low"
        parsed = parse_agent_spec_shape("codex:gpt-5.4:high")
        assert parsed.agent == "codex"
        assert parsed.model == "gpt-5.4"
        assert parsed.effort == "high"

    def test_parse_non_premium_agent_preserves_model_colons(self) -> None:
        parsed = parse_agent_spec_shape("hermes:provider:model")
        assert parsed.agent == "hermes"
        assert parsed.model == "provider:model"


class TestResolveDefaultProfile:
    def test_explicit_default_name_selects_correct_profile(self) -> None:
        profiles = {
            "standard": {"draft": "claude", "review": "codex"},
            "light": {"draft": "claude:low", "review": "codex"},
        }
        name, stage_map = resolve_default_profile(profiles, default_name="light")
        assert name == "light"
        assert stage_map["draft"] == "claude:low"

    def test_metadata_string_ref_selects_referenced_profile(self) -> None:
        profiles = {
            "standard": {"draft": "claude", "review": "codex"},
            "light": {"draft": "claude:low", "review": "codex"},
        }
        metadata = {"custom": {"default": "standard"}}
        name, stage_map = resolve_default_profile(profiles, metadata=metadata)
        assert name == "standard"
        assert stage_map["draft"] == "claude"

    def test_metadata_bool_true_selects_self(self) -> None:
        profiles = {
            "standard": {"draft": "claude", "review": "codex"},
            "light": {"draft": "claude:low", "review": "codex"},
        }
        metadata = {"light": {"default": True}}
        name, stage_map = resolve_default_profile(profiles, metadata=metadata)
        assert name == "light"
        assert stage_map["draft"] == "claude:low"

    def test_falls_back_to_first_profile_when_no_default_marker(self) -> None:
        profiles = {
            "standard": {"draft": "claude", "review": "codex"},
            "light": {"draft": "claude:low", "review": "codex"},
        }
        name, stage_map = resolve_default_profile(profiles)
        assert name == "standard"

    def test_empty_profiles_raises(self) -> None:
        with pytest.raises(ProfileLoadError, match="no profiles available"):
            resolve_default_profile({})

    def test_unknown_explicit_name_raises(self) -> None:
        profiles = {"standard": {"draft": "claude"}}
        with pytest.raises(ProfileLoadError, match="Cannot resolve default profile 'nonexistent'"):
            resolve_default_profile(profiles, default_name="nonexistent")

    def test_metadata_string_ref_to_nonexistent_is_skipped(self) -> None:
        profiles = {
            "standard": {"draft": "claude", "review": "codex"},
            "light": {"draft": "claude:low", "review": "codex"},
        }
        metadata = {"custom": {"default": "nonexistent"}}
        # Falls through to first profile.
        name, _stage_map = resolve_default_profile(profiles, metadata=metadata)
        assert name == "standard"


class TestComposedPipelineProfiles:
    """Profile loading for composed (parent + child) pipelines."""

    STAGE_KEYS = frozenset({"synth", "panel_review", "revise"})
    AGENTS = frozenset({"claude", "codex", "hermes"})

    def test_nested_child_profile_map_via_toml_subtable(self, tmp_path: Path) -> None:
        """A TOML subtable like [profiles.panel.panel_review] flattens to dotted keys."""
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
            declared_stage_keys=self.STAGE_KEYS,
            known_agents=self.AGENTS,
        )
        panel = loaded["panel"]
        assert panel["synth"] == "claude"
        assert panel["revise"] == "claude"
        assert panel["panel_review.optimist"] == "codex"
        assert panel["panel_review.pessimist"] == "hermes:provider:model"

    def test_nested_child_profile_keys_validated_against_declared_stages(self, tmp_path: Path) -> None:
        """Child-stage keys like panel_review.optimist validate against declared stage prefixes."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"

[profiles.panel.unknown_child]
slot = "codex"
""",
        )
        with pytest.raises(ProfileLoadError, match="unknown declared stage prefix 'unknown_child'"):
            load_profiles(
                built_in_paths=(built_in,),
                declared_stage_keys=self.STAGE_KEYS,
                known_agents=self.AGENTS,
            )

    def test_named_child_profiles_with_metadata_default_selection(self, tmp_path: Path) -> None:
        """Multiple named profiles with one marked as default via metadata."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.standard]
default = true
synth = "claude"
panel_review.optimist = "codex"
panel_review.pessimist = "hermes:provider:model"
revise = "claude"

[profiles.light]
synth = "claude:low"
panel_review.optimist = "codex"
panel_review.pessimist = "hermes:provider:model"
revise = "claude:low"
""",
        )
        profiles = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=self.STAGE_KEYS,
            known_agents=self.AGENTS,
            metadata_keys=frozenset({"default"}),
        )
        metadata = load_profile_metadata(
            built_in_paths=(built_in,),
            declared_stage_keys=self.STAGE_KEYS,
            known_agents=self.AGENTS,
            metadata_keys=frozenset({"default"}),
        )

        # Both named profiles loaded.
        assert "standard" in profiles
        assert "light" in profiles

        # Default resolution picks 'standard' (default = true).
        name, stage_map = resolve_default_profile(profiles, metadata=metadata)
        assert name == "standard"
        assert stage_map["synth"] == "claude"
        assert stage_map["panel_review.optimist"] == "codex"

    def test_parent_default_profile_referenced_by_string_metadata(self, tmp_path: Path) -> None:
        """A parent profile references a child named profile via default = \"child_name\"."""
        built_in = tmp_path / "built-in.toml"
        _write_profiles(
            built_in,
            """\
[profiles.composed]
default = "child-full"
synth = "claude"

[profiles.child-full]
synth = "codex"
panel_review.optimist = "claude"
panel_review.pessimist = "hermes:provider:model"
revise = "codex"

[profiles.child-light]
synth = "codex:low"
panel_review.optimist = "claude:low"
panel_review.pessimist = "hermes:provider:model"
revise = "codex:low"
""",
        )
        profiles = load_profiles(
            built_in_paths=(built_in,),
            declared_stage_keys=self.STAGE_KEYS,
            known_agents=self.AGENTS,
            metadata_keys=frozenset({"default"}),
        )
        metadata = load_profile_metadata(
            built_in_paths=(built_in,),
            declared_stage_keys=self.STAGE_KEYS,
            known_agents=self.AGENTS,
            metadata_keys=frozenset({"default"}),
        )

        # Default resolution follows the string reference composed → child-full.
        name, stage_map = resolve_default_profile(profiles, metadata=metadata)
        assert name == "child-full"
        assert stage_map["synth"] == "codex"
        assert stage_map["panel_review.optimist"] == "claude"

    def test_nested_child_profiles_preserve_all_slots_across_layers(self, tmp_path: Path) -> None:
        """Layer merging: later layers replace entire named profiles.

        Full-profile replacement (not per-key merge) is the documented
        contract for ``merge_profile_layers``.  When a project layer
        defines a profile with only a subset of the built-in keys, only
        those keys survive — the built-in layer is wholly replaced for
        that profile name.
        """
        built_in = tmp_path / "built-in.toml"
        project = tmp_path / "project.toml"
        _write_profiles(
            built_in,
            """\
[profiles.panel]
synth = "claude"
panel_review.optimist = "codex"
panel_review.pessimist = "codex"
revise = "claude"
""",
        )
        _write_profiles(
            project,
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
            project_path=project,
            declared_stage_keys=self.STAGE_KEYS,
            known_agents=self.AGENTS,
        )
        panel = loaded["panel"]
        # All keys from the winning (project) layer.
        assert panel["synth"] == "claude"
        assert panel["panel_review.optimist"] == "codex"
        assert panel["revise"] == "claude"
        # Project override for pessimist.
        assert panel["panel_review.pessimist"] == "hermes:provider:model"


class TestBoundary:
    def test_profiles_module_has_no_megaplan_imports(self) -> None:
        source = (
            Path(__file__).resolve().parents[3]
            / "arnold_pipelines"
            / "megaplan"
            / "profiles"
            / "neutral.py"
        )
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
