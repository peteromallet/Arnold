from __future__ import annotations

import json
import shutil
from pathlib import Path

from arnold.pipelines.megaplan.auto import DriverOutcome
from arnold.pipelines.megaplan.control_interface import (
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlTarget,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from arnold.pipelines.megaplan.supervisor.chain_runner import run_chain
from arnold.pipelines.megaplan.supervisor.driver import RunRequest
from arnold.pipelines.megaplan.supervisor.ladder import SupervisorLadderPolicy
from arnold.pipelines.megaplan.supervisor.model import RunNode
from arnold.pipelines.megaplan.supervisor.state import load_supervisor_state


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "supervisor_canary"
_PLANNING_LITERAL_IDS = frozenset({"force-proceed", "replan"})


class CanaryPackRunner:
    def __init__(self) -> None:
        self.nodes: list[str] = []

    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        self.nodes.append(node.node_id)
        attempt = self.nodes.count(node.node_id)
        plan_name = f"canary-{node.node_id}-{attempt}"
        plan_dir = root / ".megaplan" / "plans" / plan_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan_name,
                    "current_state": "initialized",
                    "config": {"robustness": "standard"},
                }
            ),
            encoding="utf-8",
        )
        return plan_name


class CanaryDriver:
    def __init__(self) -> None:
        self.requests: list[RunRequest] = []
        self._statuses = {
            "canary-alpha-1": ["done"],
            "canary-beta-1": ["failed"],
            "canary-beta-2": ["done"],
        }

    def drive(self, request: RunRequest) -> DriverOutcome:
        self.requests.append(request)
        status = self._statuses[request.plan].pop(0)
        return DriverOutcome(
            status=status,
            plan=request.plan,
            final_state="done" if status == "done" else "failed",
            iterations=1,
            reason=f"canary:{status}",
            last_phase="execute",
            events=[],
        )


class ScenarioCanaryDriver:
    def __init__(self, statuses: dict[str, list[str]]) -> None:
        self.requests: list[RunRequest] = []
        self._statuses = {plan: list(plan_statuses) for plan, plan_statuses in statuses.items()}

    def drive(self, request: RunRequest) -> DriverOutcome:
        self.requests.append(request)
        status = self._statuses[request.plan].pop(0)
        return DriverOutcome(
            status=status,
            plan=request.plan,
            final_state="done" if status == "done" else status,
            iterations=len(self.requests),
            reason=f"canary:{status}",
            last_phase="execute",
            events=[],
            blocking_reasons=["quality"] if status == "blocked" else [],
        )


class CanaryBinding:
    def __init__(
        self,
        *,
        valid_targets: tuple[str, ...] = (),
        recover_targets: tuple[str, ...] = (),
    ) -> None:
        self._valid_targets = valid_targets
        self._recover_targets = recover_targets
        self.transitions: list[ControlTransitionRequest] = []

    def valid_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        del run_state
        return tuple(ControlTarget(id=target_id) for target_id in self._valid_targets)

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        del run_state
        return tuple(ControlTarget(id=target_id) for target_id in self._recover_targets)

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransitionRequest,
    ) -> ControlTransitionResult:
        del run_state
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
        del run_state, transition
        return {}


