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


def _run_without_cloud(script: str, *, cwd: Path, home: Path) -> subprocess.CompletedProcess[str]:
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


def test_core_commands_work_when_cloud_import_fails(tmp_path: Path) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    home = tmp_path / "home"
    root.mkdir()
    project_dir.mkdir()
    home.mkdir()

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("launch from file\n", encoding="utf-8")
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
    state_path = tmp_path / "chain_state.json"
    state_path.write_text(
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
        import types

        from pathlib import Path

        root = Path({str(root)!r})
        project_dir = Path({str(project_dir)!r})
        spec_path = Path({str(spec_path)!r})
        idea_file = Path({str(idea_file)!r})

        fake_auto = types.ModuleType("megaplan.auto")

        class DriverOutcome:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_auto.DEFAULT_MAX_ITERATIONS = 200
        fake_auto.DEFAULT_PHASE_TIMEOUT_SECONDS = 3600
        fake_auto.DEFAULT_POLL_SLEEP_SECONDS = 1.0
        fake_auto.DEFAULT_STALL_THRESHOLD = 5
        fake_auto.DEFAULT_STATUS_TIMEOUT_SECONDS = 60
        fake_auto.ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")
        fake_auto.DriverOutcome = DriverOutcome
        fake_auto.build_auto_parser = lambda _subparsers: None

        def drive(plan, *, cwd=None, **kwargs):
            return DriverOutcome(
                status="done",
                plan=plan,
                final_state="done",
                iterations=1,
                reason="",
                last_phase="review",
                events=[],
            )

        fake_auto.drive = drive
        sys.modules["arnold.pipelines.megaplan.auto"] = fake_auto
        sys.modules["arnold.pipelines.megaplan.cloud"] = None
        sys.modules.pop("arnold.pipelines.megaplan.cloud.cli", None)

        import arnold.pipelines.megaplan.cli as cli

        def run(argv):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli.main(argv)
            return exit_code, stdout.getvalue(), stderr.getvalue()

        chain_exit, chain_stdout, chain_stderr = run(
            ["chain", "status", "--spec", str(spec_path)]
        )
        init_exit, init_stdout, init_stderr = run(
            ["init", "--project-dir", str(project_dir), "--idea-file", str(idea_file), "--auto-start"]
        )

        print(json.dumps({{
            "chain_exit": chain_exit,
            "chain_payload": json.loads(chain_stdout),
            "chain_stderr": chain_stderr,
            "init_exit": init_exit,
            "init_payload": json.loads(init_stdout),
            "init_stderr": init_stderr,
        }}))
        """
    )

    proc = _run_without_cloud(script, cwd=root, home=home)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["chain_exit"] == 0
    assert payload["chain_payload"]["summary"]["current_milestone"] == {"label": "m1", "index": 0}
    assert payload["init_exit"] == 0
    assert payload["init_payload"]["auto_outcome"]["status"] == "done"
    assert payload["init_payload"]["next_step"] == "plan"


def test_cloud_help_still_discoverable(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        megaplan_cli.main(["cloud", "--help"])

    assert info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: megaplan cloud" in output
    assert "status" in output
    assert "deploy" in output
