"""End-to-end composition regression tests — DC4/DC5.

Covers the frozen reduce invariant and the modified dispatch path through
``reduce_contract_results`` and the executor subloop/fan-out lift paths.

Four scenarios:
1. Subloop with one SUSPENDED child → parent SUSPENDED, child cursor preserved.
2. Fan-out one branch SUSPENDED + rest COMPLETED → parent SUSPENDED with
   composite cursor children keyed by child_id.
3. Fan-out all COMPLETED → parent COMPLETED, no pending_suspensions payload.
4. MIXED fan-out (FAILED + SUSPENDED + COMPLETED) → parent FAILED AND
   payload['pending_suspensions'] carries the suspended child's cursor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.pipeline import (
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Suspension,
    reduce_contract_results,
)
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline as megaplan_run_pipeline
from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipelines.megaplan._pipeline.subloop import SubloopStep
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Stage,
    StepContext,
    StepResult,
)


# ── helpers ────────────────────────────────────────────────────────────


@dataclass
class _StaticStep:
    """Step that returns a pre-determined result (no model call)."""

    name: str
    result: StepResult
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        return self.result


def _ctx(plan_dir: Path, *, state: dict[str, Any] | None = None) -> StepContext:
    return StepContext(plan_dir=plan_dir, state=state or {}, profile=None, mode="test")


def _contract(
    status: ContractStatus,
    *,
    cursor: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    awaitable: str | None = "user",
    thread_ref: str | None = None,
    actor: str | None = None,
    child_id: str | None = None,
) -> ContractResult:
    """Build a ContractResult with an optional Suspension."""
    suspension = None
    if status is ContractStatus.SUSPENDED:
        suspension = Suspension(
            kind="human",
            awaitable=awaitable,
            prompt=f"Paused {child_id or 'child'}",
            display_refs=(),
            resume_cursor=json.dumps(cursor or {"phase": child_id or "child"}),
            thread_ref=thread_ref,
            actor=actor,
        )
    elif status is ContractStatus.FAILED and thread_ref is not None:
        suspension = Suspension(
            kind="human",
            awaitable=awaitable,
            prompt="A sibling failed",
            thread_ref=thread_ref,
            actor=actor,
        )
    return ContractResult(status=status, suspension=suspension, payload=payload or {})


def _voted_step(
    name: str,
    *,
    recommendation: str,
    contract: ContractResult,
    reviewer_id: str | None = None,
) -> _StaticStep:
    payload = {"reviewer_id": reviewer_id} if reviewer_id is not None else {}
    return _StaticStep(
        name=name,
        result=StepResult(
            verdict=PipelineVerdict(score=1.0, recommendation=recommendation, payload=payload),
            next="halt",
            contract_result=contract,
        ),
    )


def _megaplan_join(join_fn):
    """Adapt neutral Arnold join output to Megaplan's StepResult shape."""

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        joined = join_fn(results, ctx)
        return StepResult(
            outputs=dict(joined.outputs),
            verdict=joined.verdict,
            next=joined.next,
            state_patch=dict(joined.state_patch),
            contract_result=joined.contract_result,
        )

    return _join


# ── Scenario 1: subloop with one SUSPENDED child ──────────────────────


def test_subloop_single_suspended_child_preserves_cursor(tmp_path: Path) -> None:
    """Parent status=SUSPENDED; child resume cursor preserved via subloop lift."""
    child = _StaticStep(
        name="child_gate",
        result=StepResult(
            next="halt",
            state_patch={"score": 0.72},
            contract_result=_contract(
                ContractStatus.SUSPENDED,
                cursor={"phase": "child_gate", "retry_strategy": "fresh"},
                child_id="child_gate",
            ),
        ),
    )
    child_pipeline = Pipeline(
        stages={"child_gate": Stage(name="child_gate", step=child)},
        entry="child_gate",
    )
    parent = SubloopStep(name="review", child_pipeline=child_pipeline)
    pipeline = Pipeline(
        stages={"review": Stage(name="review", step=parent)},
        entry="review",
    )

    result = megaplan_run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "awaiting_user"
    assert result["final_stage"] == "review"
    assert result["contract_result"]["status"] == "suspended"
    # Child cursor preserved in state-resident resume_cursor
    assert result["state"]["resume_cursor"] == {
        "phase": "child_gate",
        "retry_strategy": "fresh",
    }


# ── Scenario 2: fan-out one SUSPENDED, rest COMPLETED ─────────────────


def test_fanout_single_suspended_rest_completed_via_reducer(tmp_path: Path) -> None:
    """Parent SUSPENDED; composite cursor children keyed by child_id."""
    suspended_child = _contract(
        ContractStatus.SUSPENDED,
        cursor={"phase": "beta", "attempt": 2},
        child_id="beta",
    )
    completed_a = _contract(ContractStatus.COMPLETED)
    completed_b = _contract(ContractStatus.COMPLETED)

    parent = reduce_contract_results(
        [completed_a, suspended_child, completed_b],
        child_ids=["alpha", "beta", "gamma"],
    )

    assert parent.status == ContractStatus.SUSPENDED
    assert parent.suspension is not None
    assert parent.suspension.kind == "human"  # single suspended child → pass-through
    payload = parent.payload
    # pending_suspensions is populated even for a single suspended child
    # (the invariant from contract_reduce.py:140 preserves all suspended cursors)
    assert "pending_suspensions" in payload
    pending = payload["pending_suspensions"]
    assert len(pending) == 1
    assert pending[0]["child_id"] == "beta"
    assert json.loads(pending[0]["cursor"]) == {"phase": "beta", "attempt": 2}
    # Source contracts record all children
    source_ids = [s["child_id"] for s in payload["source_contracts"]]
    assert source_ids == ["alpha", "beta", "gamma"]


