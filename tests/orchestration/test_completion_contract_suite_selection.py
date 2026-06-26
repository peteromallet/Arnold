from __future__ import annotations

import json
import shlex
import sys

from arnold_pipelines.megaplan.orchestration.completion_contract import (
    CompletionContext,
    CompletionSubject,
    GreenSuiteProvider,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import _pytest_command


def _ctx(tmp_path, state):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    return CompletionContext(
        plan_dir=plan_dir,
        project_dir=tmp_path,
        state=state,
        subject=CompletionSubject(kind="plan", name="p", to_state="done"),
        git_base_ref=None,
    )


def test_green_suite_backfills_scoped_command_from_finalize_selection(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path)}})
    (ctx.plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_command": None,
                "test_selection": {
                    "command_override": "pytest tests/test_narrow.py",
                },
            }
        ),
        encoding="utf-8",
    )

    config, _timeout = GreenSuiteProvider._suite_config_and_timeout(ctx)

    assert config["test_command"] == "pytest tests/test_narrow.py"
    assert config["plan_dir"] == str(ctx.plan_dir)


def test_green_suite_prefers_recorded_baseline_command(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path)}})
    (ctx.plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_command": "pytest tests/test_baseline.py",
                "test_selection": {
                    "command_override": "pytest tests/test_selection.py",
                },
            }
        ),
        encoding="utf-8",
    )

    config, _timeout = GreenSuiteProvider._suite_config_and_timeout(ctx)

    assert config["test_command"] == "pytest tests/test_baseline.py"


def test_pytest_command_uses_current_python_for_default_and_bare_pytest():
    default_parts = shlex.split(_pytest_command(None))
    explicit_parts = shlex.split(_pytest_command("pytest tests/test_narrow.py"))

    assert default_parts[:3] == [sys.executable, "-m", "pytest"]
    assert explicit_parts[:4] == [sys.executable, "-m", "pytest", "tests/test_narrow.py"]
