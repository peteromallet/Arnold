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
from arnold.pipeline.resume import read_composite_resume_cursor
from arnold.pipeline.resume_validation import parse_resume_reverify_declaration
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.pattern_joins import majority_vote, weighted_vote
from arnold.pipelines.megaplan._pipeline.resume import (
    ResumeCursor,
    extract_all_composite_child_resume_cursors,
    extract_composite_child_resume_cursor,
    extract_composite_child_resume_target,
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
    resume_input_schema: dict[str, Any] | None = None,
) -> ContractResult:
    suspension = None
    if status is ContractStatus.SUSPENDED:
        suspension = Suspension(
            kind="human",
            awaitable=awaitable,
            prompt="Paused child",
            display_refs=display_refs,
            resume_input_schema=resume_input_schema or {},
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
    assert result["halt_reason"] == "awaiting_user"
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
    durable_composite = read_composite_resume_cursor(tmp_path)
    assert first["status"] == "failed"
    assert second["status"] == "failed"
    assert first["contract_result"]["payload"]["pending_suspensions"][0]["child_id"] == "paused"
    assert composite is not None
    assert durable_composite is not None
    assert durable_composite["pending_suspensions"] == composite["pending_suspensions"]
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


def test_composite_targeted_resume_recovers_only_selected_child_suspension(
    tmp_path: Path,
) -> None:
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "attempt": 1},
                    resume_input_schema={
                        "x-arnold-resume": {
                            "reverify_produces": {
                                "port": "alpha_out",
                                "artifact_path": "alpha.json",
                            }
                        }
                    },
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 2},
                    resume_input_schema={
                        "x-arnold-resume": {
                            "reverify_produces": {
                                "port": "beta_out",
                                "artifact_path": "beta.json",
                            }
                        }
                    },
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    target = extract_composite_child_resume_target(tmp_path, "beta")
    assert target is not None
    assert target.cursor == {"phase": "beta", "attempt": 2}
    parsed = parse_resume_reverify_declaration(target.suspension)
    assert parsed.outcome == "valid"
    assert parsed.declaration is not None
    assert parsed.declaration.port == "beta_out"
    assert parsed.declaration.artifact_path == "beta.json"
    assert target.composite_cursor["children"] == {
        "alpha": {"phase": "alpha", "attempt": 1},
        "beta": {"phase": "beta", "attempt": 2},
    }


def test_composite_targeted_resume_fails_closed_without_suspension_payload(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._pipeline.resume import save_composite_resume_cursor

    save_composite_resume_cursor(
        tmp_path,
        children={"alpha": {"phase": "alpha"}, "beta": {"phase": "beta"}},
        pending_suspensions=[
            {"child_id": "alpha", "cursor": {"phase": "alpha"}},
            {"child_id": "beta", "cursor": {"phase": "beta"}},
        ],
    )

    try:
        extract_composite_child_resume_target(tmp_path, "beta")
    except ValueError as exc:
        assert "missing serialized suspension" in str(exc)
    else:  # pragma: no cover - makes the fail-closed assertion explicit.
        raise AssertionError("missing suspension payload must fail closed")


# ── T2 regression: composite cursor phase + durable metadata forwarding ──

def test_composite_cursor_carries_phase_in_state_json(tmp_path: Path) -> None:
    """``state.json::resume_cursor`` includes the origin stage name as ``phase``."""
    panel = ParallelStage(
        name="review_panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "attempt": 1},
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "attempt": 2},
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result = run_pipeline(
        Pipeline(stages={"review_panel": panel}, entry="review_panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    cursor = result["state"]["resume_cursor"]
    assert cursor["kind"] == "composite_suspension"
    assert cursor["phase"] == "review_panel"
    # children remain unchanged
    assert cursor["children"] == {
        "alpha": {"phase": "alpha", "attempt": 1},
        "beta": {"phase": "beta", "attempt": 2},
    }


def test_composite_cursor_phase_lands_in_durable_file(tmp_path: Path) -> None:
    """``composite_resume_cursor.json`` carries ``phase`` from the executor."""
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "paused",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "paused", "attempt": 3},
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

    run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    durable = read_composite_resume_cursor(tmp_path)
    assert durable is not None
    assert durable["phase"] == "panel"
    assert durable["kind"] == "composite_suspension"
    assert "children" in durable
    assert "pending_suspensions" in durable


def test_composite_cursor_shared_keys_still_forwarded_to_durable_file(tmp_path: Path) -> None:
    """``shared_awaitable``, ``shared_thread_ref``, ``shared_actor`` survive in the durable file."""
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha"},
                    awaitable="user",
                    thread_ref="t-42",
                    actor="human",
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta"},
                    awaitable="user",
                    thread_ref="t-42",
                    actor="human",
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    durable = read_composite_resume_cursor(tmp_path)
    assert durable is not None
    assert durable["shared_awaitable"] == "user"
    assert durable["shared_thread_ref"] == "t-42"
    assert durable["shared_actor"] == "human"


def test_composite_cursor_does_not_mutate_child_payloads(tmp_path: Path) -> None:
    """Adding ``phase`` at the composite level must not touch child cursor payloads."""
    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "alpha",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "alpha", "extra": 99},
                ),
            ),
            _voted_step(
                "beta",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "beta", "extra": 77},
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

    cursor = result["state"]["resume_cursor"]
    assert cursor["phase"] == "panel"
    assert cursor["children"]["alpha"] == {"phase": "alpha", "extra": 99}
    assert cursor["children"]["beta"] == {"phase": "beta", "extra": 77}


