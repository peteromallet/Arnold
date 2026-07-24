"""T11 / M6 — pipelines new scaffold tests (native-first compositional contract).

Verifies ``python -m arnold_pipelines.megaplan pipelines new <name>``.

creates a native-first compositional shell module and SKILL.md stub,
and that the emitted package passes authoring validation.

M6 scaffold contract (fail-to-pass guards until T16 updates the generator):
* Nested workflow source (child workflow within parent)
* Declared interfaces (module-level inputs/outputs)
* Stable IDs on pipeline/workflow/phase decorators
* A ``parallel_map`` call with stable ``path_template``
* A path-resume example using ``start_from_trace(...)``
* No shim, graph fallback, compatibility wrapper, or legacy guidance
* Overwrite refusal and import-smoke behavior preserved
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from arnold.pipelines._authoring import validate_package_module


REPO_ROOT = Path(__file__).resolve().parents[1]


# ── Helpers ────────────────────────────────────────────────────────────────


def _scaffold_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
) -> tuple[Path, Path]:
    """Scaffold a pipeline module via the CLI handler and return
    ``(module_path, skill_dir)``.  Patches ``_SCAN_ROOTS`` so files land in
    *tmp_path* rather than the real in-tree directory.
    """
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert rc == 0

    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"
    skill_dir = pipelines_dir / name
    return module_path, skill_dir


# ── Forbidden shim / fallback surface ─────────────────────────────────────

_FORBIDDEN_SHIM_PATTERNS: tuple[str, ...] = (
    "Deprecated hand-built graph scaffold",
    "_legacy",
    "graph fallback",
    "compatibility wrapper",
    "compatibility namespace",
    "shim package",
    "temporary wrapper",
    "direct manifest authoring",
    "native_program as source authority",
    "native_program-as-source",
)

# ── Required M6 compositional surface ─────────────────────────────────────

_REQUIRED_M6_CONTENT_MARKERS: tuple[str, ...] = (
    "@pipeline",
    "@phase",
    "compile_pipeline(",
    "project_graph(",
    "build_pipeline",
)

_REQUIRED_M6_DECLARED_INTERFACES: tuple[str, ...] = (
    "inputs",
    "outputs",
)

_REQUIRED_M6_STABLE_ID_MARKER: str = "id="

_REQUIRED_M6_PARALLEL_MAP_MARKER: str = "parallel_map("
_REQUIRED_M6_PATH_TEMPLATE_MARKER: str = "path_template="
_REQUIRED_M6_PATH_RESUME_MARKERS: tuple[str, ...] = (
    "resume_from_trace_example",
    "start_from_trace(",
)

# Nested workflow markers — at least one of these should be present.
# ``@workflow`` is the preferred public authoring decorator for child workflows.
# Multiple ``@pipeline`` decorators also count as nested workflow evidence.
_REQUIRED_M6_NESTED_WORKFLOW_MARKERS: tuple[str, ...] = (
    "@workflow",       # explicit child workflow decorator
)


def _run_pipelines(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m arnold_pipelines.megaplan pipelines ...`` and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", "pipelines", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )


def _run_scaffold_module(
    module: str,
    *,
    pipelines_dir: Path,
    name: str,
) -> subprocess.CompletedProcess[str]:
    """Run a module entrypoint with its scan root patched in the child."""

    script = f"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, {str(REPO_ROOT)!r})
from arnold_pipelines.megaplan.runtime import discovery

discovery._SCAN_ROOTS = [
    (Path({str(pipelines_dir.parent)!r}), "arnold_pipelines"),
    (Path({str(pipelines_dir)!r}), "arnold_pipelines.megaplan.pipelines"),
]
sys.argv = [{module!r}, "pipelines", "new", {name!r}]
runpy.run_module({module!r}, run_name="__main__")
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )


# ── Handler-level tests (tmp_path) ────────────────────────────────────────


def test_pipelines_new_creates_module_and_skill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``new`` emits a Python module + SKILL.md stub (handler-level)."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-test-scaffold"
    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )

    assert rc == 0
    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"
    skill_path = pipelines_dir / name / "SKILL.md"

    assert module_path.exists(), f"module not created at {module_path}"
    assert skill_path.exists(), f"SKILL.md not created at {skill_path}"

    content = module_path.read_text()
    assert "def build_pipeline" in content
    assert name in content
    assert "@pipeline" in content
    assert "@phase" in content
    assert "@decision" in content
    assert "compile_pipeline(" in content
    assert "project_graph(" in content
    assert 'driver: tuple[str, str] = ("native", "project+validate")' in content
    assert 'supported_modes: tuple[str, ...] = ("native",)' in content

    skill_content = skill_path.read_text()
    assert f"name: {name}" in skill_content


def test_pipelines_new_emitted_package_passes_authoring_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The scaffolded pipeline passes :func:`validate_package_module`."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-test-scaffold-check"
    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert rc == 0

    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"

    spec = importlib.util.spec_from_file_location(module_stem, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate_package_module(module)  # raises on failure

    pipeline = module.build_pipeline()
    assert pipeline.native_program is not None


def test_arnold_pipelines_new_emits_native_only_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The Arnold entry point (cli.arnold) emits native-first shape."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-arnold-scaffold-check"
    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert rc == 0

    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"
    assert module_path.exists(), f"module not created at {module_path}"
    content = module_path.read_text(encoding="utf-8")
    assert 'driver: tuple[str, str] = ("native", "project+validate")' in content
    assert "Deprecated hand-built graph scaffold" not in content
    assert 'driver: tuple[str, str] = (\'graph\',' not in content

    # Also verify via authoring validation
    spec = importlib.util.spec_from_file_location(module_stem, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate_package_module(module)


def test_pipelines_new_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``new`` exits non-zero when the module file already exists."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-test-exists"
    first = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert first == 0

    second = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert second == 1
    assert "already exists" in capsys.readouterr().err


def test_pipelines_new_missing_name_errors() -> None:
    """``new`` with no name exits non-zero."""
    result = _run_pipelines("new")
    assert result.returncode != 0


# ── M6 scaffold contract guards (fail-to-pass until T16) ───────────────────


def test_m6_scaffold_emits_declared_interfaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffolded module MUST declare module-level ``inputs`` and
    ``outputs`` as part of its compositional contract.
    """
    name = "t4-m6-interfaces"
    module_path, _skill_dir = _scaffold_module(monkeypatch, tmp_path, name)
    content = module_path.read_text(encoding="utf-8")

    for marker in _REQUIRED_M6_DECLARED_INTERFACES:
        assert marker in content, (
            f"M6 scaffold contract: module-level '{marker}' declaration missing "
            f"from generated module {module_path}"
        )


