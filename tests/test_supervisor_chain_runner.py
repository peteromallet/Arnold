from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from megaplan.auto import DriverOutcome
from megaplan.chain.spec import load_chain_state
from megaplan.control_interface import (
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    ControlTarget,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from megaplan.supervisor.chain_runner import SUPERVISOR_DRIVER_ESCALATE_ACTION, run_chain
from megaplan.supervisor.driver import PackRunner, RunDriver, RunRequest
from megaplan.supervisor.ladder import LadderAction, SupervisorLadderPolicy
from megaplan.supervisor.model import RunNode
from megaplan.supervisor.state import load_supervisor_state, save_supervisor_state
from megaplan.types import CliError


class FakePackRunner:
    def __init__(self) -> None:
        self.nodes: list[str] = []

    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        self.nodes.append(node.node_id)
        plan_name = f"plan-{node.node_id}-{self.nodes.count(node.node_id)}"
        plan_dir = root / ".megaplan" / "plans" / plan_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan_name,
                    "current_state": "blocked",
                    "config": {"robustness": "standard"},
                }
            ),
            encoding="utf-8",
        )
        return plan_name


class RecoverableBlockedPackRunner(FakePackRunner):
    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        plan_name = super().prepare_plan(root=root, node=node)
        plan_dir = root / ".megaplan" / "plans" / plan_name
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan_name,
                    "current_state": "blocked",
                    "config": {"robustness": "standard"},
                    "history": [{"step": "execute", "result": "blocked"}],
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "execution_batch_1.json").write_text(
            json.dumps(
                {
                    "task_updates": [
                        {"task_id": f"{node.node_id}-1", "status": "done"},
                        {"task_id": f"{node.node_id}-2", "status": "done"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        return plan_name


class GuardedBlockedPackRunner(FakePackRunner):
    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        plan_name = super().prepare_plan(root=root, node=node)
        plan_dir = root / ".megaplan" / "plans" / plan_name
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan_name,
                    "current_state": "blocked",
                    "config": {"robustness": "standard"},
                    "history": [{"step": "execute", "result": "blocked"}],
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "execution_batch_1.json").write_text(
            json.dumps(
                {
                    "task_updates": [
                        {"task_id": f"{node.node_id}-1", "status": "done"},
                        {"task_id": f"{node.node_id}-2", "status": "blocked"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        return plan_name


class AwaitingPRMergePackRunner(FakePackRunner):
    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        plan_name = super().prepare_plan(root=root, node=node)
        plan_dir = root / ".megaplan" / "plans" / plan_name
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan_name,
                    "current_state": "awaiting_pr_merge",
                    "resume_cursor": {
                        "kind": "awaiting_pr_merge",
                        "pr_number": 42,
                    },
                    "pr_number": 42,
                    "config": {"robustness": "standard"},
                }
            ),
            encoding="utf-8",
        )
        return plan_name


class FakeDriver:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = statuses
        self.requests: list[RunRequest] = []

    def drive(self, request: RunRequest) -> DriverOutcome:
        self.requests.append(request)
        status = self.statuses.pop(0)
        return DriverOutcome(
            status=status,
            plan=request.plan,
            final_state="done" if status == "done" else status,
            iterations=len(self.requests),
            reason=f"status:{status}",
            last_phase="execute",
            blocking_reasons=["quality"] if status == "blocked" else [],
        )


class FakeBinding:
    def __init__(self) -> None:
        self.transitions: list[ControlTransitionRequest] = []

    def valid_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        return ()

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        return (ControlTarget(id=CONTROL_TARGET_RECOVER_FROM_STUCK),)

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransitionRequest,
    ) -> ControlTransitionResult:
        self.transitions.append(transition)
        return ControlTransitionResult(
            accepted=True,
            mutated=True,
            reason=f"applied:{transition.target_id}",
        )

    def synthesize_artifacts(
        self,
        run_state: RunStateView,
        transition: ControlTransitionRequest,
    ) -> dict[str, object]:
        return {}


def _write_spec(tmp_path: Path, extra: str = "") -> Path:
    idea_a = tmp_path / "a.md"
    idea_b = tmp_path / "b.md"
    idea_a.write_text("A\n", encoding="utf-8")
    idea_b.write_text("B\n", encoding="utf-8")
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        f"""
milestones:
  - label: a
    idea: {idea_a}
  - label: b
    idea: {idea_b}
    depends_on: [a]
{extra}
""",
        encoding="utf-8",
    )
    return spec_path


def _run(
    spec_path: Path,
    root: Path,
    statuses: list[str],
    *,
    pack: FakePackRunner | None = None,
    **kwargs: object,
) -> tuple[dict[str, object], FakePackRunner, FakeDriver]:
    pack = pack or FakePackRunner()
    driver = FakeDriver(statuses)
    result = run_chain(
        spec_path,
        root,
        driver=driver,
        pack_runner=pack,
        writer=lambda _msg: None,
        **kwargs,
    )
    return result, pack, driver


def test_chain_runner_executes_milestones_serially_with_injected_seams(
    tmp_path: Path,
) -> None:
    spec_path = _write_spec(
        tmp_path,
        "driver:\n"
        "  max_iterations: 7\n"
        "  poll_sleep: 0.0\n"
        "  on_escalate: force-proceed\n",
    )

    result, pack, driver = _run(spec_path, tmp_path, ["done", "done"])

    assert result["status"] == "done"
    assert set(result) == {
        "base_branch",
        "chain_state",
        "events",
        "milestone_results",
        "reason",
        "status",
        "supervisor_state",
    }
    assert result["reason"] == ""
    assert [item["label"] for item in result["milestone_results"]] == ["a", "b"]
    assert [request.plan for request in driver.requests] == ["plan-a-1", "plan-b-1"]
    assert [request.max_iterations for request in driver.requests] == [7, 7]
    assert {request.escalate_action for request in driver.requests} == {
        SUPERVISOR_DRIVER_ESCALATE_ACTION
    }
    assert all(request.escalate_action != "force-proceed" for request in driver.requests)
    assert pack.nodes == ["a", "b"]
    assert isinstance(driver, RunDriver)
    assert isinstance(pack, PackRunner)
    assert {event["kind"] for event in result["events"]} >= {
        "milestone_start",
        "driver_outcome",
        "ladder_decision",
    }
    supervisor = load_supervisor_state(tmp_path, str(spec_path.resolve()))
    assert supervisor is not None
    assert supervisor.completed_node_ids == ["a", "b"]
    assert [
        (assertion.node_id, assertion.depends_on) for assertion in supervisor.dependency_assertions
    ] == [("a", ()), ("b", ("a",))]
    assert [(record.node_id, record.original_status) for record in supervisor.run_records] == [
        ("a", "done"),
        ("b", "done"),
    ]


def test_run_chain_defaults_binding_to_canonical_megaplan() -> None:
    assert inspect.signature(run_chain).parameters["binding"].default == "megaplan"


def test_chain_runner_retries_same_node_before_advancing(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)

    result, pack, driver = _run(
        spec_path,
        tmp_path,
        ["failed", "done", "done"],
        ladder_policy=SupervisorLadderPolicy(retry_limit=1),
    )

    assert result["status"] == "done"
    assert pack.nodes[:2] == ["a", "a"]
    assert [request.plan for request in driver.requests[:2]] == ["plan-a-1", "plan-a-2"]
    assert [event for event in result["events"] if event["kind"] == "ladder_decision"][0][
        "action"
    ] == LadderAction.RETRY.value


def test_chain_runner_threads_plan_dir_into_blocked_recovery(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    binding = FakeBinding()

    result, _pack, _driver = _run(
        spec_path,
        tmp_path,
        ["blocked", "done", "done"],
        binding=binding,
        ladder_policy=SupervisorLadderPolicy(retry_limit=0),
    )

    assert result["status"] == "done"
    assert len(binding.transitions) == 1
    transition = binding.transitions[0]
    assert transition.target_id == CONTROL_TARGET_RECOVER_FROM_STUCK
    assert transition.payload["plan_dir"].endswith(".megaplan/plans/plan-a-1")


def test_chain_runner_recovers_blocked_execute_only_after_legacy_guard(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    binding = FakeBinding()

    result, pack, driver = _run(
        spec_path,
        tmp_path,
        ["blocked", "done", "done"],
        pack=RecoverableBlockedPackRunner(),
        binding=binding,
        ladder_policy=SupervisorLadderPolicy(retry_limit=0),
    )

    assert result["status"] == "done"
    assert [request.plan for request in driver.requests] == ["plan-a-1", "plan-a-1", "plan-b-1"]
    assert pack.nodes == ["a", "b"]
    assert binding.transitions == []
    recovered = [
        event for event in result["events"] if event["kind"] == "blocked_execute_recovered"
    ]
    assert recovered == [
        {
            "kind": "blocked_execute_recovered",
            "label": "a",
            "plan": "plan-a-1",
        }
    ]
    state_payload = json.loads(
        (tmp_path / ".megaplan" / "plans" / "plan-a-1" / "state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state_payload["current_state"] == "executed"
    assert "resume_cursor" not in state_payload


def test_chain_runner_treats_guard_failed_blocked_execute_as_real_block(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    binding = FakeBinding()

    result, _pack, driver = _run(
        spec_path,
        tmp_path,
        ["blocked", "done", "done"],
        pack=GuardedBlockedPackRunner(),
        binding=binding,
        ladder_policy=SupervisorLadderPolicy(retry_limit=0),
    )

    assert result["status"] == "done"
    assert [request.plan for request in driver.requests] == [
        "plan-a-1",
        "plan-a-2",
        "plan-b-1",
    ]
    assert len(binding.transitions) == 1
    transition = binding.transitions[0]
    assert transition.target_id == CONTROL_TARGET_RECOVER_FROM_STUCK
    assert transition.payload["plan_dir"].endswith(".megaplan/plans/plan-a-1")
    assert not [event for event in result["events"] if event["kind"] == "blocked_execute_recovered"]


def test_chain_runner_enables_auto_merge_for_green_pr_waits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_path = _write_spec(tmp_path)
    ready_calls: list[tuple[Path, int]] = []
    merge_calls: list[tuple[Path, int]] = []

    monkeypatch.setattr("megaplan.supervisor.pr_merge.git_ops._pr_state", lambda *_a, **_k: "open")

    def fake_run_command(
        root: Path,
        argv: list[str],
        *,
        writer,
        timeout: float,
        error_code: str,
    ) -> subprocess.CompletedProcess[str]:
        del root, writer, timeout, error_code
        assert argv == ["gh", "pr", "view", "42", "--json", "state,mergeStateStatus,isDraft"]
        return subprocess.CompletedProcess(
            argv,
            0,
            '{"state":"OPEN","mergeStateStatus":"CLEAN","isDraft":false}',
            "",
        )

    monkeypatch.setattr("megaplan.supervisor.pr_merge.git_ops._run_command", fake_run_command)
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._mark_pr_ready",
        lambda root, pr_number, *, writer: ready_calls.append((root, pr_number)),
    )
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._enable_auto_merge",
        lambda root, pr_number, *, writer: merge_calls.append((root, pr_number)) or "open",
    )

    result, _pack, driver = _run(
        spec_path,
        tmp_path,
        ["awaiting_human", "done"],
        pack=AwaitingPRMergePackRunner(),
    )

    assert result["status"] == "done"
    assert [request.plan for request in driver.requests] == ["plan-a-1", "plan-b-1"]
    assert ready_calls == [(tmp_path, 42)]
    assert merge_calls == [(tmp_path, 42)]
    assert [
        event for event in result["events"] if event["kind"] == "pr_merge_resolution"
    ] == [
        {
            "kind": "pr_merge_resolution",
            "label": "a",
            "plan": "plan-a-1",
            "advanced": True,
            "pr_number": 42,
            "pr_state": "open",
            "reason": "PR #42 is merge-ready (open)",
        }
    ]
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["pr_number"] == 42
    assert saved.completed[0]["pr_state"] == "open"


def test_chain_runner_advances_when_pr_wait_is_already_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_path = _write_spec(tmp_path)
    run_calls: list[list[str]] = []
    ready_calls: list[tuple[Path, int]] = []
    merge_calls: list[tuple[Path, int]] = []

    monkeypatch.setattr("megaplan.supervisor.pr_merge.git_ops._pr_state", lambda *_a, **_k: "merged")
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._run_command",
        lambda _root, argv, **_kwargs: run_calls.append(argv) or subprocess.CompletedProcess(argv, 0, "{}", ""),
    )
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._mark_pr_ready",
        lambda root, pr_number, *, writer: ready_calls.append((root, pr_number)),
    )
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._enable_auto_merge",
        lambda root, pr_number, *, writer: merge_calls.append((root, pr_number)) or "merged",
    )

    result, _pack, driver = _run(
        spec_path,
        tmp_path,
        ["awaiting_human", "done"],
        pack=AwaitingPRMergePackRunner(),
    )

    assert result["status"] == "done"
    assert [request.plan for request in driver.requests] == ["plan-a-1", "plan-b-1"]
    assert run_calls == []
    assert ready_calls == []
    assert merge_calls == []
    assert [
        event for event in result["events"] if event["kind"] == "pr_merge_resolution"
    ] == [
        {
            "kind": "pr_merge_resolution",
            "label": "a",
            "plan": "plan-a-1",
            "advanced": True,
            "pr_number": 42,
            "pr_state": "merged",
            "reason": "PR #42 is already merged",
        }
    ]
    saved = load_chain_state(spec_path)
    assert saved.completed[0]["pr_state"] == "merged"


@pytest.mark.parametrize(
    ("merge_state_status", "expected_reason"),
    [
        ("BLOCKED", "PR #42 is not merge-ready (blocked)"),
        (None, "PR #42 is not merge-ready (missing_checks)"),
    ],
)
def test_chain_runner_enters_ladder_for_non_green_pr_waits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    merge_state_status: str | None,
    expected_reason: str,
) -> None:
    spec_path = _write_spec(tmp_path)
    ready_calls: list[tuple[Path, int]] = []
    merge_calls: list[tuple[Path, int]] = []

    monkeypatch.setattr("megaplan.supervisor.pr_merge.git_ops._pr_state", lambda *_a, **_k: "open")

    payload = {"state": "OPEN", "isDraft": False}
    if merge_state_status is not None:
        payload["mergeStateStatus"] = merge_state_status

    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._run_command",
        lambda _root, argv, **_kwargs: subprocess.CompletedProcess(argv, 0, json.dumps(payload), ""),
    )
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._mark_pr_ready",
        lambda root, pr_number, *, writer: ready_calls.append((root, pr_number)),
    )
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._enable_auto_merge",
        lambda root, pr_number, *, writer: merge_calls.append((root, pr_number)) or "open",
    )

    result, pack, driver = _run(
        spec_path,
        tmp_path,
        ["awaiting_human", "done", "done"],
        pack=AwaitingPRMergePackRunner(),
    )

    assert result["status"] == "done"
    assert pack.nodes[:2] == ["a", "a"]
    assert [request.plan for request in driver.requests] == ["plan-a-1", "plan-a-2", "plan-b-1"]
    assert ready_calls == []
    assert merge_calls == []
    assert [event for event in result["events"] if event["kind"] == "pr_merge_resolution"][0][
        "reason"
    ] == expected_reason
    assert [event for event in result["events"] if event["kind"] == "ladder_decision"][0] == {
        "kind": "ladder_decision",
        "label": "a",
        "action": LadderAction.RETRY.value,
        "target_id": None,
        "reason": "bounded_retry",
    }


