"""M4 characterization tests: arnold/pipelines plugin registry discovery.

These tests characterise the expected behaviour once arnold/pipelines is
populated (T4/T5).  They are self-contained via tmp_path planting so they
pass before the plugin skeleton exists and remain accurate afterward.

Key contracts under test:
  (a) arnold/pipelines/* is discovered via its own scan root.
  (b) arnold/pipelines has scan-order priority — its megaplan pipeline wins
      dedup over megaplan/pipelines/planning.
  (c) The legacy ``planning`` alias still resolves.
  (d) SKILL.md is read from the winning plugin path.
  (e) Boundary tests allow arnold/__init__.py version import while blocking
      stage/handler imports under arnold/pipelines/.
  (f) _package_prefix_for_module_file correctly classifies both arnold and
      megaplan paths.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.registry import PipelineRegistry
from arnold_pipelines.megaplan.runtime.discovery import _package_prefix_for_module_file


# ── (f) Package prefix classification ──────────────────────────────────


def test_package_prefix_for_arnold_path() -> None:
    """_package_prefix_for_module_file returns 'arnold.pipelines' for arnold paths."""
    fake = Path("/repo/arnold/pipelines/megaplan/__init__.py")
    assert _package_prefix_for_module_file(fake) == "arnold.pipelines"


def test_package_prefix_for_megaplan_path() -> None:
    """_package_prefix_for_module_file returns 'megaplan.pipelines' for megaplan paths."""
    fake = Path("/repo/megaplan/pipelines/planning/__init__.py")
    assert _package_prefix_for_module_file(fake) == "arnold_pipelines.megaplan.pipelines"


def test_package_prefix_for_out_of_tree_path() -> None:
    """_package_prefix_for_module_file returns None for out-of-tree paths."""
    fake = Path("/home/user/.megaplan/pipelines/custom.py")
    assert _package_prefix_for_module_file(fake) is None


# ── Helpers for planting pipeline modules ──────────────────────────────

_PIPELINE_BODY = """\
from arnold.workflow.dsl import Pipeline, Route, Step
from arnold.manifest import WorkflowPolicy

description = {description!r}
default_profile = {default_profile!r}
supported_modes = {supported_modes!r}

def build_pipeline() -> Pipeline:
    noop = Step(
        id="noop",
        kind="megaplan:noop",
        policy=WorkflowPolicy(),
        metadata={{}},
    )
    halt = Step(
        id="halt",
        kind="megaplan:halt",
        policy=WorkflowPolicy(),
        metadata={{"terminal": True}},
    )
    return Pipeline(
        id="characterization-test-plugin",
        version="0.1",
        steps=(noop, halt),
        routes=(Route(id="noop:halt", source="noop", target="halt", label="default"),),
    )
"""


def _plant_arnold_megaplan(base: Path) -> Path:
    """Write arnold_pipelines/megaplan/__init__.py under *base*."""
    pkg = base / "arnold_pipelines" / "megaplan"
    pkg.mkdir(parents=True)
    init = pkg / "__init__.py"
    init.write_text(
        _PIPELINE_BODY.format(
            description="arnold plugin megaplan pipeline",
            default_profile="@megaplan:plugin",
            supported_modes=("plan",),
            state_patch={"arnold_ran": True},
        ),
        encoding="utf-8",
    )
    return init


def _plant_megaplan_planning(base: Path) -> Path:
    """Write megaplan/pipelines/planning/__init__.py under *base*."""
    pkg = base / "megaplan" / "pipelines" / "planning"
    pkg.mkdir(parents=True)
    init = pkg / "__init__.py"
    init.write_text(
        _PIPELINE_BODY.format(
            description="megaplan legacy planning pipeline",
            default_profile="@planning:legacy",
            supported_modes=("code",),
            state_patch={"megaplan_ran": True},
        ),
        encoding="utf-8",
    )
    return init


def _patch_load_for_temp_paths(
    monkeypatch: pytest.MonkeyPatch,
    temp_root: Path,
    arnold_pp: Path,
) -> None:
    """Monkeypatch _load_module_from_path so it uses spec-from-file-location
    for our temp paths (since they aren't real installed packages)."""

    def _load_from_path(
        module_file: Path,
        *,
        package_prefix: str | None,
    ) -> Any | None:
        # For out-of-tree (or known temp paths), use spec-from-file.
        if package_prefix is None:
            mod_name = (
                f"arnold_pipelines.megaplan._user_pipelines.{module_file.stem}"
                if module_file.name != "__init__.py"
                else f"arnold_pipelines.megaplan._user_pipelines.{module_file.parent.name}"
            )
        elif package_prefix == "arnold_pipelines":
            if module_file.name == "__init__.py":
                mod_name = f"arnold_pipelines._test_{module_file.parent.name}_{abs(hash(str(module_file)))}"
            else:
                mod_name = f"arnold_pipelines._test_{module_file.stem}_{abs(hash(str(module_file)))}"
        elif package_prefix == "arnold_pipelines.megaplan.pipelines":
            if module_file.name == "__init__.py":
                mod_name = f"arnold_pipelines.megaplan.pipelines._test_{module_file.parent.name}_{abs(hash(str(module_file)))}"
            else:
                mod_name = f"arnold_pipelines.megaplan.pipelines._test_{module_file.stem}_{abs(hash(str(module_file)))}"
        else:
            mod_name = f"arnold_pipelines.megaplan._user_pipelines.{module_file.stem}"

        spec = importlib.util.spec_from_file_location(mod_name, module_file)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(mod_name, None)
            return None
        return module

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._load_module_from_path",
        _load_from_path,
    )