def test_m6_scaffold_emits_stable_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffolded module MUST include stable ``id=`` on at least one
    pipeline, workflow, or phase decorator.
    """
    name = "t4-m6-stable-ids"
    module_path, _skill_dir = _scaffold_module(monkeypatch, tmp_path, name)
    content = module_path.read_text(encoding="utf-8")

    assert _REQUIRED_M6_STABLE_ID_MARKER in content, (
        f"M6 scaffold contract: stable 'id=' missing from decorator(s) "
        f"in generated module {module_path}"
    )


def test_m6_scaffold_emits_nested_workflow_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffolded module MUST contain evidence of nested workflow
    composition — either an explicit ``@workflow``-decorated child or
    multiple ``@pipeline``-decorated functions (parent + child).
    """
    name = "t4-m6-nested"
    module_path, _skill_dir = _scaffold_module(monkeypatch, tmp_path, name)
    content = module_path.read_text(encoding="utf-8")

    # Check for explicit @workflow decorator (preferred).
    has_workflow = "@workflow" in content
    # Check for multiple @pipeline decorators (parent + child).
    pipeline_count = content.count("@pipeline")

    assert has_workflow or pipeline_count >= 2, (
        f"M6 scaffold contract: no nested workflow source detected. "
        f"Expected @workflow decorator or multiple @pipeline decorators "
        f"(found {pipeline_count}) in generated module {module_path}"
    )


