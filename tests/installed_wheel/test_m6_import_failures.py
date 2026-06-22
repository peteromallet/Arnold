from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Shared helpers: build wheel + sdist, install wheel into clean venv
# ---------------------------------------------------------------------------


def _build_wheel(tmp_path: Path) -> Path:
    """Build a wheel and return its path."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(build_dir), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    wheels = list(build_dir.glob("*.whl"))
    assert wheels, "no wheel produced"
    return wheels[0]


def _build_sdist(tmp_path: Path) -> Path:
    """Build an sdist and return its path."""
    sdist_dir = tmp_path / "sdist"
    sdist_dir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "-o", str(sdist_dir), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    sdists = list(sdist_dir.glob("*.tar.gz"))
    assert sdists, "no sdist produced"
    return sdists[0]


def _install_wheel_into_venv(tmp_path: Path, wheel: Path) -> Path:
    """Create a clean venv, install *wheel* (with deps), return python path."""
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip = venv_dir / "bin" / "pip"
    python = venv_dir / "bin" / "python"

    # Install the wheel with dependencies so that imports like pydantic resolve.
    subprocess.run(
        [str(pip), "install", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    return python


# ---------------------------------------------------------------------------
# Probe helpers – return (returncode, stdout, stderr) from subprocess python
# ---------------------------------------------------------------------------


def _run_probe(python: Path, probe: str, *, cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        [str(python), "-c", probe],
        capture_output=True,
        text=True,
        cwd=cwd or str(REPO_ROOT),
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ---------------------------------------------------------------------------
# Installed-wheel import-failure probes
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_m6_deleted_public_imports_fail_in_installed_wheel(tmp_path: Path) -> None:
    """A clean install of the wheel must not expose the deleted public surfaces."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    probe = (
        "import importlib\n"
        'for name in ("megaplan", "arnold.pipelines.megaplan"):\n'
        "    try:\n"
        "        importlib.import_module(name)\n"
        "    except ModuleNotFoundError:\n"
        "        pass\n"
        "    else:\n"
        '        raise SystemExit(f"deleted module {name!r} is still importable")\n'
        "from arnold.pipeline import Pipeline, StepContext\n"
        'for name in ("Stage", "Edge", "ParallelStage", "PipelineBuilder", "run_pipeline"):\n'
        "    try:\n"
        '        exec(f"from arnold.pipeline import {name}")\n'
        "    except ImportError:\n"
        "        pass\n"
        "    else:\n"
        '        raise SystemExit(f"deleted symbol {name!r} is still importable")\n'
        'print("ok")\n'
    )
    rc, stdout, stderr = _run_probe(python, probe)
    assert rc == 0, stderr
    assert stdout == "ok"


@pytest.mark.wheel_smoke
def test_m6_deleted_submodules_fail_in_installed_wheel(tmp_path: Path) -> None:
    """Representative deleted submodules must raise ModuleNotFoundError in
    an installed wheel (not editable install)."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    deleted_submodules = (
        "arnold_pipelines.megaplan._pipeline",
        "arnold_pipelines.megaplan._pipeline.builder",
        "arnold_pipelines.megaplan._pipeline.runtime",
        "arnold_pipelines.megaplan._pipeline.dispatch",
        "arnold_pipelines.megaplan._pipeline.types",
        "arnold_pipelines.megaplan.stages",
        "arnold_pipelines.megaplan.stages.inprocess_step",
        "arnold_pipelines.megaplan._compatibility",
    )

    probe_lines = ["import importlib", "import sys"]
    for mod_name in deleted_submodules:
        # Build the probe text using test-time f-string expansion (mod_name is a
        # test variable, not a subprocess variable).  We deliberately do NOT use
        # !r inside the inner f-string quote delimiters to avoid the f-string
        # escaping bug noted in prior batch deviations.
        probe_lines.append(
            f"try:\n"
            f"    importlib.import_module({mod_name!r})\n"
            f"    raise SystemExit('deleted submodule {mod_name} is still importable')\n"
            f"except ModuleNotFoundError:\n"
            f"    pass\n"
        )
    probe_lines.append("print('ok')")
    probe = "\n".join(probe_lines)

    rc, stdout, stderr = _run_probe(python, probe)
    assert rc == 0, f"stderr: {stderr}"
    assert stdout == "ok"


@pytest.mark.wheel_smoke
def test_m6_deleted_top_level_symbols_fail_in_installed_wheel(tmp_path: Path) -> None:
    """Top-level legacy symbols must not be importable from the installed
    megaplan package."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    probe = (
        "import arnold_pipelines.megaplan as m\n"
        "deleted = (\n"
        "    'build_legacy_pipeline',\n"
        "    'compile_planning_pipeline',\n"
        "    'WorkflowManifest',\n"
        "    'run_pipeline',\n"
        "    'InProcessHandlerStep',\n"
        "    'HandlerStep',\n"
        "    'Stage',\n"
        ")\n"
        "# top-level hasattr/getattr probe\n"
        "for name in deleted:\n"
        "    if hasattr(m, name):\n"
        '        raise SystemExit(f"deleted symbol {name!r} is still exposed via getattr")\n'
        "# from-import probe\n"
        "for name in deleted:\n"
        "    try:\n"
        '        exec(f"from arnold_pipelines.megaplan import {name}")\n'
        '        raise SystemExit(f"deleted symbol {name!r} is still importable")\n'
        "    except ImportError:\n"
        "        pass\n"
        'print("ok")\n'
    )
    rc, stdout, stderr = _run_probe(python, probe)
    assert rc == 0, stderr
    assert stdout == "ok"


