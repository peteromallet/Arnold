"""Sprint 4 Chunk D — SubloopStep runs a child Pipeline and promotes it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    PipelineVerdict,
)
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.subloop import SubloopStep


@dataclass
class _ChildLeaf:
    name: str = "leaf"
    kind: str = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        out = ctx.plan_dir / "leaf.json"
        out.write_text(json.dumps({"verdict": "ok"}))
        return StepResult(
            outputs={"leaf": out},
            next="halt",
            state_patch={"child_done": True, "score": 0.9},
        )


def _child_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "leaf": Stage(name="leaf", step=_ChildLeaf(),
                          edges=(Edge(label="halt", target="halt"),)),
        },
        entry="leaf",
    )


def test_subloop_runs_child_and_emits_verdict(tmp_path: Path) -> None:
    subloop = SubloopStep(
        name="tiebreaker",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed" if state.get("child_done") else "iterate",
    )
    assert isinstance(subloop, Step)
    assert subloop.kind == "subloop"

    pipeline = Pipeline(
        stages={
            "tiebreaker": Stage(name="tiebreaker", step=subloop,
                                edges=(
                                    Edge(label="proceed", target="done", kind="decision"),
                                )),
            "done": Stage(name="done", step=_ChildLeaf(),
                          edges=(Edge(label="halt", target="halt"),)),
        },
        entry="tiebreaker",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    # Child artifacts land under the subdir.
    assert (tmp_path / "tiebreaker" / "leaf.json").exists()
    assert (tmp_path / "tiebreaker" / "state.json").exists()
    child_state = json.loads((tmp_path / "tiebreaker" / "state.json").read_text())
    assert child_state["child_done"] is True

    # Parent reached the gate-edge target.
    assert result["final_stage"] == "done"
    parent_state = result["state"]
    assert "subloop:tiebreaker:recommendation" in parent_state
    assert parent_state["subloop:tiebreaker:recommendation"] == "proceed"


def test_subloop_promotion_callable_decides_recommendation(tmp_path: Path) -> None:
    """A different promote callable changes which gate edge fires."""

    subloop = SubloopStep(
        name="tb",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "iterate",
    )
    pipeline = Pipeline(
        stages={
            "tb": Stage(name="tb", step=subloop,
                        edges=(
                            Edge(label="iterate", target="iter_done", kind="decision"),
                            Edge(label="proceed", target="proceed_done", kind="decision"),
                        )),
            "iter_done": Stage(name="iter_done", step=_ChildLeaf(),
                               edges=(Edge(label="halt", target="halt"),)),
            "proceed_done": Stage(name="proceed_done", step=_ChildLeaf(),
                                  edges=(Edge(label="halt", target="halt"),)),
        },
        entry="tb",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "iter_done"


def test_subloop_without_child_pipeline_raises(tmp_path: Path) -> None:
    subloop = SubloopStep(name="bad", child_pipeline=None)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    with pytest.raises(ValueError, match="no child_pipeline"):
        subloop.run(ctx)


# ── M4: Suspended-child lift coverage ───────────────────────────────────────

_EXECUTOR_PATH = "arnold.pipelines.megaplan._pipeline.executor.run_pipeline"


def test_non_null_suspension_scope_raises(tmp_path: Path) -> None:
    """Setting suspension_scope to a non-None value raises NotImplementedError."""
    subloop = SubloopStep(
        name="scoped",
        child_pipeline=_child_pipeline(),
        suspension_scope="fan-out",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    with pytest.raises(NotImplementedError, match="suspension_scope"):
        subloop.run(ctx)


def test_suspended_child_lifts_contract_and_returns_halt(tmp_path: Path) -> None:
    """When the child executor returns a SUSPENDED contract, SubloopStep
    lifts it into its own StepResult with next='halt'."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    suspension = Suspension(
        kind="human",
        awaitable="user",
        prompt="Approve this step",
        resume_cursor='{"phase":"leaf","kind":"awaiting_user"}',
    )
    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=suspension,
    )

    fake_result = {
        "state": {"child_done": True, "score": 0.9},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="tiebreaker",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed" if state.get("child_done") else "iterate",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    assert result.next == "halt"
    assert result.contract_result is not None
    assert result.contract_result.status == ContractStatus.SUSPENDED
    assert result.contract_result.suspension is not None
    assert result.contract_result.suspension.kind == "human"
    assert result.contract_result.suspension.awaitable == "user"
    assert result.contract_result.suspension.prompt == "Approve this step"


def test_suspended_child_preserves_resume_cursor_in_state_patch(
    tmp_path: Path,
) -> None:
    """The child's resume_cursor is included in state_patch under
    subloop:<name>:resume_cursor so the parent's state.json carries it."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    cursor_payload = {"phase": "leaf", "retry_strategy": "awaiting_user", "kind": "awaiting_user"}
    suspension = Suspension(
        kind="human",
        awaitable="user",
        prompt="Resume needed",
        resume_cursor=json.dumps(cursor_payload),
    )
    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=suspension,
    )

    fake_result = {
        "state": {"child_done": True},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="tb",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    state_patch = dict(result.state_patch)
    assert "subloop:tb:resume_cursor" in state_patch
    assert state_patch["subloop:tb:resume_cursor"] == json.dumps(cursor_payload)


def test_suspended_child_preserves_subloop_state_key(tmp_path: Path) -> None:
    """The state_patch always includes subloop:<name>:state for observability."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    suspension = Suspension(kind="human", awaitable="user", prompt="Check")
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {"k1": "v1", "score": 0.75},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="sub",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    state_patch = dict(result.state_patch)
    assert "subloop:sub:state" in state_patch
    assert state_patch["subloop:sub:state"] == {"k1": "v1", "score": 0.75}
    assert "subloop:sub:recommendation" in state_patch
    # Suspended children use a fixed "halt" recommendation; promote is not invoked.
    assert state_patch["subloop:sub:recommendation"] == "halt"


def test_suspended_child_preserves_verdict_payload(tmp_path: Path) -> None:
    """The verdict payload carries subloop_final_stage and subloop_state."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    suspension = Suspension(kind="human", awaitable="user", prompt="Check")
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {"score": 0.88},
        "final_stage": "leaf_stage",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="sl",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    assert result.verdict is not None
    payload = result.verdict.payload
    assert payload["subloop_final_stage"] == "leaf_stage"
    assert payload["subloop_state"] == {"score": 0.88}


def test_completed_child_with_halt_reason_awaiting_user_skips_suspension_lift(
    tmp_path: Path,
) -> None:
    """When the child result carries halt_reason='awaiting_user' but the
    contract status is COMPLETED (not SUSPENDED), the subloop does NOT
    enter the suspension-lift branch and falls through to normal promotion."""
    from arnold.pipeline import ContractResult, ContractStatus

    # Completed contract (no suspension)
    contract = ContractResult(status=ContractStatus.COMPLETED)

    fake_result = {
        "state": {"child_done": True, "score": 0.95},
        "final_stage": "leaf",
        "status": "completed",
        "contract_result": contract.to_json(),
        "halt_reason": "awaiting_user",
    }

    subloop = SubloopStep(
        name="tb",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed" if state.get("child_done") else "iterate",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    # Completed child → normal promotion, not suspension lift
    assert result.contract_result is None
    assert result.next == "proceed"
    state_patch = dict(result.state_patch)
    assert state_patch["subloop:tb:recommendation"] == "proceed"
    assert state_patch["subloop:tb:state"] == {"child_done": True, "score": 0.95}


def test_suspended_child_without_resume_cursor_safe(tmp_path: Path) -> None:
    """When the child suspension has no resume_cursor, the state_patch
    omits the subloop:<name>:resume_cursor key (no crash)."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    suspension = Suspension(kind="human", awaitable="user", prompt="Check")
    # resume_cursor defaults to None
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {"done": True},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="sub",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    state_patch = dict(result.state_patch)
    # No resume_cursor key when cursor is None
    assert "subloop:sub:resume_cursor" not in state_patch
    assert result.contract_result is not None
    assert result.next == "halt"


def test_promote_raises_not_invoked_for_suspended_children(tmp_path: Path) -> None:
    """Regression: promote is NOT invoked for suspended children, so even a
    promote that raises does not affect the suspension lift."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    suspension = Suspension(
        kind="human",
        awaitable="user",
        prompt="Check",
        resume_cursor='{"phase":"leaf"}',
    )
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {"child_done": True, "score": 0.5},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    def _raising_promote(state: Any) -> Any:
        raise RuntimeError("promote must not be invoked for suspended children")

    subloop = SubloopStep(
        name="bad_promote",
        child_pipeline=_child_pipeline(),
        promote=_raising_promote,
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    # Suspension lift succeeded without touching the raising promote.
    assert result.next == "halt"
    assert result.contract_result is not None
    assert result.contract_result.status == ContractStatus.SUSPENDED


def test_promote_is_not_invoked_for_suspended_children(tmp_path: Path) -> None:
    """Prove that promote is NOT invoked for suspended children.

    The suspended-child lift uses a fixed 'halt' recommendation,
    bypassing the legacy promote callable entirely.
    """
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    called: list[dict[str, Any]] = []

    def _tracking_promote(state: Any) -> Any:
        called.append(dict(state))
        return "proceed"

    suspension = Suspension(
        kind="human",
        awaitable="user",
        prompt="Check",
        resume_cursor='{"phase":"leaf"}',
    )
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {"child_done": True, "score": 0.5},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="track",
        child_pipeline=_child_pipeline(),
        promote=_tracking_promote,
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    assert result.next == "halt"
    assert result.contract_result is not None
    # The promote callable should NOT have been called — the suspension
    # lift path bypasses legacy promotion.
    assert len(called) == 0, (
        f"promote was called {len(called)} time(s) but should not be "
        "invoked for suspended children"
    )


def test_completed_child_behavior_remains_compatible(tmp_path: Path) -> None:
    """Completed children still go through normal promote-driven routing
    and do not pick up any suspension machinery."""
    subloop = SubloopStep(
        name="tb",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "iterate",
    )
    pipeline = Pipeline(
        stages={
            "tb": Stage(name="tb", step=subloop,
                        edges=(
                            Edge(label="iterate", target="iter_done", kind="decision"),
                            Edge(label="proceed", target="proceed_done", kind="decision"),
                        )),
            "iter_done": Stage(name="iter_done", step=_ChildLeaf(),
                               edges=(Edge(label="halt", target="halt"),)),
            "proceed_done": Stage(name="proceed_done", step=_ChildLeaf(),
                                  edges=(Edge(label="halt", target="halt"),)),
        },
        entry="tb",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "iter_done"
    # Completed child should use normal promotion (no suspension machinery)


def test_suspended_child_suspension_fields_propagated(tmp_path: Path) -> None:
    """All suspension fields (thread_ref, actor, display_refs, deadline, etc.)
    survive the lift from child to parent StepResult."""
    from arnold.pipeline import ContractResult, ContractStatus, EvidenceArtifactRef, Suspension

    ref = EvidenceArtifactRef(
        uri="file:///tmp/artifact.png",
        content_type="image/png",
        name="artifact.png",
    )
    suspension = Suspension(
        kind="human",
        awaitable="user",
        prompt="Please review",
        display_refs=(ref,),
        resume_cursor='{"phase":"leaf"}',
        thread_ref="thread-42",
        actor="reviewer",
        deadline="2026-12-31T23:59:59Z",
        on_timeout="reject",
        default_action="approve",
        resume_input_schema={"type": "object", "properties": {"choice": {"type": "string"}}},
    )
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {"score": 0.7},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="full",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    assert result.contract_result is not None
    lifted = result.contract_result
    assert lifted.status == ContractStatus.SUSPENDED
    assert lifted.suspension is not None
    s = lifted.suspension
    assert s.kind == "human"
    assert s.awaitable == "user"
    assert s.prompt == "Please review"
    assert s.thread_ref == "thread-42"
    assert s.actor == "reviewer"
    assert s.deadline == "2026-12-31T23:59:59Z"
    assert s.on_timeout == "reject"
    assert s.default_action == "approve"
    assert len(s.display_refs) == 1
    assert s.display_refs[0].uri == "file:///tmp/artifact.png"
    assert s.display_refs[0].content_type == "image/png"
    assert s.resume_input_schema == {"type": "object", "properties": {"choice": {"type": "string"}}}


def test_suspended_child_contract_without_suspension_field_safe(tmp_path: Path) -> None:
    """A SUSPENDED contract whose suspension field is None or absent
    should not crash the subloop (defensive .get access)."""
    from arnold.pipeline import ContractResult, ContractStatus

    # SUSPENDED status but suspension=None (inconsistent but possible)
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=None)

    fake_result = {
        "state": {"score": 0.3},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="null_sus",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    # Should not crash — the defensive .get access survives null suspension
    assert result is not None
    assert result.next == "halt"
    assert result.contract_result is not None
    assert result.contract_result.status == ContractStatus.SUSPENDED


def test_suspended_child_malformed_contract_json_falls_through(
    tmp_path: Path,
) -> None:
    """When the contract_result is not a valid ContractResult JSON
    (e.g. schema_version mismatch), the try/except catches it and
    the subloop falls through to normal promotion."""
    bad_contract = {
        "schema_version": "9999.0.0",
        "status": "suspended",
        "payload": {},
        "suspension": None,
        "evidence_refs": [],
        "authority_level": "",
        "provenance": {},
        "freshness": {},
    }

    fake_result = {
        "state": {"child_done": True, "score": 0.8},
        "final_stage": "leaf",
        "status": "completed",
        "contract_result": bad_contract,
        "halt_reason": None,
    }

    subloop = SubloopStep(
        name="malformed",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    # Falls through to normal promotion — no crash, no contract_result
    assert result.contract_result is None
    assert result.next == "proceed"
    state_patch = dict(result.state_patch)
    assert state_patch["subloop:malformed:recommendation"] == "proceed"


def test_suspended_child_without_contract_result_falls_through(
    tmp_path: Path,
) -> None:
    """When the child result has no contract_result key at all, the
    subloop uses normal promotion."""
    fake_result = {
        "state": {"child_done": True, "score": 0.6},
        "final_stage": "leaf",
        "status": "completed",
        # No contract_result key
    }

    subloop = SubloopStep(
        name="no_contract",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    assert result.contract_result is None
    assert result.next == "proceed"


def test_suspended_child_preserves_display_refs(tmp_path: Path) -> None:
    """display_refs in the child suspension survive the lift."""
    from arnold.pipeline import ContractResult, ContractStatus, EvidenceArtifactRef, Suspension

    ref1 = EvidenceArtifactRef(uri="file:///a.txt", content_type="text/plain", name="a.txt")
    ref2 = EvidenceArtifactRef(uri="file:///b.txt", content_type="text/plain", name="b.txt")
    suspension = Suspension(
        kind="human",
        awaitable="user",
        prompt="Review",
        display_refs=(ref1, ref2),
    )
    contract = ContractResult(status=ContractStatus.SUSPENDED, suspension=suspension)

    fake_result = {
        "state": {},
        "final_stage": "leaf",
        "status": "suspended",
        "contract_result": contract.to_json(),
        "halt_reason": "suspended",
    }

    subloop = SubloopStep(
        name="refs",
        child_pipeline=_child_pipeline(),
        promote=lambda state: "proceed",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})

    with patch(_EXECUTOR_PATH, return_value=fake_result):
        result = subloop.run(ctx)

    assert result.contract_result is not None
    refs = result.contract_result.suspension.display_refs
    assert len(refs) == 2
    assert refs[0].uri == "file:///a.txt"
    assert refs[1].name == "b.txt"


# ── End M4 suspended-child lift coverage ─────────────────────────────────────
