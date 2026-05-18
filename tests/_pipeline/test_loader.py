"""Unit tests for megaplan._pipeline.loader — discovery, loading, hashing."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from megaplan._pipeline.loader import (
    LoadedPipeline,
    PipelineLoadError,
    describe_pipeline,
    discover_pipelines,
    list_pipeline_names,
    load_pipeline,
)


# ── Discovery ─────────────────────────────────────────────────────────


class TestDiscovery:
    """Pipeline discovery from built-in and user directories."""

    def test_builtin_discovery(self) -> None:
        """Built-in pipelines should be discoverable."""
        names = list_pipeline_names()
        assert "writing-panel-strict" in names
        assert "planning" in names

    def test_discover_returns_loaded_pipelines(self) -> None:
        pipelines = discover_pipelines()
        assert "writing-panel-strict" in pipelines
        lp = pipelines["writing-panel-strict"]
        assert isinstance(lp, LoadedPipeline)
        assert lp.spec.name == "writing-panel-strict"
        assert lp.spec.version == 1

    def test_list_pipeline_names_returns_sorted_tuple(self) -> None:
        names = list_pipeline_names()
        assert isinstance(names, tuple)
        assert names == tuple(sorted(names))

    def test_custom_builtin_dir(self, tmp_path: Path) -> None:
        """Discovery should respect custom directory overrides."""
        pipeline_dir = tmp_path / "custom" / "my-pipe"
        pipeline_dir.mkdir(parents=True)
        (pipeline_dir / "pipeline.yaml").write_text(
            """\
name: my-pipe
version: 1
description: "Custom test pipeline"
default_profile: partnered
stages:
  - id: s1
    kind: agent
    prompt: hello
"""
        )
        # Empty user dir (non-existent)
        user_dir = tmp_path / "user-nonexistent"
        pipelines = discover_pipelines(
            builtin_dir=tmp_path / "custom",
            user_dir=user_dir,
        )
        assert "my-pipe" in pipelines

    def test_user_override_builtin(self, tmp_path: Path) -> None:
        """User pipeline with same name shadows built-in with a warning."""
        builtin = tmp_path / "builtin" / "shadow-test"
        user = tmp_path / "user" / "shadow-test"
        builtin.mkdir(parents=True)
        user.mkdir(parents=True)

        (builtin / "pipeline.yaml").write_text(
            """\
name: shadow-test
version: 1
description: "Builtin version"
default_profile: partnered
stages:
  - id: s1
    kind: agent
    prompt: p.md
"""
        )
        (user / "pipeline.yaml").write_text(
            """\
name: shadow-test
version: 2
description: "User version"
default_profile: partnered
stages:
  - id: s1
    kind: agent
    prompt: p.md
"""
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            pipelines = discover_pipelines(
                builtin_dir=builtin.parent,
                user_dir=user.parent,
            )

            # Should warn about shadowing
            shadow_warnings = [x for x in w if "shadows" in str(x.message)]
            assert len(shadow_warnings) >= 1

        assert "shadow-test" in pipelines
        lp = pipelines["shadow-test"]
        assert lp.spec.version == 2  # User version wins


# ── Loading ───────────────────────────────────────────────────────────


class TestLoading:
    """Loading individual pipelines."""

    def test_load_pipeline_by_name(self) -> None:
        lp = load_pipeline("writing-panel-strict")
        assert lp.spec.name == "writing-panel-strict"
        assert lp.path.name == "pipeline.yaml"

    def test_load_nonexistent_pipeline(self) -> None:
        with pytest.raises(KeyError, match="No pipeline named"):
            load_pipeline("nonexistent-pipeline-xyz")

    def test_load_planning_pipeline(self) -> None:
        """The parked planning pipeline.yaml should load without error."""
        lp = load_pipeline("planning")
        assert lp.spec.name == "planning"
        assert lp.spec.version == 1
        assert len(lp.spec.stages) >= 1

    def test_pipeline_load_error_invalid_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML should raise PipelineLoadError."""
        pipeline_dir = tmp_path / "bad-yaml"
        pipeline_dir.mkdir()
        (pipeline_dir / "pipeline.yaml").write_text(
            "this: is: not: valid: yaml: ["
        )
        with pytest.raises(PipelineLoadError):
            discover_pipelines(builtin_dir=tmp_path, user_dir=tmp_path / "nope")

    def test_pipeline_load_error_not_a_dict(self, tmp_path: Path) -> None:
        """Top-level YAML that is not a dict should fail."""
        pipeline_dir = tmp_path / "bad-dict"
        pipeline_dir.mkdir()
        (pipeline_dir / "pipeline.yaml").write_text("- list item\n- not a dict\n")
        with pytest.raises(PipelineLoadError):
            discover_pipelines(builtin_dir=tmp_path, user_dir=tmp_path / "nope")