@pytest.mark.wheel_smoke
def test_m6_no_sys_modules_leakage_in_installed_wheel(tmp_path: Path) -> None:
    """After importing arnold_pipelines.megaplan in an installed wheel,
    sys.modules must not contain keys starting with deleted prefixes."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    probe = (
        "import sys\n"
        "import arnold_pipelines.megaplan\n"
        "deleted_prefixes = (\n"
        "    'arnold_pipelines.megaplan._pipeline',\n"
        "    'arnold_pipelines.megaplan.stages',\n"
        "    'arnold_pipelines.megaplan._compatibility',\n"
        ")\n"
        "leaked = [\n"
        "    key for key in sys.modules\n"
        "    if any(key == p or key.startswith(p + '.') for p in deleted_prefixes)\n"
        "]\n"
        "if leaked:\n"
        "    raise SystemExit(f'sys.modules leaks deleted prefixes: {leaked}')\n"
        'print("ok")\n'
    )
    rc, stdout, stderr = _run_probe(python, probe)
    assert rc == 0, stderr
    assert stdout == "ok"


# ---------------------------------------------------------------------------
# Wheel RECORD / namelist audit
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_wheel_record_and_namelist_lack_deleted_paths(tmp_path: Path) -> None:
    """Unpack the built wheel and assert zero files under deleted directories.

    Checks both the ZipFile namelist and the RECORD file inside the wheel.
    """
    wheel = _build_wheel(tmp_path)

    deleted_path_prefixes = (
        "arnold_pipelines/megaplan/_pipeline/",
        "arnold_pipelines/megaplan/stages/",
        "arnold_pipelines/megaplan/_compatibility.py",
        "arnold/pipelines/megaplan/",
    )

    with ZipFile(wheel) as whl:
        names = whl.namelist()

        # 1. Namelist audit: no entry starts with a deleted prefix
        violations = [
            name
            for name in names
            if any(
                name == prefix.rstrip("/") or name.startswith(prefix)
                for prefix in deleted_path_prefixes
            )
        ]
        assert not violations, (
            f"wheel namelist contains deleted paths: {violations}"
        )

        # 2. RECORD file audit: the RECORD must not list deleted paths
        record_entries = [
            name for name in names if name.endswith(".dist-info/RECORD")
        ]
        if record_entries:
            record_text = whl.read(record_entries[0]).decode("utf-8")
            record_lines = record_text.splitlines()
            record_paths = [
                line.split(",")[0] for line in record_lines if line.strip()
            ]
            record_violations = [
                rp
                for rp in record_paths
                if any(
                    rp == prefix.rstrip("/") or rp.startswith(prefix)
                    for prefix in deleted_path_prefixes
                )
            ]
            assert not record_violations, (
                f"wheel RECORD contains deleted paths: {record_violations}"
            )

        # 3. No .py file under deleted prefixes (deeper check)
        py_under_deleted = [
            name
            for name in names
            if name.endswith(".py")
            and any(
                name.startswith(prefix) for prefix in deleted_path_prefixes
            )
        ]
        assert not py_under_deleted, (
            f"wheel contains .py files under deleted prefixes: {py_under_deleted}"
        )

        # 4. No py.typed under deleted prefixes (type-checker leakage vector)
        py_typed_violations = [
            name
            for name in names
            if name.endswith("py.typed")
            and any(
                name.startswith(prefix) for prefix in deleted_path_prefixes
            )
        ]
        assert not py_typed_violations, (
            f"wheel contains py.typed under deleted prefixes: {py_typed_violations}"
        )


# ---------------------------------------------------------------------------
# Sdist tar member audit
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_sdist_lacks_deleted_paths(tmp_path: Path) -> None:
    """Unpack the sdist and assert zero members under deleted directories."""
    sdist = _build_sdist(tmp_path)

    deleted_path_prefixes = (
        "arnold_pipelines/megaplan/_pipeline/",
        "arnold_pipelines/megaplan/stages/",
        "arnold_pipelines/megaplan/_compatibility.py",
        "arnold/pipelines/megaplan/",
    )

    with tarfile.open(sdist, "r:gz") as tar:
        members = tar.getnames()

        violations = [
            name
            for name in members
            if any(
                name.endswith("/" + prefix.strip("/"))
                or name == prefix.rstrip("/")
                or (prefix.endswith("/") and name.startswith(prefix))
                or (not prefix.endswith("/") and name.endswith("/" + prefix))
                or (not prefix.endswith("/") and name == prefix)
                for prefix in deleted_path_prefixes
            )
        ]
        assert not violations, (
            f"sdist contains deleted paths: {violations}"
        )

        # .py files under deleted prefixes
        py_under_deleted = [
            name
            for name in members
            if name.endswith(".py")
            and any(
                name.startswith(prefix) for prefix in deleted_path_prefixes
            )
        ]
        assert not py_under_deleted, (
            f"sdist contains .py files under deleted prefixes: {py_under_deleted}"
        )


# ---------------------------------------------------------------------------
# importlib.metadata.entry_points() probe
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_entry_points_lack_deleted_modules(tmp_path: Path) -> None:
    """Console-script entry points must not reference deleted modules."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    probe = (
        "import importlib.metadata\n"
        "import json\n"
        "dist = importlib.metadata.distribution('arnold')\n"
        "eps = dist.entry_points\n"
        "deleted_modules = (\n"
        "    'arnold.pipelines.megaplan',\n"
        "    'megaplan',\n"
        "    'arnold_pipelines.megaplan._pipeline',\n"
        "    'arnold_pipelines.megaplan.stages',\n"
        "    'arnold_pipelines.megaplan._compatibility',\n"
        ")\n"
        "for ep in eps:\n"
        "    if any(dm in ep.value for dm in deleted_modules):\n"
        '        raise SystemExit(f"entry point {ep.name!r} references deleted module: {ep.value}")\n'
        'print("ok")\n'
    )
    rc, stdout, stderr = _run_probe(python, probe)
    assert rc == 0, stderr
    assert stdout == "ok"