def test_composite_cursor_forwards_pipeline_and_manifest_hash_when_present(
    tmp_path: Path,
) -> None:
    """When the composite cursor carries ``pipeline`` or ``pipeline_manifest_hash``,
    they are forwarded to the durable file."""
    from arnold.pipelines.megaplan._pipeline.resume import save_composite_resume_cursor

    save_composite_resume_cursor(
        tmp_path,
        children={"alpha": {"phase": "alpha"}},
        pending_suspensions=[
            {"child_id": "alpha", "cursor": {"phase": "alpha"},
             "suspension": {"kind": "human", "awaitable": "user", "prompt": "p",
                            "display_refs": [],
                            "resume_input_schema": {},
                            "resume_cursor": json.dumps({"phase": "alpha"})}}
        ],
        phase="my_stage",
        pipeline="ci/review",
        pipeline_manifest_hash="abc123",
    )

    durable = read_composite_resume_cursor(tmp_path)
    assert durable is not None
    assert durable["phase"] == "my_stage"
    assert durable["pipeline"] == "ci/review"
    assert durable["pipeline_manifest_hash"] == "abc123"


def test_composite_cursor_phase_absent_only_when_no_composite_suspension(
    tmp_path: Path,
) -> None:
    """A non-composite suspended step does not inject a ``phase`` key."""
    child = _StaticStep(
        name="simple_gate",
        result=StepResult(
            next="halt",
            contract_result=_contract(
                ContractStatus.SUSPENDED,
                cursor={"phase": "simple_gate", "retry_strategy": "fresh"},
            ),
        ),
    )
    pipeline = Pipeline(
        stages={"simple_gate": Stage(name="simple_gate", step=child)},
        entry="simple_gate",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    cursor = result["state"]["resume_cursor"]
    # Should be the child's cursor directly, not a composite envelope
    assert cursor == {"phase": "simple_gate", "retry_strategy": "fresh"}
    # No composite file should be written
    assert not (tmp_path / "composite_resume_cursor.json").exists()


# ── T8: regression — suspended child not reduced to completed at parent ──


def test_suspended_child_not_reduced_to_completed_at_parent(tmp_path: Path) -> None:
    """When one child is COMPLETED and another is SUSPENDED, the parent
    must stay SUSPENDED — never erroneously reduced to COMPLETED."""

    panel = ParallelStage(
        name="validate",
        steps=(
            _voted_step(
                "done",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "waiting",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "waiting", "token": 7},
                ),
            ),
        ),
        join=_megaplan_join(majority_vote(default_on_tie="halt")),
        edges=(Edge(label="proceed", target="halt", kind="decision"),),
    )

    result = run_pipeline(
        Pipeline(stages={"validate": panel}, entry="validate"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    # Parent contract status is SUSPENDED — NOT completed
    assert result["status"] == "suspended"
    assert result["contract_result"]["status"] == "suspended"
    assert result["halt_reason"] == "awaiting_user"

    # Only the suspended child appears in pending_suspensions
    payload = result["contract_result"]["payload"]
    pending = payload.get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 1
    assert pending[0]["child_id"] == "waiting"
    assert json.loads(pending[0]["cursor"]) == {"phase": "waiting", "token": 7}

    # The completed child must NOT appear in pending_suspensions
    child_ids = {e["child_id"] for e in pending}
    assert "done" not in child_ids


def test_completed_plus_two_suspended_parent_suspended_not_completed(
    tmp_path: Path,
) -> None:
    """Two suspended + one completed → parent SUSPENDED with both pending."""

    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "comp",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
            _voted_step(
                "sus_a",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "sus_a", "round": 1},
                ),
            ),
            _voted_step(
                "sus_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "sus_b", "round": 2},
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
    assert result["contract_result"]["status"] == "suspended"

    # pending_suspensions has exactly the two suspended children
    pending = result["contract_result"]["payload"].get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 2
    child_ids = {e["child_id"] for e in pending}
    assert child_ids == {"sus_a", "sus_b"}

    # Composite cursor records both suspended children, not the completed one
    cursor = result["state"].get("resume_cursor")
    assert isinstance(cursor, dict)
    assert cursor["kind"] == "composite_suspension"
    assert set(cursor["children"].keys()) == {"sus_a", "sus_b"}


# ── T8: regression — mixed failed+suspended pending_suspensions ──


def test_mixed_failed_plus_multiple_suspended_pending_suspensions_intact(
    tmp_path: Path,
) -> None:
    """When failed wins over multiple suspended children, pending_suspensions
    keeps every suspended child cursor — none lost, none reduced."""

    panel = ParallelStage(
        name="panel",
        steps=(
            _voted_step(
                "failed_child",
                recommendation="reject",
                reviewer_id="lead",
                contract=_contract(
                    ContractStatus.FAILED,
                    payload={"error": "denied"},
                ),
            ),
            _voted_step(
                "sus_a",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "sus_a", "token": 1},
                    awaitable="user",
                    thread_ref="thread-99",
                    actor="human",
                ),
            ),
            _voted_step(
                "sus_b",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "sus_b", "token": 2},
                    awaitable="user",
                    thread_ref="thread-99",
                    actor="human",
                ),
            ),
        ),
        join=_megaplan_join(weighted_vote(
            {"lead": 2.0, "peer": 1.0}, default_on_tie="halt",
        )),
        edges=(
            Edge(label="proceed", target="halt", kind="decision"),
            Edge(label="reject", target="halt", kind="decision"),
        ),
    )

    result = run_pipeline(
        Pipeline(stages={"panel": panel}, entry="panel"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    # Failed wins (max_wins lattice: failed > suspended > completed)
    assert result["status"] == "failed"
    assert result["contract_result"]["status"] == "failed"

    # Both suspended children still in pending_suspensions
    payload = result["contract_result"]["payload"]
    pending = payload.get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 2

    cursors = {e["child_id"]: json.loads(e["cursor"]) for e in pending}
    assert cursors["sus_a"] == {"phase": "sus_a", "token": 1}
    assert cursors["sus_b"] == {"phase": "sus_b", "token": 2}

    # Each pending entry has the serialized suspension
    for entry in pending:
        assert isinstance(entry.get("suspension"), dict)
        assert entry["suspension"]["kind"] == "human"
        assert entry["status"] == "suspended"

    # Composite cursor carries the shared metadata
    cursor = result["state"].get("resume_cursor")
    assert isinstance(cursor, dict)
    assert cursor["kind"] == "composite_suspension"
    assert cursor["shared_thread_ref"] == "thread-99"
    assert cursor["shared_actor"] == "human"


def test_mixed_failed_suspended_completed_pending_only_suspended(
    tmp_path: Path,
) -> None:
    """All three statuses present: failed wins, only suspended children
    appear in pending_suspensions — completed is excluded, failed is excluded."""

    panel = ParallelStage(
        name="triage",
        steps=(
            _voted_step(
                "failed",
                recommendation="reject",
                reviewer_id="lead",
                contract=_contract(ContractStatus.FAILED),
            ),
            _voted_step(
                "suspended",
                recommendation="proceed",
                contract=_contract(
                    ContractStatus.SUSPENDED,
                    cursor={"phase": "suspended", "attempt": 3},
                ),
            ),
            _voted_step(
                "completed",
                recommendation="proceed",
                contract=_contract(ContractStatus.COMPLETED),
            ),
        ),
        join=_megaplan_join(weighted_vote(
            {"lead": 2.0, "peer": 1.0}, default_on_tie="halt",
        )),
        edges=(
            Edge(label="proceed", target="halt", kind="decision"),
            Edge(label="reject", target="halt", kind="decision"),
        ),
    )

    result = run_pipeline(
        Pipeline(stages={"triage": panel}, entry="triage"),
        _ctx(tmp_path),
        artifact_root=tmp_path,
    )

    assert result["status"] == "failed"
    assert result["contract_result"]["status"] == "failed"

    pending = result["contract_result"]["payload"].get("pending_suspensions")
    assert isinstance(pending, list)
    assert len(pending) == 1
    assert pending[0]["child_id"] == "suspended"
    assert pending[0]["status"] == "suspended"
    assert json.loads(pending[0]["cursor"]) == {"phase": "suspended", "attempt": 3}
