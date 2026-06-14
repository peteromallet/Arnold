from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan.auto import DriverOutcome
from arnold.pipelines.megaplan.bakeoff.state import BakeoffState, load_bakeoff_state
from arnold.pipelines.megaplan.supervisor import run_supervisor_bakeoff
import arnold.pipelines.megaplan.supervisor.bakeoff_runner as runner
from arnold.pipelines.megaplan.supervisor.driver import RunRequest
from arnold.pipelines.megaplan.supervisor.state import load_supervisor_state
from arnold.pipelines.megaplan.types import CliError


async def _fake_initializer(
    root: Path,
    _state: BakeoffState,
    profile: str,
    experiment_id: str,
    _base_sha: str,
    _idea: Path,
    _robustness: str | None,
    _mode: str,
    _output: str | None,
) -> dict[str, Any]:
    worktree = root / "worktrees" / profile
    plan_dir = worktree / ".megaplan" / "plans" / experiment_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "initialized", "history": [], "meta": {}}),
        encoding="utf-8",
    )
    archive = root / ".megaplan" / "bakeoffs" / experiment_id / profile
    archive.mkdir(parents=True, exist_ok=True)
    return {
        "name": profile,
        "worktree": str(worktree),
        "plan_id": experiment_id,
        "pid": None,
        "launched_at": None,
        "terminated_at": None,
        "outcome": None,
        "log_path": str(archive / "auto.log"),
        "outcome_path": str(archive / "outcome.json"),
    }


class ParallelRecordingDriver:
    def __init__(self, profiles: int) -> None:
        self.requests: list[RunRequest] = []
        self._barrier = threading.Barrier(profiles)
        self._lock = threading.Lock()
        self._active = 0
        self.max_active = 0

    def drive(self, request: RunRequest) -> DriverOutcome:
        with self._lock:
            self.requests.append(request)
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        self._barrier.wait(timeout=2)
        time.sleep(0.01)
        with self._lock:
            self._active -= 1
        return DriverOutcome(
            status="done",
            plan=request.plan,
            final_state="done",
            iterations=1,
            reason="",
            events=[],
        )


class OutcomeMappingDriver(ParallelRecordingDriver):
    def __init__(self, outcomes_by_profile: dict[str, str]) -> None:
        super().__init__(profiles=len(outcomes_by_profile))
        self._outcomes_by_profile = outcomes_by_profile

    def drive(self, request: RunRequest) -> DriverOutcome:
        with self._lock:
            self.requests.append(request)
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        self._barrier.wait(timeout=2)
        profile = Path(request.root).name
        status = self._outcomes_by_profile[profile]
        with self._lock:
            self._active -= 1
        final_state = "done" if status == "done" else "failed"
        return DriverOutcome(
            status=status,
            plan=request.plan,
            final_state=final_state,
            iterations=1,
            reason="",
            events=[],
        )


@pytest.fixture
def bakeoff_runner_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "ensure_main_worktree_clean", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "capture_base_sha", lambda _root: "base-sha")

    def fake_metrics(_state: BakeoffState, record: dict[str, Any]) -> dict[str, Any]:
        outcome = record.get("outcome") if isinstance(record.get("outcome"), dict) else {}
        return {
            "outcome_status": outcome.get("status"),
            "duration_s": 1.0,
            "cost_usd": 0.1,
            "rework_cycles": 0,
            "escalations": 0,
            "review_verdict": "pass",
            "diff_lines": 1,
            "tests_added": 0,
            "scope_drift_severity_by_phase": {},
            "receipts_ref": [],
        }

    monkeypatch.setattr(runner, "collect_profile_metrics", fake_metrics)


