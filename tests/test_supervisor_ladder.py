from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.control_interface import (
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlTarget,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from megaplan.run_outcome import RunOutcome
from megaplan.supervisor.ladder import (
    LadderAction,
    SupervisorLadderPolicy,
    apply_ladder,
    bump_one_tier,
    select_neutral_target,
)
from megaplan.supervisor.model import RunNode, SupervisorState, SupervisorVariantKind
from megaplan.supervisor.state import load_supervisor_state


class FakeBinding:
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
        return tuple(ControlTarget(id=target_id) for target_id in self._valid_targets)

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTarget, ...]:
        return tuple(ControlTarget(id=target_id) for target_id in self._recover_targets)

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


def _state(node: RunNode) -> SupervisorState:
    return SupervisorState(
        variant=SupervisorVariantKind.CHAIN,
        run_nodes=[node],
        current_node_id=node.node_id,
    )


def _view() -> RunStateView:
    return RunStateView(run_id="run-1", raw_state={"current_state": "failed"})


def test_bump_one_tier_is_deterministic_and_bounded() -> None:
    assert bump_one_tier(None, ("premium", "apex")) == ("premium", True)
    assert bump_one_tier("premium", ("premium", "apex")) == ("apex", True)
    assert bump_one_tier("apex", ("premium", "apex")) == ("apex", False)
    assert bump_one_tier("custom", ("premium", "apex")) == ("custom", False)


def test_ladder_retries_are_bounded_and_persisted(tmp_path: Path) -> None:
    node = RunNode(node_id="m1", spec_ref="milestone:m1")
    state = _state(node)
    policy = SupervisorLadderPolicy(retry_limit=2)

    first = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )
    second = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )

    assert first.action == LadderAction.RETRY
    assert first.retry_count == 1
    assert second.action == LadderAction.RETRY
    assert second.retry_count == 2

    loaded = load_supervisor_state(tmp_path, "chain.yaml")
    assert loaded is not None
    assert loaded.metadata["retry_counts"] == {"m1": 2}
    assert [entry["reason"] for entry in loaded.metadata["ladder_transitions"]] == [
        "bounded_retry",
        "bounded_retry",
    ]


def test_ladder_bumps_profile_robustness_then_depth_after_retries(tmp_path: Path) -> None:
    node = RunNode(
        node_id="m1",
        spec_ref="milestone:m1",
        metadata={"profile": "apex", "robustness": "thorough", "depth": "high"},
    )
    state = _state(node)
    policy = SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0)

    first = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )
    second = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )

    assert first.action == LadderAction.RETRY
    assert first.bumped == {"robustness": "extreme"}
    assert second.action == LadderAction.RETRY
    assert second.bumped == {"depth": "max"}
    assert state.metadata["robustness_bumps"] == {"m1": "extreme"}
    assert state.metadata["depth_bumps"] == {"m1": "max"}


def test_ladder_allows_retry_after_bump(tmp_path: Path) -> None:
    node = RunNode(
        node_id="m1",
        spec_ref="milestone:m1",
        metadata={"profile": "apex", "robustness": "thorough", "depth": "high"},
    )
    state = _state(node)
    policy = SupervisorLadderPolicy(retry_limit=1, apex_extreme_retry_limit=1)

    first = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )
    second = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )
    third = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=policy,
    )

    assert first.retry_count == 1
    assert second.bumped == {"robustness": "extreme"}
    assert third.retry_count == 1

    loaded = load_supervisor_state(tmp_path, "chain.yaml")
    assert loaded is not None
    assert loaded.metadata["retry_counts"] == {"m1": 1}
    assert [entry["reason"] for entry in loaded.metadata["ladder_transitions"]] == [
        "bounded_retry",
        "bump_robustness",
        "bounded_retry",
    ]


def test_blocked_outcome_selects_recovery_target_and_threads_plan_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = RunNode(node_id="m1", spec_ref="milestone:m1")
    state = _state(node)
    binding = FakeBinding(
        recover_targets=(CONTROL_TARGET_REROUTE, CONTROL_TARGET_RECOVER_FROM_STUCK)
    )
    plan_dir = tmp_path / "plans" / "m1"
    captured: dict[str, object] = {}

    def _fake_apply_transition(
        run_state: RunStateView,
        transition: ControlTransitionRequest,
        binding: object,
        *,
        plan_dir: Path,
    ) -> ControlTransitionResult:
        captured["run_state"] = run_state
        captured["transition"] = transition
        captured["binding"] = binding
        captured["plan_dir"] = plan_dir
        return ControlTransitionResult(
            accepted=True,
            mutated=True,
            reason=f"applied:{transition.target_id}",
        )

    monkeypatch.setattr("megaplan.supervisor.ladder.apply_transition", _fake_apply_transition)

    decision = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.BLOCKED,
        plan_dir=plan_dir,
        binding=binding,
        policy=SupervisorLadderPolicy(retry_limit=0),
    )

    assert decision.action == LadderAction.TRANSITION
    assert decision.target_id == CONTROL_TARGET_RECOVER_FROM_STUCK
    assert captured["plan_dir"] == plan_dir
    transition = captured["transition"]
    assert isinstance(transition, ControlTransitionRequest)
    assert transition.target_id == CONTROL_TARGET_RECOVER_FROM_STUCK

    loaded = load_supervisor_state(tmp_path, "chain.yaml")
    assert loaded is not None
    assert loaded.metadata["ladder_transitions"][-1] == {
        "action": "transition",
        "node_id": "m1",
        "outcome": "blocked",
        "reason": "neutral_recovery_target",
        "target_id": CONTROL_TARGET_RECOVER_FROM_STUCK,
        "transition_accepted": True,
        "transition_mutated": True,
        "transition_reason": f"applied:{CONTROL_TARGET_RECOVER_FROM_STUCK}",
    }
    assert loaded.metadata["transition_counts"] == {
        f"m1:recovery:{CONTROL_TARGET_RECOVER_FROM_STUCK}": 1
    }


