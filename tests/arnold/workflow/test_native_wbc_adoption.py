from __future__ import annotations

import json
from pathlib import Path
import subprocess

from arnold.execution import ExecutionRegistries
from arnold.execution.backend import LocalJournalBackend, NodeOutcome, NodeState, SkeletalBackend
from arnold.execution.driver import PipelineStepwiseDriver
from arnold.execution.runner import run as run_execution
from arnold.execution.state_store import FileStateStore
from arnold.manifest import EffectRef, IdempotencyPolicy, WorkflowManifest, WorkflowNode, WorkflowPolicy
from arnold.pipeline.driver import StepwiseDriver as NeutralStepwiseDriver
from arnold.pipeline.executor import run_pipeline_resume
from arnold.pipeline.runner import run_pipeline
from arnold.pipeline.steps.human_gate import HumanGateStep
from arnold.pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import ResumeCursorRef
from arnold.supervisor.reconcile import reconcile_worktree_for_takeover
from arnold.workflow.native_wbc import native_wbc_dir


class _HaltStep:
    name = "work"
    kind = "task"

    def run(self, ctx: StepContext) -> StepResult:
        del ctx
        return StepResult(outputs={"done": True}, next="halt")


class _RecordingEffectHandler:
    def execute(self, effect_id: str, *, route: str, payload, idempotency_key: str, context):
        return {
            "effect_id": effect_id,
            "route": route,
            "idempotency_key": idempotency_key,
            "context_run_id": context.get("run_id"),
            "coordinate": payload.get("coordinate"),
        }