def test_supervisor_bakeoff_creates_parallel_profile_nodes_and_reduces_with_existing_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bakeoff_runner_fakes: None,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build it\n", encoding="utf-8")
    driver = ParallelRecordingDriver(profiles=2)
    merge_calls: list[tuple[Path, str]] = []

    async def fake_judge(
        _state: BakeoffState,
        _metrics_by_profile: dict[str, dict[str, Any]],
        judge_model: str,
    ) -> dict[str, Any]:
        return {
            "judge_model": judge_model,
            "rank": ["beta", "alpha"],
            "rationale_per_profile": {"beta": "best", "alpha": "ok"},
            "scope_drift_flags": {"beta": [], "alpha": []},
            "concerns": [],
        }

    monkeypatch.setattr(runner, "run_judge", fake_judge)
    monkeypatch.setattr(runner, "resolve_requested_judge", lambda *_args: "judge-model")

    def fake_merge(root_arg: Path, exp_id: str) -> int:
        merge_calls.append((root_arg, exp_id))
        state = load_bakeoff_state(root_arg, exp_id)
        assert state["phase"] == "picked"
        assert state["chosen_profile"] == "beta"
        return 0

    result = run_supervisor_bakeoff(
        root,
        idea,
        ["alpha", "beta"],
        "code",
        exp_id="exp-supervisor",
        driver=driver,
        initializer=_fake_initializer,
        merger=fake_merge,
        judge="auto",
    )

    assert result["status"] == "merged"
    assert result["selected_profile"] == "beta"
    assert merge_calls == [(root.resolve(), "exp-supervisor")]
    assert driver.max_active == 2
    assert [request.plan for request in driver.requests] == ["exp-supervisor", "exp-supervisor"]

    supervisor_state = load_supervisor_state(root, "exp-supervisor")
    assert supervisor_state is not None
    assert supervisor_state.variant.value == "bakeoff"
    assert [node.node_id for node in supervisor_state.run_nodes] == [
        "profile:alpha",
        "profile:beta",
    ]
    assert [assertion.to_dict() for assertion in supervisor_state.dependency_assertions] == [
        {"node_id": "profile:alpha", "depends_on": []},
        {"node_id": "profile:beta", "depends_on": []},
    ]
    assert len(supervisor_state.bakeoff_parallel_groups) == 1
    group = supervisor_state.bakeoff_parallel_groups[0]
    assert group.group_id == "exp-supervisor:profiles"
    assert group.member_node_ids == ("profile:alpha", "profile:beta")
    assert [record.original_status for record in supervisor_state.run_records] == ["done", "done"]
    assert supervisor_state.completed_node_ids == ["profile:alpha", "profile:beta"]

    comparison = json.loads(
        (root / ".megaplan" / "bakeoffs" / "exp-supervisor" / "comparison.json").read_text(
            encoding="utf-8"
        )
    )
    assert comparison["judge_verdict"]["rank"] == ["beta", "alpha"]
    assert comparison["human_decision"]["chosen_profile"] == "beta"


