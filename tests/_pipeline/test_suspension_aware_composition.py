"""End-to-end regression coverage for suspension-aware composition."""

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
)
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipelines.megaplan._pipeline.resume import (
    ResumeCursor,
    extract_all_composite_child_resume_cursors,
    extract_composite_child_resume_cursor,
    load_composite_resume_cursor,
    with_entry,
)
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


@dataclass
class _StaticStep:
    name: str
    result: StepResult
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple = ()
    consumes: tuple = ()

    def run(self, ctx: StepContext) -> StepResult:
        return self.result


def _ctx(plan_dir: Path, *, state: dict[str, Any] | None = None) -> StepContext:
    return StepContext(plan_dir=plan_dir, state=state or {}, profile=None, mode="test")


def _state_json(plan_dir: Path) -> dict[str, Any]:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def _contract(
    status: ContractStatus,
    *,
    cursor: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    awaitable: str | None = "user",
    thread_ref: str | None = None,
    actor: str | None = None,
    display_refs: tuple[EvidenceArtifactRef, ...] = (),
) -> ContractResult:
    suspension = None
    if status is ContractStatus.SUSPENDED:
        suspension = Suspension(
            kind="human",
            awaitable=awaitable,
            prompt="Paused child",
            display_refs=display_refs,
            resume_cursor=json.dumps(cursor or {"phase": "child"}),
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


def test_subloop_suspended_child_lifts_to_parent_and_persists_resume_cursor(tmp_path: Path) -> None:
    child = _StaticStep(
        name="child_gate",
        result=StepResult(
            next="halt",
            state_patch={"score": 0.72, "leaf": "paused"},
            contract_result=_contract(
                ContractStatus.SUSPENDED,
                cursor={"phase": "child_gate", "retry_strategy": "fresh"},
            ),
        ),
    )
    child_pipeline = Pipeline(
        stages={"child_gate": Stage(name="child_gate", step=child)},
        entry="child_gate",
    )
    parent = SubloopStep(name="review", child_pipeline=child_pipeline)
    pipeline = Pipeline(stages={"review": Stage(name="review", step=parent)}, entry="review")

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "suspended"
    assert result["final_stage"] == "review"
    assert result["contract_result"]["status"] == "suspended"
    assert result["state"]["subloop:review:resume_cursor"] == json.dumps(
        {"phase": "child_gate", "retry_strategy": "fresh"}
    )
    assert result["state"]["resume_cursor"] == {
        "phase": "child_gate",
        "retry_strategy": "fresh",
    }
    assert _state_json(tmp_path)["resume_cursor"] == {
        "phase": "child_gate",
        "retry_strategy": "fresh",
    }


def test_majority_vote_completed_plus_suspended_becomes_parent_suspension(tmp_path: Path) -> None:
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

    result = run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "suspended"
    assert result["contract_result"]["status"] == "suspended"
    assert result["state"]["resume_cursor"] == {
        "kind": "composite_suspension",
        "version": 1,
        "children": {"paused": {"phase": "paused", "attempt": 2}},
        "pending_suspensions": result["contract_result"]["payload"]["pending_suspensions"],
        "shared_awaitable": "user",
    }


def test_weighted_vote_failed_status_max_wins_over_completed_children(tmp_path: Path) -> None:
    panel = ParallelStage(
        name="weighted_panel",
        steps=(
            _voted_step(
                "failed",
                recommendation="approve",
                reviewer_id="lead",
                contract=_contract(
                    ContractStatus.FAILED,
                    payload={"error": "blocked"},
                ),
            ),
            _voted_step(
                "completed",
                recommendation="approve",
                reviewer_id="peer",
                contract=_contract(ContractStatus.COMPLETED),
            ),
        ),
        join=_megaplan_join(weighted_vote({"lead": 2.0, "peer": 1.0}, default_on_tie="halt")),
        edges=(Edge(label="approve", target="halt", kind="decision"),),
    )

    result = run_pipeline(
        Pipeline(stages={"weighted_panel": panel}, entry="weighted_panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "failed"
    assert result["final_stage"] == "weighted_panel"
    assert result["contract_result"]["status"] == "failed"
    assert "pending_suspensions" not in result["contract_result"]["payload"]


def test_majority_vote_multiple_suspended_children_emit_composite_m0a_fields(tmp_path: Path) -> None:
    shared_ref = EvidenceArtifactRef(
        uri="artifact://approval.md",
        content_type="text/markdown",
        name="approval.md",
    )
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "token": 1},
                    awaitable="user",
                    thread_ref="thread-9",
                    actor="human",
                    display_refs=(shared_ref,),
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "token": 2},
                    awaitable="user",
                    thread_ref="thread-9",
                    actor="human",
                    display_refs=(shared_ref,),
                ),
            ),
            _voted_step(
                "done",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result = run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    suspension = result["contract_result"]["suspension"]
    assert result["status"] == "suspended"
    assert suspension["kind"] == "composite_suspension"
    assert suspension["awaitable"] == "user"
    assert suspension["thread_ref"] == "thread-9"
    assert suspension["actor"] == "human"
    assert len(suspension["display_refs"]) == 1
    assert suspension["display_refs"][0]["uri"] == "artifact://approval.md"
    assert sorted(result["state"]["resume_cursor"]["children"]) == ["alpha", "beta"]


def test_failed_plus_suspended_resume_helpers_survive_reload_and_targeted_resume(
    tmp_path: Path,
) -> None:
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "failed",
                recommendation="proceed",
                reviewer_id="lead",
                contract=_contract(
                    ContractStatus.FAILED,
                    payload={"error": "max wins"},
                ),
            ),
            _voted_step(
                "paused",
                recommendation="proceed",
                reviewer_id="peer",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "paused", "attempt": 4},
                    awaitable="user",
                    thread_ref="thread-12",
                    actor="human",
                ),
            ),
        ),
        join=_megaplan_join(weighted_vote({"lead": 2.0, "peer": 1.0}, default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )
    pipeline = Pipeline(stages={"panel": panel}, entry="panel")

    first = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)
    reloaded_state = _state_json(tmp_path)
    resumed = with_entry(pipeline, "panel")
    second = run_pipeline(
        resumed,
        _ctx(tmp_path, state=reloaded_state),
        artifact_root=tmp_path,
    )

    composite = load_composite_resume_cursor(tmp_path)
    assert first["status"] == "failed"
    assert second["status"] == "failed"
    assert first["contract_result"]["payload"]["pending_suspensions"][0]["child_id"] == "paused"
    assert composite is not None
    assert composite["shared_awaitable"] == "user"
    assert composite["shared_thread_ref"] == "thread-12"
    assert composite["shared_actor"] == "human"
    assert extract_composite_child_resume_cursor(tmp_path, "paused") == {
        "phase": "paused",
        "attempt": 4,
    }
    assert extract_all_composite_child_resume_cursors(tmp_path) == {
        "paused": {"phase": "paused", "attempt": 4},
    }
    assert ResumeCursor.load(tmp_path) is None
