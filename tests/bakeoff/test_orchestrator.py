import asyncio
from pathlib import Path
from typing import Any

import pytest

import megaplan.bakeoff.orchestrator as orchestrator
from megaplan.bakeoff.state import BakeoffState


class FakeProcess:
    def __init__(self, returncode: int = 0, pid: int = 4242) -> None:
        self.returncode = returncode
        self.pid = pid

    async def wait(self) -> int:
        await asyncio.sleep(0)
        return self.returncode


def test_init_profile_appends_robustness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured_args: list[list[Any]] = []

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        captured_args.append(list(args))
        return FakeProcess(0)

    monkeypatch.setattr(
        "megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        orchestrator,
        "create_worktree",
        lambda _repo, target, _sha: target.mkdir(parents=True, exist_ok=True),
    )

    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build a small thing", encoding="utf-8")

    state: BakeoffState = {
        "schema_version": 1,
        "experiment_id": "exp",
        "base_sha": "abc",
        "idea_hash": "hash",
        "idea_path": str(idea),
        "mode": "code",
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }

    record = asyncio.run(
        orchestrator._init_profile(
            root, state, "standard", "exp", "abc", idea, robustness="light"
        )
    )

    assert len(captured_args) == 1
    cmd = captured_args[0]
    assert "--robustness" in cmd
    rob_idx = cmd.index("--robustness")
    assert cmd[rob_idx + 1] == "light"
    assert record["name"] == "standard"


def test_init_profile_omits_robustness_when_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured_args: list[list[Any]] = []

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        captured_args.append(list(args))
        return FakeProcess(0)

    monkeypatch.setattr(
        "megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        orchestrator,
        "create_worktree",
        lambda _repo, target, _sha: target.mkdir(parents=True, exist_ok=True),
    )

    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build a small thing", encoding="utf-8")

    state: BakeoffState = {
        "schema_version": 1,
        "experiment_id": "exp",
        "base_sha": "abc",
        "idea_hash": "hash",
        "idea_path": str(idea),
        "mode": "code",
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }

    record = asyncio.run(
        orchestrator._init_profile(
            root, state, "standard", "exp", "abc", idea
        )
    )

    assert len(captured_args) == 1
    cmd = captured_args[0]
    assert "--robustness" not in cmd
    assert record["name"] == "standard"