def _materialize_canary(tmp_path: Path, *, beta_maxed: bool = False) -> tuple[Path, Path]:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, fixture_root)
    alpha = (fixture_root / "alpha.md").resolve()
    beta = (fixture_root / "beta.md").resolve()
    spec_path = fixture_root / "supervisor-canary.yaml"
    beta_lines = ["  - label: beta", f"    idea: {beta}", "    depends_on: [alpha]"]
    if beta_maxed:
        beta_lines.extend(
            [
                "    profile: apex",
                "    robustness: extreme",
                "    depth: max",
            ]
        )
    spec_path.write_text(
        "\n".join(
            [
                "milestones:",
                "  - label: alpha",
                f"    idea: {alpha}",
                *beta_lines,
                "driver:",
                "  max_iterations: 5",
                "  poll_sleep: 0.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return fixture_root, spec_path


def _ladder_events(result: dict[str, object]) -> list[dict[str, object]]:
    return [event for event in result["events"] if event["kind"] == "ladder_decision"]


def _assert_supervisor_path_uses_only_neutral_targets(
    *,
    result: dict[str, object],
    binding: CanaryBinding | None = None,
    supervisor_state_path_root: Path | None = None,
    state_id: str | None = None,
) -> None:
    seen_target_ids = {
        event["target_id"]
        for event in _ladder_events(result)
        if isinstance(event.get("target_id"), str)
    }
    if binding is not None:
        seen_target_ids.update(transition.target_id for transition in binding.transitions)
    if supervisor_state_path_root is not None and state_id is not None:
        supervisor_state = load_supervisor_state(supervisor_state_path_root, state_id)
        assert supervisor_state is not None
        seen_target_ids.update(
            entry["target_id"]
            for entry in supervisor_state.metadata.get("ladder_transitions", [])
            if isinstance(entry.get("target_id"), str)
        )
    assert not (seen_target_ids & _PLANNING_LITERAL_IDS), seen_target_ids


def test_supervisor_canary_fixture_exercises_dependency_and_induced_failure(
    tmp_path: Path,
) -> None:
    root, spec_path = _materialize_canary(tmp_path)
    driver = CanaryDriver()
    pack_runner = CanaryPackRunner()

    result = run_chain(
        spec_path,
        root,
        driver=driver,
        pack_runner=pack_runner,
        writer=lambda _msg: None,
    )

    assert result["status"] == "done"
    assert pack_runner.nodes == ["alpha", "beta", "beta"]
    assert [request.plan for request in driver.requests] == [
        "canary-alpha-1",
        "canary-beta-1",
        "canary-beta-2",
    ]

    ladder_events = [event for event in result["events"] if event["kind"] == "ladder_decision"]
    assert {
        (event["label"], event["action"], event["reason"])
        for event in ladder_events
    } >= {
        ("beta", "retry", "bounded_retry"),
    }
    _assert_supervisor_path_uses_only_neutral_targets(
        result=result,
        supervisor_state_path_root=root,
        state_id=str(spec_path.resolve()),
    )

    supervisor_state = load_supervisor_state(root, str(spec_path.resolve()))
    assert supervisor_state is not None
    assert [node.node_id for node in supervisor_state.run_nodes] == ["alpha", "beta"]
    assert [
        (assertion.node_id, assertion.depends_on) for assertion in supervisor_state.dependency_assertions
    ] == [("alpha", ()), ("beta", ("alpha",))]
    assert supervisor_state.completed_node_ids == ["alpha", "beta"]
    assert [(record.node_id, record.original_status) for record in supervisor_state.run_records] == [
        ("alpha", "done"),
        ("beta", "failed"),
        ("beta", "done"),
    ]


def test_supervisor_canary_fixture_uses_neutral_recovery_targets_for_blocked_runs(
    tmp_path: Path,
) -> None:
    root, spec_path = _materialize_canary(tmp_path)
    driver = ScenarioCanaryDriver(
        {
            "canary-alpha-1": ["done"],
            "canary-beta-1": ["blocked"],
            "canary-beta-2": ["done"],
        }
    )
    binding = CanaryBinding(
        recover_targets=(
            CONTROL_TARGET_RECOVER_FROM_STUCK,
            CONTROL_TARGET_REROUTE,
            CONTROL_TARGET_ABORT,
        )
    )

    result = run_chain(
        spec_path,
        root,
        driver=driver,
        pack_runner=CanaryPackRunner(),
        binding=binding,
        ladder_policy=SupervisorLadderPolicy(retry_limit=0),
        writer=lambda _msg: None,
    )

    assert result["status"] == "done"
    assert [request.plan for request in driver.requests] == [
        "canary-alpha-1",
        "canary-beta-1",
        "canary-beta-2",
    ]
    assert [transition.target_id for transition in binding.transitions] == [
        CONTROL_TARGET_RECOVER_FROM_STUCK
    ]
    assert binding.transitions[0].payload["plan_dir"].endswith(".megaplan/plans/canary-beta-1")
    assert {
        (event["label"], event["action"], event["target_id"], event["reason"])
        for event in _ladder_events(result)
    } >= {
        ("beta", "transition", CONTROL_TARGET_RECOVER_FROM_STUCK, "neutral_recovery_target"),
    }
    _assert_supervisor_path_uses_only_neutral_targets(
        result=result,
        binding=binding,
        supervisor_state_path_root=root,
        state_id=str(spec_path.resolve()),
    )


def test_supervisor_canary_fixture_uses_neutral_escalation_targets_for_failed_runs(
    tmp_path: Path,
) -> None:
    root, spec_path = _materialize_canary(tmp_path, beta_maxed=True)
    driver = ScenarioCanaryDriver(
        {
            "canary-alpha-1": ["done"],
            "canary-beta-1": ["failed"],
            "canary-beta-2": ["done"],
        }
    )
    binding = CanaryBinding(
        valid_targets=(
            CONTROL_TARGET_FORCE_ADVANCE,
            CONTROL_TARGET_REROUTE,
            CONTROL_TARGET_ABORT,
        )
    )

    result = run_chain(
        spec_path,
        root,
        driver=driver,
        pack_runner=CanaryPackRunner(),
        binding=binding,
        ladder_policy=SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0),
        writer=lambda _msg: None,
    )

    assert result["status"] == "done"
    assert [request.plan for request in driver.requests] == [
        "canary-alpha-1",
        "canary-beta-1",
        "canary-beta-2",
    ]
    assert [transition.target_id for transition in binding.transitions] == [
        CONTROL_TARGET_FORCE_ADVANCE
    ]
    assert binding.transitions[0].payload["plan_dir"].endswith(".megaplan/plans/canary-beta-1")
    assert {
        (event["label"], event["action"], event["target_id"], event["reason"])
        for event in _ladder_events(result)
    } >= {
        ("beta", "transition", CONTROL_TARGET_FORCE_ADVANCE, "neutral_escalation_target"),
    }
    _assert_supervisor_path_uses_only_neutral_targets(
        result=result,
        binding=binding,
        supervisor_state_path_root=root,
        state_id=str(spec_path.resolve()),
    )
