"""Tests for megaplan.chain — the chain driver subcommand."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import ANY, patch

import pytest
import yaml

from megaplan.auto import DriverOutcome
from megaplan import chain as chain_module
from megaplan.chain import (
    ChainSpec,
    ChainState,
    MilestoneSpec,
    build_chain_parser,
    commit_plan_artifacts_to_base,
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
from megaplan.chain.git_ops import CommitResult
from megaplan.handlers.finalize import _write_finalize_artifacts
from megaplan.types import CliError, STATE_FINALIZED


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


def _write_plan_state(root: Path, plan: str, state: str) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": state, "config": {"project_dir": str(root)}}) + "\n",
        encoding="utf-8",
    )
    return plan_dir


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )


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


def test_state_path_for_canonical_brief_chain_uses_root_runtime_dir(tmp_path: Path) -> None:
    spec_dir = tmp_path / ".megaplan" / "briefs" / "artifact-store"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    state_path = _state_path_for(spec_path)

    assert state_path.parent == tmp_path / ".megaplan" / "plans" / ".chains"
    assert ".megaplan/briefs/artifact-store/.megaplan" not in state_path.as_posix()


def test_chain_review_path_for_canonical_brief_chain_uses_root_runtime_dir(tmp_path: Path) -> None:
    spec_dir = tmp_path / ".megaplan" / "briefs" / "artifact-store"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "chain.yaml"

    review_path = chain_module._chain_review_path(spec_path)

    assert review_path.parent == tmp_path / ".megaplan" / "plans" / ".chains"


def test_validate_paths_resolves_relative_ideas_from_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    idea = tmp_path / ".megaplan" / "briefs" / "artifact-store" / "m1.md"
    idea.parent.mkdir(parents=True)
    idea.write_text("milestone one", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": ".megaplan/briefs/artifact-store/m1.md",
                }
            ]
        }
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    chain_module.validate_paths(spec, tmp_path)


def test_validate_paths_skips_completed_and_adopted_current_on_resume(tmp_path: Path) -> None:
    future_idea = _touch_idea(tmp_path, "m3.txt", "future milestone")
    spec = ChainSpec.from_dict(
        {
            "milestones": [
                {"label": "m1", "idea": str(tmp_path / "missing-completed.md")},
                {"label": "m2", "idea": str(tmp_path / "missing-adopted-current.md")},
                {"label": "m3", "idea": str(future_idea)},
            ]
        }
    )
    state = ChainState(
        current_milestone_index=1,
        current_plan_name="m2-adopted-plan",
        completed=[{"label": "m1", "plan": "m1-plan", "status": "done"}],
    )

    chain_module.validate_paths(spec, tmp_path, state)


def test_validate_paths_still_requires_future_ideas_on_resume(tmp_path: Path) -> None:
    spec = ChainSpec.from_dict(
        {
            "milestones": [
                {"label": "m1", "idea": str(tmp_path / "missing-completed.md")},
                {"label": "m2", "idea": str(tmp_path / "missing-adopted-current.md")},
                {"label": "m3", "idea": str(tmp_path / "missing-future.md")},
            ]
        }
    )
    state = ChainState(
        current_milestone_index=1,
        current_plan_name="m2-adopted-plan",
        completed=[{"label": "m1", "plan": "m1-plan", "status": "done"}],
    )

    with pytest.raises(CliError) as excinfo:
        chain_module.validate_paths(spec, tmp_path, state)

    assert "m3" in excinfo.value.message


def test_load_spec_defaults_base_branch_to_main(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})

    assert load_spec(spec_path).base_branch == "main"


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


def test_commit_plan_artifacts_force_adds_ignored_files_on_base_and_restores_branch(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "main")
    (tmp_path / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "checkout", "-b", "feature")

    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    final_path = plan_dir / "final.md"
    contract_path = plan_dir / "contract.json"
    state_path.write_text('{"current_state":"finalized"}\n', encoding="utf-8")
    final_path.write_text("final review\n", encoding="utf-8")
    contract_path.write_text('{"provides":[],"assumes":[]}\n', encoding="utf-8")

    result = commit_plan_artifacts_to_base(
        tmp_path,
        "main",
        "plan-m1",
        [state_path, final_path, contract_path, plan_dir / "optional.json"],
        push_enabled=False,
    )

    assert result.committed is True
    assert result.pushed is False
    assert "optional artifact missing: .megaplan/plans/plan-m1/optional.json" in result.audit_notes
    assert _git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature"
    tracked_on_main = _git(tmp_path, "ls-tree", "-r", "--name-only", "main").stdout.splitlines()
    assert ".megaplan/plans/plan-m1/state.json" in tracked_on_main
    assert ".megaplan/plans/plan-m1/final.md" in tracked_on_main
    assert ".megaplan/plans/plan-m1/contract.json" in tracked_on_main


def test_commit_plan_artifacts_rejects_unrelated_dirty_worktree(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "main")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "checkout", "-b", "feature")
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    state_path.write_text('{"current_state":"finalized"}\n', encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        commit_plan_artifacts_to_base(
            tmp_path,
            "main",
            "plan-m1",
            [state_path],
            push_enabled=False,
        )

    assert excinfo.value.code == "dirty_worktree"
    assert _git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature"


def test_commit_plan_artifacts_requires_state_json(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "checkout", "-b", "main")
    (tmp_path / "README.md").write_text("root\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")

    with pytest.raises(CliError) as excinfo:
        commit_plan_artifacts_to_base(
            tmp_path,
            "main",
            "plan-missing",
            [],
            push_enabled=False,
        )

    assert excinfo.value.code == "missing_plan_state"


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


def test_chain_state_from_dict_defaults_reground_decisions_for_old_json() -> None:
    state = ChainState.from_dict({"current_milestone_index": 1, "retry_counts": {"m1": 2}})

    assert state.reground_decisions == {}
    assert state.retry_counts == {"m1": 2}


def test_chain_state_roundtrips_reground_decisions() -> None:
    state = ChainState(
        current_milestone_index=1,
        current_plan_name="plan-m2",
        reground_decisions={
            "m2": {
                "last_fingerprint": "abc123",
                "consecutive_count": 2,
                "decision": "stop",
                "timestamp": "2026-05-30T10:00:00Z",
                "summary": "signature changed",
                "rows": [{"symbol": "Runtime.status", "status": "MISMATCH"}],
            }
        },
    )

    raw = state.to_dict()
    assert raw["reground_decisions"] == state.reground_decisions

    reloaded = ChainState.from_dict(raw)
    assert reloaded.reground_decisions == state.reground_decisions


def test_format_chain_status_pretty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_path = _setup_three_milestones(tmp_path, seed_plan="seed-plan-20260421")
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=1,
        current_plan_name="plan-for-m2",
        last_state="done",
        completed=[
            {"label": "m1", "plan": "plan-for-m1", "status": "finalized", "plan_branch": "main"},
            {"label": "m2", "plan": "plan-for-m2", "status": "done", "plan_branch": "main"},
        ],
    )
    save_chain_state(spec_path, state)

    summary = format_chain_status(spec, state)
    # Verify existing keys are all present (backward-compatible).
    assert summary["current_milestone"] == {"label": "m2", "index": 1}
    assert summary["completed"] == [{"label": "m2", "index": 1}]
    assert summary["remaining"] == [{"label": "m1", "index": 0}, {"label": "m3", "index": 2}]
    assert summary["per_milestone"] == [
        {
            "label": "m1",
            "index": 0,
            "status": "planned",
            "planned": True,
            "executed": False,
            "plan_status": "finalized",
            "plan_branch": "main",
        },
        {
            "label": "m2",
            "index": 1,
            "status": "completed",
            "planned": True,
            "executed": True,
            "plan_status": "done",
            "plan_branch": "main",
        },
        {
            "label": "m3",
            "index": 2,
            "status": "pending",
            "planned": False,
            "executed": False,
            "plan_status": None,
            "plan_branch": None,
        },
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
    assert "Planned: 2/3" in captured.err
    assert "Executed: 1/3" in captured.err
    assert "Seed plan: seed-plan-20260421" in captured.err
    assert "Base branch: main" in captured.err
    assert "[planned] m1 (index 0, planned=1, executed=0, artifact branch main)" in captured.err
    assert "[completed] m2 (index 1, planned=1, executed=1, artifact branch main)" in captured.err


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

    with patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
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

    with patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain.auto_drive", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.workers._is_agent_available", lambda agent: True), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
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

    with patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
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
        one: bool = False,
        mode: str = "start",
        writer=None,
    ):
        del writer
        del no_push
        del one
        calls.append((spec_path_arg, root, no_git_refresh, mode))
        return {"status": "done", "reason": "", "chain_state": {}, "events": []}

    with patch("megaplan.chain.run_chain", side_effect=fake_run_chain):
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
        (spec_path.resolve(), tmp_path, True, "start"),
        (spec_path.resolve(), tmp_path, False, "start"),
    ]
    assert start_payload["status"] == "done"
    assert alias_payload["status"] == "done"


def test_chain_plan_and_execute_subcommands_parse_and_dispatch_modes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_chain_parser(subparsers)

    plan_args = parser.parse_args(["chain", "plan", "--spec", str(spec_path), "--no-git-refresh"])
    execute_args = parser.parse_args(["chain", "execute", "--spec", str(spec_path), "--one"])
    modes: list[tuple[str, bool, bool]] = []

    def fake_run_chain(
        spec_path_arg: Path,
        root: Path,
        *,
        no_git_refresh: bool = False,
        no_push: bool = False,
        one: bool = False,
        mode: str = "start",
        writer=None,
    ):
        del spec_path_arg, root, no_push, writer
        modes.append((mode, no_git_refresh, one))
        return {"status": "finalized", "reason": "", "chain_state": {}, "events": []}

    with patch("megaplan.chain.run_chain", side_effect=fake_run_chain):
        assert run_chain_cli(tmp_path, plan_args) == 0
        json.loads(capsys.readouterr().out)
        assert run_chain_cli(tmp_path, execute_args) == 0
        json.loads(capsys.readouterr().out)

    assert modes == [("plan", True, False), ("execute", False, True)]


def test_run_chain_stops_on_failure(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    drive_calls: list[str] = []

    def fake_drive(plan, **_kwargs):
        drive_calls.append(plan)
        return _fake_outcome(plan, "failed")

    with patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
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
                        "executor_notes": "finished",
                    }
                ],
            )
            return _fake_outcome(plan, "worker_blocked")
        _write_execute_plan_state(tmp_path, plan, "done")
        return _fake_outcome(plan, "done")

    with patch(
        "megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-for-{Path(idea_path).stem}",
    ), patch("megaplan.chain.auto_drive", side_effect=fake_drive), patch(
        "megaplan.chain._refresh_base_branch", lambda *a, **k: None
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
        "megaplan.chain._init_plan",
        side_effect=lambda root, idea_path, **_k: f"plan-for-{Path(idea_path).stem}",
    ), patch("megaplan.chain.auto_drive", side_effect=fake_drive), patch(
        "megaplan.chain._refresh_base_branch", lambda *a, **k: None
    ):
        result = run_chain(spec_path, tmp_path, writer=messages.append)

    assert result["status"] == "stopped"
    assert drive_calls == ["plan-for-m1"]
    assert any("treating as real block" in message for message in messages)
    saved = load_chain_state(spec_path)
    assert saved.last_state == "blocked"
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

    with patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
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
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._plan_state", side_effect=fake_plan_state), \
         patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    # Seed must be driven first, then the milestone plan.
    assert drive_calls[0] == seed_name
    assert drive_calls[1].startswith("plan-m1")


def test_drive_plan_passes_stop_at_finalized_to_auto_drive(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    spec = load_spec(spec_path)
    captured: dict[str, object] = {}

    def fake_auto_drive(plan, **kwargs):
        captured["plan"] = plan
        captured["stop_at_finalized"] = kwargs.get("stop_at_finalized")
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain.auto_drive", side_effect=fake_auto_drive):
        outcome = chain_module._drive_plan(
            tmp_path,
            "plan-m1",
            spec,
            stop_at_finalized=True,
            writer=lambda _m: None,
        )

    assert outcome.status == "finalized"
    assert captured == {"plan": "plan-m1", "stop_at_finalized": True}


def test_drive_plan_with_blocked_execute_recovery_preserves_stop_at_finalized(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    spec = load_spec(spec_path)
    plan = "plan-m1"
    _write_blocked_execute_batch(
        tmp_path,
        plan,
        [{"task_id": "T1", "status": "done", "executor_notes": "finished"}],
    )
    calls: list[bool] = []

    def fake_drive(root, driven_plan, driven_spec, **kwargs):
        del root, driven_spec
        assert driven_plan == plan
        calls.append(bool(kwargs.get("stop_at_finalized")))
        if len(calls) == 1:
            return _fake_outcome(plan, "worker_blocked")
        _write_execute_plan_state(tmp_path, plan, "done")
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._drive_plan", side_effect=fake_drive):
        outcome = chain_module._drive_plan_with_blocked_execute_recovery(
            tmp_path,
            plan,
            spec,
            stop_at_finalized=True,
            writer=lambda _m: None,
        )

    assert outcome.status == "finalized"
    assert calls == [True, True]


def test_handle_outcome_advances_on_finalized_without_mutating_ladder_state(tmp_path: Path) -> None:
    spec_path = _setup_two_milestones(tmp_path)
    spec = load_spec(spec_path)
    milestone = MilestoneSpec(label="m1", idea=_touch_idea(tmp_path, "m1.txt"))
    state = ChainState(
        retry_counts={"m1": 2},
        ladder_stage={"m1": "terminal"},
        profile_bumps={"m1": "apex"},
        robustness_bumps={"m1": "extreme"},
        depth_bumps={"m1": "max"},
    )

    decision = chain_module._handle_outcome(
        _fake_outcome("plan-m1", "finalized"),
        spec=spec,
        writer=lambda _m: None,
        milestone=milestone,
        state=state,
    )

    assert decision == "advance"
    assert state.retry_counts == {"m1": 2}
    assert state.ladder_stage == {"m1": "terminal"}
    assert state.profile_bumps == {"m1": "apex"}
    assert state.robustness_bumps == {"m1": "extreme"}
    assert state.depth_bumps == {"m1": "max"}


def test_run_chain_propagates_stop_at_finalized_through_seed_and_milestones(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    seed_name = "seed-plan-20260415"
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
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    calls: list[tuple[str, bool]] = []

    def fake_drive(root, plan, spec, **kwargs):
        del root, spec
        calls.append((plan, bool(kwargs.get("stop_at_finalized"))))
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._plan_state", side_effect=lambda _root, plan, *, timeout: "planned" if plan == seed_name else "missing"), \
         patch("megaplan.chain._drive_plan_with_blocked_execute_recovery", side_effect=fake_drive), \
         patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _m: None,
            stop_at_finalized=True,
        )

    assert result["status"] == "done"
    assert calls == [(seed_name, True), ("plan-m1", True)]
    saved = load_chain_state(spec_path)
    assert [item["status"] for item in saved.completed] == ["finalized", "finalized"]


# ---------------------------------------------------------------------------
# --no-git-refresh flag
# ---------------------------------------------------------------------------


def test_no_git_refresh_suppresses_subprocess_calls(tmp_path: Path) -> None:
    """With no_git_refresh=True, _refresh_base_branch must not invoke any subprocess."""
    from megaplan.chain import _refresh_base_branch

    msgs: list[str] = []
    with patch("megaplan.chain.subprocess.run") as mock_run:
        _refresh_base_branch(tmp_path, "setup/cloud", writer=msgs.append, no_git_refresh=True)
    assert mock_run.call_count == 0
    assert any("skipping git refresh" in m for m in msgs)


def test_refresh_base_branch_default_invokes_git(tmp_path: Path) -> None:
    """Default behavior (no_git_refresh=False) still issues the git commands."""
    from megaplan.chain import _refresh_base_branch

    class _Proc:
        returncode = 0

    with patch("megaplan.chain.subprocess.run", return_value=_Proc()) as mock_run:
        _refresh_base_branch(tmp_path, "setup/cloud", writer=lambda _m: None)
    # fetch + checkout + pull
    assert mock_run.call_count == 3
    cmds = [call.args[0] for call in mock_run.call_args_list]
    assert cmds[0] == ["git", "fetch", "origin", "setup/cloud"]
    assert cmds[1] == ["git", "checkout", "setup/cloud"]
    assert cmds[2] == ["git", "pull", "--ff-only", "origin", "setup/cloud"]


def test_refresh_base_branch_aborts_on_git_failure(tmp_path: Path) -> None:
    """A failed checkout/pull must stop the chain before stale work executes."""
    from megaplan.chain import _refresh_base_branch

    calls = [
        subprocess.CompletedProcess(
            args=["git", "fetch", "origin", "setup/cloud"],
            returncode=0,
            stdout="",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=["git", "checkout", "setup/cloud"],
            returncode=1,
            stdout="",
            stderr="local changes would be overwritten",
        ),
    ]
    msgs: list[str] = []

    with patch("megaplan.chain.subprocess.run", side_effect=calls):
        with pytest.raises(CliError) as excinfo:
            _refresh_base_branch(tmp_path, "setup/cloud", writer=msgs.append)

    assert excinfo.value.code == "git_refresh_failed"
    assert "git checkout setup/cloud exited 1" in excinfo.value.message
    assert any("local changes would be overwritten" in msg for msg in msgs)


def test_plan_state_uses_module_launcher(tmp_path: Path) -> None:
    class _Proc:
        returncode = 0
        stdout = '{"state": "planned"}'

    with patch("megaplan.chain.subprocess.run", return_value=_Proc()) as mock_run:
        from megaplan.chain import _plan_state

        assert _plan_state(tmp_path, "demo-plan", timeout=5) == "planned"

    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "megaplan",
        "status",
        "--plan",
        "demo-plan",
    ]


def test_init_plan_uses_module_launcher(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )

    with patch("megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from megaplan.chain import _init_plan

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
        "megaplan",
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


def test_init_plan_warns_when_vendor_ignored_by_locked_profile(tmp_path: Path) -> None:
    idea_path = _touch_idea(tmp_path, "m1.txt", "hello world")
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"plan": "demo-plan"}',
        stderr="",
    )
    messages: list[str] = []

    with patch("megaplan.chain.subprocess.run", return_value=proc), \
         patch("megaplan.chain.load_profile_metadata", return_value={"apex": {"vendor_locked": True}}):
        from megaplan.chain import _init_plan

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

    with patch("megaplan.chain.subprocess.run", return_value=proc), \
         patch("megaplan.chain.load_profile_metadata", return_value={"apex": {"vendor_locked": True}}), \
         patch("megaplan.chain._resolve_default_vendor", return_value="codex"):
        from megaplan.chain import _init_plan

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
    with patch("megaplan.chain.load_profile_metadata", side_effect=RuntimeError("metadata offline")):
        with pytest.raises(CliError, match="M3B_HALT_VENDOR_LOCK_PROFILE_LOAD"):
            chain_module._warn_vendor_ignored_for_locked_profile(
                tmp_path,
                profile="apex",
                vendor="codex",
                writer=lambda _: None,
            )


def test_vendor_lock_with_no_profile_and_no_vendor_is_noop(tmp_path: Path) -> None:
    writer_calls: list[str] = []

    with patch("megaplan.chain.load_profile_metadata") as load_metadata:
        chain_module._warn_vendor_ignored_for_locked_profile(
            tmp_path,
            profile=None,
            vendor=None,
            writer=writer_calls.append,
        )

    load_metadata.assert_not_called()
    assert writer_calls == []


def test_vendor_lock_default_vendor_resolution_failure_raises(tmp_path: Path) -> None:
    with patch("megaplan.chain.load_profile_metadata", return_value={"apex": {"vendor_locked": True}}), \
         patch("megaplan.chain._resolve_default_vendor", side_effect=RuntimeError("no default vendor")):
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

    with patch("megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from megaplan.chain import _init_plan

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

    with patch("megaplan.chain.subprocess.run", return_value=proc) as mock_run:
        from megaplan.chain import _init_plan

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

    with patch("megaplan.chain._init_plan", side_effect=lambda root, idea_path, **_k: f"plan-{Path(idea_path).stem}"), \
         patch("megaplan.chain.auto_drive", side_effect=fake_drive), \
         patch("megaplan.chain._refresh_base_branch", side_effect=fake_refresh):
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

    with patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain.auto_drive", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr") as ensure_pr:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_push=True)

    assert result["status"] == "done"
    checkout.assert_not_called()
    ensure_pr.assert_not_called()


def test_commit_and_push_phase_skips_empty_diff(tmp_path: Path) -> None:
    from megaplan.chain import _commit_and_push_phase

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    def fake_run(cmd, **_kwargs):
        assert cmd == ["git", "diff", "--cached", "--quiet"]
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("megaplan.chain._run_command", side_effect=fake_run_command), \
         patch("megaplan.chain.subprocess.run", side_effect=fake_run):
        _commit_and_push_phase(
            tmp_path,
            "mp/m1",
            "plan-m1",
            "plan",
            writer=lambda _m: None,
        )

    assert commands == [["git", "add", "-A"]]


def test_ensure_milestone_pr_skips_when_gh_missing(tmp_path: Path) -> None:
    from megaplan.chain import _ensure_milestone_pr

    messages: list[str] = []
    with patch("megaplan.chain.shutil.which", return_value=None), \
         patch("megaplan.chain._list_open_pr_for_branch") as list_pr, \
         patch("megaplan.chain._run_command") as run_command:
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

    with patch("megaplan.chain.subprocess.run", side_effect=fake_run):
        proc = _run_command(
            tmp_path,
            ["gh", "pr", "view", "1"],
            writer=lambda _m: None,
        )

    assert proc.returncode == 0
    assert len(calls) == 2
    assert "env" not in calls[0]


def test_checkout_milestone_branch_starts_from_configured_base_branch(tmp_path: Path) -> None:
    from megaplan.chain import _checkout_milestone_branch

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("megaplan.chain._remote_branch_exists", return_value=False), \
         patch("megaplan.chain._run_command", side_effect=fake_run_command):
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


def test_ensure_milestone_pr_uses_configured_base_branch(tmp_path: Path) -> None:
    from megaplan.chain import _ensure_milestone_pr

    commands: list[list[str]] = []

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code="command_failed"):
        del root, writer, timeout, error_code
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "https://github.com/acme/app/pull/42\n", "")

    with patch("megaplan.chain.shutil.which", return_value="/usr/bin/gh"), \
         patch("megaplan.chain._list_open_pr_for_branch", return_value=None), \
         patch("megaplan.chain._run_command", side_effect=fake_run_command):
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

    def fake_drive(root, plan, spec, *, on_phase_complete=None, writer, **_kwargs):
        del root, spec, writer
        assert plan == "plan-m1"
        assert on_phase_complete is not None
        on_phase_complete("plan", 0, "", "")
        on_phase_complete("execute", 0, "", "")
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr", return_value=17) as ensure_pr, \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch("megaplan.chain._commit_and_push_phase", side_effect=lambda root, branch, plan, phase, **_kwargs: commits.append((branch, plan, phase))), \
         patch("megaplan.chain._pr_state", return_value="open"), \
         patch("megaplan.chain._mark_pr_ready") as ready, \
         patch("megaplan.chain._enable_auto_merge", return_value="open") as merge:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    checkout.assert_called_once_with(
        tmp_path,
        "mp/m1",
        base_branch="setup/cloud",
        writer=ANY,
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


def test_run_chain_plan_mode_skips_branch_pr_lifecycle(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "base_branch": "setup/cloud",
            "milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}],
        },
    )
    (tmp_path / ".megaplan" / "plans").mkdir(parents=True)

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, writer
        assert plan == "plan-m1"
        assert stop_at_finalized is True
        assert on_phase_complete is None
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr") as ensure_pr, \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             return_value=CommitResult(committed=True, pushed=False, base_branch="setup/cloud"),
         ) as commit_artifacts, \
         patch("megaplan.chain._commit_and_push_phase") as commit_push, \
         patch("megaplan.chain._pr_state") as pr_state, \
         patch("megaplan.chain._mark_pr_ready") as ready, \
         patch("megaplan.chain._enable_auto_merge") as merge:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert result["status"] == "done"
    checkout.assert_not_called()
    ensure_pr.assert_not_called()
    commit_push.assert_not_called()
    pr_state.assert_not_called()
    ready.assert_not_called()
    merge.assert_not_called()
    commit_artifacts.assert_called_once()
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["status"] == "finalized"
    assert saved.completed[0]["plan_branch"] == "setup/cloud"
    assert saved.completed[0]["pr_number"] is None
    assert saved.completed[0]["pr_state"] is None


def test_run_chain_plan_mode_skips_awaiting_pr_merge_resume_check(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "merge_policy": "review",
            "milestones": [{"label": "m1", "idea": str(idea), "branch": "mp/m1"}],
        },
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="plan-m1",
            last_state="awaiting_pr_merge",
            pr_number=23,
            pr_state="awaiting_merge",
        ),
    )

    with patch("megaplan.chain._pr_state") as pr_state:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert result["status"] == "done"
    pr_state.assert_not_called()
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 1
    assert saved.pr_number is None
    assert saved.pr_state is None


def test_run_chain_plan_mode_records_finalized_only_after_artifact_durability(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {"base_branch": "setup/cloud", "milestones": [{"label": "m1", "idea": str(idea)}]},
    )
    (tmp_path / ".megaplan" / "plans" / "plan-m1").mkdir(parents=True)
    (tmp_path / ".megaplan" / "plans" / "plan-m1" / "state.json").write_text(
        json.dumps({"current_state": STATE_FINALIZED}) + "\n",
        encoding="utf-8",
    )

    def fake_commit(root, base_branch, plan_name, artifact_paths, push_enabled, dry_run=False):
        del root, push_enabled, dry_run
        assert base_branch == "setup/cloud"
        assert plan_name == "plan-m1"
        relpaths = {path.relative_to(tmp_path).as_posix() for path in artifact_paths}
        assert ".megaplan/plans/plan-m1/final.md" in relpaths
        assert ".megaplan/plans/plan-m1/finalize.json" in relpaths
        assert ".megaplan/plans/plan-m1/state.json" in relpaths
        assert ".megaplan/plans/plan-m1/contract.json" in relpaths
        assert idea.relative_to(tmp_path).as_posix() in relpaths
        assert load_chain_state(spec_path).completed == []
        return CommitResult(
            committed=True,
            pushed=False,
            commit_sha="abc123",
            base_branch=base_branch,
            audit_notes=["optional artifact missing: .megaplan/plans/plan-m1/final.md"],
        )

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "finalized")), \
         patch("megaplan.chain.commit_plan_artifacts_to_base", side_effect=fake_commit):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert result["status"] == "done"
    saved = load_chain_state(spec_path)
    assert saved.completed == [
        {
            "label": "m1",
            "plan": "plan-m1",
            "status": "finalized",
            "plan_branch": "setup/cloud",
            "artifact_commit_sha": "abc123",
            "artifact_pushed": False,
            "artifact_audit_notes": ["optional artifact missing: .megaplan/plans/plan-m1/final.md"],
            "pr_number": None,
            "pr_state": None,
        }
    ]


def test_run_chain_plan_mode_durability_failure_does_not_record_finalized(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    (tmp_path / ".megaplan" / "plans" / "plan-m1").mkdir(parents=True)
    (tmp_path / ".megaplan" / "plans" / "plan-m1" / "state.json").write_text(
        json.dumps({"current_state": STATE_FINALIZED}) + "\n",
        encoding="utf-8",
    )

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "finalized")), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             side_effect=CliError("git_commit_artifacts_failed", "durability failed"),
         ):
        with pytest.raises(CliError) as excinfo:
            run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert excinfo.value.code == "git_commit_artifacts_failed"
    saved = load_chain_state(spec_path)
    assert saved.completed == []


def test_run_chain_two_pass_modes_finalize_then_execute_milestones_in_order(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m1.txt")
    i2 = _touch_idea(tmp_path, "m2.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "base_branch": "setup/cloud",
            "milestones": [
                {"label": "m1", "idea": str(i1), "branch": "mp/m1"},
                {"label": "m2", "idea": str(i2), "branch": "mp/m2"},
            ],
        },
    )
    planned_commits: list[tuple[str, str, list[str]]] = []
    executed_plans: list[str] = []
    plan_names = iter(["plan-m1", "plan-m2"])

    def fake_plan_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, writer
        assert stop_at_finalized is True
        assert on_phase_complete is None
        _write_plan_state(root, plan, STATE_FINALIZED)
        return _fake_outcome(plan, "finalized")

    def fake_commit(root, base_branch, plan_name, artifact_paths, push_enabled, dry_run=False):
        del root, push_enabled, dry_run
        planned_commits.append(
            (
                base_branch,
                plan_name,
                sorted(path.name for path in artifact_paths),
            )
        )
        return CommitResult(committed=True, pushed=False, commit_sha=f"sha-{plan_name}", base_branch=base_branch)

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr") as ensure_pr, \
         patch("megaplan.chain._commit_and_push_phase") as commit_push, \
         patch("megaplan.chain._init_plan", side_effect=lambda *args, **kwargs: next(plan_names)), \
         patch("megaplan.chain._drive_plan", side_effect=fake_plan_drive), \
         patch("megaplan.chain.commit_plan_artifacts_to_base", side_effect=fake_commit):
        planned = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert planned["status"] == "done"
    checkout.assert_not_called()
    ensure_pr.assert_not_called()
    commit_push.assert_not_called()
    assert planned_commits == [
        ("setup/cloud", "plan-m1", ["contract.json", "final.md", "finalize.json", "m1.txt", "state.json"]),
        ("setup/cloud", "plan-m2", ["contract.json", "final.md", "finalize.json", "m2.txt", "state.json"]),
    ]
    saved = load_chain_state(spec_path)
    assert [(entry["label"], entry["status"], entry["plan_branch"]) for entry in saved.completed] == [
        ("m1", "finalized", "setup/cloud"),
        ("m2", "finalized", "setup/cloud"),
    ]

    def fake_execute_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        executed_plans.append(plan)
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch"), \
         patch("megaplan.chain._ensure_milestone_pr", return_value=23), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="merged"), \
         patch("megaplan.chain._mark_pr_ready"), \
         patch("megaplan.chain._enable_auto_merge"), \
         patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", side_effect=fake_execute_drive):
        executed = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert executed["status"] == "done"
    init_plan.assert_not_called()
    assert executed_plans == ["plan-m1", "plan-m2"]
    saved = load_chain_state(spec_path)
    assert [(entry["label"], entry["status"]) for entry in saved.completed] == [
        ("m1", "done"),
        ("m2", "done"),
    ]


def test_run_chain_execute_mode_recomputes_cursor_from_finalized_record(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    _write_plan_state(tmp_path, "plan-m1", STATE_FINALIZED)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name=None,
            pr_number=9,
            pr_state="open",
            completed=[{"label": "m1", "plan": "plan-m1", "status": "finalized"}],
        ),
    )

    with patch("megaplan.chain._plan_state", return_value=STATE_FINALIZED), \
         patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")) as drive:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    drive.assert_called_once()
    saved = load_chain_state(spec_path)
    assert saved.completed[-1]["status"] == "done"
    assert saved.current_milestone_index == 1
    assert saved.current_plan_name is None
    assert saved.pr_number is None
    assert saved.pr_state is None


def test_run_chain_execute_mode_skips_done_records(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m1.txt")
    i2 = _touch_idea(tmp_path, "m2.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "m1", "idea": str(i1)}, {"label": "m2", "idea": str(i2)}]},
    )
    _write_plan_state(tmp_path, "plan-m2", STATE_FINALIZED)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "m1", "plan": "plan-m1", "status": "done"},
                {"label": "m2", "plan": "plan-m2", "status": "finalized"},
            ],
        ),
    )

    with patch("megaplan.chain._plan_state", return_value=STATE_FINALIZED), \
         patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m2", "done")) as drive:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    assert drive.call_args.args[1] == "plan-m2"
    saved = load_chain_state(spec_path)
    assert [entry["label"] for entry in saved.completed] == ["m1", "m2"]
    assert saved.completed[-1]["status"] == "done"


def test_run_chain_execute_retry_preserves_finalized_plan_identity(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "on_failure": {"retry": "retry_milestone", "abort": "stop_chain"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    _write_plan_state(tmp_path, "plan-m1", STATE_FINALIZED)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "plan": "plan-m1", "status": "finalized", "plan_branch": "main"}],
        ),
    )
    outcomes = iter([
        _fake_outcome("plan-m1", "failed"),
        _fake_outcome("plan-m1", "done"),
    ])
    seen_plans: list[str] = []

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        seen_plans.append(plan)
        return next(outcomes)

    with patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    assert seen_plans == ["plan-m1", "plan-m1"]
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["plan"] == "plan-m1"
    assert saved.completed[0]["status"] == "done"


def test_run_chain_execute_mode_rehydrates_finalized_seed_before_milestones(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    seed_name = "seed-plan-20260415"
    spec_path = _write_spec(
        tmp_path,
        {
            "seed": {"plan": seed_name},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    _write_plan_state(tmp_path, seed_name, STATE_FINALIZED)
    _write_plan_state(tmp_path, "plan-m1", STATE_FINALIZED)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=1,
            completed=[
                {"label": "seed", "plan": seed_name, "status": "finalized"},
                {"label": "m1", "plan": "plan-m1", "status": "finalized", "plan_branch": "main"},
            ],
        ),
    )
    seen_plans: list[str] = []

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        seen_plans.append(plan)
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    assert seen_plans == [seed_name, "plan-m1"]
    saved = load_chain_state(spec_path)
    assert [entry["status"] for entry in saved.completed] == ["done", "done"]
    assert saved.current_milestone_index == 1


def test_run_chain_plan_retry_reinitializes_plan_name(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "on_failure": {"retry": "retry_milestone", "abort": "stop_chain"},
            "milestones": [{"label": "m1", "idea": str(idea)}],
        },
    )
    outcomes = iter([
        _fake_outcome("plan-m1a", "failed"),
        _fake_outcome("plan-m1b", "finalized"),
    ])
    seen_plans: list[str] = []

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        seen_plans.append(plan)
        return next(outcomes)

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", side_effect=["plan-m1a", "plan-m1b"]) as init_plan, \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             return_value=CommitResult(committed=True, pushed=False, base_branch="main"),
         ):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert result["status"] == "done"
    assert init_plan.call_count == 2
    assert seen_plans == ["plan-m1a", "plan-m1b"]
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["plan"] == "plan-m1b"
    assert saved.current_plan_name is None


def test_run_chain_execute_mode_clears_stale_approval_and_relies_on_execute_path(
    tmp_path: Path,
) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    plan_dir = _write_plan_state(tmp_path, "plan-m1", STATE_FINALIZED)
    state_path = plan_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "plan-m1",
                "current_state": STATE_FINALIZED,
                "config": {"project_dir": str(tmp_path), "auto_approve": True},
                "meta": {"user_approved_gate": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "plan": "plan-m1", "status": "finalized", "plan_branch": "main"}],
        ),
    )

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        assert payload["config"]["auto_approve"] is False
        assert payload["meta"].get("user_approved_gate") is None
        payload["meta"]["user_approved_gate"] = True
        state_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["config"]["auto_approve"] is False
    assert persisted["meta"]["user_approved_gate"] is True


def test_run_chain_execute_mode_all_done_returns_success_without_init(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    save_chain_state(
        spec_path,
        ChainState(current_milestone_index=1, completed=[{"label": "m1", "plan": "plan-m1", "status": "done"}]),
    )

    with patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan") as drive:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    drive.assert_not_called()


def test_run_chain_execute_mode_missing_finalized_record_errors(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    save_chain_state(spec_path, ChainState(current_milestone_index=1, completed=[]))

    with pytest.raises(CliError) as excinfo, patch("megaplan.chain._init_plan") as init_plan:
        run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert excinfo.value.code == "missing_finalized_record"
    init_plan.assert_not_called()


def test_run_chain_execute_mode_missing_state_json_errors(tmp_path: Path) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    (tmp_path / ".megaplan" / "plans" / "plan-m1").mkdir(parents=True)
    save_chain_state(
        spec_path,
        ChainState(completed=[{"label": "m1", "plan": "plan-m1", "status": "finalized"}]),
    )

    with pytest.raises(CliError) as excinfo, patch("megaplan.chain._init_plan") as init_plan:
        run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert excinfo.value.code == "missing_finalized_state"
    init_plan.assert_not_called()


@pytest.mark.parametrize(
    ("record", "state_payload", "expected_code"),
    [
        ({"label": "m1", "status": "finalized"}, None, "missing_finalized_plan"),
        ({"label": "m1", "plan": "plan-m1", "status": "finalized"}, None, "missing_finalized_plan_dir"),
        ({"label": "m1", "plan": "plan-m1", "status": "finalized"}, "{not json}\n", "invalid_finalized_state"),
        (
            {"label": "m1", "plan": "plan-m1", "status": "finalized"},
            json.dumps({"name": "plan-m1", "current_state": "planned"}) + "\n",
            "non_resumable_finalized_state",
        ),
    ],
)
def test_run_chain_execute_mode_corrupt_finalized_record_errors_clearly(
    tmp_path: Path,
    record: dict[str, str],
    state_payload: str | None,
    expected_code: str,
) -> None:
    idea = _touch_idea(tmp_path, "m1.txt")
    spec_path = _write_spec(tmp_path, {"milestones": [{"label": "m1", "idea": str(idea)}]})
    if "plan" in record and state_payload is not None:
        plan_dir = tmp_path / ".megaplan" / "plans" / record["plan"]
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(state_payload, encoding="utf-8")
    save_chain_state(spec_path, ChainState(current_milestone_index=1, completed=[record]))

    with pytest.raises(CliError) as excinfo, patch("megaplan.chain._init_plan") as init_plan:
        run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert excinfo.value.code == expected_code
    init_plan.assert_not_called()


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

    with patch("megaplan.chain._plan_state", return_value="planned"), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr", return_value=17) as ensure_pr, \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="merged"), \
         patch("megaplan.chain._mark_pr_ready"), \
         patch("megaplan.chain._enable_auto_merge"):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    checkout.assert_called_once_with(
        tmp_path,
        "mp/m1",
        base_branch="setup/cloud",
        writer=ANY,
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

    with patch("megaplan.chain._run_command", side_effect=fake_run):
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

    with patch("megaplan.chain._run_command", side_effect=fake_run):
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

    with patch("megaplan.chain._run_command", side_effect=fake_run), \
         patch("megaplan.chain.time.sleep") as sleep:
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

    with patch("megaplan.chain._run_command", side_effect=fake_run), \
         patch("megaplan.chain.time.sleep") as sleep:
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

    with patch("megaplan.chain._run_command", side_effect=fake_run), \
         patch("megaplan.chain.time.sleep") as sleep:
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

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch"), \
         patch("megaplan.chain._ensure_milestone_pr", return_value=17), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="merged"), \
         patch("megaplan.chain._mark_pr_ready") as ready, \
         patch("megaplan.chain._enable_auto_merge") as merge:
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
    _write_plan_state(tmp_path, "plan-m1", STATE_FINALIZED)
    _write_plan_state(tmp_path, "plan-m2", STATE_FINALIZED)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "m1", "plan": "plan-m1", "status": "finalized", "plan_branch": "main"},
                {"label": "m2", "plan": "plan-m2", "status": "finalized", "plan_branch": "main"},
            ],
        ),
    )

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch") as checkout, \
         patch("megaplan.chain._ensure_milestone_pr", return_value=23) as ensure_pr, \
         patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m1", "done")) as drive, \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="open"), \
         patch("megaplan.chain._mark_pr_ready"):
        first = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert first["status"] == "awaiting_pr_merge"
    waiting = load_chain_state(spec_path)
    assert waiting.current_milestone_index == 0
    assert waiting.current_plan_name == "plan-m1"
    assert waiting.pr_number == 23
    assert waiting.pr_state == "awaiting_merge"
    init_plan.assert_not_called()
    drive.assert_called_once()
    checkout.assert_called_once()
    ensure_pr.assert_called_once()

    with patch("megaplan.chain._pr_state", return_value="open"), \
         patch("megaplan.chain._ensure_milestone_pr") as ensure_pr, \
         patch("megaplan.chain._drive_plan") as drive:
        second = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")
    assert second["status"] == "awaiting_pr_merge"
    ensure_pr.assert_not_called()
    drive.assert_not_called()
    waiting = load_chain_state(spec_path)
    assert waiting.current_milestone_index == 0
    assert waiting.pr_number == 23

    with patch("megaplan.chain._pr_state", return_value="merged"), \
         patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-m2", "done")) as drive:
        final = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert final["status"] == "done"
    init_plan.assert_not_called()
    drive.assert_called_once()
    assert drive.call_args.args[1] == "plan-m2"
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert [item["label"] for item in saved.completed] == ["m1", "m2"]
    assert [item["status"] for item in saved.completed] == ["done", "done"]


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

    with patch("megaplan.chain._pr_state", return_value="merged") as pr_state:
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
        "megaplan.chain._pr_state",
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

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch"), \
         patch("megaplan.chain._ensure_milestone_pr", return_value=1), \
         patch("megaplan.chain._init_plan", return_value="plan-stub-20260520"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-stub-20260520", "done")), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="merged"):
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

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._checkout_milestone_branch"), \
         patch("megaplan.chain._ensure_milestone_pr", return_value=1), \
         patch("megaplan.chain._init_plan", return_value="plan-stub-20260520"), \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-stub-20260520", "done")), \
         patch("megaplan.chain._commit_and_push_phase"), \
         patch("megaplan.chain._pr_state", return_value="merged"):
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


# ---------------------------------------------------------------------------
# T9/T10/T12/T13: contract metadata, review, and execute reground decisions
# ---------------------------------------------------------------------------


def _write_contract(root: Path, plan: str, contract: dict[str, object]) -> None:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "contract.json").write_text(json.dumps(contract), encoding="utf-8")


def _contract_finalize_payload(
    *,
    provides: list[dict[str, object]],
    assumes: list[dict[str, object]],
    meta_commentary: str,
) -> dict[str, object]:
    return {
        "tasks": [],
        "watch_items": [],
        "sense_checks": [],
        "meta_commentary": meta_commentary,
        "validation": {
            "plan_steps_covered": [],
            "orphan_tasks": [],
            "completeness_notes": "ok",
            "coverage_complete": True,
        },
        "provides": provides,
        "assumes": assumes,
    }


def _write_finalized_contract_artifacts(
    root: Path,
    plan: str,
    *,
    payload: dict[str, object],
) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    state_path = plan_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"name": plan, "config": {}}
    state["name"] = plan
    state["current_state"] = STATE_FINALIZED
    state["iteration"] = state.get("iteration", 1) or 1
    config = state.setdefault("config", {})
    if not isinstance(config, dict):
        state["config"] = config = {}
    config["project_dir"] = str(root)
    config["mode"] = "doc"
    state.setdefault("plan_versions", [{"version": 1, "file": "plan_v1.md"}])
    (plan_dir / "plan_v1.md").write_text("# Plan\n", encoding="utf-8")
    _write_finalize_artifacts(plan_dir, payload, state)
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    return plan_dir


def _write_plan_only_finalized_state(root: Path, plan: str, *, plan_only: bool = True) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "name": plan,
        "current_state": STATE_FINALIZED,
        "iteration": 1,
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "config": {"project_dir": str(root)},
        "meta": {
            "chain_policy": {
                "plan_only": plan_only,
                "contract_context": {"plan_only": plan_only},
            }
        },
    }
    (plan_dir / "plan_v1.md").write_text("# Plan\n", encoding="utf-8")
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    return plan_dir


def test_run_chain_plan_mode_injects_dependency_provides_metadata_and_preserves_prep_direction(
    tmp_path: Path,
) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {
                    "label": "M-b",
                    "idea": str(i2),
                    "depends_on": ["M-a"],
                    "prep_direction": "keep the user's prep direction",
                },
            ]
        },
    )
    plan_names = iter(["plan-ma", "plan-mb"])
    prep_directions: list[str | None] = []

    def fake_init(root, idea_path, **kwargs):
        del idea_path
        plan = next(plan_names)
        prep_directions.append(kwargs["prep_direction"])
        _write_plan_state(root, plan, "initialized")
        return plan

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, on_phase_complete, writer
        assert stop_at_finalized is True
        state_path = root / ".megaplan" / "plans" / plan / "state.json"
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        raw_state["current_state"] = STATE_FINALIZED
        state_path.write_text(json.dumps(raw_state) + "\n", encoding="utf-8")
        if plan == "plan-ma":
            _write_contract(
                root,
                plan,
                {
                    "provides": [
                        {
                            "name": "Planner surface",
                            "interfaces": [
                                {
                                    "symbol": "Planner.run",
                                    "path": "megaplan/planner.py",
                                    "signature": "Planner.run(config) -> None",
                                }
                            ],
                        }
                    ],
                    "assumes": [],
                },
            )
        else:
            _write_contract(root, plan, {"provides": [], "assumes": []})
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             side_effect=lambda root, base, plan, paths, push, dry_run=False: CommitResult(
                 committed=True, pushed=False, commit_sha=f"sha-{plan}", base_branch=base
             ),
         ):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert result["status"] == "done"
    assert prep_directions == [None, "keep the user's prep direction"]
    mb_state = json.loads((tmp_path / ".megaplan" / "plans" / "plan-mb" / "state.json").read_text(encoding="utf-8"))
    policy = mb_state["meta"]["chain_policy"]
    assert policy["plan_only"] is True
    assert policy["dependency_labels"] == ["M-a"]
    assert policy["provided_paths"] == {"M-a": ["megaplan/planner.py"]}
    context = policy["contract_context"]
    assert context["plan_only"] is True
    assert context["milestone_label"] == "M-b"
    assert context["upstream_contracts"][0]["milestone_label"] == "M-a"
    assert context["upstream_contracts"][0]["provides"][0]["interfaces"][0]["symbol"] == "Planner.run"


def test_run_chain_start_mode_leaves_dependency_contract_prompts_inert(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    plan_names = iter(["plan-ma", "plan-mb"])

    def fake_init(root, idea_path, **_kwargs):
        del idea_path
        plan = next(plan_names)
        _write_plan_state(root, plan, "initialized")
        return plan

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, stop_at_finalized, on_phase_complete, writer
        state_path = root / ".megaplan" / "plans" / plan / "state.json"
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        raw_state["current_state"] = "done"
        state_path.write_text(json.dumps(raw_state) + "\n", encoding="utf-8")
        _write_contract(
            root,
            plan,
            {
                "provides": [
                    {
                        "name": "Start-mode provide",
                        "interfaces": [{"symbol": "S.run", "path": "s.py", "signature": "S.run()"}],
                    }
                ],
                "assumes": [],
            },
        )
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None)

    assert result["status"] == "done"
    mb_state = json.loads((tmp_path / ".megaplan" / "plans" / "plan-mb" / "state.json").read_text(encoding="utf-8"))
    policy = mb_state["meta"]["chain_policy"]
    assert policy["plan_only"] is False
    assert "contract_context" not in policy


def test_run_chain_execute_reground_records_skip_when_contract_unavailable(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    _write_plan_only_finalized_state(tmp_path, "plan-mb")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "M-a", "plan": "plan-ma", "status": "done"},
                {"label": "M-b", "plan": "plan-mb", "status": "finalized"},
            ],
        ),
    )

    with patch("megaplan.chain._init_plan") as init_plan, \
         patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-mb", "done")):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    init_plan.assert_not_called()
    saved = load_chain_state(spec_path)
    assert saved.reground_decisions["M-b"]["status"] == "skipped"
    assert saved.reground_decisions["M-b"]["reason"] == "downstream_contract_unavailable"


def test_run_chain_execute_reground_records_pass_before_driver(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    _write_plan_only_finalized_state(tmp_path, "plan-mb")
    _write_contract(
        tmp_path,
        "plan-ma",
        {
            "provides": [
                {
                    "name": "Planner",
                    "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run()"}],
                }
            ],
            "assumes": [],
        },
    )
    _write_contract(
        tmp_path,
        "plan-mb",
        {
            "provides": [],
            "assumes": [
                {
                    "name": "Planner",
                    "upstream_milestone": "M-a",
                    "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run()"}],
                }
            ],
        },
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "M-a", "plan": "plan-ma", "status": "done"},
                {"label": "M-b", "plan": "plan-mb", "status": "finalized"},
            ],
        ),
    )

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, plan, spec, stop_at_finalized, on_phase_complete, writer
        assert load_chain_state(spec_path).reground_decisions["M-b"]["status"] == "pass"
        return _fake_outcome("plan-mb", "done")

    with patch("megaplan.chain._drive_plan", side_effect=fake_drive):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    saved = load_chain_state(spec_path)
    assert saved.reground_decisions["M-b"]["material_diff_count"] == 0
    assert saved.reground_decisions["M-b"]["diff_row_count"] == 1


def test_run_chain_execute_reground_records_drift_fingerprint(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    _write_plan_only_finalized_state(tmp_path, "plan-mb")
    _write_contract(
        tmp_path,
        "plan-ma",
        {
            "provides": [
                {
                    "name": "Planner",
                    "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run(new)"}],
                }
            ],
            "assumes": [],
        },
    )
    _write_contract(
        tmp_path,
        "plan-mb",
        {
            "provides": [],
            "assumes": [
                {
                    "name": "Planner",
                    "upstream_milestone": "M-a",
                    "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run(old)"}],
                }
            ],
        },
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "M-a", "plan": "plan-ma", "status": "done"},
                {"label": "M-b", "plan": "plan-mb", "status": "finalized"},
            ],
        ),
    )

    with patch("megaplan.chain._drive_plan", return_value=_fake_outcome("plan-mb", "done")):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    decision = load_chain_state(spec_path).reground_decisions["M-b"]
    assert decision["status"] == "replanned"
    assert decision["material_diff_count"] == 1
    assert decision["material_diffs"][0]["status"] == "MISMATCH"
    assert decision["material_fingerprint"] != "[]"


def test_run_chain_plan_mode_writes_chain_review_with_contract_statuses(tmp_path: Path) -> None:
    ideas = [_touch_idea(tmp_path, f"m-{label}.txt") for label in ("a", "b", "z", "c", "d")]
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(ideas[0])},
                {"label": "M-b", "idea": str(ideas[1]), "depends_on": ["M-a"]},
                {"label": "M-z", "idea": str(ideas[2])},
                {"label": "M-c", "idea": str(ideas[3]), "depends_on": ["M-z"]},
                {"label": "M-d", "idea": str(ideas[4]), "depends_on": ["M-a"]},
            ]
        },
    )
    plan_by_label = {
        "M-a": "plan-ma",
        "M-b": "plan-mb",
        "M-z": "plan-mz",
        "M-c": "plan-mc",
        "M-d": "plan-md",
    }
    labels = iter(plan_by_label)

    def fake_init(root, idea_path, **_kwargs):
        del root, idea_path
        label = next(labels)
        plan = plan_by_label[label]
        _write_plan_state(tmp_path, plan, "initialized")
        return plan

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, stop_at_finalized, on_phase_complete, writer
        contracts = {
            "plan-ma": {
                "provides": [
                    {
                        "name": "A",
                        "interfaces": [{"symbol": "A.run", "path": "a.py", "signature": "run(new)"}],
                    }
                ],
                "assumes": [],
            },
            "plan-mb": {
                "provides": [],
                "assumes": [
                    {
                        "name": "A",
                        "upstream_milestone": "M-a",
                        "interfaces": [{"symbol": "A.run", "path": "a.py", "signature": "run(new)"}],
                    }
                ],
            },
            "plan-mz": {"provides": [], "assumes": []},
            "plan-mc": {
                "provides": [],
                "assumes": [
                    {
                        "name": "Z",
                        "upstream_milestone": "M-z",
                        "interfaces": [{"symbol": "Z.run", "path": "z.py", "signature": "run()"}],
                    }
                ],
            },
            "plan-md": {
                "provides": [],
                "assumes": [
                    {
                        "name": "A",
                        "upstream_milestone": "M-a",
                        "interfaces": [{"symbol": "A.run", "path": "a.py", "signature": "run(old)"}],
                    }
                ],
            },
        }
        _write_plan_state(root, plan, STATE_FINALIZED)
        _write_contract(root, plan, contracts[plan])
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             side_effect=lambda root, base, plan, paths, push, dry_run=False: CommitResult(
                 committed=True, pushed=False, commit_sha=f"sha-{plan}", base_branch=base
             ),
         ):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert result["status"] == "done"
    review = chain_module._chain_review_path(spec_path).read_text(encoding="utf-8")
    assert "- Status: complete" in review
    assert "| M-b | M-a | A.run | a.py | a.py | run(new) | run(new) | OK |  |" in review
    assert "| M-c | M-z | Z.run | z.py |  | run() |  | MISSING_UPSTREAM | symbol `Z.run` missing upstream |" in review
    assert "| M-d | M-a | A.run | a.py | a.py | run(old) | run(new) | MISMATCH | signature changed |" in review


def test_run_chain_three_milestone_contract_fixture_covers_artifacts_review_and_reground(
    tmp_path: Path,
) -> None:
    ideas = [_touch_idea(tmp_path, f"m-{label}.txt") for label in ("a", "b", "c")]
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(ideas[0])},
                {"label": "M-b", "idea": str(ideas[1]), "depends_on": ["M-a"]},
                {"label": "M-c", "idea": str(ideas[2])},
            ]
        },
    )
    plan_by_label = {"M-a": "plan-ma", "M-b": "plan-mb", "M-c": "plan-mc"}
    labels = iter(plan_by_label)
    contract_payloads = {
        "plan-ma": _contract_finalize_payload(
            provides=[
                {
                    "name": "Planner surface",
                    "interfaces": [
                        {
                            "symbol": "Planner.run",
                            "path": "planner.py",
                            "signature": "run()",
                        }
                    ],
                }
            ],
            assumes=[],
            meta_commentary="M-a publishes the planner surface.",
        ),
        "plan-mb": _contract_finalize_payload(
            provides=[],
            assumes=[
                {
                    "name": "Planner surface",
                    "upstream_milestone": "M-a",
                    "interfaces": [
                        {
                            "symbol": "Planner.run",
                            "path": "planner.py",
                            "signature": "run()",
                        }
                    ],
                }
            ],
            meta_commentary="M-b consumes M-a's planner surface.",
        ),
        "plan-mc": _contract_finalize_payload(
            provides=[],
            assumes=[
                {
                    "name": "Sibling-only surface",
                    "upstream_milestone": "M-b",
                    "interfaces": [
                        {
                            "symbol": "Builder.run",
                            "path": "builder.py",
                            "signature": "run()",
                        }
                    ],
                }
            ],
            meta_commentary="M-c references a sibling surface without a declared dependency.",
        ),
    }

    def fake_init(root, idea_path, **_kwargs):
        del root, idea_path
        label = next(labels)
        plan = plan_by_label[label]
        _write_plan_state(tmp_path, plan, "initialized")
        return plan

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, stop_at_finalized, on_phase_complete, writer
        _write_finalized_contract_artifacts(root, plan, payload=contract_payloads[plan])
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             side_effect=lambda root, base, plan, paths, push, dry_run=False: CommitResult(
                 committed=True, pushed=False, commit_sha=f"sha-{plan}", base_branch=base
             ),
         ):
        plan_result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan")

    assert plan_result["status"] == "done"
    plan_state_mb = json.loads(
        (tmp_path / ".megaplan" / "plans" / "plan-mb" / "state.json").read_text(encoding="utf-8")
    )
    plan_state_mc = json.loads(
        (tmp_path / ".megaplan" / "plans" / "plan-mc" / "state.json").read_text(encoding="utf-8")
    )
    mb_context = plan_state_mb["meta"]["chain_policy"]["contract_context"]
    mc_context = plan_state_mc["meta"]["chain_policy"]["contract_context"]
    assert mb_context["dependency_labels"] == ["M-a"]
    assert mb_context["upstream_contracts"][0]["milestone_label"] == "M-a"
    assert mc_context["dependency_labels"] == []
    assert mc_context["upstream_contracts"] == []

    for plan_name in ("plan-ma", "plan-mb", "plan-mc"):
        plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
        assert (plan_dir / "contract.json").exists()

    ma_final = (tmp_path / ".megaplan" / "plans" / "plan-ma" / "final.md").read_text(encoding="utf-8")
    mb_final = (tmp_path / ".megaplan" / "plans" / "plan-mb" / "final.md").read_text(encoding="utf-8")
    mc_final = (tmp_path / ".megaplan" / "plans" / "plan-mc" / "final.md").read_text(encoding="utf-8")
    assert "## Provides" in ma_final
    assert "## Assumes" not in ma_final
    assert "## Assumes" in mb_final
    assert "from `M-a`" in mb_final
    assert "## Assumes" in mc_final
    assert "from `M-b`" in mc_final

    review = chain_module._chain_review_path(spec_path).read_text(encoding="utf-8")
    assert "| M-b | M-a | Planner.run | planner.py | planner.py | run() | run() | OK |  |" in review
    assert (
        "| M-c | M-b | Builder.run | builder.py |  | run() |  | MISSING_UPSTREAM | "
        "upstream contract `M-b` missing |"
    ) in review

    saved = load_chain_state(spec_path)
    completed_by_label = {record["label"]: record for record in saved.completed}
    assert completed_by_label["M-a"]["artifact_commit_sha"] == "sha-plan-ma"
    assert completed_by_label["M-b"]["artifact_commit_sha"] == "sha-plan-mb"
    assert completed_by_label["M-c"]["artifact_commit_sha"] == "sha-plan-mc"

    _write_contract(
        tmp_path,
        "plan-ma",
        {
            "provides": [
                {
                    "name": "Planner surface",
                    "interfaces": [
                        {
                            "symbol": "Planner.run",
                            "path": "planner.py",
                            "signature": "run(updated)",
                        }
                    ],
                }
            ],
            "assumes": [],
        },
    )
    saved.current_milestone_index = len(load_spec(spec_path).milestones)
    save_chain_state(spec_path, saved)

    def fake_execute_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        current = load_chain_state(spec_path)
        if plan == "plan-mb":
            assert current.reground_decisions["M-b"]["status"] == "replanned"
            assert current.reground_decisions["M-b"]["material_diffs"][0]["status"] == "MISMATCH"
            return _fake_outcome(plan, "done")
        if plan == "plan-mc":
            assert current.reground_decisions["M-c"]["status"] == "skipped"
            assert current.reground_decisions["M-c"]["reason"] == "no_dependencies"
            return _fake_outcome(plan, "done")
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._drive_plan", side_effect=fake_execute_drive):
        execute_result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert execute_result["status"] == "done"
    execute_state = load_chain_state(spec_path)
    assert execute_state.reground_decisions["M-b"]["status"] == "replanned"
    assert execute_state.reground_decisions["M-b"]["material_diffs"][0]["status"] == "MISMATCH"
    assert execute_state.reground_decisions["M-c"]["status"] == "skipped"
    assert execute_state.reground_decisions["M-c"]["reason"] == "no_dependencies"


def test_run_chain_plan_mode_writes_partial_chain_review_on_one_exit(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {"milestones": [{"label": "M-a", "idea": str(i1)}, {"label": "M-b", "idea": str(i2)}]},
    )

    def fake_init(root, idea_path, **_kwargs):
        del idea_path
        _write_plan_state(root, "plan-ma", "initialized")
        return "plan-ma"

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, stop_at_finalized, on_phase_complete, writer
        _write_plan_state(root, plan, STATE_FINALIZED)
        _write_contract(root, plan, {"provides": [], "assumes": []})
        return _fake_outcome(plan, "finalized")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", side_effect=fake_init), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             return_value=CommitResult(committed=True, pushed=False, commit_sha="sha", base_branch="main"),
         ):
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="plan", one=True)

    assert result["status"] == "paused"
    review = chain_module._chain_review_path(spec_path).read_text(encoding="utf-8")
    assert "- Status: partial" in review
    assert "- Partial reason: completed one milestone: M-a" in review


def test_write_chain_review_uses_latest_completed_record_for_duplicate_labels(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    _write_contract(
        tmp_path,
        "old-a",
        {
            "provides": [
                {"name": "A", "interfaces": [{"symbol": "A.run", "path": "a.py", "signature": "old()"}]}
            ],
            "assumes": [],
        },
    )
    _write_contract(
        tmp_path,
        "new-a",
        {
            "provides": [
                {"name": "A", "interfaces": [{"symbol": "A.run", "path": "a.py", "signature": "new()"}]}
            ],
            "assumes": [],
        },
    )
    _write_contract(
        tmp_path,
        "plan-b",
        {
            "provides": [],
            "assumes": [
                {
                    "name": "A",
                    "upstream_milestone": "M-a",
                    "interfaces": [{"symbol": "A.run", "path": "a.py", "signature": "new()"}],
                }
            ],
        },
    )
    state = ChainState(
        completed=[
            {"label": "M-a", "plan": "old-a", "status": "finalized"},
            {"label": "M-a", "plan": "new-a", "status": "finalized"},
            {"label": "M-b", "plan": "plan-b", "status": "finalized"},
        ]
    )

    chain_module._write_chain_review(tmp_path, spec_path, load_spec(spec_path), state)
    review = chain_module._chain_review_path(spec_path).read_text(encoding="utf-8")
    assert "new()" in review
    assert "old()" not in review


def test_run_chain_execute_first_drift_replans_and_continues_same_plan(tmp_path: Path) -> None:
    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    _write_plan_only_finalized_state(tmp_path, "plan-mb")
    _write_contract(
        tmp_path,
        "plan-ma",
        {
            "provides": [
                {"name": "Planner", "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run(new)"}]}
            ],
            "assumes": [],
        },
    )
    _write_contract(
        tmp_path,
        "plan-mb",
        {
            "provides": [],
            "assumes": [
                {
                    "name": "Planner",
                    "upstream_milestone": "M-a",
                    "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run(old)"}],
                }
            ],
        },
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "M-a", "plan": "plan-ma", "status": "done"},
                {"label": "M-b", "plan": "plan-mb", "status": "finalized"},
            ],
        ),
    )

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, stop_at_finalized, on_phase_complete, writer
        saved = load_chain_state(spec_path)
        assert plan == "plan-mb"
        assert saved.current_milestone_index == 1
        assert saved.current_plan_name == "plan-mb"
        assert saved.reground_decisions["M-b"]["status"] == "replanned"
        plan_state = json.loads((tmp_path / ".megaplan" / "plans" / "plan-mb" / "state.json").read_text(encoding="utf-8"))
        assert plan_state["current_state"] == "planned"
        assert any(item.get("action") == "replan" for item in plan_state["meta"]["overrides"])
        return _fake_outcome("plan-mb", "done")

    with patch("megaplan.chain._drive_plan", side_effect=fake_drive) as drive:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "done"
    assert drive.call_count == 1
    saved = load_chain_state(spec_path)
    assert saved.current_milestone_index == 2
    assert saved.completed[-1]["label"] == "M-b"
    assert saved.completed[-1]["status"] == "done"


def test_run_chain_execute_repeated_identical_drift_stops_before_driver(tmp_path: Path) -> None:
    from megaplan.orchestration.plan_contracts import (
        contract_diff_fingerprint,
        diff_assumes_against_provides,
    )

    i1 = _touch_idea(tmp_path, "m-a.txt")
    i2 = _touch_idea(tmp_path, "m-b.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "milestones": [
                {"label": "M-a", "idea": str(i1)},
                {"label": "M-b", "idea": str(i2), "depends_on": ["M-a"]},
            ]
        },
    )
    upstream = {
        "provides": [
            {"name": "Planner", "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run(new)"}]}
        ],
        "assumes": [],
    }
    downstream = {
        "provides": [],
        "assumes": [
            {
                "name": "Planner",
                "upstream_milestone": "M-a",
                "interfaces": [{"symbol": "Planner.run", "path": "planner.py", "signature": "run(old)"}],
            }
        ],
    }
    _write_plan_only_finalized_state(tmp_path, "plan-mb")
    _write_contract(tmp_path, "plan-ma", upstream)
    _write_contract(tmp_path, "plan-mb", downstream)
    rows = diff_assumes_against_provides(
        downstream,
        [{"milestone_label": "M-a", "provides": upstream["provides"], "assumes": []}],
        downstream_label="M-b",
    )
    fingerprint = contract_diff_fingerprint(rows)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=2,
            completed=[
                {"label": "M-a", "plan": "plan-ma", "status": "done"},
                {"label": "M-b", "plan": "plan-mb", "status": "finalized"},
            ],
            reground_decisions={
                "M-b": {
                    "status": "replanned",
                    "material_fingerprint": fingerprint,
                    "material_diffs": rows,
                }
            },
        ),
    )

    with patch("megaplan.chain._drive_plan") as drive:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, mode="execute")

    assert result["status"] == "stopped"
    assert "repeated contract drift for M-b" in result["reason"]
    drive.assert_not_called()


# ---------------------------------------------------------------------------
# T8: git commit artifact loading and contract fallback
# ---------------------------------------------------------------------------


def test_read_plan_artifact_from_commit_returns_content() -> None:
    """git show success returns file content as string."""
    from megaplan.chain.git_ops import read_plan_artifact_from_commit

    fake_proc = subprocess.CompletedProcess(
        args=["git", "show", "abc123:.megaplan/plans/p/contract.json"],
        returncode=0,
        stdout='{"provides":[],"assumes":[]}\n',
        stderr="",
    )
    with patch.object(chain_module.subprocess, "run", return_value=fake_proc):
        result = read_plan_artifact_from_commit(Path("/fake"), "abc123", ".megaplan/plans/p/contract.json")
    assert result == '{"provides":[],"assumes":[]}\n'


def test_read_plan_artifact_from_commit_returns_none_for_missing_file() -> None:
    """git show for missing file returns None."""
    from megaplan.chain.git_ops import read_plan_artifact_from_commit

    for stderr in (
        "fatal: path '.megaplan/plans/p/contract.json' does not exist in 'abc123'",
        "fatal: Path 'contract.json' exists on disk, but not in 'abc123'",
        "fatal: bad revision 'abc123'",
    ):
        fake_proc = subprocess.CompletedProcess(
            args=["git", "show", "abc123:.megaplan/plans/p/contract.json"],
            returncode=128,
            stdout="",
            stderr=stderr,
        )
        with patch.object(chain_module.subprocess, "run", return_value=fake_proc):
            result = read_plan_artifact_from_commit(Path("/fake"), "abc123", ".megaplan/plans/p/contract.json")
        assert result is None, f"Should return None for stderr: {stderr!r}"


def test_read_plan_artifact_from_commit_raises_on_git_failure() -> None:
    """Real git failures (not missing-file) raise CliError."""
    from megaplan.chain.git_ops import read_plan_artifact_from_commit

    fake_proc = subprocess.CompletedProcess(
        args=["git", "show", "abc123:.megaplan/plans/p/contract.json"],
        returncode=1,
        stdout="",
        stderr="fatal: Not a git repository",
    )
    with patch.object(chain_module.subprocess, "run", return_value=fake_proc):
        with pytest.raises(CliError) as exc_info:
            read_plan_artifact_from_commit(Path("/fake"), "abc123", ".megaplan/plans/p/contract.json")
        assert exc_info.value.code == "git_artifact_read_failed"


def test_load_contract_for_completed_record_prefers_current_file(tmp_path: Path) -> None:
    """When contract.json exists on disk, it is loaded and normalized."""
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-p"
    plan_dir.mkdir(parents=True)
    contract = {"provides": [{"name": "P", "interfaces": [{"symbol": "f", "path": "src/p.py", "signature": "f()"}]}], "assumes": []}
    (plan_dir / "contract.json").write_text(json.dumps(contract), encoding="utf-8")

    record = {"plan": "plan-p"}
    result = chain_module._load_contract_for_completed_record(tmp_path, record)
    assert result is not None
    assert len(result["provides"]) == 1
    assert result["provides"][0]["name"] == "P"


def test_load_contract_for_completed_record_falls_back_to_commit(tmp_path: Path) -> None:
    """When contract.json is missing on disk, falls back to git commit artifact."""
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-p"
    plan_dir.mkdir(parents=True)
    # No contract.json on disk
    contract_content = json.dumps({"provides": [], "assumes": [{"name": "A", "upstream_milestone": "m1", "interfaces": []}]})

    record = {"plan": "plan-p", "artifact_commit_sha": "abc123"}

    fake_proc = subprocess.CompletedProcess(
        args=["git", "show", "abc123:.megaplan/plans/plan-p/contract.json"],
        returncode=0,
        stdout=contract_content,
        stderr="",
    )
    with patch.object(chain_module.subprocess, "run", return_value=fake_proc):
        result = chain_module._load_contract_for_completed_record(tmp_path, record)
    assert result is not None
    assert len(result["assumes"]) == 1
    assert result["assumes"][0]["name"] == "A"


def test_load_contract_for_completed_record_returns_none_when_missing(tmp_path: Path) -> None:
    """Returns None when no contract.json on disk and artifact commit is missing/missing-file."""
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-p"
    plan_dir.mkdir(parents=True)
    # No contract.json, no artifact_commit_sha
    record = {"plan": "plan-p"}
    result = chain_module._load_contract_for_completed_record(tmp_path, record)
    assert result is None

    # With artifact_commit_sha but file missing in commit
    record_with_sha = {"plan": "plan-p", "artifact_commit_sha": "abc123"}
    fake_proc = subprocess.CompletedProcess(
        args=["git", "show", "abc123:.megaplan/plans/plan-p/contract.json"],
        returncode=128,
        stdout="",
        stderr="fatal: path '.megaplan/plans/plan-p/contract.json' does not exist in 'abc123'",
    )
    with patch.object(chain_module.subprocess, "run", return_value=fake_proc):
        result = chain_module._load_contract_for_completed_record(tmp_path, record_with_sha)
    assert result is None

    # Also returns None for record without plan name
    assert chain_module._load_contract_for_completed_record(tmp_path, {}) is None


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
