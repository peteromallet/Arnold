import asyncio
from pathlib import Path
from typing import Any

import pytest

import arnold_pipelines.megaplan.bakeoff.orchestrator as orchestrator
from arnold_pipelines.megaplan.bakeoff.state import BakeoffState
from arnold_pipelines.megaplan.notification_safety import FixtureSafetyDecision


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
        "arnold_pipelines.megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
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
            root, state, "apex", "exp", "abc", idea, robustness="light"
        )
    )

    assert len(captured_args) == 1
    cmd = captured_args[0]
    assert "--robustness" in cmd
    rob_idx = cmd.index("--robustness")
    assert cmd[rob_idx + 1] == "light"
    assert record["name"] == "apex"


def test_init_profile_threads_doc_mode_and_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured_args: list[list[Any]] = []

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        captured_args.append(list(args))
        return FakeProcess(0)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
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
    idea.write_text("design something", encoding="utf-8")

    state: BakeoffState = {
        "schema_version": 1,
        "experiment_id": "exp",
        "base_sha": "abc",
        "idea_hash": "hash",
        "idea_path": str(idea),
        "mode": "doc",
        "output_path": "docs/foo.md",
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }

    record = asyncio.run(
        orchestrator._init_profile(
            root, state, "apex", "exp", "abc", idea,
            mode="doc", output="docs/foo.md",
        )
    )

    assert len(captured_args) == 1
    cmd = captured_args[0]
    assert "--mode" in cmd
    mode_idx = cmd.index("--mode")
    assert cmd[mode_idx + 1] == "doc"
    assert "--output" in cmd
    out_idx = cmd.index("--output")
    assert cmd[out_idx + 1] == "docs/foo.md"
    assert record["name"] == "apex"


def test_init_profile_doc_mode_requires_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        orchestrator,
        "create_worktree",
        lambda _repo, target, _sha: target.mkdir(parents=True, exist_ok=True),
    )
    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("x", encoding="utf-8")
    state: BakeoffState = {
        "schema_version": 1,
        "experiment_id": "exp",
        "base_sha": "abc",
        "idea_hash": "hash",
        "idea_path": str(idea),
        "mode": "doc",
        "output_path": None,
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }
    from arnold_pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as excinfo:
        asyncio.run(
            orchestrator._init_profile(
                root, state, "apex", "exp", "abc", idea,
                mode="doc", output=None,
            )
        )
    assert excinfo.value.code == "invalid_args"


def test_run_bakeoff_persists_doc_mode_and_output_in_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Doc-mode bake-off run should persist mode + output_path so downstream
    handlers (status/compare/merge/resume) can read them back."""
    import json
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True, capture_output=True)
    (root / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    (root / "idea.md").write_text("design x\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

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

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    async def fake_spawn(worktree: Path, plan_id: str, log_path: Path, outcome_path: Path):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n", encoding="utf-8")
        outcome_path.parent.mkdir(parents=True, exist_ok=True)
        outcome_path.write_text(
            json.dumps({"status": "done", "plan": plan_id, "final_state": "done", "iterations": 1, "reason": "", "events": []}),
            encoding="utf-8",
        )
        return FakeProcess(0), None

    monkeypatch.setattr(orchestrator, "_spawn_auto", fake_spawn)

    state = asyncio.run(
        orchestrator.run_bakeoff(
            root,
            root / "idea.md",
            ["apex"],
            "doc",
            "exp-doc",
            output="docs/foo.md",
        )
    )

    assert state["mode"] == "doc"
    assert state["output_path"] == "docs/foo.md"
    # init was invoked with --mode doc and --output docs/foo.md
    assert len(init_calls) == 1
    cmd = init_calls[0]
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "doc"
    assert "--output" in cmd
    assert cmd[cmd.index("--output") + 1] == "docs/foo.md"

    # State on disk also reflects the new fields.
    persisted = json.loads(
        (root / ".megaplan" / "bakeoffs" / "exp-doc" / "bakeoff.json").read_text(encoding="utf-8")
    )
    assert persisted["mode"] == "doc"
    assert persisted["output_path"] == "docs/foo.md"
    assert persisted["wbc_transition_evidence"]["run:exp-doc"]["fixture_safety"]["authorized"] is True
    assert persisted["profiles"][0]["wbc_transition_evidence"]["launch_profile_auto"]["destructive"] is True


def test_run_bakeoff_refuses_non_fixture_authorization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from arnold_pipelines.megaplan.types import CliError

    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("design x\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "ensure_main_worktree_clean", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrator, "capture_base_sha", lambda *_args, **_kwargs: "abc123")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.wbc.classify_fixture_safety",
        lambda **_kwargs: FixtureSafetyDecision(False, "not_fixture"),
    )

    with pytest.raises(CliError) as excinfo:
        asyncio.run(
            orchestrator.run_bakeoff(
                root,
                idea,
                ["apex"],
                "code",
                "exp-blocked",
            )
        )

    assert excinfo.value.code == "bakeoff_wbc_action_off"


def test_run_bakeoff_metaplan_mode_rejected(tmp_path: Path) -> None:
    """`--mode metaplan` is no longer accepted after the 0.23 bake-off cleanup
    (T12: the metaplan→doc alias coercion was removed). Programmatic callers
    that still pass `mode='metaplan'` must now raise CliError('invalid_args')
    so they migrate to `mode='doc'`."""
    from arnold_pipelines.megaplan.types import CliError

    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("design x\n", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        asyncio.run(
            orchestrator.run_bakeoff(
                root,
                idea,
                ["apex"],
                "metaplan",
                "exp-meta",
                output="docs/foo.md",
            )
        )
    assert excinfo.value.code == "invalid_args"


def test_run_bakeoff_joke_mode_rejected(tmp_path: Path) -> None:
    """`--mode joke` was never a valid bake-off mode and after the 0.23 cleanup
    the validation set is tightened to `{code, doc}`. Programmatic callers must
    raise CliError('invalid_args')."""
    from arnold_pipelines.megaplan.types import CliError

    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("design x\n", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        asyncio.run(
            orchestrator.run_bakeoff(
                root,
                idea,
                ["apex"],
                "joke",
                "exp-joke",
            )
        )
    assert excinfo.value.code == "invalid_args"


def test_run_bakeoff_code_and_doc_modes_validate(tmp_path: Path) -> None:
    """The tightened validation set `{code, doc}` still accepts both literals;
    the validation gate must not regress legitimate values along with the
    metaplan/joke removal."""
    from arnold_pipelines.megaplan.bakeoff.cli import BAKEOFF_SUPPORTED_MODES

    assert set(BAKEOFF_SUPPORTED_MODES) == {"code", "doc"}


def test_init_profile_omits_robustness_when_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured_args: list[list[Any]] = []

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        captured_args.append(list(args))
        return FakeProcess(0)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.bakeoff.orchestrator.asyncio.create_subprocess_exec",
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
            root, state, "apex", "exp", "abc", idea
        )
    )

    assert len(captured_args) == 1
    cmd = captured_args[0]
    assert "--robustness" not in cmd
    assert record["name"] == "apex"
