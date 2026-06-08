from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import arnold.pipelines.megaplan.cli as megaplan_cli


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_without_bakeoff(script: str, *, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not existing_pythonpath
        else os.pathsep.join([str(REPO_ROOT), existing_pythonpath])
    )
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_core_commands_work_when_bakeoff_import_fails(tmp_path: Path) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    home = tmp_path / "home"
    root.mkdir()
    project_dir.mkdir()
    home.mkdir()

    chain_idea = tmp_path / "chain-idea.txt"
    chain_idea.write_text("chain status idea\n", encoding="utf-8")
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        textwrap.dedent(
            f"""\
            milestones:
              - label: m1
                idea: {chain_idea}
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "chain_state.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 0,
                "current_plan_name": "chain-plan",
                "last_state": "done",
                "completed": [],
            }
        ),
        encoding="utf-8",
    )

    script = textwrap.dedent(
        f"""\
        import contextlib
        import io
        import json
        import sys

        from pathlib import Path

        project_dir = Path({str(project_dir)!r})
        spec_path = Path({str(spec_path)!r})

        sys.modules["arnold.pipelines.megaplan.bakeoff"] = None
        sys.modules["arnold.pipelines.megaplan.bakeoff.cli"] = None
        sys.modules["arnold.pipelines.megaplan.bakeoff.judge"] = None

        import arnold.pipelines.megaplan.cli as cli

        def run(argv):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli.main(argv)
            return exit_code, stdout.getvalue(), stderr.getvalue()

        init_exit, init_stdout, init_stderr = run(
            ["init", "--project-dir", str(project_dir), "--name", "core-plan", "core idea"]
        )
        status_exit, status_stdout, status_stderr = run(["status", "--plan", "core-plan"])
        list_exit, list_stdout, list_stderr = run(["list", "--no-tree"])
        chain_exit, chain_stdout, chain_stderr = run(["chain", "status", "--spec", str(spec_path)])

        print(json.dumps({{
            "init_exit": init_exit,
            "init_payload": json.loads(init_stdout),
            "init_stderr": init_stderr,
            "status_exit": status_exit,
            "status_payload": json.loads(status_stdout),
            "status_stderr": status_stderr,
            "list_exit": list_exit,
            "list_payload": json.loads(list_stdout),
            "list_stderr": list_stderr,
            "chain_exit": chain_exit,
            "chain_payload": json.loads(chain_stdout),
            "chain_stderr": chain_stderr,
        }}))
        """
    )

    proc = _run_without_bakeoff(script, cwd=project_dir, home=home)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["init_exit"] == 0
    assert payload["init_payload"]["plan"] == "core-plan"
    assert payload["status_exit"] == 0
    assert payload["status_payload"]["plan"] == "core-plan"
    assert payload["list_exit"] == 0
    assert payload["list_payload"]["plans"][0]["name"] == "core-plan"
    assert payload["chain_exit"] == 0
    assert payload["chain_payload"]["summary"]["current_milestone"] == {"label": "m1", "index": 0}


def test_top_level_help_lists_bakeoff(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        megaplan_cli.main(["--help"])

    assert info.value.code == 0
    output = capsys.readouterr().out
    assert "bakeoff" in output


def test_bakeoff_help_still_discoverable(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        megaplan_cli.main(["bakeoff", "--help"])

    assert info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: megaplan bakeoff" in output
    for command in ["run", "status", "tail", "compare", "pick", "merge", "resume", "abandon"]:
        assert command in output
