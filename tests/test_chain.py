"""Tests for megaplan.chain — the chain driver subcommand."""
from __future__ import annotations

import argparse
import ast
import inspect
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import ANY, patch

import pytest
import yaml

from arnold.pipelines.megaplan.auto import DriverOutcome
from arnold.pipelines.megaplan import chain as chain_module 
from arnold.pipelines.megaplan.chain import (
    ChainState,
    MilestoneSpec,
    _commit_and_push_phase,
    _command_env,
    _enable_auto_merge,
    _pr_state,
    _run_command,
    _should_retry_gh_without_env,
    _state_path_for,
    format_chain_status,
    load_chain_state,
    load_spec,
    run_chain,
    run_chain_cli,
    save_chain_state,
)
from arnold.pipelines.megaplan.supervisor.state import load_supervisor_state
from arnold.pipelines.megaplan.types import CliError


def _write_spec(tmp_path: Path, spec_dict: dict, *, name: str = "chain.yaml") -> Path:
    spec_path = tmp_path / name
    spec_path.write_text(yaml.safe_dump(spec_dict), encoding="utf-8")
    return spec_path


def _touch_idea(tmp_path: Path, name: str, body: str = "an idea") -> Path:
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir(exist_ok=True)
    path = ideas_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def _fake_outcome(plan: str, status: str = "done") -> DriverOutcome:
    return DriverOutcome(
        status=status, plan=plan, final_state=status, iterations=1, reason=""
    )


def _write_execute_plan_state(root: Path, plan: str, state: str) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan,
                "current_state": state,
                "iteration": 1,
                "config": {"project_dir": str(root)},
                "meta": {},
                "history": [{"step": "execute", "result": "blocked"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_dir


def _write_blocked_execute_batch(
    root: Path,
    plan: str,
    task_updates: list[dict[str, object]],
) -> Path:
    plan_dir = _write_execute_plan_state(root, plan, "blocked")
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": task_updates}, indent=2) + "\n",
        encoding="utf-8",
    )
    return plan_dir


def _write_authoritative_execution_batch(root: Path, plan: str, state: str = "done") -> Path:
    plan_dir = _write_execute_plan_state(root, plan, state)
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["arnold/pipelines/megaplan/chain/__init__.py"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_dir


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"{name!r} subparser not found")


def _long_options(parser: argparse.ArgumentParser) -> set[str]:
    return {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }


def _static_long_option_literals(func: object) -> set[str]:
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("--")
    }


class _CliSmokeDriver:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = list(statuses)
        self.plans: list[str] = []

    def drive(self, request) -> DriverOutcome:
        self.plans.append(request.plan)
        status = self.statuses.pop(0)
        return DriverOutcome(
            status=status,
            plan=request.plan,
            final_state="done" if status == "done" else status,
            iterations=len(self.plans),
            reason=f"status:{status}",
            last_phase="execute",
        )


class _CliSmokePackRunner:
    def __init__(self) -> None:
        self.nodes: list[str] = []

    def prepare_plan(self, *, root: Path, node) -> str:
        self.nodes.append(node.node_id)
        plan_name = f"cli-smoke-{node.node_id}-{self.nodes.count(node.node_id)}"
        plan_dir = root / ".megaplan" / "plans" / plan_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        state_payload = {
            "name": plan_name,
            "config": {"robustness": "standard"},
        }
        if node.node_id == "a":
            state_payload.update(
                {
                    "current_state": "awaiting_pr_merge",
                    "resume_cursor": {"kind": "awaiting_pr_merge", "pr_number": 42},
                    "pr_number": 42,
                }
            )
        else:
            state_payload["current_state"] = "done"
        (plan_dir / "state.json").write_text(
            json.dumps(state_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        return plan_name


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------


def test_load_spec_parses_milestones_and_seed(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": "seed-plan-20260415"},
            "base_branch": "setup/cloud-chain",
            "milestones": [
                {
                    "label": "m1",
                    "idea": str(idea),
                    "branch": "mp/m1",
                    "profile": "apex",
                    "robustness": "standard",
                    "vendor": "codex",
                    "depth": "high",
                    "critic": "kimi",
                    "with_prep": True,
                    "with_feedback": True,
                    "deepseek_provider": "direct",
                    "phase_model": ["plan=claude:high", "revise=claude:high"],
                    "bakeoff": {"enabled": True, "arms": ["apex", "all-claude", "all-codex"]},
                    "notes": "contract seam",
                },
            ],
            "on_failure": {"abort": "stop_chain"},
            "on_escalate": {"abort": "skip_milestone"},
        },
    )
    spec = load_spec(spec_path)
    assert spec.seed_plan == "seed-plan-20260415"
    assert spec.base_branch == "setup/cloud-chain"
    assert len(spec.milestones) == 1
    assert spec.milestones[0] == MilestoneSpec(
        label="m1",
        idea=str(idea),
        branch="mp/m1",
        profile="apex",
        robustness="standard",
        vendor="codex",
        depth="high",
        critic="kimi",
        with_prep=True,
        with_feedback=True,
        deepseek_provider="direct",
        phase_model=["plan=claude:high", "revise=claude:high"],
        bakeoff={"enabled": True, "arms": ["apex", "all-claude", "all-codex"]},
        notes="contract seam",
    )
    assert spec.on_failure == "stop_chain"
    assert spec.on_escalate == "skip_milestone"
    assert spec.merge_policy == "auto"


def test_load_spec_defaults_base_branch_to_main(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})

    assert load_spec(spec_path).base_branch == "main"


def test_load_spec_rejects_unknown_base_key_with_hint(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"base": "setup/cloud", "milestones": [{"label": "m1", "idea": str(idea)}]},
    )

    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)

    assert excinfo.value.code == "invalid_spec"
    assert "did you mean `base_branch`" in excinfo.value.message


def test_load_spec_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea)}], "surprise": True},
    )

    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)

    assert excinfo.value.code == "invalid_spec"
    assert "`surprise`" in excinfo.value.message


@pytest.mark.parametrize("value", ["", "   ", 42, ["main"]])
def test_load_spec_rejects_invalid_base_branch(tmp_path: Path, value: object) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"base_branch": value, "milestones": [{"label": "m1", "idea": str(idea)}]},
    )

    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)

    assert "`base_branch` must be a non-empty string" in excinfo.value.message


def test_load_spec_parses_review_merge_policy(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "merge_policy": "review",
            "milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}],
        },
    )
    assert load_spec(spec_path).merge_policy == "review"


def test_load_spec_parses_max_stall_iterations_driver_knob(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "driver": {"max_stall_iterations": 12},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )

    assert load_spec(spec_path).stall_threshold == 12


def test_load_spec_keeps_stall_threshold_as_compat_driver_knob(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "driver": {"stall_threshold": 9},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )

    assert load_spec(spec_path).stall_threshold == 9


def test_load_spec_rejects_bad_merge_policy(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, {"merge_policy": "later", "milestones": []})
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert "merge_policy" in excinfo.value.message


# ---------------------------------------------------------------------------
# T2: Chain-level policy parsing (prerequisite_policy, validation_policy,
#     review_policy.clean_milestone_pr)
# ---------------------------------------------------------------------------


def test_load_spec_defaults_policy_fields(tmp_path: Path) -> None:
    """Existing YAML without policy fields parses with conservative defaults."""
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    spec = load_spec(spec_path)
    assert spec.prerequisite_policy == "none"
    assert spec.validation_policy == "none"
    assert spec.review_policy == {"clean_milestone_pr": "auto"}
    # merge_policy must also still default correctly
    assert spec.merge_policy == "auto"


def test_load_spec_parses_explicit_prerequisite_policy(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "prerequisite_policy": "required",
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    spec = load_spec(spec_path)
    assert spec.prerequisite_policy == "required"
    assert spec.validation_policy == "none"  # still default
    assert spec.review_policy == {"clean_milestone_pr": "auto"}  # still default


def test_load_spec_parses_explicit_validation_policy(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "validation_policy": "required",
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    spec = load_spec(spec_path)
    assert spec.validation_policy == "required"


def test_load_spec_parses_nested_review_policy(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "review_policy": {"clean_milestone_pr": "manual"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    spec = load_spec(spec_path)
    assert spec.review_policy == {"clean_milestone_pr": "manual"}


def test_load_spec_parses_all_policies_together(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "prerequisite_policy": "required",
            "validation_policy": "required",
            "review_policy": {"clean_milestone_pr": "manual"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    spec = load_spec(spec_path)
    assert spec.prerequisite_policy == "required"
    assert spec.validation_policy == "required"
    assert spec.review_policy == {"clean_milestone_pr": "manual"}


def test_load_spec_rejects_invalid_prerequisite_policy(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"prerequisite_policy": "sometimes", "milestones": []},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "prerequisite_policy" in excinfo.value.message


def test_load_spec_rejects_invalid_validation_policy(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"validation_policy": "maybe", "milestones": []},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "validation_policy" in excinfo.value.message


def test_load_spec_rejects_invalid_clean_milestone_pr(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"review_policy": {"clean_milestone_pr": "never"}, "milestones": []},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "clean_milestone_pr" in excinfo.value.message


def test_load_spec_rejects_non_mapping_review_policy(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"review_policy": "auto", "milestones": []},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "review_policy" in excinfo.value.message


def test_load_spec_rejects_missing_label(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, {"milestones": [{"idea": "/tmp/x.txt"}]})
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"


def test_load_spec_parses_depends_on_in_order(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "m5-eval", "idea": "/tmp/a.txt"},
                {"label": "m5-cal", "idea": "/tmp/b.txt", "depends_on": ["m5-eval"]},
            ]
        },
    )
    spec = load_spec(spec_path)
    assert spec.milestones[1].depends_on == ["m5-eval"]
    # A bare string is normalized to a single-element list.
    assert spec.milestones[0].depends_on == []


def test_load_spec_accepts_depends_on_string(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "a", "idea": "/tmp/a.txt"},
                {"label": "b", "idea": "/tmp/b.txt", "depends_on": "a"},
            ]
        },
    )
    spec = load_spec(spec_path)
    assert spec.milestones[1].depends_on == ["a"]


