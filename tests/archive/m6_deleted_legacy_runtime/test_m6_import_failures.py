from __future__ import annotations

import subprocess
import sys
import tarfile
import textwrap
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


def _install_artifact_into_venv(
    tmp_path: Path, artifact: Path, *, venv_name: str = "venv"
) -> Path:
    """Create a clean venv, install *artifact* (with deps), return python path."""
    venv_dir = tmp_path / venv_name
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip = venv_dir / "bin" / "pip"
    python = venv_dir / "bin" / "python"

    # Install with dependencies so that imports like pydantic resolve.
    subprocess.run(
        [str(pip), "install", str(artifact)],
        check=True,
        capture_output=True,
        text=True,
    )
    return python


def _install_wheel_into_venv(tmp_path: Path, wheel: Path) -> Path:
    """Create a clean venv, install *wheel* (with deps), return python path."""
    return _install_artifact_into_venv(tmp_path, wheel)


def _install_sdist_into_venv(tmp_path: Path, sdist: Path) -> Path:
    """Create a clean venv, install *sdist* (with deps), return python path."""
    return _install_artifact_into_venv(tmp_path, sdist, venv_name="sdist-venv")


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


DELETED_IMPORT_PREFIXES = (
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan._pipeline",
    "arnold_pipelines.megaplan.stages",
    "arnold_pipelines.megaplan._compatibility",
)

DELETED_CLI_HELP_FRAGMENTS = (
    "arnold pipelines",
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan._pipeline",
    "arnold_pipelines.megaplan.stages",
    "arnold_pipelines.megaplan._compatibility",
    "megaplan init",
    "megaplan prep",
    "megaplan plan",
    "megaplan critique",
    "megaplan gate",
    "megaplan revise",
    "megaplan finalize",
    "megaplan execute",
    "megaplan review",
    "megaplan run",
)

WORKFLOW_HELP_SUBCOMMANDS = (
    "check",
    "manifest",
    "dot",
    "dry-run",
    "run",
    "resume",
    "describe",
)


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
# Installed-sdist runtime conformance
# ---------------------------------------------------------------------------