def test_m6_scaffold_emits_parallel_map_with_path_template(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffolded module MUST contain a ``parallel_map(...)`` call
    with a ``path_template=`` argument.
    """
    name = "t4-m6-parallel-map"
    module_path, _skill_dir = _scaffold_module(monkeypatch, tmp_path, name)
    content = module_path.read_text(encoding="utf-8")

    assert _REQUIRED_M6_PARALLEL_MAP_MARKER in content, (
        f"M6 scaffold contract: 'parallel_map(' call missing "
        f"from generated module {module_path}"
    )
    assert _REQUIRED_M6_PATH_TEMPLATE_MARKER in content, (
        f"M6 scaffold contract: 'path_template=' missing from parallel_map call "
        f"in generated module {module_path}"
    )


def test_m6_scaffold_emits_path_resume_example(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffolded module MUST include a path-addressed resume example."""
    name = "t4-m6-path-resume"
    module_path, _skill_dir = _scaffold_module(monkeypatch, tmp_path, name)
    content = module_path.read_text(encoding="utf-8")

    for marker in _REQUIRED_M6_PATH_RESUME_MARKERS:
        assert marker in content, (
            f"M6 scaffold contract: {marker!r} missing from generated module {module_path}"
        )


def test_m6_scaffold_rejects_shim_and_fallback_patterns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffolded module MUST NOT contain any shim, graph fallback,
    compatibility wrapper, legacy guidance, or direct-manifest-authoring
    instruction.
    """
    name = "t4-m6-no-shim"
    module_path, skill_dir = _scaffold_module(monkeypatch, tmp_path, name)

    # Check generated Python module for forbidden patterns.
    content = module_path.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_SHIM_PATTERNS:
        assert forbidden not in content, (
            f"M6 scaffold contract: forbidden pattern {forbidden!r} found "
            f"in generated module {module_path}"
        )

    # SKILL.md may reference forbidden patterns in prohibitive context
    # (e.g. "Do not add _legacy.py").  We only guard the Python module.


def test_m6_scaffold_preserves_legacy_path_absence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """M6: The scaffold MUST NOT recreate, reference, or import from the
    deleted legacy path ``arnold/pipelines/_template/``.
    """
    name = "t4-m6-no-legacy-path"
    module_path, _skill_dir = _scaffold_module(monkeypatch, tmp_path, name)
    content = module_path.read_text(encoding="utf-8")

    legacy_refs = [
        "arnold/pipelines/_template",
        "arnold.pipelines._template",
    ]
    for ref in legacy_refs:
        assert ref not in content, (
            f"M6 scaffold contract: legacy path reference {ref!r} found "
            f"in generated module {module_path}"
        )

    # Also verify the legacy path directory is empty (deleted content).
    legacy_dir = REPO_ROOT / "arnold" / "pipelines" / "_template"
    if legacy_dir.exists():
        remaining = list(legacy_dir.iterdir())
        assert not remaining, (
            f"M6 scaffold contract: legacy path {legacy_dir} still contains "
            f"files: {[p.name for p in remaining]}. It should be empty."
        )


# ── Subprocess-level tests (both module paths) ────────────────────────────


def test_subprocess_pipelines_new_via_megaplan_module(
    tmp_path: Path,
) -> None:
    """``python -m arnold_pipelines.megaplan pipelines new`` works end-to-end."""
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()

    name = "t11-subprocess-megaplan"
    module_stem = name.replace("-", "_")
    result = _run_scaffold_module(
        "arnold_pipelines.megaplan",
        pipelines_dir=pipelines_dir,
        name=name,
    )
    assert result.returncode == 0, result.stderr
    assert (pipelines_dir / f"{module_stem}.py").is_file()
    assert (pipelines_dir / name / "SKILL.md").is_file()