def test_load_spec_rejects_depends_on_listed_after(tmp_path: Path) -> None:
    # m5-cal depends on m5-eval but is listed BEFORE it -> fail loud.
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "m5-cal", "idea": "/tmp/b.txt", "depends_on": ["m5-eval"]},
                {"label": "m5-eval", "idea": "/tmp/a.txt"},
            ]
        },
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "listed before" in excinfo.value.message


def test_load_spec_rejects_depends_on_unknown(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "a", "idea": "/tmp/a.txt", "depends_on": ["ghost"]}]},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "unknown milestone" in excinfo.value.message


def test_load_spec_rejects_depends_on_self(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "a", "idea": "/tmp/a.txt", "depends_on": ["a"]}]},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert excinfo.value.code == "invalid_spec"
    assert "itself" in excinfo.value.message


def test_load_spec_rejects_bad_failure_action(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [], "on_failure": {"abort": "nonsense"}},
    )
    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)
    assert "on_failure.abort" in excinfo.value.message


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vendor", "openai"),
        ("depth", "ultra"),
        ("critic", "claude"),
        ("deepseek_provider", "openrouter"),
    ],
)
def test_load_spec_rejects_invalid_milestone_rubric_choice(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), field: value}]},
    )

    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)

    assert f"milestones[0].{field} must be one of" in excinfo.value.message


def test_load_spec_parses_prep_direction(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": str(idea),
                    "prep_direction": "  focus on the shutdown path  ",
                }
            ]
        },
    )
    spec = load_spec(spec_path)
    assert spec.milestones[0].prep_direction == "focus on the shutdown path"


def test_load_spec_defaults_prep_direction_none(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea)}]},
    )
    spec = load_spec(spec_path)
    assert spec.milestones[0].prep_direction is None


def test_load_spec_rejects_blank_prep_direction(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "prep_direction": "   "}]},
    )
    with pytest.raises(CliError) as info:
        load_spec(spec_path)
    assert "prep_direction" in info.value.message


def test_load_spec_rejects_non_string_prep_direction(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "prep_direction": 7}]},
    )
    with pytest.raises(CliError) as info:
        load_spec(spec_path)
    assert "prep_direction" in info.value.message


@pytest.mark.parametrize("field", ["with_prep", "with_feedback"])
def test_load_spec_rejects_non_boolean_milestone_rubric_flags(
    tmp_path: Path,
    field: str,
) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), field: "true"}]},
    )

    with pytest.raises(CliError) as excinfo:
        load_spec(spec_path)

    assert f"milestones[0].{field} must be a boolean" in excinfo.value.message


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def test_run_chain_errors_when_idea_missing(tmp_path: Path) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(tmp_path / "missing.txt")}]},
    )
    with pytest.raises(CliError) as excinfo:
        run_chain(spec_path, tmp_path, writer=lambda _msg: None)
    assert excinfo.value.code == "missing_idea_file"


def test_run_chain_errors_when_seed_plan_missing(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": "no-such-plan"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    # Set up a megaplan root without the seed plan.
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    with pytest.raises(CliError) as excinfo:
        run_chain(spec_path, tmp_path, writer=lambda _msg: None)
    assert excinfo.value.code == "missing_seed_plan"


def test_commit_phase_fails_when_plan_claims_dirty_nested_repo(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")

    nested = tmp_path / "reigh-app"
    nested.mkdir()
    _git(nested, "init")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "Test User")
    (nested / "tracked.ts").write_text("old\n", encoding="utf-8")
    _git(nested, "add", "tracked.ts")
    _git(nested, "commit", "-m", "nested init")
    (nested / "tracked.ts").write_text("new\n", encoding="utf-8")

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "files_changed": ["reigh-app/tracked.ts"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CliError) as excinfo:
        _commit_and_push_phase(
            tmp_path,
            "branch",
            "plan",
            "execute",
            writer=lambda _msg: None,
        )

    assert excinfo.value.code == "nested_repo_changes_uncommitted"
    assert "reigh-app" in excinfo.value.message


def test_commit_phase_ignores_unclaimed_dirty_nested_files(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "branch")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare")
    _git(tmp_path, "remote", "add", "origin", str(origin))

    nested = tmp_path / "reigh-app"
    nested.mkdir()
    _git(nested, "init")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "Test User")
    (nested / "claimed.ts").write_text("published\n", encoding="utf-8")
    (nested / "unrelated.ts").write_text("old\n", encoding="utf-8")
    _git(nested, "add", "claimed.ts", "unrelated.ts")
    _git(nested, "commit", "-m", "nested init")
    (nested / "unrelated.ts").write_text("user work\n", encoding="utf-8")

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text(
        json.dumps({"files_changed": ["reigh-app/claimed.ts"]}),
        encoding="utf-8",
    )

    _commit_and_push_phase(
        tmp_path,
        "branch",
        "plan",
        "execute",
        writer=lambda _msg: None,
    )

    assert (nested / "unrelated.ts").read_text(encoding="utf-8") == "user work\n"


def test_commit_phase_excludes_preexisting_dirty_root_files(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "branch")
    intended = tmp_path / "intended.txt"
    unrelated = tmp_path / "unrelated.txt"
    intended.write_text("base\n", encoding="utf-8")
    unrelated.write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "intended.txt", "unrelated.txt")
    _git(tmp_path, "commit", "-m", "init")
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare")
    _git(tmp_path, "remote", "add", "origin", str(origin))

    intended.write_text("base\nplanned\n", encoding="utf-8")
    unrelated.write_text("base\nuser dirty\n", encoding="utf-8")

    _commit_and_push_phase(
        tmp_path,
        "branch",
        "plan",
        "execute",
        writer=lambda _msg: None,
        preexisting_dirty_paths=[unrelated],
    )

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert committed == ["intended.txt"]
    assert " M unrelated.txt" in status


def test_commit_phase_keeps_preexisting_dirty_claimed_root_files(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "branch")
    (tmp_path / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    intended = tmp_path / "docs" / "sprint.md"
    unrelated = tmp_path / "unrelated.txt"
    intended.parent.mkdir()
    intended.write_text("base\n", encoding="utf-8")
    unrelated.write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "docs/sprint.md", "unrelated.txt")
    _git(tmp_path, "commit", "-m", "init")
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare")
    _git(tmp_path, "remote", "add", "origin", str(origin))

    intended.write_text("base\nplanned output\n", encoding="utf-8")
    unrelated.write_text("base\nuser dirty\n", encoding="utf-8")
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text(
        json.dumps({"files_changed": ["docs/sprint.md"]}),
        encoding="utf-8",
    )

    _commit_and_push_phase(
        tmp_path,
        "branch",
        "plan",
        "execute",
        writer=lambda _msg: None,
        preexisting_dirty_paths=[intended, unrelated],
    )

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert committed == ["docs/sprint.md"]
    assert " M unrelated.txt" in status
    assert "docs/sprint.md" not in status


def test_commit_phase_keeps_preexisting_claimed_nested_gitlink(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "branch")
    (tmp_path / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    origin = tmp_path.parent / f"{tmp_path.name}-origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare")
    _git(tmp_path, "remote", "add", "origin", str(origin))

    nested_origin = tmp_path.parent / f"{tmp_path.name}-nested-origin.git"
    nested_origin.mkdir()
    _git(nested_origin, "init", "--bare")
    nested_seed = tmp_path.parent / f"{tmp_path.name}-nested-seed"
    nested_seed.mkdir()
    _git(nested_seed, "init")
    _git(nested_seed, "config", "user.email", "test@example.com")
    _git(nested_seed, "config", "user.name", "Test User")
    (nested_seed / "claimed.ts").write_text("old\n", encoding="utf-8")
    _git(nested_seed, "add", "claimed.ts")
    _git(nested_seed, "commit", "-m", "nested init")
    _git(nested_seed, "remote", "add", "origin", str(nested_origin))
    _git(nested_seed, "push", "origin", "HEAD:main")

    _git(tmp_path, "-c", "protocol.file.allow=always", "submodule", "add", str(nested_origin), "reigh-app")
    _git(tmp_path, "commit", "-m", "add nested")
    _git(tmp_path, "push", "origin", "branch")

    nested = tmp_path / "reigh-app"
    (nested / "claimed.ts").write_text("new\n", encoding="utf-8")
    _git(nested, "add", "claimed.ts")
    _git(nested, "commit", "-m", "nested claimed")
    _git(nested, "push", "origin", "HEAD:main")

    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("user dirty\n", encoding="utf-8")

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution.json").write_text(
        json.dumps({"files_changed": ["reigh-app/claimed.ts"]}),
        encoding="utf-8",
    )

    _commit_and_push_phase(
        tmp_path,
        "branch",
        "plan",
        "execute",
        writer=lambda _msg: None,
        preexisting_dirty_paths=[nested, unrelated],
    )

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert committed == ["reigh-app"]
    assert "?? unrelated.txt" in status


# ---------------------------------------------------------------------------
# Chain state persistence
# ---------------------------------------------------------------------------