@pytest.mark.wheel_smoke
def test_sdist_install_imports_compile_and_cli_workflow(tmp_path: Path) -> None:
    """A clean install from the sdist must expose the same shipped runtime
    surface as the wheel smoke path."""
    sdist = _build_sdist(tmp_path)
    python = _install_sdist_into_venv(tmp_path, sdist)
    arnold = python.parent / "arnold"

    probe = (
        "from importlib.resources import files\n"
        "import arnold.kernel\n"
        "import arnold.pipeline\n"
        "import arnold.workflow\n"
        "import arnold_pipelines.megaplan as mp\n"
        "manifest = mp.build_and_compile_pipeline()\n"
        "assert manifest.id == 'megaplan'\n"
        "assert manifest.manifest_hash.startswith('sha256:')\n"
        "assert (files('arnold') / 'py.typed').is_file()\n"
        "assert (files('arnold_pipelines.megaplan') / 'py.typed').is_file()\n"
        "assert (files('arnold_pipelines.evidence_pack') / 'pipeline_ids.json').is_file()\n"
        "assert (files('arnold_pipelines.megaplan.data._composed') / 'claude_skill.md').is_file()\n"
        'print("ok")\n'
    )
    rc, stdout, stderr = _run_probe(python, probe, cwd=tmp_path)
    assert rc == 0, stderr
    assert stderr == ""
    assert stdout.splitlines()[-1] == "ok"

    for subcommand in ("check", "manifest", "dry-run"):
        result = subprocess.run(
            [
                str(arnold),
                "workflow",
                subcommand,
                "--module",
                "arnold_pipelines.megaplan.pipelines.jokes:build_pipeline",
            ],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, (
            f"arnold workflow {subcommand} failed after sdist install: {result.stderr}"
        )
        if subcommand in {"check", "manifest"}:
            assert "sha256:" in result.stdout


@pytest.mark.wheel_smoke
def test_sdist_install_deleted_surfaces_fail(tmp_path: Path) -> None:
    """Deleted modules and top-level legacy symbols must remain absent when the
    package is installed from the sdist, not only from the wheel."""
    sdist = _build_sdist(tmp_path)
    python = _install_sdist_into_venv(tmp_path, sdist)

    deleted_submodules = (
        "arnold_pipelines.megaplan._pipeline",
        "arnold_pipelines.megaplan._pipeline.builder",
        "arnold_pipelines.megaplan._pipeline.runtime",
        "arnold_pipelines.megaplan._pipeline.dispatch",
        "arnold_pipelines.megaplan._pipeline.types",
        "arnold_pipelines.megaplan.stages",
        "arnold_pipelines.megaplan.stages.inprocess_step",
        "arnold_pipelines.megaplan._compatibility",
        "arnold.pipelines.megaplan",
    )
    deleted_symbols = (
        "build_legacy_pipeline",
        "compile_planning_pipeline",
        "WorkflowManifest",
        "run_pipeline",
        "InProcessHandlerStep",
        "HandlerStep",
        "Stage",
    )

    probe_lines = [
        "import importlib",
        "import sys",
        "import arnold_pipelines.megaplan as mp",
    ]
    for mod_name in deleted_submodules:
        probe_lines.append(
            f"try:\n"
            f"    importlib.import_module({mod_name!r})\n"
            f"    raise SystemExit('deleted module {mod_name} is still importable')\n"
            f"except ModuleNotFoundError:\n"
            f"    pass\n"
        )
    probe_lines.append(f"deleted_symbols = {deleted_symbols!r}")
    probe_lines.append(
        "for name in deleted_symbols:\n"
        "    if hasattr(mp, name):\n"
        "        raise SystemExit(f'deleted symbol {name!r} is still exposed')\n"
        "    try:\n"
        "        exec(f'from arnold_pipelines.megaplan import {name}')\n"
        "        raise SystemExit(f'deleted symbol {name!r} is still importable')\n"
        "    except ImportError:\n"
        "        pass\n"
    )
    probe_lines.append(
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
        "    raise SystemExit(f'sys.modules leaks deleted prefixes: {leaked}')\n"
        "print('ok')"
    )

    rc, stdout, stderr = _run_probe(python, "\n".join(probe_lines), cwd=tmp_path)
    assert rc == 0, stderr
    assert stdout == "ok"


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


@pytest.mark.wheel_smoke
def test_installed_console_help_lacks_deleted_commands_and_paths(
    tmp_path: Path,
) -> None:
    """Collect help from the installed console script and scan the shipped CLI
    surface for deleted command strings and legacy import paths."""
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)
    arnold = python.parent / "arnold"

    commands = [
        ("arnold --help", [str(arnold), "--help"]),
        ("arnold workflow --help", [str(arnold), "workflow", "--help"]),
        *(
            (
                f"arnold workflow {subcommand} --help",
                [str(arnold), "workflow", subcommand, "--help"],
            )
            for subcommand in WORKFLOW_HELP_SUBCOMMANDS
        ),
    ]

    collected: list[tuple[str, str]] = []
    for label, command in commands:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, (
            f"{label} failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        collected.append((label, result.stdout + result.stderr))

    violations = [
        (label, fragment)
        for label, output in collected
        for fragment in DELETED_CLI_HELP_FRAGMENTS
        if fragment in output
    ]
    assert not violations, f"installed CLI help leaked deleted strings: {violations}"


@pytest.mark.wheel_smoke
def test_installed_runtime_import_tracing_lacks_deleted_prefixes(
    tmp_path: Path,
) -> None:
    """Trace dynamic import surfaces in a clean installed runtime.

    The probe wraps importlib.import_module, builtins.__import__, package
    __getattr__, entry point enumeration/loading, and shipped registry reads so
    indirect lazy loads of deleted prefixes are recorded deterministically.
    """
    wheel = _build_wheel(tmp_path)
    python = _install_wheel_into_venv(tmp_path, wheel)

    probe = textwrap.dedent(
        f"""
        import builtins
        import importlib
        import importlib.metadata as metadata
        import sys

        deleted_prefixes = {DELETED_IMPORT_PREFIXES!r}
        events = []

        def record(kind, name):
            if isinstance(name, str):
                events.append((kind, name))

        original_import = builtins.__import__

        def traced_import(name, globals=None, locals=None, fromlist=(), level=0):
            record("__import__", name)
            for item in fromlist or ():
                if isinstance(item, str):
                    record("__import__.fromlist", f"{{name}}.{{item}}")
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = traced_import

        original_import_module = importlib.import_module

        def traced_import_module(name, package=None):
            record("importlib.import_module", name)
            return original_import_module(name, package)

        importlib.import_module = traced_import_module

        original_entry_points = metadata.entry_points

        def traced_entry_points(*args, **kwargs):
            record("metadata.entry_points", "importlib.metadata.entry_points")
            eps = original_entry_points(*args, **kwargs)
            try:
                iterable = eps.select()
            except AttributeError:
                iterable = eps
            for ep in iterable:
                value = getattr(ep, "value", "")
                record("metadata.entry_point", value)
            return eps

        metadata.entry_points = traced_entry_points

        original_distribution = metadata.distribution

        def traced_distribution(name):
            record("metadata.distribution", name)
            dist = original_distribution(name)
            for ep in dist.entry_points:
                record("metadata.distribution.entry_point", ep.value)
            return dist

        metadata.distribution = traced_distribution

        original_ep_load = metadata.EntryPoint.load

        def traced_ep_load(self):
            record("metadata.EntryPoint.load", self.value)
            return original_ep_load(self)

        metadata.EntryPoint.load = traced_ep_load

        import arnold.cli as cli
        assert cli.main(["--help"]) == 0

        dist = metadata.distribution("arnold")
        for ep in dist.entry_points:
            if ep.group == "console_scripts":
                loaded = ep.load()
                record("metadata.loaded_entry_point", f"{{ep.name}}={{loaded.__module__}}")

        import arnold_pipelines.megaplan as megaplan_pkg
        original_getattr = getattr(megaplan_pkg, "__getattr__", None)

        def traced_package_getattr(name):
            record("package.__getattr__", f"arnold_pipelines.megaplan.{{name}}")
            if original_getattr is None:
                raise AttributeError(name)
            return original_getattr(name)

        megaplan_pkg.__getattr__ = traced_package_getattr
        for attr in (
            "build_legacy_pipeline",
            "compile_planning_pipeline",
            "WorkflowManifest",
            "run_pipeline",
            "Stage",
        ):
            try:
                getattr(megaplan_pkg, attr)
            except AttributeError:
                pass
            else:
                raise SystemExit(f"deleted attr {{attr!r}} resolved")

        import arnold_pipelines.discovery as discovery
        discovery.discover_shipped_pipelines()

        import arnold_pipelines.megaplan.registry as registry
        record("registry.access", "arnold_pipelines.megaplan.registry")
        registry.registered_pipelines()
        registry.describe_pipeline("planning")

        leaked_events = [
            (kind, name)
            for kind, name in events
            if any(name == prefix or name.startswith(prefix + ".") for prefix in deleted_prefixes)
        ]
        if leaked_events:
            raise SystemExit(f"deleted prefix import event leakage: {{leaked_events}}")

        for name in (
            "arnold_pipelines.megaplan._pipeline",
            "arnold_pipelines.megaplan._pipeline.builder",
            "arnold_pipelines.megaplan.stages",
            "arnold_pipelines.megaplan._compatibility",
            "arnold.pipelines.megaplan",
        ):
            try:
                importlib.import_module(name)
            except ModuleNotFoundError:
                pass
            else:
                raise SystemExit(f"deleted module {{name!r}} imported")

        leaked_modules = [
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(prefix + ".") for prefix in deleted_prefixes)
        ]
        if leaked_modules:
            raise SystemExit(f"deleted prefix sys.modules leakage: {{leaked_modules}}")
        print("ok")
        """
    )

    rc, stdout, stderr = _run_probe(python, probe, cwd=tmp_path)
    assert rc == 0, stderr
    assert stderr == ""
    assert stdout.splitlines()[-1] == "ok"


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
