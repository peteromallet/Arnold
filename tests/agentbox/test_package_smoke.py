from __future__ import annotations

import ast
import configparser
import importlib
import pytest
import subprocess
import sys
import tarfile
import tomllib
import venv
from pathlib import Path
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTBOX_ROOT = REPO_ROOT / "agentbox"


def test_agentbox_imports_from_source_tree() -> None:
    assert importlib.import_module("agentbox").__name__ == "agentbox"
    assert importlib.import_module("agentbox.cli").main([]) == 0


def test_agentbox_help_runs_from_source_tree() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "agentbox", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: agentbox" in result.stdout


def test_agentbox_console_script_and_wheel_package_metadata() -> None:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    assert pyproject["project"]["scripts"]["agentbox"] == "agentbox.cli:main"
    assert "agentbox" in pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]


def test_agentbox_wheel_includes_package_and_installed_entrypoint(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(wheel_dir),
            str(REPO_ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    expected_package_files = {
        "agentbox/__init__.py",
        "agentbox/__main__.py",
        "agentbox/adapters.py",
        "agentbox/cli.py",
        "agentbox/config.py",
        "agentbox/git_worktree.py",
        "agentbox/host.py",
        "agentbox/locks.py",
        "agentbox/operations.py",
        "agentbox/reconcile.py",
        "agentbox/repos.py",
        "agentbox/run_dirs.py",
        "agentbox/tmux.py",
        "agentbox/worktrees.py",
        "agentbox/py.typed",
    }
    expected_resident_templates = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (AGENTBOX_ROOT / "templates" / "resident").iterdir()
        if path.is_file()
    }

    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert expected_package_files <= names
        assert expected_resident_templates <= names
        entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entry_points = configparser.ConfigParser()
        entry_points.read_string(archive.read(entry_points_name).decode())
        assert entry_points["console_scripts"]["agentbox"] == "agentbox.cli:main"

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    python = venv_dir / "bin" / "python"
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "PyYAML",
            "pydantic",
            "python-ulid",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    probe = (
        "from importlib.metadata import distribution\n"
        "dist = distribution('arnold')\n"
        "entry_points = {ep.name: ep.value for ep in dist.entry_points if ep.group == 'console_scripts'}\n"
        "assert entry_points['agentbox'] == 'agentbox.cli:main'\n"
        "import agentbox\n"
        "assert agentbox.__name__ == 'agentbox'\n"
    )
    result = subprocess.run(
        [str(python), "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    generated_repo = tmp_path / "installed-resident"
    generated_repo.mkdir()
    generation = subprocess.run(
        [
            str(python),
            "-m",
            "agentbox",
            "new-resident",
            "demo2",
            "--repo",
            str(generated_repo),
        ],
        cwd=generated_repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generation.returncode == 0, generation.stderr
    assert {
        generated_repo / ".omp" / "agents" / "demo2.md",
        generated_repo / ".agentbox" / "resident_profile.py",
        generated_repo / ".agentbox" / "resident.env.example",
        generated_repo / ".agentbox" / "run-resident",
        generated_repo / ".agentbox" / "demo2-resident.service",
    } <= {path for path in generated_repo.rglob("*") if path.is_file()}
    assert (generated_repo / ".agentbox" / "run-resident").stat().st_mode & 0o111


PACKAGE_TREES = ("agentbox", "arnold", "arnold_pipelines")

# Tracked data files deliberately absent from built artifacts.
#
# Wheel: the superseded babysit skill is dropped by
# [tool.hatch.build.targets.wheel].exclude; runtime skill installs source its
# content from megaplan/data/babysit_skill.md instead.
WHEEL_INTENTIONAL_GAPS = frozenset(
    {
        "arnold_pipelines/megaplan/skills/babysit/SKILL.md",
    }
)
#
# Sdist: dead legacy arnold/pipelines/** is globally excluded and has no
# runtime importer. The wheel still carries one stray py.typed marker from
# that tree because the broad "py.typed" artifact re-include overrides
# exclusion.
SDIST_INTENTIONAL_GAPS = frozenset(
    {
        "arnold/pipelines/evidence_pack/py.typed",
    }
)


def _tracked_package_data_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", *PACKAGE_TREES],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line and not line.endswith(".py")}


def test_wheel_ships_every_tracked_runtime_data_file(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(wheel_dir),
            str(REPO_ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    (wheel,) = wheel_dir.glob("*.whl")
    with ZipFile(wheel) as archive:
        shipped = set(archive.namelist())

    missing = _tracked_package_data_files() - shipped - WHEEL_INTENTIONAL_GAPS
    assert not missing, f"data files missing from wheel: {sorted(missing)}"


def test_sdist_ships_every_tracked_runtime_data_file(tmp_path: Path) -> None:
    if importlib.util.find_spec("build") is None or importlib.util.find_spec("hatchling") is None:
        pytest.skip("the 'build' and 'hatchling' packages are required to construct the sdist")
    dist_dir = tmp_path / "sdist"
    dist_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--no-isolation",
            "--outdir",
            str(dist_dir),
            str(REPO_ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    (archive_path,) = dist_dir.glob("*.tar.gz")
    prefix = f"{archive_path.name.removesuffix('.tar.gz')}/"
    with tarfile.open(archive_path) as archive:
        shipped = {
            name.removeprefix(prefix)
            for name in archive.getnames()
            if name.startswith(prefix)
        }

    missing = _tracked_package_data_files() - shipped - SDIST_INTENTIONAL_GAPS
    assert not missing, f"data files missing from sdist: {sorted(missing)}"


def test_agentbox_runtime_modules_do_not_import_megaplan_or_out_of_scope_surfaces() -> None:
    forbidden_import_prefixes = ("arnold.pipelines", "arnold_pipelines")
    allowed_megaplan_bridges = {
        "notify.py": {
            "arnold_pipelines.megaplan.resident.discord",
            "arnold_pipelines.megaplan.resident.runtime",
            "arnold_pipelines.megaplan.store",
        },
        "reset_notifications.py": {
            "arnold_pipelines.megaplan.resident.provenance",
            "arnold_pipelines.megaplan.resident.runtime",
        },
        "resident_profile.py": {
            "arnold_pipelines.megaplan.resident.reply_chain",
            "arnold_pipelines.megaplan.resident.timezone",
        },
        "services.py": {
            "arnold_pipelines.megaplan.cloud.runtime_manifest",
        },
        "cleanup.py": {
            "arnold_pipelines.megaplan.cloud.runtime_references",
        },
    }


    for path in AGENTBOX_ROOT.glob("*.py"):
        module = ast.parse(path.read_text(), filename=str(path))
        imports: list[str] = []
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        megaplan_imports = {
            imported
            for imported in imports
            if any(
                imported == prefix or imported.startswith(f"{prefix}.")
                for prefix in forbidden_import_prefixes
            )
        }
        if path.name in allowed_megaplan_bridges:
            assert megaplan_imports <= allowed_megaplan_bridges[path.name]
        else:
            assert not megaplan_imports, (
                f"{path} imports a Megaplan package surface: {sorted(megaplan_imports)}"

            )
        text = path.read_text().lower()
        assert "docker" not in text, f"{path} contains an out-of-scope docker token"

        # Bootstrap legitimately writes an OpenSSH config file as inert data.
        # Keep the architectural boundary focused on process invocation rather
        # than rejecting that configuration vocabulary wherever it appears.
        invoked_literal_commands: list[str] = []
        for node in ast.walk(module):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            command = node.args[0]
            if isinstance(command, ast.Constant) and isinstance(command.value, str):
                tokens = command.value.strip().split(maxsplit=1)
                if tokens:
                    invoked_literal_commands.append(tokens[0].lower())
            elif isinstance(command, (ast.List, ast.Tuple)) and command.elts:
                executable = command.elts[0]
                if isinstance(executable, ast.Constant) and isinstance(executable.value, str):
                    invoked_literal_commands.append(executable.value.lower())

        assert not {"docker", "ssh"}.intersection(invoked_literal_commands), (
            f"{path} invokes an out-of-scope runtime command: {invoked_literal_commands}"
        )