def test_chain_runner_enters_ladder_when_auto_merge_enablement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_path = _write_spec(tmp_path)
    ready_calls: list[tuple[Path, int]] = []

    monkeypatch.setattr("megaplan.supervisor.pr_merge.git_ops._pr_state", lambda *_a, **_k: "open")
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._run_command",
        lambda _root, argv, **_kwargs: subprocess.CompletedProcess(
            argv,
            0,
            '{"state":"OPEN","mergeStateStatus":"CLEAN","isDraft":false}',
            "",
        ),
    )
    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._mark_pr_ready",
        lambda root, pr_number, *, writer: ready_calls.append((root, pr_number)),
    )

    def fail_enable_auto_merge(root: Path, pr_number: int, *, writer) -> str:
        del root, pr_number, writer
        raise CliError("gh_pr_merge_failed", "boom")

    monkeypatch.setattr(
        "megaplan.supervisor.pr_merge.git_ops._enable_auto_merge",
        fail_enable_auto_merge,
    )

    result, pack, driver = _run(
        spec_path,
        tmp_path,
        ["awaiting_human", "done", "done"],
        pack=AwaitingPRMergePackRunner(),
    )

    assert result["status"] == "done"
    assert pack.nodes[:2] == ["a", "a"]
    assert [request.plan for request in driver.requests] == ["plan-a-1", "plan-a-2", "plan-b-1"]
    assert ready_calls == [(tmp_path, 42)]
    assert [event for event in result["events"] if event["kind"] == "pr_merge_resolution"][0][
        "reason"
    ] == "PR #42 merge handling failed: boom"
    assert [event for event in result["events"] if event["kind"] == "ladder_decision"][0][
        "action"
    ] == LadderAction.RETRY.value


def test_chain_runner_stops_when_ladder_reaches_terminal(tmp_path: Path) -> None:
    idea = tmp_path / "a.md"
    idea.write_text("A\n", encoding="utf-8")
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        f"""
milestones:
  - label: a
    idea: {idea}
    profile: apex
    robustness: extreme
    depth: max
""",
        encoding="utf-8",
    )

    result, _pack, _driver = _run(
        spec_path,
        tmp_path,
        ["failed"],
        ladder_policy=SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0),
    )

    assert result["status"] == "stopped"
    assert result["milestone_results"] == []
    supervisor = load_supervisor_state(tmp_path, str(spec_path.resolve()))
    assert supervisor is not None
    assert supervisor.metadata["terminal_tickets"][0]["node_id"] == "a"


def test_chain_runner_rejects_unmet_supervisor_dependency(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    _run(spec_path, tmp_path, ["done"], one=True)
    supervisor = load_supervisor_state(tmp_path, str(spec_path.resolve()))
    assert supervisor is not None
    supervisor.completed_node_ids.clear()
    save_supervisor_state(tmp_path, str(spec_path.resolve()), supervisor)

    with pytest.raises(CliError, match="unmet dependencies"):
        _run(spec_path, tmp_path, ["done"])