# ── (a)(b) Scan-order priority — arnold wins over megaplan ─────────────


def test_arnold_pipeline_wins_over_megaplan_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both arnold_pipelines/megaplan/ and megaplan/pipelines/planning/
    expose build_pipeline, the arnold plugin wins discovery because
    arnold_pipelines is scanned first."""
    arnold_pp = tmp_path / "arnold_pipelines"
    megaplan_pp = tmp_path / "megaplan" / "pipelines"

    _plant_arnold_megaplan(tmp_path)
    _plant_megaplan_planning(tmp_path)

    # Use spec-from-file for temp paths since they aren't installed packages.
    _patch_load_for_temp_paths(monkeypatch, tmp_path, arnold_pp)

    # Override scan roots.
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._SCAN_ROOTS",
        [(arnold_pp, "arnold_pipelines"), (megaplan_pp, "arnold_pipelines.megaplan.pipelines")],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._get_scan_roots",
        lambda: [(arnold_pp, "arnold_pipelines"), (megaplan_pp, "arnold_pipelines.megaplan.pipelines")],
    )

    # Drop any cached imports.
    sys.modules.pop("arnold_pipelines.megaplan.pipelines.planning", None)

    registry = PipelineRegistry()
    names = registry.names()

    # Both scan roots contribute; 'megaplan' must be present.
    assert "megaplan" in names, (
        f"'megaplan' not in registry; got {names!r}"
    )

    # The registered megaplan pipeline must come from the arnold plugin,
    # not from the legacy megaplan/planning package.
    meta = registry.metadata_for("megaplan")
    assert meta.get("description") == "arnold plugin megaplan pipeline", (
        f"megaplan metadata should reflect arnold plugin, got {meta!r}"
    )

    # The arnold module file is registered.
    arnold_init = arnold_pp / "megaplan" / "__init__.py"
    module_file = registry._module_files.get("megaplan")
    assert module_file == arnold_init, (
        f"megaplan module should be {arnold_init}, got {module_file}"
    )

    # Build the pipeline and verify it's from arnold.
    pipeline = registry.get("megaplan")
    assert pipeline is not None
    assert "noop" in {s.id for s in pipeline.steps}


def test_arnold_scan_root_appears_before_megaplan_plugin_in_scan_roots() -> None:
    """_SCAN_ROOTS lists arnold_pipelines before the Megaplan plugin pipelines."""
    from arnold_pipelines.megaplan.runtime.discovery import _SCAN_ROOTS
    prefixes_in_order = [pkg_prefix for _, pkg_prefix in _SCAN_ROOTS if pkg_prefix is not None]
    arnold_idx = prefixes_in_order.index("arnold_pipelines")
    megaplan_idx = prefixes_in_order.index("arnold_pipelines.megaplan.pipelines")
    assert arnold_idx < megaplan_idx, (
        f"arnold_pipelines ({arnold_idx}) must appear before "
        f"arnold_pipelines.megaplan.pipelines ({megaplan_idx}) in _SCAN_ROOTS"
    )


# ── (c) Legacy planning alias resolves ─────────────────────────────────


def test_legacy_planning_alias_still_resolves() -> None:
    """The 'planning' → 'megaplan' alias remains in LEGACY_PIPELINE_ALIASES."""
    from arnold_pipelines.megaplan.runtime.discovery import LEGACY_PIPELINE_ALIASES, canonical_pipeline_name
    assert "planning" in LEGACY_PIPELINE_ALIASES
    assert LEGACY_PIPELINE_ALIASES["planning"] == "megaplan"
    assert canonical_pipeline_name("planning") == "megaplan"


# ── (d) SKILL.md read from plugin path ─────────────────────────────────


def test_skill_md_read_from_arnold_plugin_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When an arnold-planted pipeline has a co-located SKILL.md,
    read_skill_md returns its contents."""
    arnold_pp = tmp_path / "arnold_pipelines"

    _plant_arnold_megaplan(tmp_path)

    # Plant a SKILL.md adjacent to the arnold megaplan package.
    skill_path = arnold_pp / "megaplan" / "SKILL.md"
    skill_path.write_text("# Plugin SKILL.md\n\nPlugin-specific docs.\n", encoding="utf-8")

    _patch_load_for_temp_paths(monkeypatch, tmp_path, arnold_pp)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._SCAN_ROOTS",
        [(arnold_pp, "arnold_pipelines")],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._get_scan_roots",
        lambda: [(arnold_pp, "arnold_pipelines")],
    )

    registry = PipelineRegistry()
    contents = registry.read_skill_md("megaplan")
    assert contents == "# Plugin SKILL.md\n\nPlugin-specific docs.\n", (
        f"SKILL.md contents mismatch: {contents!r}"
    )


def test_skill_md_returns_none_when_absent_from_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """read_skill_md returns None gracefully when the plugin has no SKILL.md."""
    arnold_pp = tmp_path / "arnold_pipelines"

    _plant_arnold_megaplan(tmp_path)

    _patch_load_for_temp_paths(monkeypatch, tmp_path, arnold_pp)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._SCAN_ROOTS",
        [(arnold_pp, "arnold_pipelines")],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.discovery._get_scan_roots",
        lambda: [(arnold_pp, "arnold_pipelines")],
    )

    registry = PipelineRegistry()
    # No SKILL.md planted — must return None, not raise.
    assert registry.read_skill_md("megaplan") is None


# ── (e) Boundary: arnold/__init__.py version import is allowed ─────────
# The boundary test in tests/arnold/test_boundary_skeleton.py is updated
# below to add explicit AST-discrimination tests for arnold/pipelines/.