def test_save_and_load_chain_state_roundtrip(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    state = ChainState(
        current_milestone_index=2,
        current_plan_name="foo-20260415",
        current_milestone_base_sha="abc123base",
        last_state="done",
        pr_number=42,
        pr_state="open",
        completed=[{"label": "m1", "plan": "m1-x", "status": "done"}],
    )
    save_chain_state(spec_path, state)
    state_path = _state_path_for(spec_path)
    assert state_path.parent == tmp_path / ".megaplan" / "plans" / ".chains"
    assert state_path.exists()
    assert not (tmp_path / "chain_state.json").exists()
    loaded = load_chain_state(spec_path)
    assert loaded.current_milestone_index == 2
    assert loaded.current_plan_name == "foo-20260415"
    assert loaded.current_milestone_base_sha == "abc123base"
    assert loaded.last_state == "done"
    assert loaded.pr_number == 42
    assert loaded.pr_state == "open"
    assert loaded.completed == [{"label": "m1", "plan": "m1-x", "status": "done"}]


def test_load_chain_state_reads_legacy_sibling_state(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    (tmp_path / "chain_state.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 4,
                "current_plan_name": "legacy-plan",
                "last_state": "done",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_chain_state(spec_path)

    assert loaded.current_milestone_index == 4
    assert loaded.current_plan_name == "legacy-plan"
    assert loaded.last_state == "done"


# ---------------------------------------------------------------------------
# T5: Backward-compatible ChainState deserialization (new sync fields)
# ---------------------------------------------------------------------------


def test_chain_state_from_dict_handles_old_json_missing_sync_fields() -> None:
    """Older state JSON (no branch_head, pr_head, etc.) loads with
    defaults: None/False for sync fields."""
    raw = {
        "current_milestone_index": 3,
        "current_plan_name": "old-plan",
        "last_state": "done",
        "pr_number": 42,
        "pr_state": "OPEN",
        "completed": [{"label": "m1", "status": "done"}],
    }
    state = ChainState.from_dict(raw)
    assert state.current_milestone_index == 3
    assert state.current_plan_name == "old-plan"
    assert state.last_state == "done"
    assert state.pr_number == 42
    assert state.pr_state == "OPEN"
    assert len(state.completed) == 1
    assert state.current_milestone_base_sha is None
    # New fields default cleanly.
    assert state.branch_head is None
    assert state.pr_head is None
    assert state.last_pushed_commit is None
    assert state.dirty_flag is False
    assert state.sync_state is None


def test_chain_state_to_dict_and_from_dict_roundtrip_with_sync() -> None:
    """Full round-trip with sync fields populated."""
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-1",
        last_state="executed",
        pr_number=99,
        pr_state="OPEN",
        completed=[],
        branch_head="abc123",
        pr_head="def456",
        last_pushed_commit="abc123",
        dirty_flag=False,
        sync_state="clean",
    )
    raw = state.to_dict()
    assert raw["branch_head"] == "abc123"
    assert raw["pr_head"] == "def456"
    assert raw["last_pushed_commit"] == "abc123"
    assert raw["dirty_flag"] is False
    assert raw["sync_state"] == "clean"

    reloaded = ChainState.from_dict(raw)
    assert reloaded.branch_head == "abc123"
    assert reloaded.pr_head == "def456"
    assert reloaded.last_pushed_commit == "abc123"
    assert reloaded.dirty_flag is False
    assert reloaded.sync_state == "clean"


# T4 (W3e): ChainState schema_version forward-compat
# ---------------------------------------------------------------------------


def test_chain_state_schema_version_default() -> None:
    """schema_version defaults to 0 and is stamped in to_dict."""
    state = ChainState()
    assert state.schema_version == 0
    raw = state.to_dict()
    assert raw["schema_version"] == 0


def test_chain_state_forward_key_and_missing_schema_version_round_trips() -> None:
    """An unknown forward key plus absent schema_version round-trips without error."""
    raw: dict = {
        "current_milestone_index": 1,
        "current_plan_name": "some-plan",
        "last_state": "done",
        "_future_unknown_key": "extra-value",
        # schema_version intentionally absent
    }
    loaded = ChainState.from_dict(raw)
    assert loaded.current_milestone_index == 1
    assert loaded.schema_version == 0  # defaults to 0 when absent

    serialized = loaded.to_dict()
    assert serialized["schema_version"] == 0
    assert "_future_unknown_key" not in serialized  # unknown keys are not forwarded


def test_format_chain_status_pretty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_path = _setup_three_milestones(tmp_path, seed_plan="seed-plan-20260421")
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=1,
        current_plan_name="plan-for-m2",
        last_state="done",
        completed=[{"label": "m1", "plan": "plan-for-m1", "status": "done"}],
    )
    save_chain_state(spec_path, state)

    summary = format_chain_status(spec, state)
    # Verify existing keys are all present (backward-compatible).
    assert summary["current_milestone"] == {"label": "m2", "index": 1}
    assert summary["completed"] == [{"label": "m1", "index": 0}]
    assert summary["remaining"] == [{"label": "m2", "index": 1}, {"label": "m3", "index": 2}]
    assert summary["per_milestone"] == [
        {"label": "m1", "index": 0, "status": "completed"},
        {"label": "m2", "index": 1, "status": "in_progress"},
        {"label": "m3", "index": 2, "status": "pending"},
    ]
    assert summary["seed_plan"] == "seed-plan-20260421"
    assert summary["base_branch"] == "main"
    assert summary["current_plan_name"] == "plan-for-m2"
    assert summary["last_state"] == "done"
    # New sync section (additive, all defaulting None/False).
    assert "sync" in summary
    assert summary["sync"] == {
        "branch_head": None,
        "pr_head": None,
        "last_pushed_commit": None,
        "dirty_flag": False,
        "sync_state": None,
    }

    args = argparse.Namespace(chain_action="status", spec=str(spec_path), no_git_refresh=False)
    assert run_chain_cli(tmp_path, args, writer=lambda msg: sys.stderr.write(msg)) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["summary"] == summary
    assert payload["base_branch"] == "main"
    assert "Current milestone: m2 (index 1)" in captured.err
    assert "Seed plan: seed-plan-20260421" in captured.err
    assert "Base branch: main" in captured.err
    assert "[in_progress] m2 (index 1)" in captured.err


# ---------------------------------------------------------------------------
# Driver orchestration (auto.drive is mocked)
# ---------------------------------------------------------------------------


def _setup_two_milestones(tmp_path: Path) -> Path:
    i1 = _touch_idea(tmp_path, "m1.txt", "idea one")
    i2 = _touch_idea(tmp_path, "m1a.txt", "idea two")
    return _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "m1", "idea": str(i1)},
                {"label": "m1a", "idea": str(i2)},
            ]
        },
    )


def _setup_three_milestones(tmp_path: Path, *, seed_plan: str | None = None) -> Path:
    i1 = _touch_idea(tmp_path, "m1.txt", "idea one")
    i2 = _touch_idea(tmp_path, "m2.txt", "idea two")
    i3 = _touch_idea(tmp_path, "m3.txt", "idea three")
    payload: dict[str, object] = {
        "milestones": [
            {"label": "m1", "idea": str(i1)},
            {"label": "m2", "idea": str(i2)},
            {"label": "m3", "idea": str(i3)},
        ]
    }
    if seed_plan is not None:
        payload["seed"] = {"plan": seed_plan}
    return _write_spec(tmp_path, payload)


def test_run_chain_executes_milestones_in_order(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    init_calls: list[str] = []
    drive_calls: list[str] = []

    def fake_init(
        root,
        idea_path,
        *,
        robustness,
        auto_approve,
        profile=None,
        vendor=None,
        depth=None,
        critic=None,
        deepseek_provider=None,
        with_prep=False,
        with_feedback=False,
        prep_clarify=True,
        prep_direction=None,
        phase_model=None,
        writer,
    ):
        plan = f"plan-for-{Path(idea_path).stem}"
        init_calls.append(idea_path)
        return plan

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "done")

    with patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=fake_init), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    assert result["base_branch"] == "main"
    assert len(init_calls) == 2
    assert drive_calls == ["plan-for-m1", "plan-for-m1a"]
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert [c["label"] for c in saved.completed] == ["m1", "m1a"]


def test_run_chain_passes_milestone_rubric_knobs_to_init(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": str(idea),
                    "profile": "thoughtful",
                    "robustness": "light",
                    "vendor": "codex",
                    "depth": "xhigh",
                    "critic": "cross",
                    "with_prep": True,
                    "with_feedback": True,
                    "deepseek_provider": "fireworks",
                    "phase_model": "execute=claude:low",
                }
            ],
            "driver": {"robustness": "standard"},
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    init_kwargs: dict[str, object] = {}

    def fake_init(root, idea_path, **kwargs):
        del root, idea_path
        init_kwargs.update(kwargs)
        return "plan-m1"

    with patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=fake_init), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", return_value=_fake_outcome("plan-m1", "done")), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    assert init_kwargs == {
        "robustness": "light",
        "auto_approve": True,
        "profile": "thoughtful",
        "vendor": "codex",
        "depth": "xhigh",
        "critic": "cross",
        "deepseek_provider": "fireworks",
        "with_prep": True,
        "with_feedback": True,
        "prep_clarify": True,
        "prep_direction": None,
        "phase_model": ["execute=claude:low"],
        "writer": ANY,
    }


def test_run_chain_one_pauses_after_single_milestone(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    def fake_drive(plan, **_kwargs):
        return _fake_outcome(plan, "done")

    with patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, one=True)

    assert result["status"] == "paused"
    assert result["reason"] == "completed one milestone: m1"
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert [c["label"] for c in saved.completed] == ["m1"]


def test_chain_start_invokes_driver(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    calls: list[tuple[Path, Path, bool]] = []

    def fake_run_chain(
        spec_path_arg: Path,
        root: Path,
        *,
        no_git_refresh: bool = False,
        no_push: bool = False,
        fresh: bool = False,
        one: bool = False,
        writer=None,
    ):
        del writer
        del no_push
        del fresh
        del one
        calls.append((spec_path_arg, root, no_git_refresh))
        return {"status": "done", "reason": "", "chain_state": {}, "events": []}

    with patch("arnold.pipelines.megaplan.chain.run_chain", side_effect=fake_run_chain):
        start_args = argparse.Namespace(
            chain_action="start",
            spec=str(spec_path),
            no_git_refresh=True,
            no_push=False,
        )
        alias_args = argparse.Namespace(
            chain_action=None,
            spec=str(spec_path),
            no_git_refresh=False,
            no_push=False,
        )

        assert run_chain_cli(tmp_path, start_args) == 0
        start_payload = json.loads(capsys.readouterr().out)
        assert run_chain_cli(tmp_path, alias_args) == 0
        alias_payload = json.loads(capsys.readouterr().out)

    assert calls == [
        (spec_path.resolve(), tmp_path, True),
        (spec_path.resolve(), tmp_path, False),
    ]
    assert start_payload["status"] == "done"
    assert alias_payload["status"] == "done"


def test_chain_start_routes_to_supervisor_only_when_flag_on(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    calls: list[tuple[str, Path, Path, bool | None, bool | None, bool]] = []

    def fake_legacy_run_chain(
        spec_path_arg: Path,
        root: Path,
        *,
        no_git_refresh: bool = False,
        no_push: bool = False,
        fresh: bool = False,
        one: bool = False,
    ) -> dict[str, object]:
        calls.append(("legacy", spec_path_arg, root, no_git_refresh, no_push, one))
        return {"status": "done", "chain_state": {}}

    def fake_supervisor_run_chain(
        spec_path_arg: Path,
        root: Path,
        *,
        writer,
        one: bool = False,
    ) -> dict[str, object]:
        del writer
        calls.append(("supervisor", spec_path_arg, root, None, None, one))
        return {"status": "done", "chain_state": {}}

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr(chain_module, "run_chain", fake_legacy_run_chain)
    monkeypatch.setattr("arnold.pipelines.megaplan.supervisor.chain_runner.run_chain", fake_supervisor_run_chain)

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="start",
            spec=str(spec_path),
            no_git_refresh=True,
            no_push=True,
            one=True,
        ),
    )

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"
    assert calls == [("supervisor", spec_path.resolve(), tmp_path, None, None, True)]


