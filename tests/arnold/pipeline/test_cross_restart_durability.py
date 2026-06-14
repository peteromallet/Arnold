"""DC1 — Cross-restart durability: composite_resume_cursor.json survives state loss.

Verifies that a composite suspension writes ``composite_resume_cursor.json``
independently of ``state.json::resume_cursor``, so a restart that loses in-memory
state can still recover the fan-out cursor from the artifact root.

Phase A — suspend in tmp_path, assert both cursor stores exist.
Phase B — delete ``state['resume_cursor']`` (simulating state loss), reload
          via ``read_composite_resume_cursor(tmp_path)`` (generic layer, no
          plan_dir), reconstruct minimal state, and resume to COMPLETED.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.pipeline import (
    ContractResult,
    ContractStatus,
    Suspension,
)
from arnold.pipeline.resume import read_composite_resume_cursor
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


# ── helpers ────────────────────────────────────────────────────────────────


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
    awaitable: str | None = "user",
    thread_ref: str | None = None,
    actor: str | None = None,
    child_id: str | None = None,
    resume_input_schema: dict[str, Any] | None = None,
) -> ContractResult:
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
    return ContractResult(status=status, suspension=suspension, payload={})


def _voted_step(
    name: str,
    *,
    recommendation: str,
    contract: ContractResult,
) -> _StaticStep:
    return _StaticStep(
        name=name,
        result=StepResult(
            verdict=PipelineVerdict(score=1.0, recommendation=recommendation, payload={}),
            next="halt",
            contract_result=contract,
        ),
    )


def _megaplan_join(join_fn):
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


# ── DC1: cross-restart durability ──────────────────────────────────────────


def test_cross_restart_composite_cursor_survives_state_loss(tmp_path: Path) -> None:
    """Phase A suspends two children; Phase B deletes state-resident cursor,
    reloads from composite_resume_cursor.json, and resumes to COMPLETED."""

    # ── Phase A: initial fan-out → both children SUSPENDED ─────────────────
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

    result_a = megaplan_run_pipeline(
        Pipeline(stages={"panel": initial_panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result_a["status"] == "suspended"
    assert result_a["halt_reason"] == "suspended"

    # Both cursor stores exist
    state_a = result_a["state"]
    cursor_in_state = state_a.get("resume_cursor")
    assert isinstance(cursor_in_state, dict)
    assert cursor_in_state["kind"] == "composite_suspension"
    assert set(cursor_in_state["children"].keys()) == {"alpha", "beta"}

    # composite_resume_cursor.json is durable on disk (generic layer)
    disk_cursor = read_composite_resume_cursor(tmp_path)
    assert isinstance(disk_cursor, dict)
    assert disk_cursor["kind"] == "composite_suspension"
    assert disk_cursor["children"] == cursor_in_state["children"]

    # ── Phase B: simulate cross-restart state loss ─────────────────────────
    # Delete the state-resident cursor (mimics state.json losing resume_cursor)
    del state_a["resume_cursor"]
    assert "resume_cursor" not in state_a

    # Reload exclusively from the durable composite file (no plan_dir)
    reloaded = read_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["kind"] == "composite_suspension"
    assert set(reloaded["children"].keys()) == {"alpha", "beta"}

    # Reconstruct state: inject the durable cursor back
    state_b = dict(state_a)
    state_b["resume_cursor"] = reloaded

    # ── Phase B resume: both children complete → parent COMPLETED ──────────
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

    result_b = megaplan_run_pipeline(
        Pipeline(stages={"panel": resume_panel}, entry="panel"),
        _ctx(tmp_path, state=state_b),
        artifact_root=tmp_path,
    )

    assert result_b["status"] == "completed"
    assert result_b["final_stage"] == "panel"
    assert result_b["contract_result"]["status"] == "completed"


def test_cross_restart_no_composite_file_when_no_suspension(tmp_path: Path) -> None:
    """When all children COMPLETE, composite_resume_cursor.json is NOT written,
    and read_composite_resume_cursor returns None."""

    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "a",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "b",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
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

    assert result["status"] == "completed"

    # No composite file when no suspension
    disk = read_composite_resume_cursor(tmp_path)
    assert disk is None


def test_cross_restart_targeted_resume_after_state_loss(tmp_path: Path) -> None:
    """Phase A: 2 children SUSPENDED. Phase B: delete state cursor, reload
    from disk, resume only alpha. Parent stays SUSPENDED with beta preserved."""

    # ── Phase A ────────────────────────────────────────────────────────────
    panel_a = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "rev_a",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "rev_a", "round": 1},
                    child_id="rev_a",
                ),
            ),
            _voted_step(
                "rev_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "rev_b", "round": 1},
                    child_id="rev_b",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result_a = megaplan_run_pipeline(
        Pipeline(stages={"review": panel_a}, entry="review"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result_a["status"] == "suspended"

    # ── Phase B: state loss + reload from disk ─────────────────────────────
    state_a = dict(result_a["state"])
    del state_a["resume_cursor"]
    assert "resume_cursor" not in state_a

    reloaded = read_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["children"] == {
        "rev_a": {"phase": "rev_a", "round": 1},
        "rev_b": {"phase": "rev_b", "round": 1},
    }

    state_b = dict(state_a)
    state_b["resume_cursor"] = reloaded

    # ── Targeted resume: only rev_a completes ──────────────────────────────
    panel_b = ParallelStage(
        name="review",
        steps=(
            _voted_step(
                "rev_a",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "rev_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "rev_b", "round": 1},
                    child_id="rev_b",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result_b = megaplan_run_pipeline(
        Pipeline(stages={"review": panel_b}, entry="review"),
        _ctx(tmp_path, state=state_b),
        artifact_root=tmp_path,
    )

    # Targeted: one done, one still suspended → parent SUSPENDED
    assert result_b["status"] == "suspended"
    assert result_b["halt_reason"] == "awaiting_user"

    # The remaining child's cursor is preserved in composite payload
    cursor_b = result_b["state"].get("resume_cursor")
    assert isinstance(cursor_b, dict)
    assert cursor_b["children"] == {"rev_b": {"phase": "rev_b", "round": 1}}


# ── DC1 extension: disk-only reload → programmatic resume with schema ──


def test_cross_restart_disk_only_reload_with_resume_input_schema(
    tmp_path: Path,
) -> None:
    """Phase A: fan-out with resume_input_schema fixtures → composite cursor on disk.
    Phase B: delete state cursor, reload from composite_resume_cursor.json alone,
    extract a child's resume target including its resume_input_schema, and prove
    the schema is intact for programmatic resume without human interaction."""

    # ── Phase A: suspended children carry resume_input_schema ───────────────
    panel_a = ParallelStage(
        name="verify",
        steps=(
            _voted_step(
                "check_a",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "check_a", "attempt": 1},
                    child_id="check_a",
                    resume_input_schema={
                        "type": "object",
                        "properties": {
                            "choice": {
                                "type": "string",
                                "enum": ["approve", "reject"],
                            }
                        },
                        "required": ["choice"],
                    },
                ),
            ),
            _voted_step(
                "check_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "check_b", "attempt": 2},
                    child_id="check_b",
                    resume_input_schema={
                        "type": "object",
                        "properties": {
                            "choice": {
                                "type": "string",
                                "enum": ["pass", "fail"],
                            }
                        },
                        "required": ["choice"],
                    },
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result_a = megaplan_run_pipeline(
        Pipeline(stages={"verify": panel_a}, entry="verify"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result_a["status"] == "suspended"

    # ── Phase B: simulate state loss, reload from disk only ────────────────
    state_a = dict(result_a["state"])
    del state_a["resume_cursor"]
    assert "resume_cursor" not in state_a

    # Generic layer: no plan_dir, reads composite_resume_cursor.json directly
    reloaded = read_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["kind"] == "composite_suspension"
    assert set(reloaded["children"].keys()) == {"check_a", "check_b"}

    # pending_suspensions carries the serialized Suspension with schema
    pending = reloaded.get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 2

    # Verify check_a's suspension carries the resume_input_schema enum intact
    check_a_susp = next(
        (p["suspension"] for p in pending if p.get("child_id") == "check_a"), None
    )
    assert check_a_susp is not None
    schema_a = check_a_susp.get("resume_input_schema", {})
    choice_enum = schema_a.get("properties", {}).get("choice", {}).get("enum")
    assert choice_enum == ["approve", "reject"]

    # Verify check_b's schema similarly survives
    check_b_susp = next(
        (p["suspension"] for p in pending if p.get("child_id") == "check_b"), None
    )
    assert check_b_susp is not None
    schema_b = check_b_susp.get("resume_input_schema", {})
    choice_enum_b = schema_b.get("properties", {}).get("choice", {}).get("enum")
    assert choice_enum_b == ["pass", "fail"]

    # Reconstruct state and run targeted resume programmatically (no human)
    state_b = dict(state_a)
    state_b["resume_cursor"] = reloaded

    # Targeted: only check_a completes; check_b stays suspended
    panel_b = ParallelStage(
        name="verify",
        steps=(
            _voted_step(
                "check_a",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "check_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "check_b", "attempt": 2},
                    child_id="check_b",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result_b = megaplan_run_pipeline(
        Pipeline(stages={"verify": panel_b}, entry="verify"),
        _ctx(tmp_path, state=state_b),
        artifact_root=tmp_path,
    )

    # Targeted resume: parent stays SUSPENDED (check_b still suspended)
    assert result_b["status"] == "suspended"
    assert result_b["halt_reason"] == "awaiting_user"
    cursor_b = result_b["state"].get("resume_cursor")
    assert isinstance(cursor_b, dict)
    assert cursor_b["children"] == {"check_b": {"phase": "check_b", "attempt": 2}}
