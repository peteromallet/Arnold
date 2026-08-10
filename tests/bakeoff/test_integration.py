import asyncio
import json
import os
import subprocess
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import arnold_pipelines.megaplan.bakeoff.orchestrator as orchestrator
from arnold_pipelines.megaplan.bakeoff.handlers import handle_compare, handle_merge, handle_pick, handle_status
from arnold_pipelines.megaplan.bakeoff.lifecycle import resume_bakeoff
from arnold_pipelines.megaplan.bakeoff.state import load_bakeoff_state


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeProcess:
    def __init__(self, returncode: int = 0, pid: int = 4242) -> None:
        self.returncode = returncode
        self.pid = pid

    async def wait(self) -> int:
        await asyncio.sleep(0)
        return self.returncode


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    (repo / "idea.md").write_text("build a small thing\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "README.md", "idea.md")
    _git(repo, "commit", "-m", "initial")


def _write_user_profile(config_home: Path) -> None:
    profile_dir = config_home / "megaplan"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profiles.toml").write_text(
        """
[profiles.extra]
plan = "claude"
execute = "codex"
review = "codex"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _prepare_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    _init_repo(root)
    config_home = tmp_path / "config"
    _write_user_profile(config_home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    existing = os.environ.get("PYTHONPATH")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(REPO_ROOT) if not existing else os.pathsep.join([str(REPO_ROOT), existing]),
    )
    return root


def _install_fake_spawn(
    monkeypatch: pytest.MonkeyPatch,
    *,
    calls: list[str],
    crash_profiles: set[str] | None = None,
    nonterminal_profiles: set[str] | None = None,
    write_untracked_for: set[str] | None = None,
) -> None:
    crash_profiles = crash_profiles or set()
    nonterminal_profiles = nonterminal_profiles or set()
    write_untracked_for = write_untracked_for or set()

    async def fake_spawn(worktree: Path, plan_id: str, log_path: Path, outcome_path: Path) -> tuple[FakeProcess, None]:
        profile = worktree.name
        calls.append(profile)
        if profile in crash_profiles:
            raise RuntimeError(f"{profile} exploded")
        plan_dir = worktree / ".megaplan" / "plans" / plan_id
        state_path = plan_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["current_state"] = "planned" if profile in nonterminal_profiles else "done"
        state["history"] = [
            {
                "step": "execute",
                "cost_usd": 0.01,
                "output_file": str(plan_dir / "execution.json"),
            },
            {"step": "review", "cost_usd": 0.02},
        ]
        state.setdefault("meta", {})["total_cost_usd"] = 0.03
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        (plan_dir / "execution.json").write_text("{}", encoding="utf-8")
        (plan_dir / "review.json").write_text(json.dumps({"verdict": "pass"}), encoding="utf-8")
        if profile in write_untracked_for:
            generated = worktree / "src" / f"{profile}_generated.py"
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


def test_bakeoff_happy_path_compare_pick_merge_with_untracked_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    calls: list[str] = []
    _install_fake_spawn(monkeypatch, calls=calls, write_untracked_for={"apex"})

    state = asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex", "all-open", "extra"],
            "code",
            "exp-happy",
        )
    )

    assert sorted(calls) == ["all-open", "apex", "extra"]
    assert state["phase"] == "running"
    assert handle_status(root, Namespace(exp="exp-happy")) == 0
    status_output = capsys.readouterr().out
    assert "apex" in status_output
    assert "all-open" in status_output
    assert "extra" in status_output

    assert handle_compare(root, Namespace(exp="exp-happy", judge=None, force=False)) == 0
    comparison_path = root / ".megaplan" / "bakeoffs" / "exp-happy" / "comparison.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["judge_verdict"] is None
    assert {profile["name"] for profile in comparison["profiles"]} == {"apex", "all-open", "extra"}

    assert handle_pick(root, Namespace(exp="exp-happy", profile="apex", rationale="best")) == 0
    assert handle_merge(root, Namespace(exp="exp-happy")) == 0

    merged_state = load_bakeoff_state(root, "exp-happy")
    assert merged_state["phase"] == "merged"
    assert (root / "src" / "apex_generated.py").read_text(encoding="utf-8") == "VALUE = 7\n"
    winner_patch = (root / ".megaplan" / "bakeoffs" / "exp-happy" / "winner.patch").read_text(
        encoding="utf-8"
    )
    assert "--- /dev/null" in winner_patch
    for profile in ["apex", "all-open", "extra"]:
        assert (root / ".megaplan" / "bakeoffs" / "exp-happy" / profile / "plan").is_dir()
        record = next(item for item in merged_state["profiles"] if item["name"] == profile)
        assert not Path(record["worktree"]).exists()
    live_plans = sorted(path.name for path in (root / ".megaplan" / "plans").iterdir() if path.is_dir())
    assert live_plans == ["exp-happy-apex"]


def test_bakeoff_crash_isolation_still_compares_siblings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    calls: list[str] = []
    _install_fake_spawn(monkeypatch, calls=calls, crash_profiles={"all-open"})

    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex", "all-open", "extra"],
            "code",
            "exp-crash",
        )
    )

    state = load_bakeoff_state(root, "exp-crash")
    crashed = next(record for record in state["profiles"] if record["name"] == "all-open")
    assert crashed["outcome"]["status"] == "failed"
    assert (Path(crashed["worktree"]) / "BAKEOFF_CRASHED").exists()
    assert {record["outcome"]["status"] for record in state["profiles"]} == {"done", "failed"}

    assert handle_compare(root, Namespace(exp="exp-crash", judge=None, force=False)) == 0
    comparison = json.loads((root / ".megaplan" / "bakeoffs" / "exp-crash" / "comparison.json").read_text())
    crashed_profile = next(profile for profile in comparison["profiles"] if profile["name"] == "all-open")
    assert crashed_profile["outcome_status"] == "failed"
    assert crashed_profile["metrics"]["duration_s"] is None


def test_bakeoff_copies_project_profiles_toml_into_worktree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    (root / ".megaplan").mkdir(exist_ok=True)
    project_profiles = """[profiles.project-only]
plan = "claude"
execute = "codex"
review = "codex"
"""
    (root / ".megaplan" / "profiles.toml").write_text(project_profiles, encoding="utf-8")
    _install_fake_spawn(monkeypatch, calls=[])
    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["project-only"],
            "code",
            "exp-proj-profile",
        )
    )
    state = load_bakeoff_state(root, "exp-proj-profile")
    worktree = Path(state["profiles"][0]["worktree"])
    copied = worktree / ".megaplan" / "profiles.toml"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == project_profiles


def test_bakeoff_init_tolerates_missing_project_profiles_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    assert not (root / ".megaplan" / "profiles.toml").exists()
    _install_fake_spawn(monkeypatch, calls=[])
    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex"],
            "code",
            "exp-no-proj-profile",
        )
    )
    state = load_bakeoff_state(root, "exp-no-proj-profile")
    worktree = Path(state["profiles"][0]["worktree"])
    assert not (worktree / ".megaplan" / "profiles.toml").exists()


def test_bakeoff_detach_returns_without_awaiting_profile_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    never_completes = asyncio.Event()

    async def blocking_spawn(worktree: Path, plan_id: str, log_path: Path, outcome_path: Path) -> tuple[FakeProcess, None]:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("spawned\n", encoding="utf-8")

        class BlockingProcess:
            pid = 9999
            returncode = None

            async def wait(self) -> int:
                await never_completes.wait()
                return 0

        return BlockingProcess(), None

    monkeypatch.setattr(orchestrator, "_spawn_auto", blocking_spawn)

    state = asyncio.run(
        asyncio.wait_for(
            orchestrator.run_bakeoff(
                root,
                root / "idea.md",
                ["apex"],
                "code",
                "exp-detach",
                detach=True,
            ),
            timeout=10.0,
        )
    )
    # detach=True must return before the spawned process completes; outcome stays
    # unrecorded and terminated_at is still None — the user polls via bakeoff status.
    assert state["phase"] == "running"
    record = state["profiles"][0]
    assert record["outcome"] is None
    assert record["terminated_at"] is None


def test_bakeoff_resume_relaunches_only_nonterminal_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    initial_calls: list[str] = []
    _install_fake_spawn(
        monkeypatch,
        calls=initial_calls,
        nonterminal_profiles={"all-open"},
    )
    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex", "all-open"],
            "code",
            "exp-resume",
        )
    )
    assert sorted(initial_calls) == ["all-open", "apex"]

    resume_calls: list[str] = []
    _install_fake_spawn(monkeypatch, calls=resume_calls)
    assert resume_bakeoff(root, "exp-resume") == 0

    assert resume_calls == ["all-open"]
    resumed_state = load_bakeoff_state(root, "exp-resume")
    all_open = next(record for record in resumed_state["profiles"] if record["name"] == "all-open")
    assert all_open["outcome"]["status"] == "done"
    assert json.loads(
        (Path(all_open["worktree"]) / ".megaplan" / "plans" / "exp-resume" / "state.json").read_text(
            encoding="utf-8"
        )
    )["current_state"] == "done"


def test_bakeoff_run_robustness_propagation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _prepare_repo(tmp_path, monkeypatch)
    init_calls: list[list[str]] = []

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        cmd = list(args)
        if "init" in cmd:
            init_calls.append(cmd)
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
        return FakeProcess(0)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    _install_fake_spawn(monkeypatch, calls=[])

    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex"],
            "code",
            "exp-robust",
            robustness="light",
        )
    )

    assert len(init_calls) == 1
    cmd = init_calls[0]
    assert "--robustness" in cmd
    rob_idx = cmd.index("--robustness")
    assert cmd[rob_idx + 1] == "light"

    init_calls.clear()

    asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex"],
            "code",
            "exp-no-robust",
        )
    )

    assert len(init_calls) == 1
    cmd = init_calls[0]
    assert "--robustness" not in cmd