def test_select_neutral_target_uses_required_order() -> None:
    binding = FakeBinding(
        valid_targets=(CONTROL_TARGET_ABORT, CONTROL_TARGET_REROUTE, CONTROL_TARGET_FORCE_ADVANCE),
        recover_targets=(CONTROL_TARGET_ABORT, CONTROL_TARGET_REROUTE),
    )

    escalation = select_neutral_target(_view(), binding, recovery=False)
    recovery = select_neutral_target(_view(), binding, recovery=True)

    assert escalation is not None
    assert escalation.id == CONTROL_TARGET_FORCE_ADVANCE
    assert recovery is not None
    assert recovery.id == CONTROL_TARGET_REROUTE


def test_terminal_ticket_is_emitted_when_ladder_exhausts(tmp_path: Path) -> None:
    node = RunNode(
        node_id="m1",
        spec_ref="milestone:m1",
        metadata={"profile": "apex", "robustness": "extreme", "depth": "max"},
    )
    state = _state(node)

    decision = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.FAILED,
        plan_dir=tmp_path / "plan",
        binding=FakeBinding(),
        policy=SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0),
    )

    assert decision.action == LadderAction.TERMINAL
    assert decision.ticket_path is not None
    ticket = json.loads(Path(decision.ticket_path).read_text(encoding="utf-8"))
    assert ticket["kind"] == "supervisor_ladder_terminal"
    assert ticket["node_id"] == "m1"
    assert ticket["outcome"] == RunOutcome.FAILED.value

    loaded = load_supervisor_state(tmp_path, "chain.yaml")
    assert loaded is not None
    assert loaded.metadata["terminal_tickets"][0]["path"] == decision.ticket_path
    assert loaded.metadata["ladder_transitions"][-1]["ticket_path"] == decision.ticket_path


def test_escalation_targets_follow_order_then_stop_with_ticket(tmp_path: Path) -> None:
    node = RunNode(
        node_id="m1",
        spec_ref="milestone:m1",
        metadata={"profile": "apex", "robustness": "extreme", "depth": "max"},
    )
    state = _state(node)
    binding = FakeBinding(
        valid_targets=(
            CONTROL_TARGET_ABORT,
            CONTROL_TARGET_REROUTE,
            CONTROL_TARGET_FORCE_ADVANCE,
        )
    )
    policy = SupervisorLadderPolicy(retry_limit=0, apex_extreme_retry_limit=0)

    first = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.ESCALATED,
        plan_dir=tmp_path / "plan",
        binding=binding,
        policy=policy,
    )
    second = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.ESCALATED,
        plan_dir=tmp_path / "plan",
        binding=binding,
        policy=policy,
    )
    third = apply_ladder(
        root=tmp_path,
        state_id="chain.yaml",
        state=state,
        node=node,
        run_state=_view(),
        outcome=RunOutcome.ESCALATED,
        plan_dir=tmp_path / "plan",
        binding=binding,
        policy=policy,
    )

    assert first.action == LadderAction.TRANSITION
    assert first.target_id == CONTROL_TARGET_FORCE_ADVANCE
    assert second.action == LadderAction.TRANSITION
    assert second.target_id == CONTROL_TARGET_REROUTE
    assert third.action == LadderAction.TERMINAL
    assert third.target_id == CONTROL_TARGET_ABORT
    assert third.ticket_path is not None
    assert Path(third.ticket_path).exists()

    loaded = load_supervisor_state(tmp_path, "chain.yaml")
    assert loaded is not None
    reasons = [entry["reason"] for entry in loaded.metadata["ladder_transitions"]]
    assert reasons == [
        "neutral_escalation_target",
        "neutral_escalation_target",
        "neutral_escalation_target",
        "abort_target_selected",
    ]
    assert loaded.metadata["transition_counts"] == {
        f"m1:escalation:{CONTROL_TARGET_FORCE_ADVANCE}": 1,
        f"m1:escalation:{CONTROL_TARGET_REROUTE}": 1,
        f"m1:escalation:{CONTROL_TARGET_ABORT}": 1,
    }