def test_supervisor_bakeoff_preserves_profile_order_when_no_judge_is_requested(
    tmp_path: Path,
    bakeoff_runner_fakes: None,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build it\n", encoding="utf-8")
    driver = ParallelRecordingDriver(profiles=2)
    merge_calls: list[str] = []

    result = run_supervisor_bakeoff(
        root,
        idea,
        ["alpha", "beta"],
        "code",
        exp_id="exp-no-judge",
        driver=driver,
        initializer=_fake_initializer,
        merger=lambda _root, exp_id: merge_calls.append(exp_id) or 0,
    )

    assert result["selected_profile"] == "alpha"
    assert merge_calls == ["exp-no-judge"]
    bakeoff_state = load_bakeoff_state(root, "exp-no-judge")
    assert [record["name"] for record in bakeoff_state["profiles"]] == ["alpha", "beta"]
    assert bakeoff_state["chosen_profile"] == "alpha"


def test_supervisor_bakeoff_reuses_compare_judge_and_merge_helpers_for_ranked_n_profile_reduction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bakeoff_runner_fakes: None,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build it\n", encoding="utf-8")
    profiles = ["alpha", "beta", "gamma"]
    driver = OutcomeMappingDriver({"alpha": "done", "beta": "failed", "gamma": "done"})

    helper_calls: dict[str, Any] = {
        "resolve": None,
        "judge": None,
        "comparison": None,
        "write": None,
        "merge": None,
    }
    real_build_comparison = runner.build_comparison
    real_write_comparison = runner.write_comparison

    def fake_resolve(root_arg: Path, state: BakeoffState, requested: str | None) -> str:
        helper_calls["resolve"] = {
            "root": root_arg,
            "requested": requested,
            "profiles": [record["name"] for record in state["profiles"]],
        }
        return "judge-model"

    async def fake_judge(
        state: BakeoffState,
        metrics_by_profile: dict[str, dict[str, Any]],
        judge_model: str,
    ) -> dict[str, Any]:
        helper_calls["judge"] = {
            "judge_model": judge_model,
            "profile_order": list(metrics_by_profile),
            "outcome_statuses": {
                profile: metrics["outcome_status"] for profile, metrics in metrics_by_profile.items()
            },
            "state_profiles": [record["name"] for record in state["profiles"]],
        }
        return {
            "judge_model": judge_model,
            "rank": ["beta", "gamma", "alpha"],
            "rationale_per_profile": {
                "beta": "ranked first but failed",
                "gamma": "best successful profile",
                "alpha": "fallback",
            },
            "scope_drift_flags": {profile: [] for profile in metrics_by_profile},
            "concerns": ["beta failed execution"],
        }

    def spy_build_comparison(
        state: BakeoffState,
        profile_metrics: dict[str, dict[str, Any]],
        judge_verdict: dict[str, Any] | None,
    ) -> dict[str, Any]:
        helper_calls["comparison"] = {
            "profile_order": [record["name"] for record in state["profiles"]],
            "metric_keys": list(profile_metrics),
            "judge_rank": None if judge_verdict is None else judge_verdict.get("rank"),
        }
        return real_build_comparison(state, profile_metrics, judge_verdict)

    def spy_write_comparison(root_arg: Path, comparison: dict[str, Any]) -> tuple[Path, Path]:
        helper_calls["write"] = {
            "root": root_arg,
            "profile_names": [profile["name"] for profile in comparison["profiles"]],
            "judge_rank": comparison["judge_verdict"]["rank"],
        }
        return real_write_comparison(root_arg, comparison)

    def fake_merge(root_arg: Path, exp_id: str) -> int:
        state = load_bakeoff_state(root_arg, exp_id)
        helper_calls["merge"] = {
            "root": root_arg,
            "exp_id": exp_id,
            "phase": state["phase"],
            "chosen_profile": state["chosen_profile"],
            "profiles": [record["name"] for record in state["profiles"]],
        }
        return 0

    monkeypatch.setattr(runner, "resolve_requested_judge", fake_resolve)
    monkeypatch.setattr(runner, "run_judge", fake_judge)
    monkeypatch.setattr(runner, "build_comparison", spy_build_comparison)
    monkeypatch.setattr(runner, "write_comparison", spy_write_comparison)
    monkeypatch.setattr(runner, "merge_bakeoff", fake_merge)

    result = run_supervisor_bakeoff(
        root,
        idea,
        profiles,
        "code",
        exp_id="exp-ranked",
        driver=driver,
        initializer=_fake_initializer,
        judge="auto",
    )

    assert result["status"] == "merged"
    assert result["selected_profile"] == "gamma"
    assert helper_calls["resolve"] == {
        "root": root.resolve(),
        "requested": "auto",
        "profiles": profiles,
    }
    assert helper_calls["judge"] == {
        "judge_model": "judge-model",
        "profile_order": profiles,
        "outcome_statuses": {"alpha": "done", "beta": "failed", "gamma": "done"},
        "state_profiles": profiles,
    }
    assert helper_calls["comparison"] == {
        "profile_order": profiles,
        "metric_keys": profiles,
        "judge_rank": ["beta", "gamma", "alpha"],
    }
    assert helper_calls["write"] == {
        "root": root.resolve(),
        "profile_names": profiles,
        "judge_rank": ["beta", "gamma", "alpha"],
    }
    assert helper_calls["merge"] == {
        "root": root.resolve(),
        "exp_id": "exp-ranked",
        "phase": "picked",
        "chosen_profile": "gamma",
        "profiles": profiles,
    }

    supervisor_state = load_supervisor_state(root, "exp-ranked")
    assert supervisor_state is not None
    assert [record.original_status for record in supervisor_state.run_records] == [
        "done",
        "failed",
        "done",
    ]
    assert [record.metadata["profile"] for record in supervisor_state.run_records] == profiles


def test_supervisor_bakeoff_no_judge_selects_first_successful_profile_from_n_profile_matrix(
    tmp_path: Path,
    bakeoff_runner_fakes: None,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build it\n", encoding="utf-8")
    driver = OutcomeMappingDriver({"alpha": "failed", "beta": "done", "gamma": "done"})
    merge_calls: list[str] = []

    result = run_supervisor_bakeoff(
        root,
        idea,
        ["alpha", "beta", "gamma"],
        "code",
        exp_id="exp-no-judge-n",
        driver=driver,
        initializer=_fake_initializer,
        merger=lambda _root, exp_id: merge_calls.append(exp_id) or 0,
    )

    assert result["selected_profile"] == "beta"
    assert merge_calls == ["exp-no-judge-n"]
    bakeoff_state = load_bakeoff_state(root, "exp-no-judge-n")
    assert [record["name"] for record in bakeoff_state["profiles"]] == ["alpha", "beta", "gamma"]
    assert [record["outcome"]["status"] for record in bakeoff_state["profiles"]] == [
        "failed",
        "done",
        "done",
    ]
    assert bakeoff_state["chosen_profile"] == "beta"


def test_supervisor_bakeoff_reuses_existing_mode_validation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    idea = root / "idea.md"
    idea.write_text("build it\n", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        run_supervisor_bakeoff(
            root,
            idea,
            ["alpha"],
            "doc",
            exp_id="exp-invalid",
            driver=ParallelRecordingDriver(profiles=1),
            initializer=_fake_initializer,
            merge=False,
        )

    assert excinfo.value.code == "invalid_args"