# ---------------------------------------------------------------------------
# python -m probe
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_python_m_deleted_targets_fail(tmp_path: Path) -> None:
    """``python -m <deleted_module>`` must fail with ModuleNotFoundError."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    deleted_modules = (
        "arnold_pipelines.megaplan._pipeline",
        "arnold_pipelines.megaplan._pipeline.builder",
        "arnold_pipelines.megaplan._pipeline.runtime",
        "arnold_pipelines.megaplan._pipeline.dispatch",
        "arnold_pipelines.megaplan._pipeline.types",
        "arnold_pipelines.megaplan.stages",
        "arnold_pipelines.megaplan.stages.inprocess_step",
        "arnold_pipelines.megaplan._compatibility",
    )

    for mod_name in deleted_modules:
        result = subprocess.run(
            [str(python), "-m", mod_name],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            f"python -m {mod_name} unexpectedly succeeded"
        )
        # ModuleNotFoundError is the expected failure mode
        assert "ModuleNotFoundError" in result.stderr or "No module named" in result.stderr, (
            f"python -m {mod_name} failed with unexpected error: {result.stderr[:200]}"
        )


# ---------------------------------------------------------------------------
# Subprocess public-surface import + sys.modules enumeration (comprehensive)
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_public_surface_import_then_sys_modules_clean(tmp_path: Path) -> None:
    """Do a full public-surface import in a subprocess, then enumerate
    sys.modules for deleted-prefix leakage.

    This is the comprehensive integration probe: it first imports the canonical
    public surfaces (arnold_pipelines.megaplan, arnold.workflow, arnold.kernel,
    arnold.pipeline) and then checks that no deleted-prefix keys appear in
    sys.modules.
    """
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    probe = (
        "import sys\n"
        "# Import canonical public surfaces\n"
        "import arnold_pipelines.megaplan\n"
        "import arnold.workflow\n"
        "import arnold.kernel\n"
        "import arnold.pipeline\n"
        "# Check sys.modules for deleted prefixes\n"
        "deleted_prefixes = (\n"
        "    'arnold_pipelines.megaplan._pipeline',\n"
        "    'arnold_pipelines.megaplan.stages',\n"
        "    'arnold_pipelines.megaplan._compatibility',\n"
        "    'arnold.pipelines.megaplan',\n"
        ")\n"
        "leaked = [\n"
        "    key for key in sys.modules\n"
        "    if any(key == p or key.startswith(p + '.') for p in deleted_prefixes)\n"
        "]\n"
        "if leaked:\n"
        "    raise SystemExit(f'sys.modules leaks deleted prefixes after public import: {leaked}')\n"
        "# Also verify canonical imports work\n"
        "assert hasattr(arnold_pipelines.megaplan, 'build_pipeline'), 'build_pipeline missing'\n"
        "assert arnold.workflow is not None\n"
        "assert arnold.kernel is not None\n"
        "assert arnold.pipeline is not None\n"
        'print("ok")\n'
    )
    rc, stdout, stderr = _run_probe(python, probe)
    assert rc == 0, stderr
    assert stdout == "ok"


# ---------------------------------------------------------------------------
# Source-tree absence checks (no venv/wheel needed)
# ---------------------------------------------------------------------------


def test_source_tree_lacks_deleted_paths() -> None:
    """Deleted source roots are absent from the working tree."""
    deleted = [
        REPO_ROOT / "arnold" / "pipelines" / "megaplan",
        REPO_ROOT / "arnold" / "pipelines" / "jokes",
        REPO_ROOT / "arnold" / "pipelines" / "creative",
        REPO_ROOT / "arnold" / "pipelines" / "doc",
        REPO_ROOT / "arnold" / "pipelines" / "live_supervisor",
        REPO_ROOT / "arnold" / "pipelines" / "select_tournament",
        REPO_ROOT / "arnold" / "pipelines" / "writing_panel_strict.py",
        REPO_ROOT / "arnold" / "pipelines" / "writing_panel_strict",
        REPO_ROOT / "arnold" / "pipelines" / "evidence_pack",
        REPO_ROOT / "arnold" / "pipelines" / "_template",
        REPO_ROOT / "arnold" / "pipelines" / "_authoring.py",
        REPO_ROOT / "arnold" / "pipelines" / "__init__.py",
        REPO_ROOT / "scripts" / "backfill_step_receipts.py",
        REPO_ROOT / "scripts" / "m4_oracle_bisect.py",
        REPO_ROOT / "scripts" / "record_oracle_traces.py",
        REPO_ROOT / "scripts" / "silent_failure_census.py",
        REPO_ROOT / "tools" / "m4_oracle_bisect.py",
        REPO_ROOT / "_gen_corpus.py",
        REPO_ROOT / "_gen_golden_traces.py",
    ]
    present = [str(p.relative_to(REPO_ROOT)) for p in deleted if p.exists()]
    assert not present, f"deleted paths still present: {present}"


def test_source_tree_lacks_deleted_megaplan_dirs() -> None:
    """M4-deleted megaplan directories (_pipeline, stages, _compatibility.py)
    are absent from the working tree.

    Note: _pipeline may contain only __pycache__ residue from prior test runs;
    the check uses ``p.exists()`` which flags the directory.  Clean-up of stale
    caches is handled by T14; this test documents the expected steady state.
    """
    deleted_megaplan = [
        REPO_ROOT / "arnold_pipelines" / "megaplan" / "_pipeline",
        REPO_ROOT / "arnold_pipelines" / "megaplan" / "stages",
        REPO_ROOT / "arnold_pipelines" / "megaplan" / "_compatibility.py",
    ]
    present = [str(p.relative_to(REPO_ROOT)) for p in deleted_megaplan if p.exists()]
    assert not present, f"deleted megaplan paths still present: {present}"