def test_chain_override_stays_on_legacy_path_when_supervisor_flag_on(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
    )
    supervisor_called = False

    def fail_if_supervisor_called(*args, **kwargs):
        del args, kwargs
        nonlocal supervisor_called
        supervisor_called = True
        raise AssertionError("supervisor chain runner should not handle override")

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr("arnold.pipelines.megaplan.supervisor.chain_runner.run_chain", fail_if_supervisor_called)

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="override",
            spec=str(spec_path),
            set_prerequisite_policy="required",
            set_validation_policy=None,
            set_review_clean_milestone_pr=None,
        ),
        writer=lambda _m: None,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["effective_policy"]["prerequisite_policy"] == "required"
    assert supervisor_called is False


def test_chain_status_stays_on_legacy_path_when_supervisor_flag_on(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    fake_spec = chain_module.chain_spec.ChainSpec(milestones=[])
    fake_state = chain_module.chain_spec.ChainState()
    supervisor_called = False

    def fail_if_supervisor_called(*args, **kwargs):
        del args, kwargs
        nonlocal supervisor_called
        supervisor_called = True
        raise AssertionError("supervisor chain runner should not handle status")

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr("arnold.pipelines.megaplan.supervisor.chain_runner.run_chain", fail_if_supervisor_called)
    monkeypatch.setattr(chain_module.chain_spec, "load_spec", lambda _path: fake_spec)
    monkeypatch.setattr(chain_module.chain_spec, "load_chain_state", lambda _path: fake_state)
    monkeypatch.setattr(chain_module.chain_spec, "load_runtime_policy", lambda _path: {})
    monkeypatch.setattr(
        chain_module.chain_spec,
        "effective_chain_policy",
        lambda _spec, _overrides: {"prerequisite_policy": "none", "validation_policy": "none"},
    )
    monkeypatch.setattr(chain_module, "format_chain_status", lambda _spec, _state: {"status": "idle"})

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(chain_action="status", spec=str(spec_path)),
        writer=lambda _msg: None,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"] == {"status": "idle"}
    assert supervisor_called is False


def test_chain_start_supervisor_flag_on_smoke_uses_fakes_and_persists_serial_deps(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "a", "idea": str(_touch_idea(tmp_path, "a.txt"))},
                {
                    "label": "b",
                    "idea": str(_touch_idea(tmp_path, "b.txt")),
                    "depends_on": ["a"],
                },
            ]
        },
    )
    driver = _CliSmokeDriver(["awaiting_human", "done"])
    pack_runner = _CliSmokePackRunner()
    ready_calls: list[tuple[Path, int]] = []
    merge_calls: list[tuple[Path, int]] = []

    monkeypatch.setenv("MEGAPLAN_SUPERVISOR_TIER", "1")
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.supervisor.chain_runner.DefaultRunDriver",
        lambda: driver,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.supervisor.chain_runner.ChainMilestonePackRunner",
        lambda: pack_runner,
    )
    monkeypatch.setattr("arnold.pipelines.megaplan.supervisor.pr_merge.git_ops._pr_state", lambda *_a, **_k: "open")
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.supervisor.pr_merge.git_ops._run_command",
        lambda _root, argv, **_kwargs: subprocess.CompletedProcess(
            argv,
            0,
            '{"state":"OPEN","mergeStateStatus":"CLEAN","isDraft":false}',
            "",
        ),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.supervisor.pr_merge.git_ops._mark_pr_ready",
        lambda root, pr_number, *, writer: ready_calls.append((root, pr_number)),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.supervisor.pr_merge.git_ops._enable_auto_merge",
        lambda root, pr_number, *, writer: merge_calls.append((root, pr_number)) or "open",
    )

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(
            chain_action="start",
            spec=str(spec_path),
            no_git_refresh=True,
            no_push=True,
            one=False,
        ),
        writer=lambda _msg: None,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "done"
    assert [item["label"] for item in payload["milestone_results"]] == ["a", "b"]
    assert [event["kind"] for event in payload["events"]].count("pr_merge_resolution") == 1
    assert driver.plans == ["cli-smoke-a-1", "cli-smoke-b-1"]
    assert pack_runner.nodes == ["a", "b"]
    assert ready_calls == [(tmp_path, 42)]
    assert merge_calls == [(tmp_path, 42)]

    supervisor_state = load_supervisor_state(tmp_path, str(spec_path.resolve()))
    assert supervisor_state is not None
    assert [
        (assertion.node_id, assertion.depends_on)
        for assertion in supervisor_state.dependency_assertions
    ] == [("a", ()), ("b", ("a",))]