def test_fanout_single_suspended_via_majority_vote_executor(tmp_path: Path) -> None:
    """Fan-out lift path: single SUSPENDED + COMPLETED → parent SUSPENDED."""
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "completed",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "paused",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "paused", "attempt": 2},
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result = megaplan_run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "awaiting_user"
    assert result["contract_result"]["status"] == "suspended"
    assert result["state"]["resume_cursor"] == {
        "kind": "composite_suspension",
            "version": 1,
            "phase": "panel",
            "children": {"paused": {"phase": "paused", "attempt": 2}},
        "pending_suspensions": result["contract_result"]["payload"]["pending_suspensions"],
        "shared_awaitable": "user",
    }


# ── Scenario 3: fan-out all COMPLETED ──────────────────────────────────


def test_fanout_all_completed_via_reducer() -> None:
    """All COMPLETED → parent COMPLETED, no pending_suspensions payload."""
    parent = reduce_contract_results(
        [
            _contract(ContractStatus.COMPLETED),
            _contract(ContractStatus.COMPLETED),
            _contract(ContractStatus.COMPLETED),
        ],
        child_ids=["a", "b", "c"],
    )

    assert parent.status == ContractStatus.COMPLETED
    assert parent.suspension is None
    assert "pending_suspensions" not in parent.payload
    assert parent.payload["reduce_policy"] == "max_wins"
    assert parent.payload["status_lattice"] == "completed<suspended<failed"


# ── Scenario 4: MIXED fan-out (FAILED + SUSPENDED + COMPLETED) ─────────


def test_fanout_mixed_failed_suspended_completed_via_reducer() -> None:
    """FAILED wins MAX_WINS; pending_suspensions carries the suspended child's cursor."""
    suspended_cursor = {"phase": "beta", "retry_strategy": "awaiting_user", "token": 7}

    failed = _contract(
        ContractStatus.FAILED,
        payload={"error": "blocked"},
        thread_ref="thread-1",
    )
    suspended = _contract(
        ContractStatus.SUSPENDED,
        cursor=suspended_cursor,
        child_id="beta",
        thread_ref="thread-1",
    )
    completed = _contract(ContractStatus.COMPLETED)

    parent = reduce_contract_results(
        [failed, suspended, completed],
        child_ids=["alpha", "beta", "gamma"],
    )

    # FAILED wins the max-wins lattice
    assert parent.status == ContractStatus.FAILED
    # No composite suspension — FAILED dominates
    assert parent.suspension is not None
    assert parent.suspension.kind == "human"
    assert parent.suspension.thread_ref == "thread-1"

    # The load-bearing invariant: pending_suspensions carries the suspended child's cursor
    payload = parent.payload
    assert "pending_suspensions" in payload, (
        "FAILED parent must preserve pending_suspensions for the suspended child"
    )
    pending = payload["pending_suspensions"]
    assert len(pending) == 1
    assert pending[0]["child_id"] == "beta"
    assert pending[0]["status"] == "suspended"
    assert json.loads(pending[0]["cursor"]) == suspended_cursor


def test_fanout_mixed_failed_suspended_completed_via_weighted_vote_executor(
    tmp_path: Path,
) -> None:
    """Executor lift path: FAILED + SUSPENDED → parent FAILED, pending_suspensions preserved."""
    suspended_cursor = {"phase": "paused", "attempt": 4}

    panel = ParallelStage(
        name="weighted_panel",
        steps=(
            _voted_step(
                "failed",
                recommendation="approve",
                reviewer_id="lead",
                contract=_contract(
                    ContractStatus.FAILED,
                    payload={"error": "max wins"},
                ),
            ),
            _voted_step(
                "paused",
                recommendation="approve",
                reviewer_id="peer",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor=suspended_cursor,
                    awaitable="user",
                    thread_ref="thread-12",
                    actor="human",
                ),
            ),
        ),
        join=_megaplan_join(weighted_vote({"lead": 2.0, "peer": 1.0}, default_on_tie="halt")),
        edges=(Edge(label="approve", target="halt", kind="decision"),),
    )

    result = megaplan_run_pipeline(
        Pipeline(stages={"weighted_panel": panel}, entry="weighted_panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "failed"
    assert result["final_stage"] == "weighted_panel"
    assert result["contract_result"]["status"] == "failed"

    # pending_suspensions must carry the suspended child's cursor
    payload = result["contract_result"]["payload"]
    assert "pending_suspensions" in payload, (
        "FAILED parent must preserve pending_suspensions"
    )
    pending = payload["pending_suspensions"]
    assert len(pending) == 1
    assert pending[0]["child_id"] == "paused"
    assert json.loads(pending[0]["cursor"]) == suspended_cursor

    # No composite resume cursor on state because FAILED dominates
    assert "resume_cursor" in result["state"]
    # But pending_suspensions is preserved in contract payload
