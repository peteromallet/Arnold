from __future__ import annotations

import ast
import configparser
import importlib
import subprocess
import sys
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

    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert expected_package_files <= names
        entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entry_points = configparser.ConfigParser()
        entry_points.read_string(archive.read(entry_points_name).decode())
        assert entry_points["console_scripts"]["agentbox"] == "agentbox.cli:main"

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    python = venv_dir / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
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
    result = subprocess.run([str(python), "-c", probe], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


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