def test_chain_verify_reports_divergence_without_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _git(project_dir, "init", "-q")
    _git(project_dir, "config", "user.email", "t@t.test")
    _git(project_dir, "config", "user.name", "t")
    (project_dir / ".gitignore").write_text(".megaplan/\nideas/\nchain.yaml\n", encoding="utf-8")
    (project_dir / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(project_dir, "add", "-A")
    _git(project_dir, "commit", "-q", "-m", "seed")
    base_sha = _git(project_dir, "rev-parse", "HEAD").stdout.strip()

    spec_path = _write_spec(
        project_dir,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(project_dir, "m1.txt"))}]},
    )
    plan_name = "plan-m1"
    plan_dir = project_dir / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "done",
                "config": {"project_dir": str(project_dir)},
                "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
                {
                    "tasks": [
                        {
                            "id": "T1",
                            "status": "done",
                            "files_changed": ["src/claimed.py"],
                            "commands_run": ["edit src/claimed.py"],
                            "executor_notes": "verified landed diff claim against the declared milestone window",
                        }
                    ],
                "sense_checks": [
                    {
                        "id": "SC1",
                        "executor_note": "confirmed the verifier remains read-only and does not execute providers",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sentinel_verdict = '{"sentinel": true}\n'
    verdict_path = plan_dir / "completion_verdict.json"
    verdict_path.write_text(sentinel_verdict, encoding="utf-8")

    lib_dir = project_dir / "lib"
    lib_dir.mkdir()
    (lib_dir / "other.py").write_text("print('dirty')\n", encoding="utf-8")

    save_chain_state(
        spec_path,
        ChainState(
            completion_contract_mode="enforce",
            completed=[{"label": "m1", "plan": plan_name, "status": "done"}],
        ),
    )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_chain_parser(subparsers)
    args = parser.parse_args(
        ["chain", "verify", "--spec", str(spec_path), "--project-dir", str(project_dir)]
    )

    with patch(
        "arnold.pipelines.megaplan.orchestration.completion_contract.GreenSuiteProvider.collect",
        side_effect=AssertionError("chain verify must not execute green-suite providers"),
    ):
        assert run_chain_cli(project_dir, args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["verified_count"] == 1
    assert payload["divergence_count"] == 1
    milestone = payload["milestones"][0]
    assert milestone["label"] == "m1"
    assert milestone["accepted"] is False
    assert milestone["would_block"] is True
    assert milestone["files_claimed"] == ["src/claimed.py"]
    assert milestone["files_in_diff"] == ["lib/"]
    assert milestone["diff_source"] == "declared_authoritative"
    assert milestone["evidence_window"]["source"] == "declared"
    assert milestone["evidence_window"]["base_sha"] == base_sha
    assert verdict_path.read_text(encoding="utf-8") == sentinel_verdict


def test_run_chain_stops_on_failure(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    drive_calls: list[str] = []

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "failed")

    with patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "stopped"
    assert len(drive_calls) == 1  # did not proceed to second milestone
    saved = load_chain_state(spec_path)
    assert saved.last_state == "failed"


def test_run_chain_recovers_blocked_execute_when_latest_batch_tasks_done(
    tmp_path: Path,
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    messages: list[str] = []
    drive_calls: list[str] = []
    attempts: dict[str, int] = {}

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        attempts[plan] = attempts.get(plan, 0) + 1
        if plan == "plan-for-m1" and attempts[plan] == 1:
            _write_blocked_execute_batch(
                tmp_path,
                plan,
                [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["arnold/pipelines/megaplan/chain/__init__.py"],
                        "executor_notes": "finished",
                    }
                ],
            )
            return _fake_outcome(plan, "worker_blocked")
        _write_authoritative_execution_batch(tmp_path, plan)
        return _fake_outcome(plan, "done")

    with patch(
        "arnold.pipelines.megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-for-{Path(idea_path).stem}",
    ), patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), patch(
        "arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "done"
    assert drive_calls == ["plan-for-m1", "plan-for-m1", "plan-for-m1a"]
    assert any("continuing from executed state" in message for message in messages)
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert [completed["label"] for completed in saved.completed] == ["m1", "m1a"]


def test_run_chain_treats_blocked_execute_with_pending_tasks_as_failure(
    tmp_path: Path,
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    messages: list[str] = []
    drive_calls: list[str] = []

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        _write_blocked_execute_batch(
            tmp_path,
            plan,
            [
                {
                    "task_id": "T1",
                    "status": "pending",
                    "executor_notes": "still blocked",
                }
            ],
        )
        return _fake_outcome(plan, "blocked")

    with patch(
        "arnold.pipelines.megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-for-{Path(idea_path).stem}",
    ), patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), patch(
        "arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "stopped"
    assert drive_calls == ["plan-for-m1"]
    assert any("treating as real block" in message for message in messages)
    saved = load_chain_state(spec_path)
    assert saved.last_state == "blocked"
    assert saved.completed == []


def test_run_chain_treats_blocked_execute_raw_done_without_authority_as_failure(
    tmp_path: Path,
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    messages: list[str] = []
    drive_calls: list[str] = []

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        _write_blocked_execute_batch(
            tmp_path,
            plan,
            [{"task_id": "T1", "status": "done", "executor_notes": "legacy claim"}],
        )
        return _fake_outcome(plan, "blocked")

    with patch(
        "arnold.pipelines.megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-for-{Path(idea_path).stem}",
    ), patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), patch(
        "arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "stopped"
    assert drive_calls == ["plan-for-m1"]
    assert any("non-authoritative tasks" in message for message in messages)
    saved = load_chain_state(spec_path)
    assert saved.completed == []


def test_run_chain_resumes_from_chain_state(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    # Pretend milestone m1 already completed.
    pre = ChainState(
        current_milestone_index=1,
        current_plan_name=None,
        last_state="done",
        completed=[{"label": "m1", "plan": "plan-m1", "status": "done"}],
    )
    save_chain_state(spec_path, pre)

    init_calls: list[str] = []

    def fake_init(
        root,
        idea_path,
        *,
        robustness,
        auto_approve,
        profile=None,
        vendor=None,
        depth=None,
        critic=None,
        deepseek_provider=None,
        with_prep=False,
        with_feedback=False,
        prep_clarify=True,
        prep_direction=None,
        phase_model=None,
        writer,
    ):
        init_calls.append(idea_path)
        return f"plan-{Path(idea_path).stem}"

    def fake_drive(plan, **_kwargs):
        return _fake_outcome(plan, "done")

    with patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=fake_init), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    # Only the second idea (m1a) should have been init'd; m1 is skipped.
    assert result["status"] == "done"
    assert len(init_calls) == 1
    assert "m1a" in init_calls[0]


def test_run_chain_with_seed_drives_seed_first(tmp_path: Path) -> None:
    """When seed plan isn't terminal, drive it before milestones."""
    i1 = _touch_idea(tmp_path, "m1.txt")
    seed_name = "seed-plan-20260415"
    # Fake-create the seed plan dir so resolve_plan_dir accepts it.
    seed_dir = tmp_path / ".megaplan" / "plans" / seed_name
    seed_dir.mkdir(parents=True)
    (seed_dir / "state.json").write_text(
        json.dumps({"name": seed_name, "current_state": "planned", "iteration": 1}),
        encoding="utf-8",
    )
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": seed_name},
            "milestones": [{"label": "m1", "idea": str(i1)}],
        },
    )

    plan_state_calls: list[str] = []
    drive_calls: list[str] = []

    def fake_plan_state(root, plan, *, timeout):
        plan_state_calls.append(plan)
        # Seed is mid-flight; milestone plans always "missing" until init.
        if plan == seed_name:
            return "planned"
        return "missing"

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        _write_authoritative_execution_batch(tmp_path, plan)
        return _fake_outcome(plan, "done")

    with patch("arnold.pipelines.megaplan.chain._plan_state", side_effect=fake_plan_state), \
         patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    # Seed must be driven first, then the milestone plan.
    assert drive_calls[0] == seed_name
    assert drive_calls[1].startswith("plan-m1")


def test_run_chain_blocks_terminal_seed_skip_without_authority(
    tmp_path: Path,
) -> None:
    i1 = _touch_idea(tmp_path, "m1.txt")
    seed_name = "seed-plan-20260415"
    seed_dir = tmp_path / ".megaplan" / "plans" / seed_name
    seed_dir.mkdir(parents=True)
    (seed_dir / "state.json").write_text(
        json.dumps({"name": seed_name, "current_state": "done", "iteration": 1}),
        encoding="utf-8",
    )
    (seed_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )
    spec_path = _write_spec(
        tmp_path,
        {"seed": {"plan": seed_name}, "milestones": [{"label": "m1", "idea": str(i1)}]},
    )
    messages: list[str] = []

    with patch(
        "arnold.pipelines.megaplan.chain._plan_state",
        side_effect=lambda root, plan, *, timeout: "done" if plan == seed_name else "missing",
    ), patch(
        "arnold.pipelines.megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}",
    ), patch("arnold.pipelines.megaplan.chain.auto_drive") as drive, patch(
        "arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "blocked"
    assert "seed plan terminal state lacks authority" in result["reason"]
    assert drive.call_count == 0
    assert any("lacks authority" in message for message in messages)
    saved = load_chain_state(spec_path)
    assert saved.current_plan_name == seed_name
    assert saved.completed == []


def test_run_chain_blocks_current_plan_advance_without_authority(
    tmp_path: Path,
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    plan_name = "plan-for-m1"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "current_state": "done", "iteration": 1}),
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        ChainState(current_milestone_index=0, current_plan_name=plan_name),
    )
    messages: list[str] = []

    with patch(
        "arnold.pipelines.megaplan.chain._plan_state",
        return_value="done",
    ), patch(
        "arnold.pipelines.megaplan.chain.auto_drive",
        return_value=_fake_outcome(plan_name, "done"),
    ) as drive, patch(
        "arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "blocked"
    assert drive.call_count == 1
    assert any("lacks task authority" in message for message in messages)
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 0
    assert saved.current_plan_name == plan_name
    assert saved.completed == []


# ---------------------------------------------------------------------------
# --no-git-refresh flag
# ---------------------------------------------------------------------------


def test_no_git_refresh_suppresses_subprocess_calls(tmp_path: Path) -> None:
    """With no_git_refresh=True, _refresh_base_branch must not invoke any subprocess."""
    from arnold.pipelines.megaplan.chain import _refresh_base_branch

    msgs: list[str] = []
    with patch("arnold.pipelines.megaplan.chain.subprocess.run") as mock_run:
        _refresh_base_branch(tmp_path, "setup/cloud", writer=msgs.append, no_git_refresh=True)
    assert mock_run.call_count == 0
    assert any("skipping git refresh" in m for m in msgs)


def test_refresh_base_branch_default_fetches_without_checkout(tmp_path: Path) -> None:
    """Default refresh must not checkout a base that may be locked in another worktree."""
    from arnold.pipelines.megaplan.chain import _refresh_base_branch

    calls = [
        subprocess.CompletedProcess(
            args=["git", "fetch", "origin", "setup/cloud"],
            returncode=0,
            stdout="",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=["git", "symbolic-ref", "--short", "HEAD"],
            returncode=0,
            stdout="feature\n",
            stderr="",
        ),
    ]
    msgs: list[str] = []

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", side_effect=calls) as mock_run:
        _refresh_base_branch(tmp_path, "setup/cloud", writer=msgs.append)
    cmds = [call.args[0] for call in mock_run.call_args_list]
    assert cmds[0] == ["git", "fetch", "origin", "setup/cloud"]
    assert ["git", "checkout", "setup/cloud"] not in cmds
    assert any("local setup/cloud checkout refresh skipped" in msg for msg in msgs)


def test_refresh_base_branch_aborts_on_fetch_failure(tmp_path: Path) -> None:
    """A failed fetch still stops the chain before stale work executes."""
    from arnold.pipelines.megaplan.chain import _refresh_base_branch

    calls = [
        subprocess.CompletedProcess(
            args=["git", "fetch", "origin", "setup/cloud"],
            returncode=128,
            stdout="",
            stderr="fatal: unable to access origin",
        ),
    ]
    msgs: list[str] = []

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", side_effect=calls):
        with pytest.raises(CliError) as excinfo:
            _refresh_base_branch(tmp_path, "setup/cloud", writer=msgs.append)

    assert excinfo.value.code == "git_refresh_failed"
    assert "git fetch origin setup/cloud exited 128" in excinfo.value.message
    assert any("unable to access origin" in msg for msg in msgs)


def test_plan_state_uses_module_launcher(tmp_path: Path) -> None:
    class _Proc:
        returncode = 0
        stdout = '{"state": "planned"}'

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=_Proc()) as mock_run:
        from arnold.pipelines.megaplan.chain import _plan_state

        assert _plan_state(tmp_path, "demo-plan", timeout=5) == "planned"

    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "arnold.pipelines.megaplan",
        "status",
        "--project-dir",
        str(tmp_path),
        "--plan",
        "demo-plan",
    ]
    assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)
    env = mock_run.call_args.kwargs["env"]
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(chain_module.megaplan_engine_root())


def test_init_plan_uses_module_launcher(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from arnold.pipelines.megaplan.chain import _init_plan

        assert _init_plan(
            tmp_path,
            str(idea_path),
            robustness="standard",
            auto_approve=True,
            profile="apex",
            vendor="codex",
            depth="high",
            critic="kimi",
            deepseek_provider="direct",
            with_prep=True,
            with_feedback=True,
            phase_model=["plan=claude:high", "revise=claude:high"],
            writer=lambda _m: None,
        ) == "demo-plan"

    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "arnold.pipelines.megaplan",
        "init",
        "--project-dir",
        str(tmp_path),
        "--auto-approve",
        "--robustness",
        "standard",
        "--profile",
        "apex",
        "--vendor",
        "codex",
        "--depth",
        "high",
        "--critic",
        "kimi",
        "--deepseek-provider",
        "direct",
        "--with-prep",
        "--with-feedback",
        "--phase-model",
        "plan=claude:high",
        "--phase-model",
        "revise=claude:high",
        "--idea-file",
        str(idea_path),
    ]
    assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)
    env = mock_run.call_args.kwargs["env"]
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(chain_module.megaplan_engine_root())


def test_init_plan_resolves_relative_idea_against_project_root_and_uses_absolute_args(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "relative.txt", "hello")
    proc = subprocess.CompletedProcess(args=[], returncode=0, stdout='{"plan": "demo"}', stderr="")

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from arnold.pipelines.megaplan.chain import _init_plan

        assert _init_plan(
            tmp_path,
            str(Path("ideas") / idea_path.name),
            robustness="standard",
            auto_approve=True,
            writer=lambda _m: None,
        ) == "demo"

    argv = mock_run.call_args.args[0]
    assert argv[argv.index("--project-dir") + 1] == str(tmp_path.resolve())
    assert argv[argv.index("--idea-file") + 1] == str(idea_path.resolve())
    assert mock_run.call_args.kwargs["cwd"] == str(tmp_path.resolve())


