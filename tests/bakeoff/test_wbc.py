from __future__ import annotations

import asyncio
import json
import subprocess
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import arnold_pipelines.megaplan.bakeoff.orchestrator as orchestrator
from arnold_pipelines.megaplan.bakeoff.handlers import handle_abandon, handle_compare, handle_pick
from arnold_pipelines.megaplan.bakeoff.lifecycle import resume_bakeoff
from arnold_pipelines.megaplan.bakeoff.merge import merge_bakeoff
from arnold_pipelines.megaplan.bakeoff.state import load_bakeoff_state


class FakeProcess:
    def __init__(self, returncode: int = 0, pid: int = 4242) -> None:
        self.returncode = returncode
        self.pid = pid

    async def wait(self) -> int:
        await asyncio.sleep(0)
        return self.returncode


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_repo(root: Path) -> None:
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    (root / "idea.md").write_text("build a small thing\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "README.md", "idea.md")
    _git(root, "commit", "-m", "initial")


def _install_fake_init(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        cmd = list(args)
        worktree = kwargs.get("cwd")
        if worktree and "--name" in cmd:
            plan_id = cmd[cmd.index("--name") + 1]
            plan_dir = Path(worktree) / ".megaplan" / "plans" / plan_id
            plan_dir.mkdir(parents=True, exist_ok=True)
            plan_dir.joinpath("state.json").write_text(
                json.dumps({"current_state": "initialized", "history": [], "meta": {}}),
                encoding="utf-8",
            )
        return FakeProcess(0)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )


def _install_fake_spawn(
    monkeypatch: pytest.MonkeyPatch,
    *,
    nonterminal_profiles: set[str] | None = None,
) -> None:
    nonterminal_profiles = nonterminal_profiles or set()

    async def fake_spawn(worktree: Path, plan_id: str, log_path: Path, outcome_path: Path) -> tuple[FakeProcess, None]:
        profile = worktree.name
        plan_dir = worktree / ".megaplan" / "plans" / plan_id
        state_path = plan_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["current_state"] = "planned" if profile in nonterminal_profiles else "done"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        if profile == "apex":
            generated = worktree / "src" / "apex_generated.py"
            generated.parent.mkdir(exist_ok=True)
            generated.write_text("VALUE = 7\n", encoding="utf-8")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"{profile} auto log\n", encoding="utf-8")
        outcome_path.parent.mkdir(parents=True, exist_ok=True)
        outcome_path.write_text(
            json.dumps(
                {
                    "status": "done",
                    "plan": plan_id,
                    "final_state": state["current_state"],
                    "iterations": 1,
                    "reason": "",
                    "events": [],
                }
            ),
            encoding="utf-8",
        )
        return FakeProcess(), None

    monkeypatch.setattr(orchestrator, "_spawn_auto", fake_spawn)


def test_compare_pick_merge_record_bakeoff_wbc_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    _install_fake_init(monkeypatch)
    _install_fake_spawn(monkeypatch)

    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex", "extra"],
            "code",
            "exp-wbc",
        )
    )

    assert handle_compare(root, Namespace(exp="exp-wbc", judge=None, force=False)) == 0
    assert handle_pick(root, Namespace(exp="exp-wbc", profile="apex", rationale="best")) == 0
    assert merge_bakeoff(root, "exp-wbc") == 0

    state = load_bakeoff_state(root, "exp-wbc")
    assert state["wbc_transition_evidence"]["compare:exp-wbc"]["surface_name"].endswith("compare")
    assert state["wbc_transition_evidence"]["pick:exp-wbc"]["extra"]["selected_profile"] == "apex"
    assert state["wbc_transition_evidence"]["merge:exp-wbc"]["fixture_safety"]["authorized"] is True
    assert state["profiles"][0]["wbc_transition_evidence"]["launch_profile_auto"]["destructive"] is True


def test_resume_and_abandon_record_bakeoff_wbc_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "repo"
    _init_repo(root)
    _install_fake_init(monkeypatch)
    _install_fake_spawn(monkeypatch, nonterminal_profiles={"extra"})

    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex", "extra"],
            "code",
            "exp-wbc-resume",
        )
    )

    _install_fake_spawn(monkeypatch)
    assert resume_bakeoff(root, "exp-wbc-resume") == 0
    resumed = load_bakeoff_state(root, "exp-wbc-resume")
    assert resumed["wbc_transition_evidence"]["resume:exp-wbc-resume"]["fixture_safety"] == {
        "authorized": True,
        "reason": "pytest_environment",
    }

    assert handle_abandon(root, Namespace(exp="exp-wbc-resume")) == 0
    abandoned = load_bakeoff_state(root, "exp-wbc-resume")
    assert abandoned["phase"] == "abandoned"
    assert abandoned["wbc_transition_evidence"]["abandon:exp-wbc-resume"]["fixture_safety"] == {
        "authorized": True,
        "reason": "pytest_environment",
    }
