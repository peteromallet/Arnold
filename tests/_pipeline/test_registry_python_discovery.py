"""T10 — Python-module pipeline discovery + metadata + SKILL.md surface.

Covers the six contract points laid out in the brief:
  (a) registered_pipelines() lists planning, doc-critique, judges, writing-panel-strict.
  (b) A drop-in user pipeline at a temp ~/.megaplan/pipelines/foo.py
      (monkeypatched HOME) is discovered and runnable via the registry.
  (c) metadata['writing-panel-strict'] exposes description, default_profile,
      supported_modes.
  (d) registry.read_skill_md('writing-panel-strict') returns the contents of
      megaplan/pipelines/writing-panel-strict/SKILL.md.
  (e) read_skill_md for a user pipeline WITHOUT a co-located SKILL.md
      returns None and does not raise.
  (f) discover_python_pipelines() rejects/skips a planted sibling whose
      CLI name would collide with a hardcoded built-in (planning /
      doc-critique / judges). The collision check is root-agnostic;
      planting under the user-scan root proves the semantic.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

from megaplan._pipeline.registry import (
    PipelineRegistry,
    discover_python_pipelines,
    register_pipeline,
)


# ── (a) Built-ins + writing-panel-strict are all visible ────────────────


def test_registered_pipelines_lists_builtins_plus_writing_panel_strict() -> None:
    from megaplan._pipeline.registry import registered_pipelines

    names = registered_pipelines()
    for required in ("planning", "doc-critique", "judges", "writing-panel-strict"):
        assert required in names, (
            f"missing {required!r} in registry; got {names!r}"
        )


# ── (c) Metadata round-trip for writing-panel-strict ────────────────────


def test_writing_panel_strict_metadata_exposes_module_constants() -> None:
    from megaplan._pipeline.registry import pipeline_metadata

    meta = pipeline_metadata("writing-panel-strict")
    assert meta.get("description"), (
        f"writing-panel-strict description missing; meta={meta!r}"
    )
    assert meta.get("default_profile") == "@writing-panel-strict:standard"
    assert meta.get("supported_modes") == ("polish", "restructure", "provoke")


# ── (d) read_skill_md returns the on-disk SKILL.md text ─────────────────


def test_read_skill_md_returns_writing_panel_strict_contents() -> None:
    from megaplan._pipeline.registry import read_pipeline_skill_md

    contents = read_pipeline_skill_md("writing-panel-strict")
    on_disk = (
        Path(__file__).resolve().parents[2]
        / "megaplan"
        / "pipelines"
        / "writing-panel-strict"
        / "SKILL.md"
    )
    assert on_disk.exists(), "writing-panel-strict/SKILL.md vanished from disk"
    expected = on_disk.read_text(encoding="utf-8")
    assert contents == expected


# ── (b) User-pipeline discovery from ~/.megaplan/pipelines/foo.py ───────
# ── (e) read_skill_md returns None for user pipeline with no SKILL.md ───


def _fresh_registry_with_home(tmp_home: Path, *, monkeypatch: pytest.MonkeyPatch) -> PipelineRegistry:
    """Build a registry whose user-root is *tmp_home*/.megaplan/pipelines.

    HOME is monkeypatched so Path.home() inside the discover walk
    resolves to the temp directory. A fresh PipelineRegistry sidesteps
    the global cache so discovery actually re-runs.
    """

    monkeypatch.setenv("HOME", str(tmp_home))
    # On macOS Path.home() can also consult HOMEDRIVE/HOMEPATH on win or
    # the pwd database; on Darwin a HOME override is sufficient.
    registry = PipelineRegistry()
    register_pipeline.__self__ if False else None  # noqa: B015 — silence ruff
    return registry


def test_user_pipeline_is_discovered_and_runnable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_dir = tmp_path / ".megaplan" / "pipelines"
    user_dir.mkdir(parents=True)
    foo_py = user_dir / "foo.py"
    foo_py.write_text(
        "from megaplan._pipeline.types import Pipeline, Stage, Edge, "
        "StepContext, StepResult, Step\n"
        "from dataclasses import dataclass\n"
        "\n"
        "description = 'Tiny foo pipeline used by registry discovery tests.'\n"
        "\n"
        "@dataclass\n"
        "class _NoopStep(Step):\n"
        "    name: str = 'noop'\n"
        "    def run(self, ctx: StepContext) -> StepResult:  # noqa: D401\n"
        "        return StepResult(next='halt', state_patch={'foo_ran': True})\n"
        "\n"
        "def build_pipeline() -> Pipeline:\n"
        "    return Pipeline(\n"
        "        stages={'noop': Stage(name='noop', step=_NoopStep(),\n"
        "                              edges=(Edge(label='halt', target='halt'),))},\n"
        "        entry='noop',\n"
        "    )\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    # Drop any prior user-module import so the fresh discovery re-execs.
    sys.modules.pop("megaplan._user_pipelines.foo", None)

    registry = PipelineRegistry()
    names = registry.names()
    assert "foo" in names, (
        f"user pipeline 'foo' not discovered under {user_dir!s}; got {names!r}"
    )

    # Metadata picks up the module-level description.
    meta = registry.metadata_for("foo")
    assert meta.get("description") == (
        "Tiny foo pipeline used by registry discovery tests."
    )
    assert meta.get("source_path") == str(foo_py)

    # Pipeline is runnable: build_pipeline() returns a real Pipeline value.
    from megaplan._pipeline.types import Pipeline as _PipelineCls

    pipeline = registry.get("foo")
    assert isinstance(pipeline, _PipelineCls)
    assert pipeline.entry == "noop"
    assert "noop" in pipeline.stages

    # (e) — no co-located SKILL.md → graceful None, no exception.
    assert registry.read_skill_md("foo") is None


# ── (f) Collision detection: planted name shadowing a built-in is skipped


def test_discover_python_pipelines_skips_built_in_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plant a sibling file whose CLI name == 'planning' under the user
    scan root and assert discovery refuses to register it (warning
    emitted + skipped). The same code path serves both the in-tree
    megaplan/pipelines/ root and the user ~/.megaplan/pipelines/ root,
    so this proves the collision semantic without requiring us to write
    into the real source tree.
    """

    user_dir = tmp_path / ".megaplan" / "pipelines"
    user_dir.mkdir(parents=True)
    planted = user_dir / "planning.py"
    planted.write_text(
        "from megaplan._pipeline.types import Pipeline, Stage, Edge, "
        "StepContext, StepResult, Step\n"
        "from dataclasses import dataclass\n"
        "\n"
        "description = 'BOGUS override of the built-in planning pipeline.'\n"
        "\n"
        "@dataclass\n"
        "class _BogusStep(Step):\n"
        "    name: str = 'bogus'\n"
        "    def run(self, ctx: StepContext) -> StepResult:\n"
        "        return StepResult(next='halt')\n"
        "\n"
        "def build_pipeline() -> Pipeline:\n"
        "    return Pipeline(\n"
        "        stages={'bogus': Stage(name='bogus', step=_BogusStep(),\n"
        "                               edges=(Edge(label='halt', target='halt'),))},\n"
        "        entry='bogus',\n"
        "    )\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    sys.modules.pop("megaplan._user_pipelines.planning", None)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        discovered = discover_python_pipelines()

    discovered_names = {entry[0] for entry in discovered}
    # The planted 'planning' module must NOT appear among discovered
    # entries — collision detection short-circuits before it is loaded.
    planted_entries = [
        entry for entry in discovered if entry[0] == "planning"
    ]
    assert planted_entries == [], (
        f"collision skipped; expected no discovered 'planning', "
        f"got {planted_entries!r}"
    )

    # A UserWarning naming the planted path + the colliding built-in
    # must have been emitted.
    matching = [
        w for w in captured
        if issubclass(w.category, UserWarning)
        and "planning" in str(w.message)
        and str(planted) in str(w.message)
    ]
    assert matching, (
        f"expected UserWarning about planted {planted!s}; got "
        f"{[str(w.message) for w in captured]!r}"
    )

    # And the registry still resolves the built-in planning pipeline
    # via the module-level API (which is backed by the global registry
    # where the built-in was registered at import time).
    from megaplan._pipeline.registry import (
        get_pipeline,
        pipeline_metadata,
    )

    pipeline = get_pipeline("planning")
    assert "bogus" not in pipeline.stages, (
        "built-in planning pipeline was clobbered by the planted sibling"
    )

    # The built-in metadata never carries the planted bogus description.
    builtin_meta = pipeline_metadata("planning")
    assert builtin_meta.get("description") != (
        "BOGUS override of the built-in planning pipeline."
    )