def test_run_chain_persists_execution_contract_before_driving(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    metadata = load_chain_state(spec_path).metadata["engine_isolation"]
    assert metadata["last_observed_phase"] == "chain_start"
    assert Path(metadata["target_root"]).is_absolute()
    assert Path(metadata["engine_root"]).is_absolute()


def test_run_chain_refuses_preflight_before_init_or_drive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    calls: list[str] = []

    def refuse(*_args, **_kwargs):
        raise CliError("engine_pin_drift", "refuse before chain mutation")

    def should_not_run(*_args, **_kwargs):
        calls.append("ran")
        raise AssertionError("chain should refuse before init/drive")

    monkeypatch.setattr(chain_module, "resolve_execution_environment", refuse)
    monkeypatch.setattr(chain_module, "_init_plan", should_not_run)
    monkeypatch.setattr(chain_module, "_drive_plan", should_not_run)

    with pytest.raises(CliError) as excinfo:
        run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert excinfo.value.code == "engine_pin_drift"
    assert calls == []


def test_init_plan_long_options_are_registered_on_init_parser() -> None:
    from arnold.pipelines.megaplan.cli import build_parser

    emitted = _static_long_option_literals(chain_module._init_plan)
    registered = _long_options(_subparser(build_parser(), "init"))

    assert emitted <= registered


def test_init_plan_warns_when_vendor_ignored_by_locked_profile(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )
    messages: list[str] = []

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=proc), \
         patch("arnold.pipelines.megaplan.chain.load_profile_metadata", return_value={"apex": {"vendor_locked": True}}):
        from arnold.pipelines.megaplan.chain import _init_plan

        _init_plan(
            tmp_path,
            str(idea_path),
            robustness="standard",
            auto_approve=True,
            profile="apex",
            vendor="codex",
            writer=messages.append,
        )

    joined = "".join(messages)
    assert "profile apex is vendor-locked" in joined
    assert "vendor=codex is ignored" in joined


def test_init_plan_warns_when_inherited_vendor_ignored_by_locked_profile(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )
    messages: list[str] = []

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=proc), \
         patch("arnold.pipelines.megaplan.chain.load_profile_metadata", return_value={"apex": {"vendor_locked": True}}), \
         patch("arnold.pipelines.megaplan.chain._resolve_default_vendor", return_value="codex"):
        from arnold.pipelines.megaplan.chain import _init_plan

        _init_plan(
            tmp_path,
            str(idea_path),
            robustness="standard",
            auto_approve=True,
            profile="apex",
            vendor=None,
            writer=messages.append,
        )

    joined = "".join(messages)
    assert "profile apex is vendor-locked" in joined
    assert "inherited vendor=codex is ignored" in joined


def test_vendor_lock_profile_metadata_load_failure_raises(tmp_path: Path) -> None:
    with patch("arnold.pipelines.megaplan.chain.load_profile_metadata", side_effect=RuntimeError("metadata offline")):
        with pytest.raises(CliError, match="M3B_HALT_VENDOR_LOCK_PROFILE_LOAD"):
            chain_module._warn_vendor_ignored_for_locked_profile(
                tmp_path,
                profile="apex",
                vendor="codex",
                writer=lambda _: None,
            )


def test_vendor_lock_with_no_profile_and_no_vendor_is_noop(tmp_path: Path) -> None:
    writer_calls: list[str] = []

    with patch("arnold.pipelines.megaplan.chain.load_profile_metadata") as load_metadata:
        chain_module._warn_vendor_ignored_for_locked_profile(
            tmp_path,
            profile=None,
            vendor=None,
            writer=writer_calls.append,
        )

    load_metadata.assert_not_called()
    assert writer_calls == []


def test_vendor_lock_default_vendor_resolution_failure_raises(tmp_path: Path) -> None:
    with patch("arnold.pipelines.megaplan.chain.load_profile_metadata", return_value={"apex": {"vendor_locked": True}}), \
         patch("arnold.pipelines.megaplan.chain._resolve_default_vendor", side_effect=RuntimeError("no default vendor")):
        with pytest.raises(CliError, match="M3B_HALT_VENDOR_LOCK_RESOLVE"):
            chain_module._warn_vendor_ignored_for_locked_profile(
                tmp_path,
                profile="apex",
                vendor=None,
                writer=lambda _: None,
            )


def test_init_plan_forwards_prep_direction_flag(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from arnold.pipelines.megaplan.chain import _init_plan

        _init_plan(
            tmp_path,
            str(idea_path),
            robustness="standard",
            auto_approve=False,
            prep_direction="focus on the shutdown path",
            writer=lambda _m: None,
        )

    args = mock_run.call_args.args[0]
    assert "--prep-direction" in args
    assert args[args.index("--prep-direction") + 1] == "focus on the shutdown path"


def test_init_plan_omits_prep_direction_when_none(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from arnold.pipelines.megaplan.chain import _init_plan

        _init_plan(
            tmp_path,
            str(idea_path),
            robustness="standard",
            auto_approve=False,
            writer=lambda _m: None,
        )

    assert "--prep-direction" not in mock_run.call_args.args[0]


def test_run_chain_no_git_refresh_skips_refresh(tmp_path: Path) -> None:
    """End-to-end: run_chain(..., no_git_refresh=True) propagates the flag."""
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    refresh_calls: list[tuple[str, bool]] = []

    def fake_refresh(root, base_branch, *, writer, no_git_refresh=False):
        refresh_calls.append((base_branch, no_git_refresh))

    def fake_drive(plan, **_kwargs):
        return _fake_outcome(plan, "done")

    with patch("arnold.pipelines.megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", side_effect=fake_refresh):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_git_refresh=True)

    assert result["status"] == "done"
    assert len(refresh_calls) == 2
    assert all(call == ("main", True) for call in refresh_calls)


def test_run_chain_no_push_skips_branch_pr_lifecycle(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}]},
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("arnold.pipelines.megaplan.chain.auto_drive", return_value=_fake_outcome("plan-m1", "done")), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr") as ensure_pr:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_push=True)

    assert result["status"] == "done"
    checkout.assert_not_called()
    ensure_pr.assert_not_called()


def test_commit_and_push_phase_skips_empty_diff(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.chain import _commit_and_push_phase

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    def fake_run(cmd, **_kwargs):
        assert cmd == ["git", "diff", "--cached", "--quiet"]
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run_command), \
         patch("arnold.pipelines.megaplan.chain.subprocess.run", side_effect=fake_run):
        _commit_and_push_phase(
            tmp_path,
            "mp/m1",
            "plan-m1",
            "plan",
            writer=lambda _m: None,
        )

    assert commands == [["git", "add", "-A"]]


def test_ensure_milestone_pr_skips_when_gh_missing(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.chain import _ensure_milestone_pr

    messages: list[str] = []
    with patch("arnold.pipelines.megaplan.chain.shutil.which", return_value=None), \
         patch("arnold.pipelines.megaplan.chain._list_open_pr_for_branch") as list_pr, \
         patch("arnold.pipelines.megaplan.chain._run_command") as run_command:
        pr_number = _ensure_milestone_pr(
            tmp_path,
            MilestoneSpec(label="m1", idea="idea.txt", branch="mp/m1"),
            base_branch="setup/cloud",
            writer=messages.append,
        )

    assert pr_number is None
    assert "skipping PR creation" in "".join(messages)
    list_pr.assert_not_called()
    run_command.assert_not_called()


def test_command_env_clears_gh_token_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "bad-token")
    monkeypatch.setenv("GITHUB_TOKEN", "other-bad-token")
    monkeypatch.setenv("KEEP_ME", "yes")

    env = _command_env(["gh", "pr", "view", "1"])

    assert env is not None
    assert "GH_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    assert env["KEEP_ME"] == "yes"


def test_command_env_leaves_non_gh_commands_on_default_env() -> None:
    assert _command_env(["git", "status"]) is None


def test_should_retry_gh_without_env_only_on_token_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GH_TOKEN", "bad-token")
    auth_failure = subprocess.CompletedProcess(
        ["gh", "pr", "view", "1"],
        1,
        "",
        "HTTP 401: Bad credentials",
    )
    not_found = subprocess.CompletedProcess(
        ["gh", "pr", "view", "1"],
        1,
        "",
        "could not resolve to a PullRequest",
    )

    assert _should_retry_gh_without_env(["gh", "pr", "view", "1"], auth_failure)
    assert not _should_retry_gh_without_env(["gh", "pr", "view", "1"], not_found)
    assert not _should_retry_gh_without_env(["git", "status"], auth_failure)


def test_run_command_retries_gh_auth_failure_without_env_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GH_TOKEN", "bad-token")
    monkeypatch.setenv("GITHUB_TOKEN", "other-bad-token")
    calls: list[dict[str, object]] = []

    def fake_run(cmd, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                cmd,
                1,
                "",
                "HTTP 401: Bad credentials",
            )
        env = kwargs.get("env")
        assert isinstance(env, dict)
        assert "GH_TOKEN" not in env
        assert "GITHUB_TOKEN" not in env
        return subprocess.CompletedProcess(cmd, 0, '{"state":"MERGED"}', "")

    with patch("arnold.pipelines.megaplan.chain.subprocess.run", side_effect=fake_run):
        proc = _run_command(
            tmp_path,
            ["gh", "pr", "view", "1"],
            writer=lambda _m: None,
        )

    assert proc.returncode == 0
    assert len(calls) == 2
    assert "env" not in calls[0]


def test_checkout_milestone_branch_starts_from_configured_base_branch(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.chain import _checkout_milestone_branch

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("arnold.pipelines.megaplan.chain._remote_branch_exists", return_value=False), \
         patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run_command):
        _checkout_milestone_branch(
            tmp_path,
            "mp/m1",
            base_branch="setup/cloud",
            writer=lambda _m: None,
        )

    assert commands == [
        ["git", "checkout", "-B", "mp/m1", "setup/cloud"],
        ["git", "push", "-u", "origin", "mp/m1"],
    ]