class _SuspendingBackend(LocalJournalBackend):
    def __init__(self, *, suspend_on_ask: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self._suspend_on_ask = suspend_on_ask

    def _execute_node_payload(self, coordinate, node, context):
        del context
        if node.id == "ask" and self._suspend_on_ask:
            return NodeOutcome(state=NodeState.SUSPENDED, suspension_route_id="operator")
        return NodeOutcome(state=NodeState.COMPLETED, outputs={"node": coordinate.node_ref})


def _records(root: Path, producer_family: str, surface: str) -> list[dict[str, object]]:
    path = native_wbc_dir(root, producer_family=producer_family, surface=surface) / "events.ndjson"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _envelope(root: Path, *, run_id: str = "run-1") -> RuntimeEnvelope:
    return RuntimeEnvelope(
        plugin_id="plugin.demo",
        manifest_hash="sha256:demo",
        run_id=run_id,
        artifact_root=str(root),
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(("git", "init", "-b", "main"), cwd=path, check=True, stdout=subprocess.PIPE)
    subprocess.run(("git", "config", "user.email", "agentbox@example.test"), cwd=path, check=True)
    subprocess.run(("git", "config", "user.name", "AgentBox Tests"), cwd=path, check=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(("git", "add", "README.md"), cwd=path, check=True)
    subprocess.run(("git", "commit", "-m", "initial"), cwd=path, check=True, stdout=subprocess.PIPE)
    return path


def test_execution_runner_and_drivers_emit_native_wbc(tmp_path: Path) -> None:
    execution_root = tmp_path / "execution"
    manifest = WorkflowManifest(
        id="demo",
        nodes=(WorkflowNode(id="start", kind="noop"),),
    )
    result = run_execution(
        manifest,
        artifact_root=execution_root,
        backend=SkeletalBackend(),
    )
    assert result.state.value == "completed"

    pipeline = Pipeline(
        stages={
            "work": Stage(
                name="work",
                step=_HaltStep(),
                edges=(Edge(label="halt", target="halt"),),
            )
        },
        entry="work",
    )
    driver_root = tmp_path / "drivers"
    envelope = _envelope(driver_root)
    driver = PipelineStepwiseDriver(pipeline)
    advance = driver.advance(envelope)
    checkpoint = driver.checkpoint(envelope)
    cursor = ResumeCursorRef(
        plugin_id="plugin.demo",
        run_id="run-1",
        cursor={"stage": "work", "state": {"resume": True}, "iteration": 2},
    )
    resumed = driver.resume(envelope, cursor)
    neutral = NeutralStepwiseDriver()
    neutral.advance(envelope)
    neutral.checkpoint(envelope)
    neutral.resume(envelope, cursor)

    assert advance.kind == "halted"
    assert checkpoint.kind == "advanced"
    assert resumed.resume_cursor == cursor
    assert resumed.artifact_root == envelope.artifact_root

    runner_events = _records(execution_root, "arnold_execution", "runner")
    assert [event["event"] for event in runner_events] == ["started", "effect", "terminal"]
    assert runner_events[-1]["payload"]["status"] == "completed"
    assert runner_events[-1]["ownership"]["wbc_controls_topology"] is False

    assert _records(driver_root, "arnold_execution", "stepwise_driver.advance")[-1]["payload"][
        "outcome"
    ] == "halted"
    assert _records(driver_root, "arnold_execution", "stepwise_driver.checkpoint")[-1]["payload"][
        "outcome"
    ] == "advanced"
    assert _records(driver_root, "arnold_execution", "stepwise_driver.resume")[-1]["payload"][
        "outcome"
    ] == "resumed"
    assert _records(driver_root, "arnold_pipeline", "driver.advance")[-1]["payload"]["outcome"] == "advanced"
    assert _records(driver_root, "arnold_pipeline", "driver.resume")[-1]["payload"]["outcome"] == "resumed"


def test_execution_backend_state_store_resume_and_effects_emit_native_wbc(tmp_path: Path) -> None:
    effect_root = tmp_path / "backend-effects"
    effect_store = FileStateStore(tmp_path / "backend-checkpoints")
    effect_manifest = WorkflowManifest(
        id="effect-demo",
        nodes=(
            WorkflowNode(
                id="fx",
                kind="task",
                policy=WorkflowPolicy(
                    effects=(
                        EffectRef(
                            effect_id="fx.write",
                            idempotency=IdempotencyPolicy(key_ref="fx-write"),
                        ),
                    )
                ),
            ),
        ),
    )
    effect_backend = LocalJournalBackend(state_store=effect_store)
    result = effect_backend.run_manifest(
        effect_manifest,
        artifact_root=effect_root,
        registries=ExecutionRegistries(effects={"fx.write": _RecordingEffectHandler()}),
    )

    assert result.state.value == "completed"

    backend_events = _records(effect_root, "arnold_execution", "backend.run_manifest")
    assert "effect_intent" in [event["event"] for event in backend_events]
    effect_outcomes = [event for event in backend_events if event["event"] == "effect_outcome"]
    assert any(event["payload"]["status"] == "fulfilled" for event in effect_outcomes)
    assert all(event["authority"]["grants_authority"] is False for event in backend_events)
    assert all(event["authority"]["leases_authority"] is False for event in backend_events)

    store_events = _records(tmp_path / "backend-checkpoints", "arnold_execution", "state_store")
    assert "effect_outcome" in [event["event"] for event in store_events]

    resume_manifest = WorkflowManifest(
        id="resume-demo",
        nodes=(WorkflowNode(id="ask", kind="human"), WorkflowNode(id="after", kind="noop")),
    )
    resume_root = tmp_path / "backend-resume"
    suspended_backend = _SuspendingBackend(suspend_on_ask=True)
    suspended = suspended_backend.run_manifest(
        resume_manifest,
        artifact_root=resume_root,
        registries=ExecutionRegistries(),
    )
    assert suspended.state is not None
    assert suspended.resume_cursor is not None

    resumed_backend = _SuspendingBackend(
        suspend_on_ask=False,
        run_id=suspended_backend._run_id,
    )
    resumed = resumed_backend.run_manifest(
        resume_manifest,
        artifact_root=resume_root,
        registries=ExecutionRegistries(),
        resume_cursor=suspended.resume_cursor,
    )

    assert resumed.state.value == "completed"
    resume_events = _records(resume_root, "arnold_execution", "backend.run_manifest")
    resume_payloads = [event["payload"] for event in resume_events if event["event"] == "resume"]
    assert any(payload["name"] == "node_resumed" for payload in resume_payloads)


def test_pipeline_runner_runtime_hooks_and_resume_emit_native_wbc(tmp_path: Path) -> None:
    artifact_root = tmp_path / "native"

    def human_gate(ctx):
        raise AssertionError("human gate decision body should not execute")

    human_gate.__decision_human_gate__ = True
    human_gate.__decision_artifact_stage__ = "review"
    human_gate.__decision_choices__ = ("continue", "stop")
    human_gate.__decision_name__ = "human_review"

    program = NativeProgram(
        name="native-demo",
        instructions=(
            NativeInstruction(
                pc=0,
                op="decision",
                name="human_review",
                func=human_gate,
                branches={"continue": 1, "stop": 1},
            ),
            NativeInstruction(pc=1, op="halt", name="halt"),
        ),
    )
    pipeline = Pipeline(stages={}, entry="native", native_program=program)
    envelope = _envelope(artifact_root, run_id="native-run")

    suspended = run_pipeline(pipeline, {}, envelope)
    resumed = run_pipeline_resume(
        pipeline,
        {},
        envelope,
        human_input={"choice": "continue"},
    )

    assert suspended.suspended is True
    assert resumed.suspended is False

    runner_events = _records(artifact_root, "arnold_pipeline", "runner")
    assert runner_events[-1]["payload"]["status"] == "completed"

    dispatch_events = _records(artifact_root, "arnold_pipeline", "executor.native_dispatch")
    dispatch_statuses = [event["payload"].get("status") for event in dispatch_events if event["event"] == "terminal"]
    assert dispatch_statuses == ["completed", "completed"]

    resume_events = _records(artifact_root, "arnold_pipeline", "executor.resume")
    assert resume_events[-1]["payload"]["outcome"] == "native_resume"

    runtime_events = _records(artifact_root, "arnold_native", "runtime")
    runtime_effects = [
        event["payload"]["name"]
        for event in runtime_events
        if event["event"] == "effect"
    ]
    assert "human_gate_checkpoint_written" in runtime_effects
    assert "resume_cursor_restored" in runtime_effects
    assert "human_gate_resume_selected" in runtime_effects
    assert runtime_events[-1]["payload"]["status"] == "completed"

    hook_events = _records(artifact_root, "arnold_native", "hooks")
    hook_effects = [event["payload"]["name"] for event in hook_events if event["event"] == "effect"]
    assert "on_checkpoint" in hook_effects
    assert hook_events[-1]["payload"]["status"] == "completed"


def test_human_gate_step_emits_pause_and_resume_wbc(tmp_path: Path) -> None:
    artifact_root = tmp_path / "human-gate"
    step = HumanGateStep(
        name="approve",
        _artifact_stage="review",
        _choices=["continue", "stop"],
        _pipeline_name="demo",
        _prompt="review the output",
    )
    ctx = StepContext(artifact_root=str(artifact_root), state={})

    paused = step.run(ctx)
    checkpoint = artifact_root / "awaiting_user.json"
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["_resume_choice"] = "continue"
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")
    resumed = step.run(ctx)

    assert paused.next == "halt"
    assert resumed.next == "continue"

    events = _records(artifact_root, "arnold_pipeline", "human_gate_step")
    effect_names = [event["payload"]["name"] for event in events if event["event"] == "effect"]
    assert "checkpoint_written" in effect_names
    assert "resume_choice" in effect_names
    assert events[-1]["payload"]["status"] == "completed"


def test_reconcile_takeover_emits_native_wbc(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    decision = reconcile_worktree_for_takeover(repo)

    assert decision.state == "clean"

    events = _records(repo / ".git", "arnold_supervisor", "reconcile_takeover")
    assert [event["event"] for event in events] == ["started", "effect", "terminal"]
    assert events[-1]["payload"]["outcome"] == "clean"
