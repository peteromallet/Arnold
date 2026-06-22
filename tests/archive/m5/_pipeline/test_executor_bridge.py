"""Focused executor bridge coverage for suspension-aware terminal paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import ContractResult, ContractStatus, Suspension
from arnold.pipeline.step_invocation import StepInvocation
from arnold.pipelines.megaplan._pipeline.envelope import RunEnvelope
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.runtime import RuntimePolicy, StallDetector
from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep
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
    calls: int = 0

    def run(self, ctx: StepContext) -> StepResult:
        self.calls += 1
        return self.result


@dataclass
class _LoopStep:
    name: str = "loop"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple = ()
    consumes: tuple = ()
    calls: int = 0

    def run(self, ctx: StepContext) -> StepResult:
        self.calls += 1
        return StepResult(next="again", state_patch={"calls": self.calls})


def _contract(
    status: ContractStatus,
    *,
    cursor: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> ContractResult:
    suspension = None
    if status is ContractStatus.SUSPENDED:
        suspension = Suspension(
            kind="human",
            awaitable="user",
            prompt="Paused child",
            resume_cursor=json.dumps(cursor or {"phase": "child"}),
        )
    return ContractResult(status=status, suspension=suspension, payload=payload or {})


def _ctx(tmp_path: Path) -> StepContext:
    return StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")


def _state_json(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))


def test_explicit_suspended_contract_returns_terminal_suspension_and_persists_resume_cursor(
    tmp_path: Path,
) -> None:
    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Need approval",
            resume_cursor=json.dumps({"phase": "review", "retry_strategy": "fresh"}),
        ),
    )
    step = _StaticStep(
        name="gate",
        result=StepResult(
            next="halt",
            state_patch={"stage_seen": True},
            contract_result=contract,
        ),
    )
    pipeline = Pipeline(stages={"gate": Stage(name="gate", step=step)}, entry="gate")

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "awaiting_user"
    assert result["contract_result"]["status"] == "suspended"
    assert result["state"]["contract_result"] == result["contract_result"]
    assert result["state"]["resume_cursor"] == {
        "phase": "review",
        "retry_strategy": "fresh",
    }
    assert _state_json(tmp_path)["contract_result"] == result["contract_result"]
    assert _state_json(tmp_path)["resume_cursor"] == {
        "phase": "review",
        "retry_strategy": "fresh",
    }


def test_suspended_contract_takes_precedence_over_next_proceed_and_skips_routing(
    tmp_path: Path,
) -> None:
    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Paused before proceeding",
            resume_cursor=json.dumps({"phase": "gate"}),
        ),
    )
    gate = _StaticStep(
        name="gate",
        result=StepResult(next="proceed", contract_result=contract),
    )
    downstream = _StaticStep(name="downstream", result=StepResult(next="halt"))
    pipeline = Pipeline(
        stages={
            "gate": Stage(
                name="gate",
                step=gate,
                edges=(Edge(label="proceed", target="downstream"),),
            ),
            "downstream": Stage(name="downstream", step=downstream),
        },
        entry="gate",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "gate"
    assert result["halt_reason"] == "awaiting_user"
    assert downstream.calls == 0


def test_agent_stage_invocation_is_materialized_on_runtime_step(tmp_path: Path) -> None:
    invocation = StepInvocation(kind="model", metadata={"message": "hello"})
    seen: list[StepInvocation | None] = []

    @dataclass
    class _InvocationAwareAgentStep(AgentStep):
        def run(self, ctx: StepContext) -> StepResult:
            seen.append(self._invocation)
            return StepResult(next="halt")

    step = _InvocationAwareAgentStep(name="draft")
    pipeline = Pipeline(
        stages={
            "draft": Stage(name="draft", step=step, invocation=invocation),
        },
        entry="draft",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "draft"
    assert seen == [invocation]
    assert step._invocation is None


def test_agent_model_invocation_surfaces_captured_contract_result(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    (pipeline_dir / "draft.md").write_text("Write the draft.", encoding="utf-8")

    class _HaltingAgentStep(AgentStep):
        def run(self, ctx: StepContext) -> StepResult:
            result = super().run(ctx)
            return StepResult(
                outputs=result.outputs,
                verdict=result.verdict,
                next="halt",
                state_patch=result.state_patch,
                contract_result=result.contract_result,
                envelope=result.envelope,
            )

    step = _HaltingAgentStep(
        name="draft",
        _prompt_ref="draft.md",
        _pipeline_dir=pipeline_dir,
        _pipeline_name="writer",
        _worker=lambda **kwargs: json.dumps({"output": kwargs["prompt"]}),
    )
    pipeline = Pipeline(
        stages={
            "draft": Stage(
                name="draft",
                step=step,
                invocation=StepInvocation.model(metadata={"worker": "codex"}),
            ),
        },
        entry="draft",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "draft"
    assert result["contract_result"] is not None
    payload = result["contract_result"]["payload"]
    assert payload["legacy_payload"] == {"output": "Write the draft."}
    assert payload["telemetry"]["terminal_status"] == "captured"
    assert (tmp_path / "draft" / "v1.md").read_text(encoding="utf-8") == json.dumps(
        {"output": "Write the draft."}
    )


def test_builder_derived_legacy_model_invocation_keeps_plain_worker_path(tmp_path: Path) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    (pipeline_dir / "draft.md").write_text("Write the draft.", encoding="utf-8")

    built = (
        Pipeline.builder("writer", pipeline_dir=pipeline_dir, worker=lambda **kwargs: "plain text output")
        .agent("draft", prompt="draft.md")
        .build()
    )
    draft = built.stages["draft"]
    assert isinstance(draft, Stage)
    pipeline = Pipeline(
        stages={
            "draft": Stage(
                name=draft.name,
                step=draft.step,
                edges=(Edge(label="done", target="finish"),),
                reads=draft.reads,
                writes=draft.writes,
                invocation=draft.invocation,
                required_capabilities=draft.required_capabilities,
            ),
            "finish": Stage(name="finish", step=_StaticStep(name="finish", result=StepResult(next="halt"))),
        },
        entry="draft",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "finish"
    assert result.get("contract_result") is None
    assert (tmp_path / "draft" / "v1.md").read_text(encoding="utf-8") == "plain text output"


@pytest.mark.parametrize(
    ("awaiting_payload", "expected_cursor", "expected_choices"),
    [
        (
            {
                "pipeline": "writer",
                "stage": "gate",
                "message": "Please choose",
                "artifact_path": "/tmp/output.md",
                "choices": ["proceed", "abort"],
            },
            {
                "phase": "gate",
                "retry_strategy": "awaiting_user",
                "kind": "awaiting_user",
                "choices": ["proceed", "abort"],
            },
            ["proceed", "abort"],
        ),
        (None, {"phase": "gate", "retry_strategy": "awaiting_user", "kind": "awaiting_user"}, []),
        ("malformed", {"phase": "gate", "retry_strategy": "awaiting_user", "kind": "awaiting_user"}, []),
    ],
)
def test_legacy_awaiting_user_bridge_handles_valid_missing_and_malformed_sidecars(
    tmp_path: Path,
    awaiting_payload: dict[str, Any] | str | None,
    expected_cursor: dict[str, Any],
    expected_choices: list[str],
) -> None:
    if isinstance(awaiting_payload, dict):
        (tmp_path / "awaiting_user.json").write_text(json.dumps(awaiting_payload), encoding="utf-8")
    elif awaiting_payload == "malformed":
        (tmp_path / "awaiting_user.json").write_text("{not-json", encoding="utf-8")

    step = _StaticStep(
        name="gate",
        result=StepResult(
            next="halt",
            state_patch={
                "_pipeline_paused": True,
                "_pipeline_paused_stage": "gate",
            },
        ),
    )
    pipeline = Pipeline(stages={"gate": Stage(name="gate", step=step)}, entry="gate")

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "suspended"
    assert result["halt_reason"] == "awaiting_user"
    assert result["contract_result"]["status"] == "suspended"
    assert result["contract_result"]["payload"]["source"] == "awaiting_user.json"
    assert result["contract_result"]["payload"]["awaiting_user"] == (
        awaiting_payload if isinstance(awaiting_payload, dict) else {}
    )
    assert result["state"]["contract_result"] == result["contract_result"]
    schema = result["contract_result"]["suspension"]["resume_input_schema"]
    assert schema["properties"]["choice"]["enum"] == expected_choices
    assert _state_json(tmp_path)["contract_result"] == result["contract_result"]
    assert result["state"]["resume_cursor"] == expected_cursor
    assert _state_json(tmp_path)["resume_cursor"] == expected_cursor


def test_failed_contract_surfaces_pending_suspensions_and_persists_composite_cursor(
    tmp_path: Path,
) -> None:
    pending = [
        {"child_id": "worker_a", "cursor": json.dumps({"phase": "execute", "attempt": 2})},
        {"child_id": "worker_b", "cursor": {"phase": "critique", "attempt": 1}},
    ]
    contract = ContractResult(
        status=ContractStatus.FAILED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="One child failed while others are suspended",
            thread_ref="thread-7",
            actor="human",
        ),
        payload={"pending_suspensions": pending, "winner": "failed"},
    )
    step = _StaticStep(
        name="fanout_join",
        result=StepResult(next="halt", contract_result=contract),
    )
    pipeline = Pipeline(
        stages={"fanout_join": Stage(name="fanout_join", step=step)},
        entry="fanout_join",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "failed"
    assert result["contract_result"]["payload"]["pending_suspensions"] == pending
    assert result["state"]["resume_cursor"] == {
        "kind": "composite_suspension",
        "version": 1,
        "phase": "fanout_join",
        "children": {
            "worker_a": {"phase": "execute", "attempt": 2},
            "worker_b": {"phase": "critique", "attempt": 1},
        },
        "pending_suspensions": pending,
        "shared_awaitable": "user",
        "shared_thread_ref": "thread-7",
        "shared_actor": "human",
    }


def test_parallel_join_omitted_contract_reduces_suspended_child_and_preserves_join_result(
    tmp_path: Path,
) -> None:
    child_a = _StaticStep(
        name="child_a",
        result=StepResult(
            next="halt",
            contract_result=_contract(
                ContractStatus.SUSPENDED,
                cursor={"phase": "child_a", "attempt": 3},
            ),
        ),
    )
    child_b = _StaticStep(
        name="child_b",
        result=StepResult(next="halt", contract_result=_contract(ContractStatus.COMPLETED)),
    )

    def join(results: list[StepResult], ctx: StepContext) -> StepResult:
        return StepResult(
            verdict=PipelineVerdict(score=0.8, recommendation="proceed"),
            next="proceed",
            state_patch={"joined": True},
        )

    pipeline = Pipeline(
        stages={
            "panel": ParallelStage(
                name="panel",
                steps=(child_a, child_b),
                join=join,
                edges=(Edge(label="proceed", target="downstream"),),
            ),
            "downstream": Stage(
                name="downstream",
                step=_StaticStep(name="downstream", result=StepResult(next="halt")),
            ),
        },
        entry="panel",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "panel"
    assert result["halt_reason"] == "awaiting_user"
    assert result["state"]["joined"] is True
    assert result["contract_result"]["status"] == "suspended"
    payload = result["contract_result"]["payload"]
    assert [source["child_id"] for source in payload["source_contracts"]] == [
        "child_a",
        "child_b",
    ]
    assert payload["pending_suspensions"][0]["child_id"] == "child_a"
    assert result["state"]["resume_cursor"]["children"]["child_a"] == {
        "phase": "child_a",
        "attempt": 3,
    }


def test_parallel_join_composes_suspension_before_governor_fold_and_preserves_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _StaticStep(
        name="child",
        result=StepResult(
            next="halt",
            contract_result=_contract(
                ContractStatus.SUSPENDED,
                cursor={"phase": "child", "attempt": 1},
            ),
        ),
    )
    joined_envelope = RunEnvelope(
        cost=2.5,
        lineage=("join",),
        lease_id="lease-1",
        fencing_token=7,
    )

    class _GovernorSpy:
        def __init__(self) -> None:
            self.seen: list[RunEnvelope] = []

        def charge(self, envelope: RunEnvelope) -> None:
            return None

        def fold_shard_spend(self, envelope: RunEnvelope) -> None:
            self.seen.append(envelope)

    governor = _GovernorSpy()
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.runtime.governor.current_governor",
        lambda: governor,
    )

    def join(results: list[StepResult], ctx: StepContext) -> StepResult:
        return StepResult(
            next="proceed",
            verdict=PipelineVerdict(score=0.9, recommendation="proceed"),
            envelope=joined_envelope,
        )

    pipeline = Pipeline(
        stages={
            "panel": ParallelStage(
                name="panel",
                steps=(child,),
                join=join,
                edges=(Edge(label="proceed", target="downstream"),),
            ),
            "downstream": Stage(
                name="downstream",
                step=_StaticStep(name="downstream", result=StepResult(next="halt")),
            ),
        },
        entry="panel",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "panel"
    assert result["halt_reason"] == "awaiting_user"
    assert joined_envelope in governor.seen
    assert governor.seen[-1] == joined_envelope
    assert result["envelope"] == joined_envelope


def test_parallel_join_keeps_explicit_completed_contract_when_all_children_completed(
    tmp_path: Path,
) -> None:
    child_a = _StaticStep(
        name="child_a",
        result=StepResult(next="halt", contract_result=_contract(ContractStatus.COMPLETED)),
    )
    child_b = _StaticStep(
        name="child_b",
        result=StepResult(next="halt", contract_result=_contract(ContractStatus.COMPLETED)),
    )
    join_contract = ContractResult(
        status=ContractStatus.COMPLETED,
        payload={"source": "custom_join", "summary": "all clear"},
    )

    def join(results: list[StepResult], ctx: StepContext) -> StepResult:
        return StepResult(next="halt", contract_result=join_contract)

    pipeline = Pipeline(
        stages={
            "panel": ParallelStage(name="panel", steps=(child_a, child_b), join=join),
        },
        entry="panel",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "completed"
    assert result["contract_result"]["payload"] == {
        "source": "custom_join",
        "summary": "all clear",
    }


def test_parallel_join_failed_child_reduces_and_retains_explicit_join_metadata(
    tmp_path: Path,
) -> None:
    child_a = _StaticStep(
        name="child_a",
        result=StepResult(
            next="halt",
            contract_result=_contract(
                ContractStatus.SUSPENDED,
                cursor={"phase": "child_a"},
                payload={"child_payload": "suspended"},
            ),
        ),
    )
    child_b = _StaticStep(
        name="child_b",
        result=StepResult(
            next="halt",
            contract_result=_contract(
                ContractStatus.FAILED,
                payload={"error": "child failed"},
            ),
        ),
    )
    join_contract = ContractResult(
        status=ContractStatus.COMPLETED,
        payload={"source": "custom_join", "aggregate": "metadata"},
    )

    def join(results: list[StepResult], ctx: StepContext) -> StepResult:
        return StepResult(
            next="halt",
            state_patch={"joined": "yes"},
            contract_result=join_contract,
        )

    pipeline = Pipeline(
        stages={
            "panel": ParallelStage(name="panel", steps=(child_a, child_b), join=join),
        },
        entry="panel",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["status"] == "failed"
    assert result["state"]["joined"] == "yes"
    payload = result["contract_result"]["payload"]
    assert payload["pending_suspensions"][0]["child_id"] == "child_a"
    assert [source["child_id"] for source in payload["source_contracts"]] == [
        "child_a",
        "child_b",
    ]
    assert payload["executor_composition"]["source"] == "_run_parallel_stage.post_join"
    assert payload["executor_composition"]["join_payload"] == {
        "source": "custom_join",
        "aggregate": "metadata",
    }
    assert payload["executor_composition"]["join_contract"]["status"] == "completed"


def test_terminal_exit_max_iterations(tmp_path: Path) -> None:
    step = _LoopStep()
    pipeline = Pipeline(
        stages={
            "loop": Stage(name="loop", step=step, edges=(Edge(label="again", target="loop"),)),
        },
        entry="loop",
    )
    policy = RuntimePolicy(max_iterations=1)

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path, policy=policy)

    assert result["halt_reason"] == "max_iterations"
    assert step.calls == 1


def test_terminal_exit_stalled(tmp_path: Path) -> None:
    step = _StaticStep(name="steady", result=StepResult(next="again"))
    pipeline = Pipeline(
        stages={
            "steady": Stage(name="steady", step=step, edges=(Edge(label="again", target="steady"),)),
        },
        entry="steady",
    )
    policy = RuntimePolicy(stall=StallDetector(threshold=1))

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path, policy=policy)

    assert result["halt_reason"] == "stalled"
    assert step.calls == 1


def test_terminal_exit_cost_cap(tmp_path: Path) -> None:
    step = _StaticStep(
        name="expensive",
        result=StepResult(next="again", state_patch={"meta": {"total_cost_usd": 12.5}}),
    )
    pipeline = Pipeline(
        stages={
            "expensive": Stage(
                name="expensive",
                step=step,
                edges=(Edge(label="again", target="expensive"),),
            ),
        },
        entry="expensive",
    )
    policy = RuntimePolicy()
    policy.cost.cap_usd = 5.0

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path, policy=policy)

    assert result["halt_reason"] == "cost_cap"
    assert step.calls == 1


def test_terminal_exit_explicit_halt(tmp_path: Path) -> None:
    step = _StaticStep(name="done", result=StepResult(next="halt"))
    pipeline = Pipeline(stages={"done": Stage(name="done", step=step)}, entry="done")

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "done"
    assert result.get("halt_reason") is None


def test_terminal_exit_loop_condition(tmp_path: Path) -> None:
    step = _StaticStep(name="loop", result=StepResult(next="again"))
    downstream = _StaticStep(name="downstream", result=StepResult(next="halt"))
    pipeline = Pipeline(
        stages={
            "loop": Stage(
                name="loop",
                step=step,
                edges=(Edge(label="again", target="downstream"),),
                loop_condition=lambda _: True,
            ),
            "downstream": Stage(name="downstream", step=downstream),
        },
        entry="loop",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["halt_reason"] == "loop_condition"
    assert downstream.calls == 0


def test_terminal_exit_resolve_edge_halt_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    step = _StaticStep(name="gate", result=StepResult(next="proceed"))
    downstream = _StaticStep(name="downstream", result=StepResult(next="halt"))
    pipeline = Pipeline(
        stages={
            "gate": Stage(
                name="gate",
                step=step,
                edges=(Edge(label="proceed", target="downstream"),),
            ),
            "downstream": Stage(name="downstream", step=downstream),
        },
        entry="gate",
    )

    monkeypatch.setattr("arnold.pipeline.routing.resolve_edge", lambda **_: None)

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "gate"
    assert result.get("halt_reason") is None
    assert downstream.calls == 0


def test_terminal_exit_halt_target_edge(tmp_path: Path) -> None:
    step = _StaticStep(name="gate", result=StepResult(next="stop"))
    downstream = _StaticStep(name="downstream", result=StepResult(next="halt"))
    pipeline = Pipeline(
        stages={
            "gate": Stage(
                name="gate",
                step=step,
                edges=(Edge(label="stop", target="halt"),),
            ),
            "downstream": Stage(name="downstream", step=downstream),
        },
        entry="gate",
    )

    result = run_pipeline(pipeline, _ctx(tmp_path), artifact_root=tmp_path)

    assert result["final_stage"] == "gate"
    assert result.get("halt_reason") is None
    assert downstream.calls == 0