def test_checkout_milestone_branch_forks_from_origin_when_from_origin(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.chain import _checkout_milestone_branch

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def fake_subprocess_run(cmd, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("arnold.pipelines.megaplan.chain._remote_branch_exists", return_value=False), \
         patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run_command), \
         patch("arnold.pipelines.megaplan.chain.subprocess.run", side_effect=fake_subprocess_run):
        _checkout_milestone_branch(
            tmp_path,
            "mp/m2",
            base_branch="main",
            writer=lambda _m: None,
            from_origin=True,
        )

    assert ["git", "checkout", "-B", "mp/m2", "origin/main"] in commands
    assert ["git", "checkout", "-B", "mp/m2", "main"] not in commands
    assert ["git", "push", "-u", "origin", "mp/m2"] in commands


def test_checkout_milestone_branch_falls_back_to_local_base_when_fetch_fails(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.chain import _checkout_milestone_branch

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def fake_subprocess_run(cmd, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(cmd, 1, "", "no upstream")

    with patch("arnold.pipelines.megaplan.chain._remote_branch_exists", return_value=False), \
         patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run_command), \
         patch("arnold.pipelines.megaplan.chain.subprocess.run", side_effect=fake_subprocess_run):
        _checkout_milestone_branch(
            tmp_path,
            "mp/m2",
            base_branch="main",
            writer=lambda _m: None,
            from_origin=True,
        )

    assert ["git", "checkout", "-B", "mp/m2", "main"] in commands
    assert ["git", "checkout", "-B", "mp/m2", "origin/main"] not in commands


def test_ensure_milestone_pr_uses_configured_base_branch(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.chain import _ensure_milestone_pr

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "https://github.com/acme/app/pull/42\n", "")

    with patch("arnold.pipelines.megaplan.chain.shutil.which", return_value="/usr/bin/gh"), \
         patch("arnold.pipelines.megaplan.chain._list_open_pr_for_branch", return_value=None), \
         patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run_command):
        number = _ensure_milestone_pr(
            tmp_path,
            MilestoneSpec(label="m1", idea="idea.txt", branch="mp/m1"),
            base_branch="setup/cloud",
            writer=lambda _m: None,
        )

    assert number == 42
    assert commands[0][0:6] == ["gh", "pr", "create", "--draft", "--base", "setup/cloud"]


def test_run_chain_branch_pr_commit_and_auto_merge(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "base_branch": "setup/cloud",
            "milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    commits: list[tuple[str, str, str]] = []

    def fake_drive(root, plan, spec, *, on_phase_complete=None, writer):
        del root, spec, writer
        assert plan == "plan-m1"
        assert on_phase_complete is not None
        on_phase_complete("plan", 0, "", "")
        on_phase_complete("execute", 0, "", "")
        return _fake_outcome(plan, "done")

    with patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr", return_value=17) as ensure_pr, \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch("arnold.pipelines.megaplan.chain._commit_and_push_phase", side_effect=lambda root, branch, plan, phase, **_kwargs: commits.append((branch, plan, phase))), \
         patch("arnold.pipelines.megaplan.chain._pr_state", return_value="open"), \
         patch("arnold.pipelines.megaplan.chain._mark_pr_ready") as ready, \
         patch("arnold.pipelines.megaplan.chain._enable_auto_merge", return_value="open") as merge:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    checkout.assert_called_once_with(
        tmp_path,
        "mp/m1",
        base_branch="setup/cloud",
        writer=ANY,
        from_origin=ANY,
    )
    ensure_pr.assert_called_once_with(
        tmp_path,
        MilestoneSpec(label="m1", idea=str(idea), branch="mp/m1"),
        base_branch="setup/cloud",
        writer=ANY,
    )
    assert commits == [
        ("mp/m1", "plan-m1", "init"),
        ("mp/m1", "plan-m1", "plan"),
        ("mp/m1", "plan-m1", "execute"),
        ("mp/m1", "plan-m1", "done"),
    ]
    assert ready.call_args.args == (tmp_path, 17)
    assert merge.call_args.args == (tmp_path, 17)
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert saved.pr_number is None


def test_run_chain_resume_milestone_pr_uses_base_branch(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "base_branch": "setup/cloud",
            "milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)
    save_chain_state(
        spec_path,
        ChainState(current_milestone_index=0, current_plan_name="plan-m1", last_state=None),
    )

    with patch("arnold.pipelines.megaplan.chain._plan_state", return_value="planned"), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr", return_value=17) as ensure_pr, \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("arnold.pipelines.megaplan.chain._commit_and_push_phase"), \
         patch("arnold.pipelines.megaplan.chain._pr_state", return_value="merged"), \
         patch("arnold.pipelines.megaplan.chain._mark_pr_ready"), \
         patch("arnold.pipelines.megaplan.chain._enable_auto_merge"):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    checkout.assert_called_once_with(
        tmp_path,
        "mp/m1",
        base_branch="setup/cloud",
        writer=ANY,
        from_origin=ANY,
    )
    ensure_pr.assert_called_once_with(
        tmp_path,
        MilestoneSpec(label="m1", idea=str(idea), branch="mp/m1"),
        base_branch="setup/cloud",
        writer=ANY,
    )


def test_enable_auto_merge_falls_back_when_repo_disallows_auto_merge(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    messages: list[str] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        if "--auto" in argv:
            raise CliError(
                "gh_pr_merge_failed",
                "gh pr merge failed",
                extra={"stderr": "GraphQL: Auto merge is not allowed for this repository"},
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    with patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run):
        state = _enable_auto_merge(tmp_path, 7, writer=messages.append)

    assert calls == [
        ["gh", "pr", "merge", "7", "--auto", "--squash", "--delete-branch"],
        ["gh", "pr", "merge", "7", "--squash", "--delete-branch"],
    ]
    assert state == "merged"
    assert "falling back" in "".join(messages)


def test_enable_auto_merge_records_immediate_auto_merge(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        if argv[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(argv, 0, '{"state":"MERGED"}', "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    with patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run):
        state = _enable_auto_merge(tmp_path, 7, writer=lambda _m: None)

    assert state == "merged"
    assert calls == [
        ["gh", "pr", "merge", "7", "--auto", "--squash", "--delete-branch"],
        ["gh", "pr", "view", "7", "--json", "state"],
    ]


def test_pr_state_retries_transient_gh_failures(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    messages: list[str] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        if len(calls) == 1:
            raise CliError(
                "gh_pr_view_failed",
                "gh pr view failed",
                extra={"stderr": "HTTP 504: 504 Gateway Timeout (https://api.github.com/graphql)"},
            )
        return subprocess.CompletedProcess(argv, 0, '{"state":"OPEN"}', "")

    with patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run), \
         patch("arnold.pipelines.megaplan.chain.time.sleep") as sleep:
        state = _pr_state(tmp_path, 11, writer=messages.append)

    assert state == "open"
    assert len(calls) == 2
    assert "transient gh pr view failure" in "".join(messages)
    sleep.assert_called_once()


def test_pr_state_retries_graphql_timeout_until_attempts_exhausted(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        raise CliError(
            "gh_pr_view_failed",
            "gh pr view failed",
            extra={"stderr": "GraphQL: timeout while checking pull request state"},
        )

    with patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run), \
         patch("arnold.pipelines.megaplan.chain.time.sleep") as sleep:
        with pytest.raises(CliError) as exc_info:
            _pr_state(tmp_path, 11, writer=lambda _m: None)

    assert exc_info.value.code == "gh_pr_view_failed"
    assert len(calls) == 3
    assert sleep.call_count == 2


def test_pr_state_does_not_retry_non_transient_gh_failures(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(root, argv, *, writer, timeout, error_code):
        del root, writer, timeout, error_code
        calls.append(argv)
        raise CliError(
            "gh_pr_view_failed",
            "gh pr view failed",
            extra={"stderr": "GraphQL: Could not resolve to a PullRequest with the number of 11."},
        )

    with patch("arnold.pipelines.megaplan.chain._run_command", side_effect=fake_run), \
         patch("arnold.pipelines.megaplan.chain.time.sleep") as sleep:
        with pytest.raises(CliError) as exc_info:
            _pr_state(tmp_path, 11, writer=lambda _m: None)

    assert exc_info.value.code == "gh_pr_view_failed"
    assert len(calls) == 1
    sleep.assert_not_called()


def test_run_chain_advances_when_pr_already_merged(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}]},
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch"), \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr", return_value=17), \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("arnold.pipelines.megaplan.chain._commit_and_push_phase"), \
         patch("arnold.pipelines.megaplan.chain._pr_state", return_value="merged"), \
         patch("arnold.pipelines.megaplan.chain._mark_pr_ready") as ready, \
         patch("arnold.pipelines.megaplan.chain._enable_auto_merge") as merge:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    ready.assert_not_called()
    merge.assert_not_called()
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert saved.completed[0]["pr_state"] == "merged"


def test_run_chain_review_policy_awaits_and_resumes_after_pr_merge(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m1.txt")
    i2 = _touch_idea(tmp_path, "m2.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "merge_policy": "review",
            "milestones": [
                {"label": "m1", "idea": str(i1), "branch": "mp/m1"},
                {"label": "m2", "idea": str(i2)},
            ],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    with patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch"), \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr", return_value=23), \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("arnold.pipelines.megaplan.chain._commit_and_push_phase"), \
         patch("arnold.pipelines.megaplan.chain._pr_state", return_value="open"), \
         patch("arnold.pipelines.megaplan.chain._mark_pr_ready"):
        first = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert first["status"] == "awaiting_pr_merge"
    waiting = load_chain_state(spec_path)
    assert waiting.current_milestone_index == 0
    assert waiting.pr_number == 23
    assert waiting.pr_state == "awaiting_merge"

    with patch("arnold.pipelines.megaplan.chain._pr_state", return_value="open"):
        second = run_chain(spec_path, tmp_path, writer=lambda _m: None)
    assert second["status"] == "awaiting_pr_merge"
    assert load_chain_state(spec_path).current_milestone_index == 0

    with patch("arnold.pipelines.megaplan.chain._pr_state", return_value="merged"), \
         patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-m2"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m2", "done")):
        final = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert final["status"] == "done"
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert [item["label"] for item in saved.completed] == ["m1", "m2"]


def test_run_chain_reconciles_terminal_completed_pr_state(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea)}]},
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name=None,
            last_state="done",
            completed=[
                {
                    "label": "m1",
                    "plan": "plan-m1",
                    "status": "done",
                    "pr_number": 16,
                    "pr_state": "draft",
                }
            ],
        ),
    )

    with patch("arnold.pipelines.megaplan.chain._pr_state", return_value="merged") as pr_state:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, one=True)

    assert result["status"] == "done"
    pr_state.assert_called_once_with(tmp_path, 16, writer=ANY)
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["pr_state"] == "merged"


