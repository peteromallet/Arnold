"""DC2 — Targeted + batch composite resume via the megaplan adapter path.

Two end-to-end fixture-driven scenarios that exercise fan-out suspend → resume
through ``run_pipeline`` (the megaplan executor adapter), asserting:

* **Targeted** (one ``child_id`` resolved) keeps the parent SUSPENDED with the
  remaining child's cursor preserved in the composite payload.
* **Batch** (all ``child_ids`` resolved) reaches COMPLETED with no residual
  suspension.
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
from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
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
    resume_input_schema: dict[str, Any] | None = None,
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
            resume_input_schema=resume_input_schema or {},
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


# ── DC2 Scenario A: targeted resume (one child_id) → parent SUSPENDED ──


def test_targeted_resume_one_child_keeps_parent_suspended(tmp_path: Path) -> None:
    """Run fan-out with two SUSPENDED children, then resume only child_a.

    After targeted resume child_a completes but child_b stays SUSPENDED,
    so the parent remains SUSPENDED with child_b's cursor preserved.
    """
    # ── Phase 1: initial fan-out → both children SUSPENDED ──────────
    initial_panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "attempt": 1},
                    child_id="alpha",
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 1},
                    child_id="beta",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result1 = megaplan_run_pipeline(
        Pipeline(stages={"panel": initial_panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result1["status"] == "suspended"
    # Two suspended children → composite suspension → halt_reason "suspended"
    assert result1["halt_reason"] == "suspended"
    assert result1["contract_result"]["status"] == "suspended"

    # The composite cursor records both children
    cursor1 = result1["state"].get("resume_cursor")
    assert isinstance(cursor1, dict)
    assert cursor1["kind"] == "composite_suspension"
    assert set(cursor1["children"].keys()) == {"alpha", "beta"}

    # ── Phase 2: targeted resume — only alpha completes ──────────────
    # Simulate the adapter extracting just alpha's cursor and re-running
    # the pipeline with alpha resolved.  Beta remains suspended.
    resume_panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 1},
                    child_id="beta",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result2 = megaplan_run_pipeline(
        Pipeline(stages={"panel": resume_panel}, entry="panel"),
        _ctx(tmp_path, state=dict(result1["state"])),
        artifact_root=tmp_path,
    )

    # Targeted: alpha completed, beta still suspended → parent SUSPENDED
    assert result2["status"] == "suspended"
    # Single suspended child → pass-through suspension (kind "human") →
    # halt_reason "awaiting_user"
    assert result2["halt_reason"] == "awaiting_user"
    assert result2["contract_result"]["status"] == "suspended"

    # The composite cursor still records the remaining suspended child (beta)
    cursor2 = result2["state"].get("resume_cursor")
    assert isinstance(cursor2, dict)
    assert cursor2["kind"] == "composite_suspension"
    assert cursor2["children"] == {"beta": {"phase": "beta", "attempt": 1}}

    # pending_suspensions preserves only beta
    payload = result2["contract_result"]["payload"]
    pending = payload.get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 1
    assert pending[0]["child_id"] == "beta"


# ── DC2 Scenario B: batch resume (all child_ids) → parent COMPLETED ──


def test_batch_resume_all_children_reaches_completed(tmp_path: Path) -> None:
    """Run fan-out with two SUSPENDED children, then resume both at once.

    After batch resume both children complete, so the parent reaches
    COMPLETED with no residual suspension.
    """
    # ── Phase 1: initial fan-out → both children SUSPENDED ──────────
    initial_panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "attempt": 1},
                    child_id="alpha",
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 1},
                    child_id="beta",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result1 = megaplan_run_pipeline(
        Pipeline(stages={"panel": initial_panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result1["status"] == "suspended"
    assert result1["halt_reason"] == "suspended"

    # ── Phase 2: batch resume — both children complete ──────────────
    resume_panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result2 = megaplan_run_pipeline(
        Pipeline(stages={"panel": resume_panel}, entry="panel"),
        _ctx(tmp_path, state=dict(result1["state"])),
        artifact_root=tmp_path,
    )

    # Batch: both children completed → parent COMPLETED
    assert result2["status"] == "completed"
    assert result2["final_stage"] == "panel"
    assert result2["contract_result"]["status"] == "completed"

    # No pending_suspensions when all children complete
    payload = result2["contract_result"]["payload"]
    pending = payload.get("pending_suspensions")
    assert pending is None or len(pending) == 0


# ── DC2 Scenario C: targeted resume with composite cursor round-trip ──


def test_targeted_resume_preserves_composite_cursor_in_contract_payload(
    tmp_path: Path,
) -> None:
    """Targeted resume preserves the child cursor in pending_suspensions.

    When one child completes and another stays suspended, the contract
    payload's pending_suspensions must still carry the suspended child's
    cursor so a subsequent batch resume can locate it.
    """
    panel = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "reviewer_a",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "reviewer_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "reviewer_b", "token": 42},
                    child_id="reviewer_b",
                    thread_ref="th-2",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result = megaplan_run_pipeline(
        Pipeline(stages={"review": panel}, entry="review"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "awaiting_user"

    # pending_suspensions carries the suspended child's cursor
    payload = result["contract_result"]["payload"]
    pending = payload.get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 1
    assert pending[0]["child_id"] == "reviewer_b"
    assert json.loads(pending[0]["cursor"]) == {"phase": "reviewer_b", "token": 42}

    # The state-resident composite cursor keys off pending_suspensions
    cursor = result["state"].get("resume_cursor")
    assert isinstance(cursor, dict)
    assert cursor["kind"] == "composite_suspension"
    assert cursor["children"] == {"reviewer_b": {"phase": "reviewer_b", "token": 42}}


# ── DC2 Scenario D: batch resume from composite with all children ──────


def test_batch_resume_from_composite_all_children_complete(tmp_path: Path) -> None:
    """Batch resume with three children: all complete → parent COMPLETED."""
    panel = ParallelStage(
        name="tribunal",
        steps=(
            _voted_step(
                "judge_a",
                recommendation="approve",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "judge_b",
                recommendation="approve",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "judge_c",
                recommendation="approve",
                contract=_contract(ContractStatus.COMPLETED),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="approve", target="halt", kind="decision"),),
    )

    result = megaplan_run_pipeline(
        Pipeline(stages={"tribunal": panel}, entry="tribunal"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "completed"
    assert result["final_stage"] == "tribunal"
    assert result["contract_result"]["status"] == "completed"

    # No suspension, no pending_suspensions
    payload = result["contract_result"]["payload"]
    assert "pending_suspensions" not in payload
    # No composite cursor on state (nothing to resume)
    assert result["state"].get("resume_cursor") is None


# ── T8: programmatic targeted/batch resume with resume_input_schema ──


def test_targeted_resume_with_resume_input_schema_fixture(tmp_path: Path) -> None:
    """Programmatic targeted resume: children carry resume_input_schema,
    one child completes while the other stays suspended. No human interaction."""

    # ── Phase 1: fan-out with resume_input_schema on each child ──────
    schema_a = {
        "type": "object",
        "properties": {
            "choice": {"type": "string", "enum": ["approve", "reject"]}
        },
        "required": ["choice"],
    }
    schema_b = {
        "type": "object",
        "properties": {
            "choice": {"type": "string", "enum": ["pass", "fail", "retry"]}
        },
        "required": ["choice"],
    }

    initial_panel = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "attempt": 1},
                    child_id="alpha",
                    resume_input_schema=schema_a,
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 2},
                    child_id="beta",
                    resume_input_schema=schema_b,
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result1 = megaplan_run_pipeline(
        Pipeline(stages={"review": initial_panel}, entry="review"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result1["status"] == "suspended"
    assert result1["halt_reason"] == "suspended"

    # The composite cursor records both children
    cursor1 = result1["state"].get("resume_cursor")
    assert isinstance(cursor1, dict)
    assert cursor1["kind"] == "composite_suspension"
    assert set(cursor1["children"].keys()) == {"alpha", "beta"}

    # pending_suspensions carries the serialized suspension with schema
    payload1 = result1["contract_result"]["payload"]
    pending1 = payload1.get("pending_suspensions")
    assert isinstance(pending1, list)
    assert len(pending1) == 2

    # Verify schemas survived in pending_suspensions
    for entry in pending1:
        susp = entry.get("suspension", {})
        schema = susp.get("resume_input_schema", {})
        choice_enum = schema.get("properties", {}).get("choice", {}).get("enum")
        assert isinstance(choice_enum, list)

    # ── Phase 2: targeted resume — alpha completes, beta stays ───────
    resume_panel = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 2},
                    child_id="beta",
                    resume_input_schema=schema_b,
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result2 = megaplan_run_pipeline(
        Pipeline(stages={"review": resume_panel}, entry="review"),
        _ctx(tmp_path, state=dict(result1["state"])),
        artifact_root=tmp_path,
    )

    # Targeted: alpha completed, beta still suspended → parent SUSPENDED
    assert result2["status"] == "suspended"
    assert result2["halt_reason"] == "awaiting_user"
    assert result2["contract_result"]["status"] == "suspended"

    # Only beta remains in composite cursor
    cursor2 = result2["state"].get("resume_cursor")
    assert isinstance(cursor2, dict)
    assert cursor2["kind"] == "composite_suspension"
    assert cursor2["children"] == {"beta": {"phase": "beta", "attempt": 2}}

    # pending_suspensions has only beta, and its schema is intact
    payload2 = result2["contract_result"]["payload"]
    pending2 = payload2.get("pending_suspensions")
    assert isinstance(pending2, list)
    assert len(pending2) == 1
    assert pending2[0]["child_id"] == "beta"
    susp_b = pending2[0].get("suspension", {})
    schema_b2 = susp_b.get("resume_input_schema", {})
    assert schema_b2.get("properties", {}).get("choice", {}).get("enum") == [
        "pass", "fail", "retry",
    ]


def test_batch_resume_with_resume_input_schema_fixture(tmp_path: Path) -> None:
    """Programmatic batch resume: all children carry resume_input_schema,
    both complete on resume → parent COMPLETED. No human interaction."""

    schema_shared = {
        "type": "object",
        "properties": {
            "choice": {"type": "string", "enum": ["approve", "reject", "escalate"]}
        },
        "required": ["choice"],
    }

    # ── Phase 1: fan-out with resume_input_schema ────────────────────
    initial_panel = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "attempt": 1},
                    child_id="alpha",
                    resume_input_schema=schema_shared,
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 1},
                    child_id="beta",
                    resume_input_schema=schema_shared,
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result1 = megaplan_run_pipeline(
        Pipeline(stages={"review": initial_panel}, entry="review"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result1["status"] == "suspended"
    assert result1["halt_reason"] == "suspended"

    # Verify schemas present in pending_suspensions
    payload1 = result1["contract_result"]["payload"]
    pending1 = payload1.get("pending_suspensions")
    assert isinstance(pending1, list)
    assert len(pending1) == 2
    for entry in pending1:
        susp = entry.get("suspension", {})
        schema = susp.get("resume_input_schema", {})
        assert schema.get("type") == "object"
        assert "choice" in schema.get("properties", {})

    # ── Phase 2: batch resume — both children complete ───────────────
    resume_panel = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result2 = megaplan_run_pipeline(
        Pipeline(stages={"review": resume_panel}, entry="review"),
        _ctx(tmp_path, state=dict(result1["state"])),
        artifact_root=tmp_path,
    )

    # Batch: both completed → parent COMPLETED
    assert result2["status"] == "completed"
    assert result2["final_stage"] == "review"
    assert result2["contract_result"]["status"] == "completed"

    # No pending_suspensions when all children complete
    payload2 = result2["contract_result"]["payload"]
    pending2 = payload2.get("pending_suspensions")
    assert pending2 is None or len(pending2) == 0