# ── Content hash ──────────────────────────────────────────────────────


class TestContentHash:
    """Content hash stability and isolation."""

    def test_hash_stable_for_same_pipeline(self) -> None:
        lp1 = load_pipeline("writing-panel-strict")
        lp2 = load_pipeline("writing-panel-strict")
        assert lp1.content_hash == lp2.content_hash
        assert len(lp1.content_hash) == 64  # SHA-256 hex

    def test_hash_different_for_different_pipelines(self) -> None:
        lp1 = load_pipeline("writing-panel-strict")
        lp2 = load_pipeline("planning")
        assert lp1.content_hash != lp2.content_hash

    def test_hash_changes_when_pipeline_yaml_changes(self, tmp_path: Path) -> None:
        """Modifying pipeline.yaml should change the hash."""
        pipeline_dir = tmp_path / "hash-test"
        pipeline_dir.mkdir()
        yaml_path = pipeline_dir / "pipeline.yaml"
        yaml_path.write_text(
            """\
name: hash-test
version: 1
description: "V1"
default_profile: partnered
stages:
  - id: s1
    kind: agent
    prompt: p.md
"""
        )
        (pipeline_dir / "p.md").write_text("prompt content")

        pipelines1 = discover_pipelines(builtin_dir=tmp_path, user_dir=tmp_path / "nope")
        h1 = pipelines1["hash-test"].content_hash

        # Change the description
        yaml_path.write_text(
            """\
name: hash-test
version: 1
description: "V2 — modified"
default_profile: partnered
stages:
  - id: s1
    kind: agent
    prompt: p.md
"""
        )
        pipelines2 = discover_pipelines(builtin_dir=tmp_path, user_dir=tmp_path / "nope")
        h2 = pipelines2["hash-test"].content_hash

        assert h1 != h2


# ── SKILL.md ──────────────────────────────────────────────────────────


class TestSkillMd:
    """SKILL.md loading and rendering."""

    def test_skill_md_loaded(self) -> None:
        lp = load_pipeline("writing-panel-strict")
        assert lp.skill_md is not None
        assert "writing-panel-strict" in lp.skill_md
        assert "## Modes" in lp.skill_md

    def test_describe_includes_skill_md(self) -> None:
        desc = describe_pipeline("writing-panel-strict")
        assert "─── SKILL.md ───" in desc
        assert "Adversarial review" in desc

    def test_describe_includes_metadata(self) -> None:
        desc = describe_pipeline("writing-panel-strict")
        assert "Pipeline: writing-panel-strict" in desc
        assert "Source:" in desc
        assert "Default profile:" in desc


# ── Error handling ────────────────────────────────────────────────────


class TestErrorHandling:
    """Error paths produce clear messages."""

    def test_describe_unknown_pipeline(self) -> None:
        with pytest.raises(KeyError, match="No pipeline named"):
            describe_pipeline("nonexistent")

    def test_load_unknown_raises_keyerror(self) -> None:
        with pytest.raises(KeyError, match="No pipeline named"):
            load_pipeline("completely-unknown-name")

    def test_empty_dirs_produce_empty_results(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        pipelines = discover_pipelines(builtin_dir=empty, user_dir=tmp_path / "nope")
        assert pipelines == {}