def test_run_chain_terminal_pr_reconcile_failure_is_non_fatal(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(idea)}]},
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=1,
            last_state="done",
            completed=[
                {
                    "label": "m1",
                    "plan": "plan-m1",
                    "status": "done",
                    "pr_number": 16,
                    "pr_state": "draft",
                }
            ],
        ),
    )
    messages: list[str] = []

    with patch(
        "arnold.pipelines.megaplan.chain._pr_state",
        side_effect=CliError("gh_pr_view_failed", "gh failed"),
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append, one=True)

    assert result["status"] == "done"
    assert "terminal PR reconciliation skipped" in "".join(messages)
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["pr_state"] == "draft"


# ---------------------------------------------------------------------------
# T4: chain override subcommand (runtime policy artifacts)
# ---------------------------------------------------------------------------


def test_chain_override_no_setter_flags_fails_with_cli_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bare `chain override --spec ...` with no setter flags must fail before writing."""
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
    )
    args = argparse.Namespace(
        chain_action="override",
        spec=str(spec_path),
        set_prerequisite_policy=None,
        set_validation_policy=None,
        set_review_clean_milestone_pr=None,
    )
    rc = run_chain_cli(tmp_path, args, writer=lambda _m: None)
    assert rc != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert "invalid_spec" in payload.get("error", "")
    assert "At least one --set-* flag" in payload.get("message", "")


def test_chain_override_sets_prerequisite_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """override with --set-prerequisite-policy required persists artifact."""
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
    )
    args = argparse.Namespace(
        chain_action="override",
        spec=str(spec_path),
        set_prerequisite_policy="required",
        set_validation_policy=None,
        set_review_clean_milestone_pr=None,
    )
    rc = run_chain_cli(tmp_path, args, writer=lambda _m: None)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["effective_policy"]["prerequisite_policy"] == "required"
    assert payload["effective_policy"]["source"] == "runtime_override"

    # Verify the runtime artifact was written (never chain.yaml).
    runtime_path = chain_module._runtime_policy_path_for(spec_path)
    assert runtime_path.exists()
    saved = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert saved["prerequisite_policy"] == "required"

    # Chain status reports effective policy.
    status_args = argparse.Namespace(chain_action="status", spec=str(spec_path))
    rc2 = run_chain_cli(tmp_path, status_args, writer=lambda _m: None)
    assert rc2 == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["policy"]["prerequisite_policy"] == "required"


def test_chain_override_sets_validation_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """override with --set-validation-policy required persists artifact."""
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
    )
    args = argparse.Namespace(
        chain_action="override",
        spec=str(spec_path),
        set_prerequisite_policy=None,
        set_validation_policy="required",
        set_review_clean_milestone_pr=None,
    )
    rc = run_chain_cli(tmp_path, args, writer=lambda _m: None)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["effective_policy"]["validation_policy"] == "required"


def test_chain_override_sets_review_clean_milestone_pr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """override with --set-review-clean-milestone-pr manual persists artifact."""
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
    )
    args = argparse.Namespace(
        chain_action="override",
        spec=str(spec_path),
        set_prerequisite_policy=None,
        set_validation_policy=None,
        set_review_clean_milestone_pr="manual",
    )
    rc = run_chain_cli(tmp_path, args, writer=lambda _m: None)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["effective_policy"]["review_policy"]["clean_milestone_pr"] == "manual"


def test_chain_override_accumulates_multiple_setters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Setting multiple policies in one call merges into a single artifact."""
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(_touch_idea(tmp_path, "m1.txt"))}]},
    )
    args = argparse.Namespace(
        chain_action="override",
        spec=str(spec_path),
        set_prerequisite_policy="required",
        set_validation_policy="required",
        set_review_clean_milestone_pr="manual",
    )
    rc = run_chain_cli(tmp_path, args, writer=lambda _m: None)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["effective_policy"]["prerequisite_policy"] == "required"
    assert payload["effective_policy"]["validation_policy"] == "required"
    assert payload["effective_policy"]["review_policy"]["clean_milestone_pr"] == "manual"
    # Verify artifact.
    runtime_path = chain_module._runtime_policy_path_for(spec_path)
    saved = json.loads(runtime_path.read_text(encoding="utf-8"))
    assert saved["prerequisite_policy"] == "required"
    assert saved["review_policy"]["clean_milestone_pr"] == "manual"


def test_chain_status_cli_uses_shared_spec_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Status routing should resolve spec/state through ``megaplan.chain.spec``."""
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    calls: list[tuple[str, Path]] = []
    fake_spec = chain_module.chain_spec.ChainSpec(milestones=[])
    fake_state = chain_module.chain_spec.ChainState()

    def fake_load_spec(path: Path) -> chain_module.ChainSpec:
        calls.append(("load_spec", path))
        return fake_spec

    def fake_load_chain_state(path: Path) -> chain_module.ChainState:
        calls.append(("load_chain_state", path))
        return fake_state

    monkeypatch.setattr(chain_module.chain_spec, "load_spec", fake_load_spec)
    monkeypatch.setattr(chain_module.chain_spec, "load_chain_state", fake_load_chain_state)
    monkeypatch.setattr(chain_module.chain_spec, "load_runtime_policy", lambda _path: {})
    monkeypatch.setattr(
        chain_module.chain_spec,
        "effective_chain_policy",
        lambda _spec, _overrides: {"prerequisite_policy": "none", "validation_policy": "none"},
    )
    monkeypatch.setattr(chain_module, "format_chain_status", lambda _spec, _state: {"status": "idle"})

    rc = run_chain_cli(
        tmp_path,
        argparse.Namespace(chain_action="status", spec=str(spec_path)),
        writer=lambda _msg: None,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["chain_state"] == fake_state.to_dict()
    assert payload["summary"] == {"status": "idle"}
    assert calls == [("load_spec", spec_path.resolve()), ("load_chain_state", spec_path.resolve())]


# ---------------------------------------------------------------------------
# T7: chain policy propagation into plan metadata
# ---------------------------------------------------------------------------


def test_initialized_plan_receives_chain_policy_metadata(
    tmp_path: Path,
) -> None:
    """After _init_plan returns, the plan's state.json must contain meta.chain_policy."""
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "prerequisite_policy": "required",
            "validation_policy": "required",
            "review_policy": {"clean_milestone_pr": "manual"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    # Create a stub plan directory so resolve_plan_dir succeeds.
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-stub-20260520"
    plan_dir.mkdir(parents=True)
    stub_state = {
        "current_state": "initialized",
        "meta": {},
        "idea": str(idea),
    }
    (plan_dir / "state.json").write_text(json.dumps(stub_state), encoding="utf-8")
    _write_authoritative_execution_batch(tmp_path, "plan-stub-20260520")

    with patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch"), \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr", return_value=1), \
         patch("arnold.pipelines.megaplan.chain._current_head_sha", return_value="abc123base"), \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-stub-20260520"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-stub-20260520", "done")), \
         patch("arnold.pipelines.megaplan.chain._commit_and_push_phase"), \
         patch("arnold.pipelines.megaplan.chain._pr_state", return_value="merged"):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"

    # Verify the plan state.json now contains chain policy metadata.
    updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    cp = updated_state["meta"]["chain_policy"]
    assert cp["prerequisite_policy"] == "required"
    assert cp["validation_policy"] == "required"
    assert cp["review_policy"]["clean_milestone_pr"] == "manual"
    assert cp["source"] == "chain_yaml"
    assert cp["milestone_label"] == "m1"
    assert cp["milestone_base_sha"] == "abc123base"


def test_initialized_plan_respects_runtime_override_source(
    tmp_path: Path,
) -> None:
    """When runtime overrides exist, the plan meta must reflect runtime_override source."""
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "prerequisite_policy": "none",
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    # Pre-write a runtime policy override so effective_chain_policy reports it.
    chain_module.save_runtime_policy(
        spec_path, {"prerequisite_policy": "required"}
    )

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-stub-20260520"
    plan_dir.mkdir(parents=True)
    stub_state = {
        "current_state": "initialized",
        "meta": {},
        "idea": str(idea),
    }
    (plan_dir / "state.json").write_text(json.dumps(stub_state), encoding="utf-8")
    _write_authoritative_execution_batch(tmp_path, "plan-stub-20260520")

    with patch("arnold.pipelines.megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("arnold.pipelines.megaplan.chain._checkout_milestone_branch"), \
         patch("arnold.pipelines.megaplan.chain._ensure_milestone_pr", return_value=1), \
         patch("arnold.pipelines.megaplan.chain._init_plan", return_value="plan-stub-20260520"), \
         patch("arnold.pipelines.megaplan.chain._drive_plan", return_value=_fake_outcome("plan-stub-20260520", "done")), \
         patch("arnold.pipelines.megaplan.chain._commit_and_push_phase"), \
         patch("arnold.pipelines.megaplan.chain._pr_state", return_value="merged"):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    cp = updated_state["meta"]["chain_policy"]
    assert cp["prerequisite_policy"] == "required"
    assert cp["source"] == "runtime_override"
    assert cp["milestone_label"] == "m1"


def test_load_runtime_policy_logs_corrupt_json(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    runtime_path = chain_module._runtime_policy_path_for(spec_path)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text("{not valid json", encoding="utf-8")

    caplog.set_level("WARNING", logger="megaplan")
    assert chain_module.load_runtime_policy(spec_path) == {}
    assert any("M3A_WARN_CHAIN_POLICY_READ" in record.getMessage() for record in caplog.records)


def test_branch_head_logs_git_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        chain_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git missing")),
    )

    caplog.set_level("WARNING", logger="megaplan")
    assert chain_module._branch_head(tmp_path) is None
    assert any("M3A_WARN_BRANCH_HEAD" in record.getMessage() for record in caplog.records)


def test_latest_execute_result_logs_corrupt_state(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text("{not valid json", encoding="utf-8")

    caplog.set_level("WARNING", logger="megaplan")
    assert chain_module._latest_execute_result(plan_dir) is None
    assert any("M3A_WARN_EXECUTE_RESULT_READ" in record.getMessage() for record in caplog.records)


def test_latest_execution_batch_completion_requires_corroborated_task_evidence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )

    all_done, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert all_done is False
    assert "non-authoritative tasks" in reason
    assert "T1" in reason


def test_latest_execution_batch_completion_requires_finalize_authority(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["arnold/pipelines/megaplan/chain/__init__.py"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )

    all_done, reason = chain_module._latest_execution_batch_all_tasks_done(plan_dir)

    assert all_done is False
    assert "finalize.json has non-authoritative tasks" in reason
    assert "T1" in reason
